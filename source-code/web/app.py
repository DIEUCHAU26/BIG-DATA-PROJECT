import base64
import io
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from pymongo.errors import PyMongoError

import db
import models
from admin_pages import ROLE_NAMES, page_backup, page_crud, page_users
from data_loader import LABELS, get_data
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
# 3. CÁC TRANG MÔ HÌNH HỌC MÁY (phần tính toán nằm trong models.py)
# =====================================================================
def _cot_ve(ten):
    """Tên đặc trưng hiển thị -> tên cột trong bảng dữ liệu."""
    return models.FEATURES[ten][0]


def page_clustering():
    page_header("Phân cụm (K-Means)")
    df = get_data()
    c1, c2 = st.columns([2, 1])
    ten_dt = c1.multiselect("Đặc trưng dùng để phân cụm", list(models.FEATURES),
                            default=["Giá bán", "Mức giảm giá", "Lượt đánh giá"])
    k = c2.slider("Số cụm (K)", 2, 8, 4)
    if len(ten_dt) < 2:
        st.warning("Hãy chọn ít nhất 2 đặc trưng.")
        return
    if len(df) < k * 20:
        st.warning("Không đủ dữ liệu để phân cụm.")
        return

    nhan, sil, _ = models.run_kmeans(df, ten_dt, k)
    # Đánh số cụm theo giá TB tăng dần: "Cụm 1" luôn là cụm rẻ nhất
    thu_tu = df.groupby(nhan)["price"].mean().sort_values().index
    doi = {c: f"Cụm {i + 1}" for i, c in enumerate(thu_tu)}
    df = df.assign(cum=[doi[x] for x in nhan])

    lon_nhat = df["cum"].value_counts()
    cards([
        ("Số cụm", str(k), "plum"),
        ("Điểm silhouette", f"{sil:.2f}", "teal", "càng gần 1 càng tách cụm tốt"),
        ("Cụm lớn nhất", lon_nhat.index[0], "rose", f"{fmt_int(lon_nhat.iloc[0])} sản phẩm"),
        ("Số sản phẩm", fmt_int(len(df)), "gold"),
    ])

    x_ten = st.selectbox("Trục ngang", ten_dt, index=0)
    y_ten = st.selectbox("Trục dọc", ten_dt, index=1)
    x, y = _cot_ve(x_ten), _cot_ve(y_ten)
    ve = df[[x, y, "cum"]].dropna()
    if x != y:
        ve = ve[(ve[x] <= ve[x].quantile(0.995)) & (ve[y] <= ve[y].quantile(0.995))]
    ve = ve.rename(columns={x: x_ten, y: y_ten, "cum": "Cụm"}).sort_values("Cụm")
    if x_ten == y_ten:
        st.info("Hãy chọn hai đặc trưng khác nhau cho hai trục.")
    else:
        st.scatter_chart(ve, x=x_ten, y=y_ten, color="Cụm", height=420)

    st.subheader("Đặc điểm trung bình của từng cụm")
    prof = df.groupby("cum").agg(
        so_san_pham=("id", "size"), gia_ban=("price", "mean"), gia_niem_yet=("price_original", "mean"),
        giam_gia=("discount_pct", "mean"), luot_danh_gia=("review_count", "mean"),
        danh_gia=("rating", "mean"), dung_tich=("dung_tich", "median"),
        nhom_pho_bien=("category_group", lambda s: s.mode().iat[0] if not s.mode().empty else ""),
        thuong_hieu_pho_bien=("brand", lambda s: s.mode().iat[0] if not s.mode().empty else ""),
    ).round(1)
    prof.columns = ["Số SP", "Giá bán TB", "Giá niêm yết TB", "Giảm giá TB (%)", "Lượt ĐG TB", "Đánh giá TB",
                    "Dung tích (trung vị)", "Nhóm phổ biến", "Thương hiệu phổ biến"]
    prof.index.name = "Cụm"
    st.dataframe(prof, width="stretch")

    st.subheader("Thành phần nhóm ngành hàng trong mỗi cụm")
    cheo = pd.crosstab(df["cum"], df["category_group"])
    bar(cheo, color=CHART_COLORS[:cheo.shape[1]])

    if st.checkbox("Xem biểu đồ Elbow (gợi ý chọn K)"):
        khuỷu = pd.Series(models.elbow(df, ten_dt), name="Inertia")
        khuỷu.index = [f"K = {i}" for i in khuỷu.index]
        st.line_chart(khuỷu, color=CHART_COLORS[0])
        st.caption("Chọn K tại 'khuỷu tay' - nơi đường giảm chậm lại rõ rệt.")


