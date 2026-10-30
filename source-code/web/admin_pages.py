from datetime import date

import pandas as pd
import streamlit as st

import db
from data_loader import get_data
from ui import flash, fmt_int, page_header, show_flash, show_table

ROLE_NAMES = {"admin": "Quản trị viên", "editor": "Biên tập viên", "viewer": "Người xem"}
ROLES = ("admin", "editor", "viewer")


def _text(v):
    """Giá trị trống (NaN/None) -> chuỗi rỗng, để đưa vào ô nhập."""
    return "" if v is None or pd.isna(v) else str(v)


# =========================== CRUD DỮ LIỆU SẢN PHẨM ===========================
def _product_form(key, df, row=None):
    """Vẽ các ô nhập của một sản phẩm (dùng chung cho Thêm và Sửa). Trả về dict giá trị đang nhập."""
    r = row if row is not None else {}
    nguon_ds = sorted(df["source"].dropna().unique()) or ["hasaki", "cocolux"]
    nhom_ds = sorted(df["category_group"].dropna().unique()) or ["Khác"]

    def chon(ds, gia_tri):
        return ds.index(gia_tri) if gia_tri in ds else 0

    c1, c2 = st.columns(2)
    source = c1.selectbox("Nguồn", nguon_ds, index=chon(nguon_ds, r.get("source")), format_func=str.title, key=f"{key}_source", accept_new_options=True)
    nhom = c2.selectbox("Nhóm ngành hàng", nhom_ds, index=chon(nhom_ds, r.get("category_group")), key=f"{key}_group", accept_new_options=True)
    c3, c4 = st.columns(2)
    category = c3.text_input("Danh mục", value=_text(r.get("category")), key=f"{key}_cat")
    brand = c4.text_input("Thương hiệu", value=_text(r.get("brand")), key=f"{key}_brand")
    name = st.text_input("Tên sản phẩm", value=_text(r.get("name")), key=f"{key}_name")
    c5, c6 = st.columns(2)
    price = c5.number_input("Giá bán (đ)", min_value=0, value=int(r.get("price", 100000)), step=1000, key=f"{key}_price")
    original = c6.number_input("Giá niêm yết (đ)", min_value=0, value=int(r.get("price_original", 150000)), step=1000,
                               key=f"{key}_orig")
    c7, c8, c9 = st.columns(3)
    rating = c7.number_input("Đánh giá (0 = chưa có)", 0.0, 5.0, 0.0 if pd.isna(r.get("rating", float("nan"))) else float(r["rating"]),
                             step=0.1, key=f"{key}_rating")
    reviews = c8.number_input("Lượt đánh giá", min_value=0, value=int(r.get("review_count", 0)), step=1, key=f"{key}_reviews")
    in_stock = c9.checkbox("Còn hàng", value=bool(r.get("in_stock", 1)), key=f"{key}_stock")
    c10, c11, c12 = st.columns(3)
    volume = c10.text_input("Dung tích (vd 100ml)", value=_text(r.get("volume")), key=f"{key}_vol")
    origin = c11.text_input("Xuất xứ", value=_text(r.get("origin")), key=f"{key}_origin")
    code = c12.text_input("Mã sản phẩm", value=_text(r.get("product_code")), key=f"{key}_code")
    url = st.text_input("Link sản phẩm", value=_text(r.get("url")), key=f"{key}_url")
    st.caption("Phần trăm giảm giá được tự tính từ giá bán và giá niêm yết.")
    return {
        "source": source, "category_group": nhom, "category": category, "brand": brand, "name": name,
        "price": price, "price_original": original, "rating": rating, "review_count": reviews,
        "in_stock": in_stock, "volume": volume, "origin": origin, "product_code": code, "url": url,
    }


def _chon_san_pham(df, key):
    """Ô tìm kiếm + danh sách chọn (hiện tối đa 50 kết quả vì có hàng nghìn sản phẩm). Trả về hàng đã chọn."""
    tu_khoa = st.text_input("Tìm sản phẩm theo tên, thương hiệu hoặc ID", key=f"{key}_q")
    ds = df
    if tu_khoa.strip():
        t = tu_khoa.strip()
        ds = df[
            df["name"].str.contains(t, case=False, regex=False)
            | df["brand"].str.contains(t, case=False, regex=False)
            | (df["id"].astype(str) == t)
        ]
    if ds.empty:
        st.info("Không tìm thấy sản phẩm nào.")
        return None
    if len(ds) > 50:
        st.caption(f"Có {fmt_int(len(ds))} kết quả, đang hiện 50 kết quả đầu. Gõ thêm từ khóa để thu hẹp.")
        ds = ds.head(50)
    nhan = {i: f"#{i} · {n[:70]} ({b})" for i, n, b in zip(ds["id"], ds["name"], ds["brand"].fillna(""))}
    rid = st.selectbox("Chọn sản phẩm", list(nhan), format_func=nhan.get, key=f"{key}_sel")
    return df[df["id"] == rid].iloc[0]


