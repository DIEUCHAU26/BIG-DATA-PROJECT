import base64
import io
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from pymongo.errors import ConfigurationError, InvalidURI, OperationFailure, PyMongoError, ServerSelectionTimeoutError

import db
from admin_pages import ROLE_NAMES, page_backup, page_crud, page_users
from data_loader import LABELS, get_data
import ml_pages
from dashboards import (page_danh_gia_ton_kho, page_gia_khuyen_mai, page_so_sanh, page_thong_ke,
                        page_thuong_hieu, page_tong_quan)
from ui import (CHART_COLORS, apply_style, bar, cards, flash, fmt_int, fmt_vnd, page_header,
                show_flash, show_table)

st.set_page_config(page_title="Hệ thống phân tích dữ liệu", layout="wide")


def ranked(series):
    """Đánh số thứ hạng vào nhãn ('01. Cocoon') để biểu đồ giữ đúng thứ tự xếp hạng."""
    series = series.copy()
    series.index = [f"{i + 1:02d}. {k}" for i, k in enumerate(series.index)]
    return series


def pick_sources(df, key):
    """Ô chọn nguồn (Hasaki / Cocolux). Không chọn gì = lấy tất cả."""
    chon = st.multiselect("Nguồn dữ liệu", sorted(df["nguon"].unique()), key=key, placeholder="Tất cả nguồn")
    return df[df["nguon"].isin(chon)] if chon else df


# =====================================================================
# 1. ĐĂNG NHẬP / ĐĂNG KÝ
# =====================================================================
def logo_html(ten_file="logo.png", rong=96, canh_giua=True):
    """Đọc ảnh logo và nhúng thẳng vào HTML (không có ảnh thì dùng emoji)."""
    duong_dan = Path(__file__).parent / ten_file
    if not duong_dan.exists():
        return '<div class="logo">💄</div>' if canh_giua else '<span style="font-size:2rem">💄</span>'
    loai = "jpeg" if duong_dan.suffix.lower() in (".jpg", ".jpeg") else "png"
    du_lieu = base64.b64encode(duong_dan.read_bytes()).decode()
    kieu = "display:block;margin:0 auto 10px auto;" if canh_giua else ""
    return f'<img src="data:image/{loai};base64,{du_lieu}" width="{rong}" style="{kieu}">'


def login_page():
    st.markdown("<style>.block-container{max-width:460px;}</style>", unsafe_allow_html=True)
    info = db.backend_info()
    st.markdown(
        '<div class="login-title">' + logo_html() + "<h2>Hệ thống phân tích dữ liệu</h2></div>",
        unsafe_allow_html=True,
    )
    if info["note"] and info["backend"] == "SQLite":
        st.warning(info["note"])
    show_flash()
    tab_dang_nhap, tab_dang_ky = st.tabs(["Đăng nhập", "Đăng ký"])

    # ---------- Tab ĐĂNG NHẬP ----------
    with tab_dang_nhap:
        with st.form("login"):
            username = st.text_input("Tên đăng nhập")
            password = st.text_input("Mật khẩu", type="password")
            bam_nut = st.form_submit_button("Đăng nhập", type="primary", width="stretch")
        if bam_nut:
            user = db.verify_user(username.strip(), password)
            if user:
                st.session_state.user = user  # nhớ người đang đăng nhập
                st.rerun()
            else:
                st.error("Sai tên đăng nhập hoặc mật khẩu")
        st.caption("Đăng nhập bằng tài khoản được quản trị viên cấp.")

    # ---------- Tab ĐĂNG KÝ ----------
    with tab_dang_ky:
        with st.form("register", clear_on_submit=True):
            ho_ten = st.text_input("Họ tên")
            ten_moi = st.text_input("Tên đăng nhập mới")
            mk_moi = st.text_input("Mật khẩu (tối thiểu 10 ký tự)", type="password")
            mk_lai = st.text_input("Nhập lại mật khẩu", type="password")
            bam_dang_ky = st.form_submit_button("Đăng ký", type="primary", width="stretch")
        if bam_dang_ky:
            if mk_moi != mk_lai:
                st.error("Hai mật khẩu không giống nhau")
            else:
                
                ok, thong_bao = db.add_user(ten_moi, mk_moi, ho_ten, "viewer")
                if ok:
                    flash("Đăng ký thành công! Hãy đăng nhập bằng tài khoản vừa tạo.")
                    st.rerun()
                else:
                    st.error(thong_bao)