@st.cache_resource(show_spinner="Đang huấn luyện mô hình...", max_entries=4)
def _huan_luyen(df, kind):
    return models.train_price_model(df, kind)


def page_predict():
    page_header("Dự đoán giá niêm yết")
    df = get_data()
    if (df["price_original"] > 0).sum() < 200:
        st.warning("Cần ít nhất 200 sản phẩm để huấn luyện.")
        return
    kind = st.radio("Mô hình", ["forest", "ridge"], horizontal=True,
                    format_func={"forest": "Random Forest", "ridge": "Hồi quy tuyến tính (Ridge)"}.get)
    goi = _huan_luyen(df, kind)
    m = goi["metrics"]
    cards([
        ("Độ phù hợp R² (thang log)", f"{m['r2_log']:.2f}", "teal", "trên 20% dữ liệu kiểm tra"),
        ("Sai số tuyệt đối TB (MAE)", fmt_vnd(m["mae"]), "rose"),
        ("Sai số tương đối (trung vị)", f"{m['mape_median']:.0f}%", "gold"),
        ("Train / Test", f"{fmt_int(m['n_train'])} / {fmt_int(m['n_test'])}", "plum"),
    ])

    trai, phai = st.columns(2)
    with trai:
        st.subheader("Thực tế so với dự đoán (đ)")
        mau = goi["test"].sample(min(800, len(goi["test"])), random_state=1)
        st.scatter_chart(mau, x="Thực tế", y="Dự đoán", color=CHART_COLORS[0], height=340)
    with phai:
        st.subheader("Yếu tố ảnh hưởng đến giá")
        if goi["importance"] is not None:
            ten = {"source": "Nguồn", "category_group": "Nhóm ngành hàng", "category": "Danh mục",
                   "brand_top": "Thương hiệu", "xuat_xu": "Xuất xứ", "dung_tich": "Dung tích",
                   "la_combo": "Là combo / set", "la_mini": "Là bản mini"}
            quan_trong = (goi["importance"] * 100).round(1).rename(index=ten)
            bar(ranked(quan_trong).rename("Mức quan trọng %"), horizontal=True, color=CHART_COLORS[1], height=340)
        else:
            st.info("Hồi quy tuyến tính không có biểu đồ độ quan trọng; hãy chọn Random Forest.")

    st.subheader("Thử dự đoán cho một sản phẩm")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        nguon = c1.selectbox("Nguồn", sorted(df["source"].dropna().unique()), format_func=str.title)
        nhom = c2.selectbox("Nhóm ngành hàng", sorted(df["category_group"].dropna().unique()))
        dm = c3.selectbox("Danh mục", sorted(df.loc[df["category_group"] == nhom, "category"].dropna().unique()))
        c4, c5, c6 = st.columns(3)
        hang = c4.selectbox("Thương hiệu", goi["top_brands"] + ["Khác"])
        xuat_xu = c5.selectbox("Xuất xứ", sorted(df["xuat_xu"].unique()))
        dung_tich = c6.number_input("Dung tích (ml hoặc g)", 0.0, 5000.0, 100.0, step=10.0)
        c7, c8, c9 = st.columns(3)
        combo = c7.checkbox("Là combo / set")
        mini = c8.checkbox("Là bản mini")
        giam = c9.slider("Giảm giá dự kiến (%)", 0, 80, 0)
    gia = models.predict_price(goi, nguon, nhom, dm, hang, xuat_xu, dung_tich, combo, mini)
    cards([
        ("Giá niêm yết dự đoán", fmt_vnd(round(gia, -3)), "rose"),
        (f"Giá bán sau giảm {giam}%", fmt_vnd(round(gia * (1 - giam / 100), -3)), "teal"),
    ])


