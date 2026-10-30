"""Các trang "Mô hình" của web, dùng mô hình học máy ở source-code/ml/ (xem source-code/ml/document/).

- Mô hình, biểu đồ, metrics:  source-code/ml/models, source-code/ml/bieu_do
- Bảng kết quả theo url:      dataset/ml/ (do source-code/ml/chay_tat_ca.py tạo ra)
Sản phẩm mới thêm qua CRUD chưa có trong bảng kết quả nên được dự đoán trực tiếp bằng du_doan.py.
"""
import json
import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import compat

compat.patch_threadpoolctl()

SOURCE_CODE = Path(__file__).resolve().parent.parent
ML_DIR = SOURCE_CODE / "ml"
DATASET_ML = SOURCE_CODE.parent / "dataset" / "ml"
sys.path.append(str(ML_DIR))  # du_doan, dac_trung, quy_tac (không đè các module của web)

from data_loader import get_data  # noqa: E402
from ui import CHART_COLORS, bar, cards, fmt_int, fmt_vnd, page_header, show_table  # noqa: E402

LOAI_SP = {
    "ve_sinh_pn": "Vệ sinh phụ nữ", "dao_cao": "Dao cạo", "thiet_bi": "Thiết bị", "kem_danh_rang": "Kem đánh răng",
    "long_mi_gia": "Lông mi giả", "khan_giay": "Khăn, giấy, bông tẩy trang", "phu_kien": "Phụ kiện",
    "mat_na_toc": "Mặt nạ tóc", "mat_na": "Mặt nạ", "tay_trang": "Tẩy trang", "rua_mat": "Rửa mặt",
    "chong_nang": "Chống nắng", "toner": "Toner", "trang_diem": "Trang điểm", "serum": "Serum",
    "nuoc_hoa": "Nước hoa", "son": "Son", "dau_goi_xa": "Dầu gội, xả", "sua_tam": "Sữa tắm", "kem": "Kem", "khac": "Khác",
}
DAC_TRUNG = {
    "brand_te": "Thương hiệu (giá trung bình)", "brand_top": "Thương hiệu (nhóm top)", "loai_sp": "Loại sản phẩm",
    "log_vol": "Dung tích", "vol_missing": "Thiếu dung tích", "is_combo": "Là combo", "is_mini": "Là bản mini",
    "log_sl": "Số lượng trong bộ", "origin": "Xuất xứ", "category_group": "Nhóm ngành hàng", "category": "Danh mục",
    "unit": "Đơn vị", "source": "Nguồn", "log_price_original": "Giá niêm yết", "discount_pct": "Giảm giá",
    "log_reviews": "Lượt đánh giá",
}
DAC_TRUNG_CUM = {
    "log_so_sp": "Số sản phẩm", "log_gia": "Giá", "giam_gia": "Giảm giá", "het_hang": "Hết hàng",
    "log_danh_gia": "Đánh giá", "combo": "Tỷ lệ combo",
}
CAC_COT_NHAP = ["source", "category_group", "category", "name", "brand", "volume", "origin"]


# ----------------------------- ĐỌC DỮ LIỆU ML -----------------------------
@st.cache_data(show_spinner=False)
def _csv(path, mtime):
    return pd.read_csv(path)


def doc_csv(path):
    path = Path(path)
    if not path.exists():
        st.error(f"Chưa có file `{path.name}`. Hãy chạy `python chay_tat_ca.py` trong source-code/ml/.")
        st.stop()
    return _csv(str(path), path.stat().st_mtime).copy()


@st.cache_data(show_spinner=False)
def _json(path, mtime):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def metrics():
    p = ML_DIR / "models" / "metrics.json"
    if not p.exists():
        st.error("Chưa có `models/metrics.json`. Hãy chạy `python chay_tat_ca.py` trong source-code/ml/.")
        st.stop()
    return _json(str(p), p.stat().st_mtime)