# =====================================================================
# 2. CÁC TRANG PHÂN TÍCH
# =====================================================================
def page_explore():
    page_header("Khám phá & Lọc dữ liệu")
    df = get_data()
    if df.empty:
        st.info("Chưa có dữ liệu.")
        return

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        nguon = c1.multiselect("Nguồn", sorted(df["nguon"].unique()), placeholder="Tất cả")
        nhom = c2.multiselect("Nhóm ngành hàng", sorted(df["category_group"].dropna().unique()), placeholder="Tất cả")
        goc = df[df["category_group"].isin(nhom)] if nhom else df
        danh_muc = c3.multiselect("Danh mục", sorted(goc["category"].dropna().unique()), placeholder="Tất cả")
        c4, c5 = st.columns(2)
        thuong_hieu = c4.multiselect("Thương hiệu", sorted(df["brand"].dropna().unique()), placeholder="Tất cả")
        xuat_xu = c5.multiselect("Xuất xứ", sorted(df["xuat_xu"].unique()), placeholder="Tất cả")
        tu_khoa = st.text_input("Tìm theo tên sản phẩm hoặc thương hiệu", placeholder="Ví dụ: kem chống nắng, Cocoon...")
        s1, s2 = st.columns(2)
        cao = int(df["price"].max())
        khoang_gia = s1.slider("Khoảng giá bán (đ)", 0, max(cao, 1000), (0, max(cao, 1000)), step=1000)
        khoang_giam = s2.slider("Khoảng giảm giá (%)", 0, 100, (0, 100))
        o1, o2, o3 = st.columns(3)
        con_hang = o1.checkbox("Chỉ sản phẩm còn hàng")
        co_dg = o2.checkbox("Chỉ sản phẩm có đánh giá")
        sap_xep = o3.selectbox(
            "Sắp xếp theo",
            ["Mặc định", "Giá bán tăng dần", "Giá bán giảm dần", "Giảm giá nhiều nhất", "Nhiều lượt đánh giá nhất"],
        )

    kq = df[df["price"].between(*khoang_gia) & df["discount_pct"].between(*khoang_giam)]
    if nguon:
        kq = kq[kq["nguon"].isin(nguon)]
    if nhom:
        kq = kq[kq["category_group"].isin(nhom)]
    if danh_muc:
        kq = kq[kq["category"].isin(danh_muc)]
    if thuong_hieu:
        kq = kq[kq["brand"].isin(thuong_hieu)]
    if xuat_xu:
        kq = kq[kq["xuat_xu"].isin(xuat_xu)]
    if con_hang:
        kq = kq[kq["in_stock"] == 1]
    if co_dg:
        kq = kq[kq["co_danh_gia"]]
    if tu_khoa.strip():
        t = tu_khoa.strip()
        kq = kq[kq["name"].str.contains(t, case=False, regex=False) | kq["brand"].str.contains(t, case=False, regex=False)]

    kieu = {
        "Giá bán tăng dần": ("price", True),
        "Giá bán giảm dần": ("price", False),
        "Giảm giá nhiều nhất": ("discount_pct", False),
        "Nhiều lượt đánh giá nhất": ("review_count", False),
    }
    if sap_xep in kieu:
        kq = kq.sort_values(kieu[sap_xep][0], ascending=kieu[sap_xep][1])

    cards([
        ("Tìm thấy", fmt_int(len(kq)), "rose", f"trên tổng {fmt_int(len(df))} sản phẩm"),
        ("Giá bán trung bình", fmt_vnd(kq["price"].mean()) if len(kq) else "—", "plum"),
        ("Giảm giá trung bình", f"{kq['discount_pct'].mean():.1f}%" if len(kq) else "—", "coral"),
    ])
    cot = ["id", "nguon", "category_group", "category", "name", "brand", "price", "price_original", "discount_pct",
           "rating", "review_count", "in_stock", "xuat_xu", "volume", "url"]
    hien = kq[cot].copy()
    hien["in_stock"] = hien["in_stock"].astype(bool)
    show_table(hien, height=520)
    st.download_button("Tải kết quả lọc (CSV)", kq[cot].rename(columns=LABELS).to_csv(index=False).encode("utf-8-sig"),
                       file_name="ket_qua_loc.csv", mime="text/csv")