def page_crud():
    db.require_role("admin", "editor")
    page_header("Quản lý dữ liệu")
    if st.button("Tải lại dữ liệu từ CSDL", key="crud_refresh"):
        db.bump()
        st.rerun()
    show_flash()
    from data_loader import enrich
    term = st.text_input("Tìm trong toàn bộ sản phẩm", key="catalog_search")
    requested_page = st.number_input("Trang", min_value=1, value=1, step=1, key="catalog_page")
    raw, total, current_page = db.product_page(term, int(requested_page))
    df = enrich(raw)
    st.caption(f"Trang {current_page}/{max(1, (total + 99) // 100)} · {fmt_int(total)} kết quả · tối đa 100 sản phẩm/trang")
    tab_list, tab_add, tab_edit, tab_del = st.tabs(["Danh sách", "Thêm", "Sửa", "Xóa"])

    # ---- Xem ----
    with tab_list:
        st.write(f"Đang hiển thị **{fmt_int(len(df))}** / **{fmt_int(total)}** sản phẩm")
        cot = ["id", "source", "category_group", "category", "name", "brand", "price", "price_original",
               "discount_pct", "rating", "review_count", "in_stock", "volume", "origin", "url"]
        hien = df[cot].copy()
        hien["in_stock"] = hien["in_stock"].astype(bool)
        show_table(hien, height=520)

    # ---- Thêm ----
    with tab_add:
        with st.form("form_add", clear_on_submit=False):
            data = _product_form("add", df)
            if st.form_submit_button("Thêm sản phẩm", type="primary"):
                ok, msg = db.add_product(data)
                if ok:
                    flash(msg)
                    st.rerun()
                else:
                    st.error(msg)

    # ---- Sửa ----
    with tab_edit:
        if df.empty:
            st.info("Chưa có sản phẩm để sửa.")
        else:
            row = _chon_san_pham(df, "edit")
            if row is not None:
                rid = int(row["id"])
                with st.form(f"form_edit_{rid}"):
                    data = _product_form(f"edit{rid}", df, row)
                    if st.form_submit_button("Lưu thay đổi", type="primary"):
                        ok, msg = db.update_product(rid, data)
                        if ok:
                            flash(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    # ---- Xóa ----
    with tab_del:
        if df.empty:
            st.info("Chưa có sản phẩm để xóa.")
        else:
            row = _chon_san_pham(df, "del")
            if row is not None:
                rid = int(row["id"])
                show_table(df[df["id"] == rid][["id", "source", "name", "brand", "price", "price_original", "url"]])
                sure = st.checkbox("Tôi chắc chắn muốn xóa sản phẩm này", key=f"del_sure_{rid}")
                if st.button("Xóa sản phẩm", type="primary", disabled=not sure):
                    ok, msg = db.delete_product(rid)
                    if ok:
                        flash(msg)
                        st.rerun()
                    else:
                        st.error(msg)


# =========================== QUẢN TRỊ NGƯỜI DÙNG ===========================
def page_users():
    db.require_role("admin")
    page_header("Quản trị người dùng", "Tạo tài khoản, phân quyền, đặt lại mật khẩu, xóa tài khoản")
    show_flash()
    me = st.session_state.user
    users = db.list_users()
    names = dict(zip(users["id"], users["username"]))  # {id: tên đăng nhập}
    tab_list, tab_add, tab_edit, tab_del = st.tabs(["Danh sách", "Tạo tài khoản", "Sửa / Phân quyền", "Xóa"])

    # ---- Danh sách ----
    with tab_list:
        shown = users.copy()
        shown["role"] = shown["role"].map(ROLE_NAMES)
        shown.columns = ["ID", "Tên đăng nhập", "Họ tên", "Vai trò"]
        st.dataframe(shown, width="stretch", hide_index=True)
        st.markdown(
            "**Phân quyền:**\n"
            "- **Quản trị viên**: toàn quyền, gồm quản lý người dùng và sao lưu\n"
            "- **Biên tập viên**: xem tất cả và thêm/sửa/xóa dữ liệu\n"
            "- **Người xem**: chỉ xem phân tích, mô hình và báo cáo"
        )

    # ---- Tạo ----
    with tab_add:
        with st.form("form_user_add", clear_on_submit=False):
            c1, c2 = st.columns(2)
            username = c1.text_input("Tên đăng nhập")
            full_name = c2.text_input("Họ tên")
            c3, c4 = st.columns(2)
            password = c3.text_input("Mật khẩu (tối thiểu 10 ký tự)", type="password")
            role = c4.selectbox("Vai trò", ROLES, index=2, format_func=ROLE_NAMES.get)
            if st.form_submit_button("Tạo tài khoản", type="primary"):
                ok, msg = db.add_user(username, password, full_name, role)
                if ok:
                    flash(msg)
                    st.rerun()
                else:
                    st.error(msg)

    # ---- Sửa / phân quyền ----
    with tab_edit:
        uid = st.selectbox("Chọn tài khoản", users["id"], format_func=names.get, key="user_edit_id")
        row = users[users["id"] == uid].iloc[0]
        with st.form(f"form_user_edit_{uid}"):
            full_name = st.text_input("Họ tên", value=row["full_name"])
            role = st.selectbox("Vai trò", ROLES, index=ROLES.index(row["role"]), format_func=ROLE_NAMES.get)
            new_pw = st.text_input("Mật khẩu mới (bỏ trống nếu không đổi)", type="password")
            if st.form_submit_button("Lưu thay đổi", type="primary"):
                ok, msg = db.update_user(int(uid), full_name, role, new_pw)
                if ok:
                    if int(uid) == me["id"]:  # tự sửa chính mình thì cập nhật luôn phiên đăng nhập
                        st.session_state.user["role"] = role
                        st.session_state.user["full_name"] = full_name
                    flash(msg)
                    st.rerun()
                else:
                    st.error(msg)

    # ---- Xóa ----
    with tab_del:
        uid = st.selectbox("Chọn tài khoản cần xóa", users["id"], format_func=names.get, key="user_del_id")
        sure = st.checkbox("Tôi chắc chắn muốn xóa tài khoản này")
        if st.button("Xóa tài khoản", type="primary", disabled=not sure):
            if int(uid) == me["id"]:
                st.error("Không thể tự xóa tài khoản đang đăng nhập")
            else:
                ok, msg = db.delete_user(int(uid))
                if ok:
                    flash(msg)
                    st.rerun()
                else:
                    st.error(msg)


# =========================== SAO LƯU & PHỤC HỒI ===========================
def page_backup():
    db.require_role("admin")
    ext = db.backup_ext()
    page_header("Sao lưu & phục hồi")
    show_flash()

    if isinstance(db.get_store(), db.MongoStore):
        with st.expander("Nhật ký thay đổi gần đây"):
            if st.button("Tải nhật ký"):
                entries = list(db.get_store().db.audit_log.find({}, {"_id": 0}).sort("at", -1).limit(100))
                st.dataframe(pd.DataFrame(entries), width="stretch", hide_index=True)

    st.subheader("Sao lưu")
    if st.button("Chuẩn bị bản sao lưu"):
        st.session_state["backup_download"] = db.backup_bytes()
    st.download_button(
        f"Tải bản sao lưu (.{ext})",
        st.session_state.get("backup_download", b""),
        disabled="backup_download" not in st.session_state,
        file_name=f"backup_{date.today():%Y%m%d}.{ext}",
        mime="application/octet-stream",
    )

    st.divider()
    st.subheader("Phục hồi")
    st.warning("Phục hồi sẽ ghi đè toàn bộ dữ liệu và tài khoản hiện tại, sau đó phải đăng nhập lại.")
    uploaded = st.file_uploader(f"Chọn file sao lưu (.{ext})", type=["db"] if ext == "db" else ["gz"])
    if uploaded is not None:
        sure = st.checkbox("Tôi hiểu và muốn phục hồi")
        if st.button("Phục hồi dữ liệu", type="primary", disabled=not sure):
            ok, msg = db.restore_from_bytes(uploaded.getvalue())
            if ok:
                st.session_state.clear()
                flash(msg + ". Vui lòng đăng nhập lại.")
                st.rerun()
            else:
                st.error(msg)