def _du_doan():
    """Nạp du_doan.py một lần; báo lỗi rõ ràng nếu thiếu mô hình hoặc sai phiên bản thư viện."""
    try:
        import du_doan
        du_doan.nap_mo_hinh("dinh_gia")
        du_doan.nap_mo_hinh("het_hang")
        return du_doan
    except Exception as e:
        st.error(f"Không nạp được mô hình ML: {e}")
        st.stop()


def ket_qua_ml(df):
    """Ghép dữ liệu trong CSDL với bảng kết quả theo url. Sản phẩm chưa có kết quả (mới thêm) được dự đoán trực tiếp."""
    d = df.merge(doc_csv(DATASET_ML / "san_pham_ml.csv"), on="url", how="left")
    for c in ("gia_bat_thuong", "iqr", "iso", "lof"):
        d[c] = d[c].eq(True)  # NaN (sản phẩm chưa có kết quả) -> False
    d["so_phuong_phap"] = d["so_phuong_phap"].astype(float)

    thieu_gia = d["gia_du_doan"].isna() & (d["price_original"] > 0)
    thieu_hh = d["xs_het_hang"].isna() & (d["source"] == "hasaki") & d[["price_original", "discount_pct", "review_count"]].notna().all(axis=1)
    if thieu_gia.any() or thieu_hh.any():
        dd = _du_doan()
        try:
            if thieu_gia.any():
                d.loc[thieu_gia, "gia_du_doan"] = dd.du_doan_gia(d[thieu_gia]).round(-3)
                d.loc[thieu_gia, "chenh_lech_pct"] = ((d.loc[thieu_gia, "price_original"] / d.loc[thieu_gia, "gia_du_doan"] - 1) * 100).round(1)
            if thieu_hh.any():
                r = dd.du_doan_het_hang(d[thieu_hh])
                d.loc[thieu_hh, "xs_het_hang"] = r["xs_het_hang"]
                d.loc[thieu_hh, "du_doan_het_hang"] = r["du_doan_het_hang"]
        except Exception as e:  # dữ liệu mới thiếu cột: bỏ qua, các dòng đó chỉ không có dự đoán
            st.warning(f"Một số sản phẩm mới chưa dự đoán được: {e}")
    return d


def _hien_loai(s):
    return s.map(LOAI_SP).fillna(s)


def _dong_nhap(df, co_gia=False, key=""):
    """Form nhập thông tin 1 sản phẩm, trả về dict đúng định dạng du_doan.py cần."""
    c1, c2, c3 = st.columns(3)
    nguon = c1.selectbox("Nguồn", sorted(df["source"].dropna().unique()), format_func=str.title, key=key + "nguon")
    nhom = c2.selectbox("Nhóm ngành hàng", sorted(df["category_group"].dropna().unique()), key=key + "nhom")
    dm = c3.selectbox("Danh mục", sorted(df.loc[df["category_group"] == nhom, "category"].dropna().unique()), key=key + "dm")
    ten = st.text_input("Tên sản phẩm (mô hình đọc loại sản phẩm, số lượng, combo từ tên)", key=key + "ten",
                        value="Sữa Rửa Mặt CeraVe Sạch Sâu Cho Da Thường Đến Da Dầu 236ml")
    c4, c5, c6 = st.columns(3)
    hang = c4.selectbox("Thương hiệu", sorted(df["brand"].dropna().str.upper().unique()), key=key + "hang")
    dung_tich = c5.text_input("Dung tích (ví dụ 100ml, 50g)", value="236ml", key=key + "dt")
    xuat_xu = c6.selectbox("Xuất xứ", ["(không rõ)"] + sorted(df["origin"].dropna().unique()), key=key + "xx")
    sp = {"source": nguon, "category_group": nhom, "category": dm, "name": ten, "brand": hang,
          "volume": dung_tich or None, "origin": None if xuat_xu == "(không rõ)" else xuat_xu}
    if co_gia:
        c7, c8, c9 = st.columns(3)
        sp["price_original"] = c7.number_input("Giá niêm yết (đ)", 1000, 20_000_000, 300_000, step=10_000, key=key + "gia")
        sp["discount_pct"] = c8.slider("Giảm giá (%)", 0, 90, 20, key=key + "gg")
        sp["review_count"] = c9.number_input("Lượt đánh giá", 0, 100_000, 10, key=key + "dg")
    return sp


