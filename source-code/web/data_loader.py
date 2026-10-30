
import re

import numpy as np
import pandas as pd

import db

LABELS = {
    "id": "ID", "source": "Nguồn", "nguon": "Nguồn", "category_group": "Nhóm ngành hàng",
    "category": "Danh mục", "name": "Tên sản phẩm", "brand": "Thương hiệu", "product_code": "Mã SP",
    "price": "Giá bán (đ)", "price_original": "Giá niêm yết (đ)", "discount_pct": "Giảm giá (%)",
    "rating": "Đánh giá", "review_count": "Lượt đánh giá", "in_stock": "Còn hàng",
    "volume": "Dung tích", "origin": "Xuất xứ", "xuat_xu": "Xuất xứ", "url": "Link",
    "scraped_at": "Thu thập lúc", "dung_tich": "Dung tích (ml/g)", "khoang_gia": "Khoảng giá",
    "muc_giam": "Mức giảm", "giam_gia_vnd": "Tiền giảm (đ)",
    "diem": "Điểm bất thường", "ly_do": "Lý do nổi bật", "co_danh_gia": "Có đánh giá",
}

KHOANG_GIA = ["1) Dưới 100k", "2) 100k – 200k", "3) 200k – 500k", "4) 500k – 1 triệu", "5) Trên 1 triệu"]
MUC_GIAM = ["1) Không giảm", "2) 1 – 20%", "3) 21 – 40%", "4) 41 – 60%", "5) Trên 60%"]

_VOL = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ml|gr|g|kg|l)\b", re.I)


def _dung_tich(text):
    """'500ml' -> 500, '1.5l' -> 1500, '22g' -> 22. Không đọc được thì trả về NaN."""
    if not isinstance(text, str):
        return np.nan
    m = _VOL.search(text)
    if not m:
        return np.nan
    so = float(m.group(1).replace(",", "."))
    return so * 1000 if m.group(2).lower() in ("l", "kg") else so


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Thêm các cột dẫn xuất (không lưu vào CSDL)."""
    df = df.copy()
    df["nguon"] = df["source"].str.title()
    df["xuat_xu"] = df["origin"].fillna("Không rõ")
    df["dung_tich"] = df["volume"].map(_dung_tich)
    df["giam_gia_vnd"] = df["price_original"] - df["price"]
    df["khoang_gia"] = pd.cut(
        df["price"], [-1, 1e5, 2e5, 5e5, 1e6, np.inf], labels=KHOANG_GIA
    ).astype(str)
    df["muc_giam"] = pd.cut(
        df["discount_pct"], [-1, 0, 20, 40, 60, 100], labels=MUC_GIAM
    ).astype(str)
    df["co_danh_gia"] = df["rating"].notna()
    df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")
    return df


def get_data() -> pd.DataFrame:
    """Read the current database on every page rerun, including Atlas edits."""
    import streamlit as st
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx(suppress_warning=True) is None:
        return enrich(db.get_products())
    if "_data_snapshot" not in st.session_state:
        st.session_state["_data_snapshot"] = enrich(db.get_products())
    return st.session_state["_data_snapshot"].copy()
