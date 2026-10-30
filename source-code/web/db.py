import gzip
import hashlib
import hmac
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "app.db"
DATASET_PATHS = [BASE_DIR / "dataset" / "products_final_2.xlsx", BASE_DIR / "products_final_2.xlsx"]
ROLES = ("admin", "editor", "viewer")

USER_COLS = ["id", "username", "password_hash", "full_name", "role"]
PRODUCT_COLS = [
    "id", "source", "category_group", "category", "name", "brand", "product_code",
    "price", "price_original", "discount_pct", "rating", "review_count", "in_stock",
    "volume", "origin", "url", "scraped_at",
]
COLUMNS = {"users": USER_COLS, "products": PRODUCT_COLS}
INT_COLS = ["price", "price_original", "discount_pct", "review_count", "in_stock"]


class DuplicateError(Exception):
    """Trùng khóa duy nhất (ví dụ tên đăng nhập đã tồn tại)."""


def _check(table, keys):
    if table not in COLUMNS:
        raise ValueError("Bảng không hợp lệ")
    bad = [k for k in keys if k not in COLUMNS[table]]
    if table not in COLUMNS or bad:
        raise ValueError(f"Cột không hợp lệ: {bad}")


# =====================================================================
# KHO LƯU TRỮ 1: SQLITE
# =====================================================================
class SQLiteStore:
    name = "SQLite"

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self):
        with self._conn() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL DEFAULT 'viewer'
                )"""
            )
            c.execute(
                """CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    category_group TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL,
                    brand TEXT NOT NULL DEFAULT '',
                    product_code TEXT,
                    price INTEGER NOT NULL,
                    price_original INTEGER NOT NULL,
                    discount_pct INTEGER NOT NULL DEFAULT 0,
                    rating REAL,
                    review_count INTEGER NOT NULL DEFAULT 0,
                    in_stock INTEGER NOT NULL DEFAULT 1,
                    volume TEXT,
                    origin TEXT,
                    url TEXT,
                    scraped_at TEXT
                )"""
            )

    def _where(self, table, where):
        _check(table, where)
        if not where:
            return "", []
        return " WHERE " + " AND ".join(f"{k}=?" for k in where), list(where.values())

    def fetch(self, table, **where):
        sql_where, args = self._where(table, where)
        sql = f"SELECT {', '.join(COLUMNS[table])} FROM {table}{sql_where} ORDER BY id"
        with self._conn() as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]

    def frame(self, table):
        sql = f"SELECT {', '.join(COLUMNS[table])} FROM {table} ORDER BY id"
        with self._conn() as c:
            return pd.read_sql_query(sql, c)

    def insert(self, table, doc):
        doc = {k: v for k, v in doc.items() if k != "id"}
        _check(table, doc)
        sql = f"INSERT INTO {table} ({', '.join(doc)}) VALUES ({', '.join('?' * len(doc))})"
        try:
            with self._conn() as c:
                return c.execute(sql, list(doc.values())).lastrowid
        except sqlite3.IntegrityError as e:
            raise DuplicateError(str(e)) from e

    def insert_many(self, table, docs, keep_ids=False):
        cols = COLUMNS[table] if keep_ids else COLUMNS[table][1:]
        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
        with self._conn() as c:
            c.executemany(sql, [tuple(d.get(k) for k in cols) for d in docs])

    def update(self, table, item_id, fields):
        _check(table, fields)
        sets = ", ".join(f"{k}=?" for k in fields)
        with self._conn() as c:
            return c.execute(f"UPDATE {table} SET {sets} WHERE id=?", [*fields.values(), int(item_id)]).rowcount > 0

    def delete(self, table, item_id):
        _check(table, {})
        with self._conn() as c:
            return c.execute(f"DELETE FROM {table} WHERE id=?", (int(item_id),)).rowcount > 0

    def count(self, table, **where):
        sql_where, args = self._where(table, where)
        with self._conn() as c:
            return c.execute(f"SELECT COUNT(*) FROM {table}{sql_where}", args).fetchone()[0]

    def clear(self, table):
        _check(table, {})
        with self._conn() as c:
            c.execute(f"DELETE FROM {table}")


# =====================================================================
# KHO LƯU TRỮ 2: MONGODB  (mỗi bản ghi có thêm trường số nguyên "id" để giao diện dùng chung)
# =====================================================================
from mongo_store import MongoStore


# =====================================================================
# CHỌN KHO LƯU TRỮ
# =====================================================================
_store = None
_info = {"backend": "SQLite", "note": ""}
_lock = threading.Lock()
_init_lock = threading.Lock()
_inited = False
_version = 0  # tăng lên mỗi khi dữ liệu đổi, để bộ nhớ đệm biết mà tải lại


def _mongo_option(key):
    value = os.environ.get(key, "").strip()
    if not value:
        try:
            import streamlit as st

            value = str(st.secrets.get(key, "")).strip()
        except Exception:
            pass
    return value


def _mongo_settings():
    return _mongo_option("MONGO_URI"), (_mongo_option("MONGO_DB") or "phan_tich_my_pham")


def get_store():
    global _store
    if _store is None:
        with _lock:
            if _store is None:
                uri, db_name = _mongo_settings()
                if uri:
                    try:
                        _store = MongoStore(uri, db_name)
                        _info.update(backend="MongoDB", note=f"Database: {db_name} · Collection: {_store.products_collection}")
                    except Exception as e:
                        raise ConnectionError(
                            "Không kết nối được MongoDB. Hãy kiểm tra mạng và cấu hình Atlas rồi tải lại trang. "
                            "Thao tác chưa được lưu; ứng dụng không chuyển sang SQLite."
                        ) from e
                if _store is None:
                    _store = SQLiteStore()
    return _store


def backend_info():
    get_store()
    return dict(_info)


def data_version():
    return _version


def bump():
    global _version
    _version += 1


def change_password(old_password, new_password):
    from security import current_user
    user = current_user()
    if not user or not verify_user(user["username"], old_password):
        return False, "Mật khẩu hiện tại không đúng hoặc phiên đăng nhập đã hết hạn"
    if len(new_password) < 10 or new_password == old_password:
        return False, "Mật khẩu mới cần ít nhất 10 ký tự và khác mật khẩu hiện tại"
    if not get_store().update("users", user["id"], {"password_hash": hash_password(new_password)}):
        return False, "Tài khoản không còn tồn tại"
    return True, "Đã đổi mật khẩu"


# ----------------------------- MẬT KHẨU -----------------------------
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + "$" + digest.hex()


def check_password(password: str, stored: str) -> bool:
    if not isinstance(stored, str) or "$" not in stored:
        return False
    try:
        salt_hex, digest_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
        if len(salt) != 16 or len(bytes.fromhex(digest_hex)) != 32:
            return False
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return hmac.compare_digest(digest.hex(), digest_hex)


# ----------------------------- KHỞI TẠO + NẠP DỮ LIỆU MẪU -----------------------------
def _native(v):
    """Đổi giá trị numpy/pandas sang kiểu Python thường (SQLite và MongoDB không nhận kiểu numpy)."""
    if v is None or (not isinstance(v, (str, bytes)) and pd.isna(v)):
        return None
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    return v


def load_seed_records():
    """Đọc file Excel dữ liệu thật thành danh sách dict (chưa có cột id)."""
    for path in DATASET_PATHS:
        if path.exists():
            df = pd.read_excel(path)
            break
    else:
        return []
    for c in PRODUCT_COLS[1:]:
        if c not in df.columns:
            df[c] = None
    df = df[PRODUCT_COLS[1:]].drop_duplicates(subset="url")
    df["product_code"] = df["product_code"].astype("string")
    records = [{k: _native(v) for k, v in row.items()} for row in df.to_dict("records")]
    for r in records:
        r["in_stock"] = int(r["in_stock"] or 0)
        for k in ("price", "price_original", "discount_pct", "review_count"):
            r[k] = int(r[k] or 0)
    return records


def dataset_path():
    """File Excel dữ liệu đang được dùng (None nếu không tìm thấy). Thư mục dataset/ được ưu tiên trước."""
    for path in DATASET_PATHS:
        if path.exists():
            return path
    return None


def reload_products():
    """Xóa toàn bộ sản phẩm rồi nạp lại từ file Excel. Tài khoản người dùng được giữ nguyên."""
    records = load_seed_records()  # đọc file trước: nếu file lỗi thì chưa xóa gì cả
    if not records:
        return False, "Không tìm thấy file products_final_2.xlsx hoặc file không có dữ liệu"
    store = get_store()
    require_role("admin")
    save_safety_backup()
    for i, row in enumerate(records, 1):
        row["id"] = i
    replace_tables({"products": records})
    bump()  # báo cho bộ nhớ đệm biết dữ liệu đã đổi để tải lại
    return True, f"Đã nạp lại {fmt_so(len(records))} sản phẩm từ file {dataset_path().name}"


def fmt_so(n):
    return f"{n:,}".replace(",", ".")


def init_db():
    with _init_lock:
        _initialize_db()


def _initialize_db():
    global _inited
    if _inited:
        return
    store = get_store()
    store.init()
    from security import initialize_accounts
    initialize_accounts(store)
    # Atlas is authoritative: an empty collection must stay empty after deletion.
    # Excel is imported automatically only for the standalone SQLite demo.
    if isinstance(store, SQLiteStore) and store.count("products") == 0:
        records = load_seed_records()
        if records:
            store.insert_many("products", records)
    _inited = True


# ----------------------------- NGƯỜI DÙNG -----------------------------
def verify_user(username: str, password: str):
    rows = get_store().fetch("users", username=username)
    if rows and check_password(password, rows[0]["password_hash"]):
        r = rows[0]
        return {"id": r["id"], "username": r["username"], "full_name": r["full_name"], "role": r["role"], "auth_token": hashlib.sha256(r["password_hash"].encode()).hexdigest()}
    return None


def list_users() -> pd.DataFrame:
    return get_store().frame("users")[["id", "username", "full_name", "role"]]


def _admin_count() -> int:
    return get_store().count("users", role="admin")


def add_user(username, password, full_name, role):
    username = username.strip()
    if not username:
        return False, "Tên đăng nhập không được để trống"
    if role != "viewer":
        require_role("admin")
    if len(password) < 10:
        return False, "Mật khẩu phải có ít nhất 10 ký tự"
    if role not in ROLES:
        return False, "Vai trò không hợp lệ"
    try:
        get_store().insert(
            "users",
            {"username": username, "password_hash": hash_password(password), "full_name": full_name.strip(), "role": role},
        )
    except DuplicateError:
        return False, "Tên đăng nhập đã tồn tại"
    return True, f"Đã tạo tài khoản '{username}'"


def update_user(user_id, full_name, role, new_password=""):
    require_role("admin")
    if role not in ROLES:
        return False, "Vai trò không hợp lệ"
    store = get_store()
    rows = store.fetch("users", id=int(user_id))
    if not rows:
        return False, "Không tìm thấy người dùng"
    if rows[0]["role"] == "admin" and role != "admin" and _admin_count() <= 1:
        return False, "Hệ thống phải còn ít nhất một quản trị viên"
    fields = {"full_name": full_name.strip(), "role": role}
    if new_password:
        if len(new_password) < 10:
            return False, "Mật khẩu mới phải có ít nhất 10 ký tự"
        fields["password_hash"] = hash_password(new_password)
    store.update("users", user_id, fields)
    return True, "Đã cập nhật tài khoản"


def delete_user(user_id):
    require_role("admin")
    store = get_store()
    rows = store.fetch("users", id=int(user_id))
    if not rows:
        return False, "Không tìm thấy người dùng"
    if rows[0]["role"] == "admin" and _admin_count() <= 1:
        return False, "Không thể xóa quản trị viên cuối cùng"
    store.delete("users", user_id)
    return True, "Đã xóa tài khoản"


# ----------------------------- SẢN PHẨM (CRUD) -----------------------------
def get_products() -> pd.DataFrame:
    df = get_store().frame("products")
    return normalize_products(df)


def normalize_products(df):
    for c in INT_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    for c in ("source", "name", "brand", "category_group", "category"):
        df[c] = df[c].fillna("").astype(str)
    return df


def product_page(term="", page=1, size=100):
    """Search and paginate in MongoDB instead of transferring the entire catalog."""
    import re
    store = get_store()
    if isinstance(store, MongoStore):
        store.ensure_ids("products")
        query = {}
        if term.strip():
            regex = {"$regex": re.escape(term.strip()), "$options": "i"}
            choices = [{"name": regex}, {"brand": regex}]
            if term.strip().isdigit():
                choices.append({"id": int(term.strip())})
            query = {"$or": choices}
        coll = store.collection("products")
        total = coll.count_documents(query)
        page = max(1, min(page, max(1, (total + size - 1) // size)))
        rows = list(coll.find(query, {"_id": 0}).sort("id", 1).skip((page-1)*size).limit(size))
        return normalize_products(pd.DataFrame(rows, columns=PRODUCT_COLS)), total, page
    df = get_products()
    if term.strip():
        mask = df["name"].str.contains(term, case=False, regex=False) | df["brand"].str.contains(term, case=False, regex=False) | df["id"].astype(str).eq(term)
        df = df[mask]
    total = len(df)
    page = max(1, min(page, max(1, (total + size - 1) // size)))
    return df.iloc[(page-1)*size:page*size].copy(), total, page


def _clean_product(data: dict):
    """Kiểm tra dữ liệu nhập tay. Trả về (dict sạch, thông báo lỗi)."""
    text = lambda k: (str(data.get(k) or "")).strip()  # noqa: E731
    if not text("name"):
        return None, "Tên sản phẩm không được để trống"
    if not text("source"):
        return None, "Nguồn không được để trống"
    try:
        price, original = int(data.get("price") or 0), int(data.get("price_original") or 0)
        reviews = int(data.get("review_count") or 0)
        rating = float(data.get("rating") or 0)
        if not np.isfinite(rating) or not 0 <= rating <= 5 or reviews < 0:
            return None, "Đánh giá phải từ 0 đến 5, lượt đánh giá không được âm"
    except (ValueError, TypeError, OverflowError):
        return None, "Giá và lượt đánh giá phải là số hợp lệ"
    if price < 0 or original <= 0:
        return None, "Giá bán phải ≥ 0 và giá niêm yết phải > 0"
    if price > original:
        return None, "Giá bán không được lớn hơn giá niêm yết"
    rating = rating if rating > 0 else None
    doc = {
        "source": text("source").lower(),
        "category_group": text("category_group"),
        "category": text("category"),
        "name": text("name"),
        "brand": text("brand"),
        "product_code": text("product_code") or None,
        "price": price,
        "price_original": original,
        "discount_pct": round((1 - price / original) * 100),  # tự tính, không cho nhập tay để khỏi lệch
        "rating": rating,
        "review_count": reviews,
        "in_stock": int(bool(data.get("in_stock"))),
        "volume": text("volume") or None,
        "origin": text("origin") or None,
        "url": text("url") or None,
    }
    return doc, ""


def add_product(data: dict):
    doc, err = _clean_product(data)
    if err:
        return False, err
    doc["scraped_at"] = datetime.now().isoformat(timespec="seconds")
    require_role("admin", "editor")
    try:
        new_id = get_store().insert("products", doc)
    except DuplicateError as exc:
        return False, str(exc)
    bump()
    return True, f"Đã thêm sản phẩm #{new_id}"


def update_product(product_id, data: dict):
    doc, err = _clean_product(data)
    if err:
        return False, err
    require_role("admin", "editor")
    try:
        if not get_store().update("products", product_id, doc):
            return False, "Sản phẩm không còn tồn tại. Hãy tải lại dữ liệu."
    except DuplicateError as exc:
        return False, str(exc)
    bump()
    return True, f"Đã cập nhật sản phẩm #{product_id}"


def delete_product(product_id):
    require_role("admin", "editor")
    if not get_store().delete("products", product_id):
        return False, "Sản phẩm không còn tồn tại. Hãy tải lại dữ liệu."
    bump()
    return True, f"Đã xóa sản phẩm #{product_id}"


# ----------------------------- SAO LƯU / PHỤC HỒI -----------------------------
def backup_ext() -> str:
    return "db" if isinstance(get_store(), SQLiteStore) else "json.gz"


def backup_bytes() -> bytes:
    store = get_store()
    if isinstance(store, SQLiteStore):
        return DB_PATH.read_bytes()
    payload = {t: store.fetch(t) for t in COLUMNS}  # MongoDB: xuất JSON nén
    from bson import json_util
    return gzip.compress(json_util.dumps(payload, ensure_ascii=False).encode("utf-8"))


def restore_from_bytes(data: bytes):
    require_role("admin")
    store = get_store()
    if isinstance(store, SQLiteStore):
        import tempfile
        if not data.startswith(b"SQLite format 3\x00"):
            return False, "File không phải cơ sở dữ liệu SQLite hợp lệ"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=BASE_DIR, suffix=".restore", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(data)
            with sqlite3.connect(temporary) as conn:
                conn.row_factory = sqlite3.Row
                if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ValueError("File bị hỏng")
                payload = {t: [dict(r) for r in conn.execute(f"SELECT {', '.join(cols)} FROM {t}")] for t, cols in COLUMNS.items()}
                validate_backup(payload)
            save_safety_backup()
            os.replace(temporary, DB_PATH)
            bump()
            return True, "Đã phục hồi dữ liệu; bản trước phục hồi được lưu trong backups/"
        except (sqlite3.Error, ValueError, KeyError, TypeError):
            return False, "Bản sao lưu SQLite không hợp lệ hoặc thiếu quản trị viên"
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    try:
        from bson import json_util
        payload = json_util.loads(gzip.decompress(data).decode("utf-8"))
        validate_backup(payload)
    except Exception:
        return False, "Bản sao lưu không hợp lệ: cần tài khoản quản trị, ID duy nhất và các trường dữ liệu đúng kiểu."
    save_safety_backup()
    store.replace_tables(payload)
    bump()
    return True, "Đã phục hồi dữ liệu; bản trước phục hồi được lưu trong backups/"


def validate_backup(payload):
    if not isinstance(payload, dict) or set(payload) != set(COLUMNS):
        raise ValueError("Sai cấu trúc")
    for table, rows in payload.items():
        if not isinstance(rows, list):
            raise ValueError("Sai kiểu danh sách")
        ids = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("id"), int) or row["id"] <= 0 or row["id"] in ids:
                raise ValueError("ID không hợp lệ")
            ids.add(row["id"])
            if table == "users":
                if not row.get("username") or row.get("role") not in ROLES:
                    raise ValueError("Tài khoản không hợp lệ")
                salt, digest = row["password_hash"].split("$")
                if len(bytes.fromhex(salt)) != 16 or len(bytes.fromhex(digest)) != 32:
                    raise ValueError("Mật khẩu không hợp lệ")
            else:
                if not row.get("name") or not row.get("source"):
                    raise ValueError("Thiếu thông tin sản phẩm")
                for key in INT_COLS:
                    if not isinstance(row.get(key), (int, float)) or not np.isfinite(row[key]):
                        raise ValueError("Sai kiểu số")
    users = payload["users"]
    if not any(row["role"] == "admin" for row in users) or len({r["username"] for r in users}) != len(users):
        raise ValueError("Cần quản trị viên và tên đăng nhập duy nhất")


def save_safety_backup():
    import uuid
    folder = BASE_DIR / "backups"
    folder.mkdir(exist_ok=True)
    target = folder / f"before_change_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.{backup_ext()}"
    target.write_bytes(backup_bytes())
    return target


def replace_tables(payload):
    store = get_store()
    if isinstance(store, MongoStore):
        store.replace_tables(payload)
    else:
        with store._conn() as conn:
            for table, rows in payload.items():
                cols = COLUMNS[table]
                conn.execute(f"DELETE FROM {table}")
                conn.executemany(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                    [tuple(r.get(k) for k in cols) for r in rows])


def actor_name():
    from security import current_user
    user = current_user()
    return user["username"] if user else "maintenance"


def require_role(*roles):
    from security import current_user
    user = current_user()
    if not user or user["role"] not in roles:
        raise PermissionError("Phiên đăng nhập hoặc quyền truy cập đã thay đổi. Vui lòng đăng nhập lại.")