def page_quality():
    page_header("Chất lượng dữ liệu")
    df = get_data()
    if df.empty:
        st.info("Chưa có dữ liệu.")
        return
    goc = ["source", "category_group", "category", "name", "brand", "product_code", "price", "price_original",
           "discount_pct", "rating", "review_count", "in_stock", "volume", "origin", "url"]
    thieu = df[goc].isna().sum()
    cards([
        ("Số dòng", fmt_int(len(df)), "rose", f"{len(goc)} cột dữ liệu gốc"),
        ("Dòng trùng link", fmt_int(int(df.duplicated('url').sum())), "plum"),
        ("Giá nghi ngờ nhập sai (< 1.000 đ)", fmt_int(int((df['price'] < 1000).sum())), "coral"),
    ])

    trai, phai = st.columns(2)
    with trai:
        st.subheader("Tỷ lệ thiếu theo từng cột (%)")
        ty_le = (thieu / len(df) * 100).round(1)
        ty_le = ty_le[ty_le > 0].sort_values(ascending=False)
        bar(ranked(ty_le.rename(index=LABELS)).rename("Tỷ lệ thiếu %"), horizontal=True, color=CHART_COLORS[3])
    with phai:
        st.subheader("Tỷ lệ thiếu theo nguồn (%)")
        theo_nguon = (df[["rating", "volume", "origin"]].isna().groupby(df["nguon"]).mean() * 100).round(1)
        theo_nguon.columns = [LABELS[c] for c in theo_nguon.columns]
        theo_nguon.index.name = "Nguồn"
        st.dataframe(theo_nguon, width="stretch")

    st.subheader("Các vấn đề phát hiện và cách xử lý đề xuất")
    van_de = [
        ("Giá bán < 1.000 đ (nghi nhập sai)", int((df["price"] < 1000).sum()), "Loại khỏi phân tích hoặc sửa lại giá"),
        ("Giảm giá 100%", int((df["discount_pct"] >= 100).sum()), "Kiểm tra lại, thường do giá bán bị sai"),
        ("Giá bán > giá niêm yết", int((df["price"] > df["price_original"]).sum()), "Đổi chỗ hoặc loại bỏ"),
        ("Trùng link sản phẩm", int(df.duplicated("url").sum()), "Giữ một bản ghi"),
        ("Trùng tên + thương hiệu + nguồn", int(df.duplicated(["name", "brand", "source"]).sum()),
         "Xem xét gộp (có thể là biến thể khác nhau)"),
        ("Thiếu dung tích", int(df["volume"].isna().sum()), "Điền trung vị khi chạy mô hình"),
        ("Có dung tích nhưng không đọc được số", int((df["volume"].notna() & df["dung_tich"].isna()).sum()),
         "Chuẩn hóa lại chuỗi dung tích"),
        ("Thiếu xuất xứ", int(df["origin"].isna().sum()), "Gán 'Không rõ'"),
        ("Chưa có đánh giá (rating trống)", int(df["rating"].isna().sum()), "Giữ nguyên, không điền số liệu giả"),
    ]
    bang = pd.DataFrame(van_de, columns=["Vấn đề", "Số dòng", "Cách xử lý đề xuất"])
    bang["Tỷ lệ (%)"] = (bang["Số dòng"] / len(df) * 100).round(2)
    st.dataframe(bang[["Vấn đề", "Số dòng", "Tỷ lệ (%)", "Cách xử lý đề xuất"]], width="stretch", hide_index=True)

    st.subheader("Thống kê mô tả các cột số")
    so = df[["price", "price_original", "discount_pct", "rating", "review_count", "dung_tich"]].describe().T
    so.index = [LABELS[i] for i in so.index]
    st.dataframe(so.round(2), width="stretch")


