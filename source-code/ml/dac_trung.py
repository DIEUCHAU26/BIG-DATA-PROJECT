# Tạo đặc trưng dùng chung cho huấn luyện (2_dinh_gia, 3_het_hang) và dự đoán (du_doan, web).
# Đầu vào "thô" = các cột như bảng products của web / products_final.xlsx.
import numpy as np, pandas as pd
from quy_tac import (chuan_hoa_brand, gan_loai_sp, dem_so_luong, REGEX_HSD, REGEX_COMBO, REGEX_MINI, REGEX_VOLUME,
                     QUY_DOI_DON_VI)

COT_GIA = ["source", "category_group", "category", "brand_top", "unit", "origin", "loai_sp",
           "log_vol", "vol_missing", "is_combo", "is_mini", "log_sl", "brand_te"]
COT_HET_HANG = ["category_group", "brand_top", "unit", "origin",
                "log_price_original", "discount_pct", "log_reviews", "log_vol", "is_combo", "is_mini",
                "brand_te"]


def lam_sach_co_ban(df):
    """Thêm các cột dẫn xuất giống 0_lam_sach.py (không lọc, không bỏ dòng).
    Dung tích đọc từ chuỗi 'volume' (web chỉ có cột này), kết quả trùng với
    volume_value/volume_unit đã quy đổi trong 0_lam_sach.py (kiểm tra bằng kiem_tra_du_doan.py)."""
    df = df.copy()
    df["brand"] = chuan_hoa_brand(df["brand"])
    v = df["volume"].astype("object").str.lower().str.extract(REGEX_VOLUME)
    so = pd.to_numeric(v[0].str.replace(",", "."), errors="coerce")
    qd = v[1].map(QUY_DOI_DON_VI)
    df["vol"] = so * qd.map(lambda x: x[1] if isinstance(x, tuple) else np.nan)
    df["unit"] = qd.map(lambda x: x[0] if isinstance(x, tuple) else np.nan).fillna("khong_ro")
    ten = df["name"].astype("object").fillna("")
    df["is_hsd"] = ten.str.contains(REGEX_HSD, regex=True).astype(int)
    df["is_combo"] = ten.str.contains(REGEX_COMBO, regex=True).astype(int)
    df["is_mini"] = ten.str.contains(REGEX_MINI, regex=True).astype(int)
    df.loc[df["is_combo"] == 1, "vol"] = np.nan
    if "price_original" in df:
        df["log_price_original"] = np.log(df["price_original"].astype(float))
    if "review_count" in df:
        df["log_reviews"] = np.log1p(df["review_count"].astype(float).fillna(0))
    return df


def _chung(df, top_brands):
    """Các đặc trưng cả hai mô hình đều dùng. df đã qua lam_sach_co_ban."""
    X = pd.DataFrame(index=df.index)
    X["brand_top"] = np.where(df["brand"].isin(top_brands), df["brand"], "Khác")
    X["brand_te"] = df["brand"].fillna("?")
    X["log_vol"] = np.log1p(df["vol"].fillna(0))
    for c in ["source", "category_group", "category", "unit", "origin", "is_combo", "is_mini"]:
        X[c] = df[c]
    return X


def dac_trung_gia(df, top_brands):
    X = _chung(df, top_brands)
    X["vol_missing"] = df["vol"].isna().astype(int)
    X["loai_sp"] = gan_loai_sp(df["name"])
    X["log_sl"] = np.log1p(dem_so_luong(df["name"]).fillna(1))
    return X[COT_GIA]


def dac_trung_het_hang(df, top_brands):
    X = _chung(df, top_brands)
    for c in ["log_price_original", "discount_pct", "log_reviews"]:
        X[c] = df[c]
    return X[COT_HET_HANG]
