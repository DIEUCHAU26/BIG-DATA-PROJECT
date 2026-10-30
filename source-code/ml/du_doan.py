# Dự đoán bằng mô hình đã huấn luyện, dùng cho web (Streamlit) và kiểm tra.
#   from du_doan import du_doan_gia, du_doan_het_hang
#   du_doan_gia(df_tho)          -> Series giá niêm yết dự đoán (đ)
#   du_doan_het_hang(df_tho)     -> DataFrame xs_het_hang, du_doan_het_hang, theo
# df_tho: 1 hoặc nhiều dòng, cột như bảng products của web
#   (source, category_group, category, name, brand, volume, origin, price_original, discount_pct, review_count)
import os, sys, warnings
from functools import lru_cache
import joblib, numpy as np, pandas as pd, sklearn

THU_MUC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THU_MUC)          # để import được dac_trung/quy_tac khi chép sang thư mục ml/ của web
from dac_trung import lam_sach_co_ban, dac_trung_gia, dac_trung_het_hang

THU_MUC_MODEL = os.path.join(THU_MUC, "models")


@lru_cache(maxsize=None)
def nap_mo_hinh(ten):
    """ten = 'dinh_gia' hoặc 'het_hang'. Trả về gói dict {model, top_brands, ...}."""
    goi = joblib.load(os.path.join(THU_MUC_MODEL, f"model_{ten}.joblib"))
    if goi["phien_ban_sklearn"] != sklearn.__version__:
        warnings.warn(f"Mô hình huấn luyện bằng scikit-learn {goi['phien_ban_sklearn']}, "
                      f"đang chạy {sklearn.__version__}: kết quả có thể sai hoặc lỗi khi dự đoán.")
    # Web chạy trên đường dẫn có dấu: tránh tạo tiến trình con
    if hasattr(goi["model"][-1], "n_jobs"):
        goi["model"][-1].n_jobs = 1
    return goi


def _chuan_bi(df_tho):
    if isinstance(df_tho, dict):
        df_tho = pd.DataFrame([df_tho])
    df = df_tho.copy()
    for c in ["source", "category_group", "category", "name", "brand", "volume", "origin"]:
        if c not in df:
            df[c] = np.nan
        df[c] = df[c].astype("object").where(df[c].notna(), np.nan)
    return lam_sach_co_ban(df)


def du_doan_gia(df_tho):
    goi = nap_mo_hinh("dinh_gia")
    df = _chuan_bi(df_tho)
    X = dac_trung_gia(df, goi["top_brands"])
    return pd.Series(np.exp(goi["model"].predict(X)), index=df.index, name="gia_du_doan")


def du_doan_het_hang(df_tho):
    """Hàng cận hạn [HSD] dùng quy tắc (tỷ lệ hết hàng thực tế), hàng thường dùng mô hình."""
    goi = nap_mo_hinh("het_hang")
    df = _chuan_bi(df_tho)
    for c in ["price_original", "discount_pct", "review_count"]:
        if c not in df or df[c].isna().any():
            raise ValueError(f"Thiếu cột '{c}' để dự đoán hết hàng")
    X = dac_trung_het_hang(df, goi["top_brands"])
    xs = goi["model"].predict_proba(X)[:, 1]
    can_han = df["is_hsd"].values == 1
    xs = np.where(can_han, goi["ty_le_het_hang_can_han"], xs)
    return pd.DataFrame({
        "xs_het_hang": xs,
        "du_doan_het_hang": xs >= goi["nguong"],
        "theo": np.where(can_han, "quy_tac_can_han", "mo_hinh"),
    }, index=df.index)


def thong_tin_mo_hinh():
    """Thông tin để web hiển thị (không gồm đối tượng mô hình)."""
    return {ten: {k: v for k, v in nap_mo_hinh(ten).items() if k not in ("model", "top_brands")}
            for ten in ["dinh_gia", "het_hang"]}


if __name__ == "__main__":
    vi_du = {"source": "hasaki", "category_group": "Chăm sóc da", "category": "Chăm sóc da mặt",
             "name": "Cây Nặn Mụn Suri Inox 2 Đầu - E493", "brand": "Suri", "volume": None, "origin": None,
             "price_original": 20000, "discount_pct": 10, "review_count": 3}
    print("Gia du doan:", round(du_doan_gia(vi_du).iloc[0], -3))
    print(du_doan_het_hang(vi_du))