def page_anomaly():
    page_header("Phát hiện bất thường")
    df = get_data()
    if len(df) < 50:
        st.warning("Cần ít nhất 50 sản phẩm.")
        return
    phan_tram = st.slider("Tỷ lệ bất thường giả định (%)", 1, 10, 2)
    kq = models.detect_anomalies(df, phan_tram / 100)
    bat_thuong = kq[kq["bat_thuong"]].sort_values("diem")

    cards([
        ("Sản phẩm được phân tích", fmt_int(len(kq)), "plum"),
        ("Bất thường phát hiện", fmt_int(len(bat_thuong)), "rose"),
        ("Tỷ lệ giả định", f"{phan_tram}%", "gold"),
    ])
    st.info("Bất thường chỉ có nghĩa là khác biệt về thống kê, chưa chắc là lỗi hay gian lận.")

    cac_cot = {"Giá bán": "price", "Giá niêm yết": "price_original", "Mức giảm giá": "discount_pct",
               "Lượt đánh giá": "review_count"}
    c1, c2 = st.columns(2)
    x_ten = c1.selectbox("Trục ngang", list(cac_cot), index=0)
    y_ten = c2.selectbox("Trục dọc", list(cac_cot), index=3)
    if x_ten == y_ten:
        st.info("Hãy chọn hai đặc trưng khác nhau cho hai trục.")
    else:
        ve = pd.DataFrame({x_ten: kq[cac_cot[x_ten]]})
        # Hai cột y riêng để tô hai màu: xám cho bình thường, hồng cho bất thường
        ve["Bình thường"] = np.where(kq["bat_thuong"], np.nan, kq[cac_cot[y_ten]])
        ve["Bất thường"] = np.where(kq["bat_thuong"], kq[cac_cot[y_ten]], np.nan)
        st.scatter_chart(ve, x=x_ten, y=["Bình thường", "Bất thường"], color=["#C9BFD0", "#D6336C"], height=420)
        st.caption(f"Trục dọc: {y_ten}.")

    trai, phai = st.columns(2)
    with trai:
        st.subheader("Bất thường theo nhóm ngành hàng")
        bar(bat_thuong["category_group"].value_counts().rename("Số sản phẩm"), color=CHART_COLORS[0])
    with phai:
        st.subheader("Lý do nổi bật")
        bar(ranked(bat_thuong["ly_do"].value_counts()).rename("Số sản phẩm"), horizontal=True, color=CHART_COLORS[3])

    st.subheader("Danh sách sản phẩm bất thường (bất thường nhất ở trên cùng)")
    cot = ["id", "nguon", "name", "brand", "price", "price_original", "discount_pct", "review_count", "rating",
           "diem", "ly_do", "url"]
    show_table(bat_thuong[cot], height=420)
    st.download_button("Tải danh sách bất thường (CSV)",
                       bat_thuong[cot].rename(columns=LABELS).to_csv(index=False).encode("utf-8-sig"),
                       file_name="bat_thuong.csv", mime="text/csv")


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
    ("Mô hình", "Phân cụm", page_clustering, "phan-cum", TAT_CA),
    ("Mô hình", "Dự đoán giá", page_predict, "du-doan-gia", TAT_CA),
    ("Mô hình", "Phát hiện bất thường", page_anomaly, "bat-thuong", TAT_CA),
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
    db.init_db()
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


try:
    main()
except (ConnectionError, PermissionError, ValueError, db.DuplicateError) as exc:
    st.error(str(exc))
except PyMongoError:
    st.error("Không thể hoàn tất thao tác với MongoDB. Hãy tải lại dữ liệu để kiểm tra trạng thái trước khi thử lại.")