# ============================ 1. PHÂN KHÚC THƯƠNG HIỆU ============================
def page_phan_cum_thuong_hieu():
    page_header("Phân khúc thương hiệu (K-Means)",
                "Phân cụm thương hiệu theo số sản phẩm, giá, mức giảm giá, đánh giá, tỷ lệ combo. Chạy riêng từng sàn vì chính sách giá hai sàn khác nhau.")
    san = st.radio("Sàn", ["hasaki", "cocolux"], format_func=str.title, horizontal=True)
    m = metrics()["phan_cum"][san]

    cards([
        ("Số thương hiệu", fmt_int(m["so_thuong_hieu"]), "plum", "có từ 5 sản phẩm trở lên"),
        ("Số cụm (K)", str(m["k"]), "rose"),
        ("Điểm silhouette", f"{m['silhouette_kmeans']:.2f}", "teal", "càng gần 1 càng tách cụm tốt"),
        ("Thương hiệu ngoại lai", fmt_int(m["dbscan_nhieu"]), "gold", "theo DBSCAN"),
    ])

    pca = doc_csv(ML_DIR / "bieu_do" / f"phan_cum_{san}_pca.csv")
    trai, phai = st.columns(2)
    with trai:
        st.subheader("Các cụm trên mặt phẳng PCA")
        st.scatter_chart(pca.rename(columns={"ten_cum": "Cụm", "so_san_pham": "Số SP"}), x="pc1", y="pc2",
                         color="Cụm", size="Số SP", height=380)
    with phai:
        st.subheader("Chọn số cụm K")
        ck = pd.DataFrame(m["chon_k"]).set_index("k")
        st.line_chart(ck[["silhouette"]].rename(columns={"silhouette": "Silhouette (cao hơn tốt hơn)"}), color=CHART_COLORS[2], height=180)
        st.line_chart(ck[["inertia"]].rename(columns={"inertia": "Inertia / Elbow (thấp hơn tốt hơn)"}), color=CHART_COLORS[0], height=180)

    st.subheader("Hồ sơ từng cụm")
    st.caption("Độ lệch chuẩn so với trung bình: đỏ cao hơn trung bình, xanh thấp hơn.")
    hs = doc_csv(ML_DIR / "bieu_do" / f"phan_cum_{san}_ho_so.csv").rename(columns=DAC_TRUNG_CUM)
    hs = hs.melt("ten_cum", var_name="Đặc trưng", value_name="Độ lệch")
    st.altair_chart(alt.Chart(hs).mark_rect().encode(
        x=alt.X("Đặc trưng:N", sort=list(DAC_TRUNG_CUM.values()), axis=alt.Axis(labelAngle=0)),
        y=alt.Y("ten_cum:N", title="Cụm"),
        color=alt.Color("Độ lệch:Q", scale=alt.Scale(scheme="redblue", reverse=True, domain=[-2, 2])),
        tooltip=["ten_cum", "Đặc trưng", "Độ lệch"]), width="stretch")

    st.subheader("Danh sách thương hiệu theo cụm")
    bang = doc_csv(DATASET_ML / f"phan_cum_thuong_hieu_{san}.csv")
    c1, c2 = st.columns([1, 2])
    tim = c1.text_input("Tìm thương hiệu")
    chon = c2.multiselect("Cụm", sorted(bang["ten_cum"].unique()), placeholder="Tất cả cụm")
    if tim:
        bang = bang[bang["brand"].str.contains(tim, case=False, regex=False)]
    if chon:
        bang = bang[bang["ten_cum"].isin(chon)]
    bang = bang.drop(columns="cum").rename(columns={
        "brand": "Thương hiệu", "so_san_pham": "Số SP", "gia_tb": "Giá niêm yết (trung vị)", "giam_gia_tb": "Giảm giá TB (%)",
        "ti_le_het_hang": "Tỷ lệ hết hàng", "danh_gia_tb": "Lượt đánh giá TB", "ti_le_combo": "Tỷ lệ combo", "ten_cum": "Cụm"})
    if san == "cocolux":
        bang = bang.drop(columns="Tỷ lệ hết hàng")  # Cocolux gần như không có hàng hết nên không dùng để phân cụm
    show_table(bang.round(2).sort_values("Số SP", ascending=False), height=380)
    if san == "cocolux":
        st.caption("Cocolux có 99,97% sản phẩm còn hàng nên đặc trưng hết hàng không được dùng để phân cụm.")