def page_report():
    page_header("Xuất báo cáo")
    df = get_data()
    if df.empty:
        st.info("Chưa có dữ liệu.")
        return

    so = df[["price", "price_original", "discount_pct", "rating", "review_count", "dung_tich"]].describe().T
    so.index = [LABELS[i] for i in so.index]
    theo_nhom = df.groupby(["nguon", "category_group"]).agg(
        so_san_pham=("id", "size"), gia_tb=("price", "mean"), giam_gia_tb=("discount_pct", "mean")
    ).round(1).reset_index()
    theo_hang = df.groupby("brand").agg(
        so_san_pham=("id", "size"), gia_tb=("price", "mean"), giam_gia_tb=("discount_pct", "mean"),
        luot_danh_gia=("review_count", "sum")
    ).round(1).sort_values("so_san_pham", ascending=False).reset_index()

    st.subheader("Thống kê mô tả")
    st.dataframe(so.round(2), width="stretch")
    st.subheader("Tổng hợp theo nguồn và nhóm ngành hàng")
    st.dataframe(theo_nhom, width="stretch", hide_index=True)

    xuat = df.drop(columns=["khoang_gia", "muc_giam", "xuat_xu", "nguon", "co_danh_gia", "giam_gia_vnd"]).rename(columns=LABELS)
    c1, c2 = st.columns(2)
    c1.download_button("Tải CSV", xuat.to_csv(index=False).encode("utf-8-sig"), file_name="bao_cao.csv", mime="text/csv")
    if c2.button("Chuẩn bị file Excel"):
        bo_nho = io.BytesIO()
        with pd.ExcelWriter(bo_nho, engine="openpyxl") as writer:
            xuat.to_excel(writer, sheet_name="Du lieu", index=False)
            so.to_excel(writer, sheet_name="Thong ke")
            theo_nhom.to_excel(writer, sheet_name="Theo nhom", index=False)
            theo_hang.to_excel(writer, sheet_name="Theo thuong hieu", index=False)
        c2.download_button(
            "Tải Excel",
            bo_nho.getvalue(),
            file_name="bao_cao.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )



# =====================================================================
# 3. CÁC TRANG MÔ HÌNH HỌC MÁY: nằm trong ml_pages.py (mô hình ở source-code/ml/)
# =====================================================================


# =====================================================================
# 4. BẢNG MENU + PHÂN QUYỀN
#    Mỗi dòng: (nhóm trên thanh menu, tên trang, hàm vẽ trang, đường dẫn, ai được xem)
#    Muốn thêm trang mới: viết hàm rồi thêm một dòng vào đây.
# =====================================================================
TAT_CA = ("admin", "editor", "viewer")
QUAN_LY = ("admin", "editor")

PAGES = [
    ("Dashboard", "Tổng quan thị trường", page_tong_quan, "tong-quan", TAT_CA),
    ("Dashboard", "Thống kê & Min-Max", page_thong_ke, "thong-ke", TAT_CA),
    ("Dashboard", "So sánh Hasaki – Cocolux", page_so_sanh, "so-sanh", TAT_CA),
    ("Dashboard", "Thương hiệu & Xuất xứ", page_thuong_hieu, "thuong-hieu", TAT_CA),
    ("Dashboard", "Giá & Khuyến mãi", page_gia_khuyen_mai, "gia-khuyen-mai", TAT_CA),
    ("Dashboard", "Đánh giá & Tồn kho", page_danh_gia_ton_kho, "danh-gia-ton-kho", TAT_CA),
    ("Phân tích", "Khám phá dữ liệu", page_explore, "kham-pha", TAT_CA),
    ("Phân tích", "Chất lượng dữ liệu", page_quality, "chat-luong", TAT_CA),
    ("Phân tích", "Xuất báo cáo", page_report, "bao-cao", TAT_CA),
    ("Mô hình", "Phân khúc thương hiệu", ml_pages.page_phan_cum_thuong_hieu, "phan-khuc-thuong-hieu", TAT_CA),
    ("Mô hình", "Dự đoán giá", ml_pages.page_dinh_gia, "du-doan-gia", TAT_CA),
    ("Mô hình", "Dự đoán hết hàng", ml_pages.page_het_hang, "du-doan-het-hang", TAT_CA),
    ("Mô hình", "Phát hiện bất thường", ml_pages.page_bat_thuong, "bat-thuong", TAT_CA),
    ("Quản lý", "Quản lý dữ liệu", page_crud, "crud", QUAN_LY),
    ("Quản lý", "Quản trị người dùng", page_users, "nguoi-dung", ("admin",)),
    ("Quản lý", "Sao lưu & phục hồi", page_backup, "sao-luu", ("admin",)),
]


def build_menu(vai_tro):
    """Trả về {tên nhóm: [các trang]} chỉ gồm những trang vai trò này được xem."""
    menu = {}
    for nhom, ten, ham, duong_dan, duoc_xem in PAGES:
        if vai_tro in duoc_xem:
            menu.setdefault(nhom, []).append(st.Page(ham, title=ten, url_path=duong_dan))
    return menu


# =====================================================================
# 5. HÀM CHÍNH
# =====================================================================
def account_bar(user):
    """Nút tài khoản trên thanh navbar. Bấm vào để xem thông tin, làm mới dữ liệu, đăng xuất."""
    ten = user["full_name"] or user["username"]
    with st.container(key="account_bar"):
        with st.popover(f"Chào {ten}", icon=":material/account_circle:"):
            st.markdown(f"**{ten}**")
            st.caption(f"Tài khoản: {user['username']}")
            st.markdown(f'<span class="role-badge">{ROLE_NAMES[user["role"]]}</span>', unsafe_allow_html=True)
            if st.button("Làm mới dữ liệu", width="stretch"):
                db.bump()  # xóa bộ nhớ đệm để tải lại từ CSDL
                st.rerun()
            with st.form("change_own_password"):
                old = st.text_input("Mật khẩu hiện tại", type="password")
                new = st.text_input("Mật khẩu mới (ít nhất 10 ký tự)", type="password")
                again = st.text_input("Nhập lại mật khẩu mới", type="password")
                if st.form_submit_button("Đổi mật khẩu"):
                    if new != again:
                        st.error("Hai mật khẩu mới không giống nhau")
                    else:
                        ok, msg = db.change_password(old, new)
                        if ok:
                            st.session_state.user = db.verify_user(user["username"], new)
                            flash(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            if st.button("Đăng xuất", type="primary", width="stretch"):
                st.session_state.clear()
                st.rerun()


def navbar(user, menu):
    """Thanh điều hướng 1 hàng: [logo + tên web] [3 nhóm chức năng] ...... [tài khoản]."""
    # chừa chỗ phía trên cho thanh navbar cố định (chỉ khi đã đăng nhập)
    st.markdown("<style>.block-container{padding-top:6.3rem !important;}</style>", unsafe_allow_html=True)
    with st.container(key="topnav"):
        with st.container(key="nav_row"):
            trang_chu = next(iter(menu.values()))[0]  # trang đầu tiên của menu = trang chủ (Dashboard)
            with st.container(key="brand"):
                st.markdown(
                    f'<div class="brand">{logo_html(rong=44, canh_giua=False)}'
                    '<div class="brand-text"><b>Phân tích dữ liệu</b><span>Hasaki &amp; Cocolux</span></div></div>',
                    unsafe_allow_html=True,
                )
                st.page_link(trang_chu, label="Về trang chủ")
            for nhom, cac_trang in menu.items():  # Phân tích / Mô hình / Quản lý
                with st.popover(nhom):
                    for p in cac_trang:
                        st.page_link(p, label=p.title)
            account_bar(user)  # nằm cuối hàng, được CSS đẩy sang sát bên phải


def main():
    st.session_state.pop("_data_snapshot", None)
    startup = st.empty()
    startup.info("Đang kết nối và khởi tạo dữ liệu…")
    try:
        db.init_db()
    finally:
        startup.empty()
    apply_style()

    from security import current_user
    user = current_user()
    if user:
        st.session_state.user = user
    else:
        st.session_state.pop("user", None)
    if not user:  # chưa đăng nhập thì chỉ hiện form đăng nhập / đăng ký
        login_page()
        return

    menu = build_menu(user["role"])
    trang = st.navigation([p for ds in menu.values() for p in ds], position="hidden")  # menu mặc định bị ẩn
    navbar(user, menu)  # thanh điều hướng riêng của web
    trang.run()  # chạy trang đang được chọn


def show_database_error(exc):
    cause = exc.__cause__ or exc
    # Do not log exception text: driver messages can contain connection details.
    code = getattr(cause, "code", None)
    logging.getLogger(__name__).error("Database request failed: type=%s code=%s", type(cause).__name__, code)
    if isinstance(cause, InvalidURI):
        message = "MONGO_URI không hợp lệ. Kiểm tra chuỗi kết nối và mã hóa URL các ký tự đặc biệt trong mật khẩu."
    elif isinstance(cause, OperationFailure) and code == 18:
        message = "MongoDB từ chối đăng nhập. Kiểm tra username và password trong Database Access của Atlas và cập nhật MONGO_URI."
    elif isinstance(cause, OperationFailure) and code == 13:
        message = "Tài khoản MongoDB chưa đủ quyền. Kiểm tra quyền readWrite trên database được đặt trong MONGO_DB."
    elif isinstance(cause, ServerSelectionTimeoutError):
        message = "Không tìm được máy chủ MongoDB trong thời gian chờ. Kiểm tra Network Access cho máy chủ Streamlit, trạng thái cluster và hostname trong MONGO_URI."
    elif isinstance(cause, ConfigurationError):
        message = "Cấu hình MongoDB hoặc DNS không hợp lệ. Kiểm tra hostname trong MONGO_URI và cấu hình kết nối Atlas."
    else:
        message = "Không thể hoàn tất thao tác với MongoDB. Kiểm tra cấu hình Atlas và tải lại trang trước khi thử lại."
    st.error(message)
    st.caption(f"Mã chẩn đoán: {type(cause).__name__}" + (f" · {code}" if code is not None else ""))


try:
    main()
except ConnectionError as exc:
    show_database_error(exc)
except (PermissionError, ValueError, db.DuplicateError) as exc:
    st.error(str(exc))
except PyMongoError as exc:
    show_database_error(exc)
