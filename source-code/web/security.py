"""Session revalidation and private bootstrap credentials."""
import hashlib
import json
import secrets


def current_user():
    import db
    import streamlit as st
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx(suppress_warning=True) is None:
        return None
    user = st.session_state.get("user")
    if not user:
        return None
    rows = db.get_store().fetch("users", id=int(user["id"]))
    if not rows:
        return None
    row = rows[0]
    token = hashlib.sha256(row["password_hash"].encode()).hexdigest()
    if not secrets.compare_digest(user.get("auth_token", ""), token):
        return None
    return {k: row[k] for k in ("id", "username", "full_name", "role")} | {"auth_token": token}


def initialize_accounts(store):
    import db
    path = db.BASE_DIR / ".streamlit" / "initial_accounts.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    defaults = {"admin": "admin123", "editor": "editor123", "viewer": "viewer123"}
    rows = store.fetch("users")
    pending = [r for r in rows if r["username"] in defaults and db.check_password(defaults[r["username"]], r["password_hash"])]
    if not rows:
        pending = [{"username": "admin", "full_name": "Quản trị viên", "role": "admin"}]
    if not pending:
        return
    for row in pending:
        saved.setdefault(row["username"], secrets.token_urlsafe(18))
    path.parent.mkdir(exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    for row in pending:
        password_hash = db.hash_password(saved[row["username"]])
        if "id" in row:
            store.update("users", row["id"], {"password_hash": password_hash})
        else:
            store.insert("users", {**row, "password_hash": password_hash})