# ============================ 2. ĐỊNH GIÁ ============================
def page_dinh_gia():
    page_header("Dự đoán giá niêm yết", "Mô hình học trên tên sản phẩm, thương hiệu, ngành hàng, dung tích, xuất xứ để ước lượng giá niêm yết hợp lý.")
    mt = metrics()["dinh_gia"]
    ct = mt["cac_mo_hinh"][mt["mo_hinh_chon"]]
    cards([
        ("Mô hình", mt["mo_hinh_chon"], "plum", f"{fmt_int(mt['so_mau'])} sản phẩm huấn luyện"),
        ("R² trên tập kiểm tra", f"{ct['test_r2']:.2f}", "teal", f"kiểm định chéo {ct['cv_r2']:.2f}"),
        ("Sai lệch trung vị", f"{ct['sai_lech_trung_vi_pct']:.0f}%", "gold"),
        ("Sai số tuyệt đối TB (MAE)", fmt_vnd(ct["mae"]), "rose"),
    ])

    so_sanh = pd.DataFrame(mt["cac_mo_hinh"]).T[["cv_r2", "test_r2", "mae", "sai_lech_trung_vi_pct"]]
    so_sanh.columns = ["R² kiểm định chéo", "R² kiểm tra", "MAE (đ)", "Sai lệch trung vị (%)"]
    st.subheader("So sánh các mô hình")
    st.dataframe(so_sanh.rename_axis("Mô hình"), width="stretch")

    trai, phai = st.columns(2)
    with trai:
        st.subheader("Giá thật so với giá dự đoán (đ)")
        t = doc_csv(ML_DIR / "bieu_do" / "dinh_gia_test.csv")
        t = t.sample(min(800, len(t)), random_state=1).rename(columns={"gia_that": "Thực tế", "gia_du_doan": "Dự đoán"})
        st.scatter_chart(t, x="Thực tế", y="Dự đoán", color=CHART_COLORS[0], height=340)
    with phai:
        st.subheader("Yếu tố ảnh hưởng đến giá")
        fi = pd.Series(mt["feature_importance"]).clip(lower=0).sort_values(ascending=False).rename(index=DAC_TRUNG)
        fi.index = [f"{i + 1:02d}. {k}" for i, k in enumerate(fi.index)]
        bar((fi * 100).round(1).rename("Mức quan trọng (%)"), horizontal=True, color=CHART_COLORS[1], height=340)

    trai, phai = st.columns(2)
    with trai:
        st.subheader("Đường học (thêm dữ liệu có giúp ích?)")
        lc = pd.DataFrame(mt["learning_curve"]).set_index("so_mau")
        st.line_chart(lc.rename(columns={"train_r2": "R² huấn luyện", "cv_r2": "R² kiểm định chéo"}),
                      color=[CHART_COLORS[3], CHART_COLORS[2]], height=300)
    with phai:
        st.subheader("Tỷ lệ đoán đúng theo loại sản phẩm")
        sl = doc_csv(ML_DIR / "bieu_do" / "dinh_gia_sai_lech_loai_sp.csv")
        sl["loai_sp"] = _hien_loai(sl["loai_sp"])
        sl = sl.sort_values("ty_le_doan_that", ascending=False)
        sl["loai_sp"] = [f"{i + 1:02d}. {k}" for i, k in enumerate(sl["loai_sp"])]
        bar(sl.set_index("loai_sp")["ty_le_doan_that"].rename("Tỷ lệ"), horizontal=True, color=CHART_COLORS[4], height=300)

    st.subheader("Thử dự đoán cho một sản phẩm")
    df = get_data()
    with st.container(border=True):
        sp = _dong_nhap(df, key="dg_")
        giam = st.slider("Giảm giá dự kiến (%)", 0, 80, 0, key="dg_giam")
    dd = _du_doan()
    gia = float(dd.du_doan_gia(sp).iloc[0])
    cards([
        ("Giá niêm yết dự đoán", fmt_vnd(round(gia, -3)), "rose"),
        (f"Giá bán sau giảm {giam}%", fmt_vnd(round(gia * (1 - giam / 100), -3)), "teal"),
    ])


# ============================ 3. HẾT HÀNG ============================
def page_het_hang():
    page_header("Dự đoán hết hàng", "Xác suất một sản phẩm Hasaki bị hết hàng. Cocolux gần như không có hàng hết nên không áp dụng.")
    mt = metrics()["het_hang"]
    ct = mt["cac_mo_hinh"][mt["mo_hinh_chon"]]
    tn = mt["test_tai_nguong"]
    cards([
        ("Mô hình", mt["mo_hinh_chon"], "plum", f"{fmt_int(mt['so_mau'])} sản phẩm huấn luyện"),
        ("AUC trên tập kiểm tra", f"{ct['test_auc']:.2f}", "teal", f"kiểm định chéo {ct['cv_auc']:.2f}"),
        ("Ngưỡng quyết định", f"{mt['nguong']:.2f}", "gold", "chọn để bắt được nhiều hàng sắp hết"),
        ("Bắt được hàng hết (recall)", f"{tn['recall']:.0%}", "rose", f"precision {tn['precision']:.0%}"),
    ])
    st.info(f"Hàng cận hạn [HSD] có {mt['ty_le_het_hang_can_han']:.1%} bị hết hàng nên được dự đoán bằng quy tắc, không dùng mô hình.")

    trai, phai = st.columns(2)
    rp = doc_csv(ML_DIR / "bieu_do" / "het_hang_roc_pr.csv")
    with trai:
        st.subheader("Đường ROC")
        roc = rp[rp["duong"] == "ROC"].rename(columns={"x": "Tỷ lệ báo nhầm", "y": "Tỷ lệ bắt đúng"})
        st.line_chart(roc, x="Tỷ lệ báo nhầm", y="Tỷ lệ bắt đúng", color=CHART_COLORS[0], height=300)
    with phai:
        st.subheader("Đường Precision - Recall")
        pr = rp[rp["duong"] == "PR"].rename(columns={"x": "Recall", "y": "Precision"})
        st.line_chart(pr, x="Recall", y="Precision", color=CHART_COLORS[1], height=300)

    trai, phai = st.columns(2)
    with trai:
        st.subheader("Ma trận nhầm lẫn (tập kiểm tra)")
        mtr = mt["ma_tran_nham_lan"]
        st.dataframe(pd.DataFrame(mtr["gia_tri"], index=[f"Thật: {n}" for n in mtr["nhan"]],
                                  columns=[f"Đoán: {n}" for n in mtr["nhan"]]), width="stretch")
    with phai:
        st.subheader("Yếu tố ảnh hưởng")
        fi = pd.Series(mt["feature_importance"]).clip(lower=0).sort_values(ascending=False).rename(index=DAC_TRUNG)
        fi.index = [f"{i + 1:02d}. {k}" for i, k in enumerate(fi.index)]
        bar((fi * 100).round(1).rename("Mức quan trọng (% giảm AUC)"), horizontal=True, color=CHART_COLORS[3], height=300)

    st.subheader("Sản phẩm Hasaki còn hàng có nguy cơ hết")
    d = ket_qua_ml(get_data())
    d = d[(d["source"] == "hasaki") & (d["in_stock"] == 1) & d["xs_het_hang"].notna()]
    c1, c2 = st.columns([2, 1])
    nguong = c1.slider("Ngưỡng xác suất hết hàng", 0.0, 1.0, float(mt["nguong"]), 0.01)
    nhom = c2.multiselect("Nhóm ngành hàng", sorted(d["category_group"].dropna().unique()), placeholder="Tất cả")
    if nhom:
        d = d[d["category_group"].isin(nhom)]
    nguy_co = d[d["xs_het_hang"] >= nguong].sort_values("xs_het_hang", ascending=False)
    st.caption(f"{fmt_int(len(nguy_co))} / {fmt_int(len(d))} sản phẩm còn hàng có xác suất hết ≥ {nguong:.2f}.")
    bang = nguy_co[["name", "brand", "price", "discount_pct", "review_count", "xs_het_hang", "het_hang_theo", "url"]].copy()
    bang["xs_het_hang"] = (bang["xs_het_hang"] * 100).round(1)
    bang["het_hang_theo"] = bang["het_hang_theo"].map({"mo_hinh": "Mô hình", "quy_tac_can_han": "Quy tắc cận hạn"}).fillna("Mô hình")
    show_table(bang.rename(columns={"xs_het_hang": "Xác suất hết (%)", "het_hang_theo": "Dự đoán theo"}), height=380)
    st.download_button("Tải danh sách nguy cơ (CSV)", bang.to_csv(index=False).encode("utf-8-sig"),
                       file_name="nguy_co_het_hang.csv", mime="text/csv")

    st.subheader("Thử dự đoán cho một sản phẩm Hasaki")
    df = get_data()
    df = df[df["source"] == "hasaki"]
    with st.container(border=True):
        sp = _dong_nhap(df, co_gia=True, key="hh_")
    sp["source"] = "hasaki"
    kq = _du_doan().du_doan_het_hang(sp).iloc[0]
    cards([
        ("Xác suất hết hàng", f"{kq['xs_het_hang']:.0%}", "rose"),
        ("Dự đoán", "Có thể hết hàng" if kq["du_doan_het_hang"] else "Còn hàng", "teal" if not kq["du_doan_het_hang"] else "gold",
         "theo quy tắc cận hạn" if kq["theo"] == "quy_tac_can_han" else "theo mô hình"),
    ])


# ============================ 4. BẤT THƯỜNG ============================
def page_bat_thuong():
    page_header("Phát hiện bất thường", "Kết hợp 3 phương pháp: IQR, Isolation Forest, LOF trên giá theo đơn vị, mức giảm, đánh giá và độ lệch so với giá mô hình. Thêm danh sách giá lệch xa giá dự đoán.")
    mt = metrics()["bat_thuong"]
    gc = mt["so_gan_co"]
    cards([
        ("Sản phẩm được phân tích", fmt_int(mt["so_mau"]), "plum", "hàng thường, có giá trên đơn vị"),
        ("Gắn cờ bởi IQR", fmt_int(gc["iqr"]), "rose"),
        ("Gắn cờ bởi Isolation Forest", fmt_int(gc["iso"]), "gold"),
        ("Gắn cờ bởi LOF", fmt_int(gc["lof"]), "teal"),
    ])
    st.info(f"{fmt_int(gc['tu_2_phuong_phap'])} sản phẩm bị gắn cờ bởi từ 2 phương pháp, {fmt_int(gc['ca_3'])} sản phẩm bị cả 3. "
            "Bất thường chỉ có nghĩa là khác biệt về thống kê, chưa chắc là lỗi hay gian lận.")

    d = ket_qua_ml(get_data())
    tab_kh, tab_gia = st.tabs(["Kết hợp 3 phương pháp", "Giá lệch so với mô hình"])
    with tab_kh:
        c1, c2 = st.columns([1, 2])
        n = c1.radio("Số phương pháp tối thiểu", [1, 2, 3], index=1, horizontal=True)
        nhom = c2.multiselect("Nhóm ngành hàng", sorted(d["category_group"].dropna().unique()), placeholder="Tất cả", key="bt_nhom")
        kq = d[d["so_phuong_phap"] >= n]
        if nhom:
            kq = kq[kq["category_group"].isin(nhom)]
        kq = kq.sort_values(["so_phuong_phap", "iso_score"], ascending=[False, True])
        trai, phai = st.columns(2)
        with trai:
            st.subheader("Theo nhóm ngành hàng")
            bar(kq["category_group"].value_counts().rename("Số sản phẩm"), color=CHART_COLORS[0], height=260)
        with phai:
            st.subheader("Theo phương pháp phát hiện")
            bar(pd.Series({"IQR": int(kq["iqr"].sum()), "Isolation Forest": int(kq["iso"].sum()), "LOF": int(kq["lof"].sum())},
                          name="Số sản phẩm"), color=CHART_COLORS[3], height=260)
        bang = kq[["name", "brand", "source", "price", "price_original", "gia_du_doan", "discount_pct", "review_count",
                   "iqr", "iso", "lof", "so_phuong_phap", "url"]].copy()
        bang["source"] = bang["source"].str.title()
        bang = bang.rename(columns={"source": "Nguồn", "gia_du_doan": "Giá dự đoán (đ)", "iqr": "IQR", "iso": "Isolation Forest",
                                    "lof": "LOF", "so_phuong_phap": "Số phương pháp"})
        bang["Số phương pháp"] = bang["Số phương pháp"].astype(int)
        st.caption(f"{fmt_int(len(bang))} sản phẩm.")
        show_table(bang, height=420)
        st.download_button("Tải danh sách bất thường (CSV)", bang.rename(columns={"url": "Link"}).to_csv(index=False).encode("utf-8-sig"),
                           file_name="bat_thuong.csv", mime="text/csv")

    with tab_gia:
        st.caption(f"Sản phẩm có giá niêm yết lệch xa giá mô hình dự đoán (|z| > {metrics()['dinh_gia']['nguong_z']}). "
                   "Giá dự đoán lấy từ mô hình định giá, tính trên phần dữ liệu mô hình chưa từng học (out-of-fold).")
        g = d[d["gia_bat_thuong"]].copy()
        g["loai_sp"] = _hien_loai(g["loai_sp"])
        g = g.sort_values("lech")
        g["huong"] = np.where(g["chenh_lech_pct"] > 0, "Cao hơn dự đoán", "Thấp hơn dự đoán")
        trai, phai = st.columns(2)
        with trai:
            st.subheader("Theo loại sản phẩm")
            bar(g["loai_sp"].value_counts().rename("Số sản phẩm"), horizontal=True, color=CHART_COLORS[1], height=300)
        with phai:
            st.subheader("Cao hay thấp hơn dự đoán")
            bar(g["huong"].value_counts().rename("Số sản phẩm"), color=CHART_COLORS[4], height=300)
        bang = g[["name", "brand", "source", "loai_sp", "price_original", "gia_du_doan", "chenh_lech_pct", "url"]].rename(columns={
            "source": "Nguồn", "loai_sp": "Loại SP", "gia_du_doan": "Giá dự đoán (đ)", "chenh_lech_pct": "Chênh lệch (%)"})
        bang["Nguồn"] = bang["Nguồn"].str.title()
        st.caption(f"{fmt_int(len(bang))} sản phẩm.")
        show_table(bang, height=420)
