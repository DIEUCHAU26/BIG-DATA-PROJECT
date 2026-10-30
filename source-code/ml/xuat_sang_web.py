# Ghép kết quả các mô hình thành 1 bảng cho web: dataset/ml/san_pham_ml.csv (mỗi sản phẩm 1 dòng, khóa là url).
#   python xuat_sang_web.py
# Chạy SAU các bước 0-5 của chay_tat_ca.py. Web (source-code/web/ml_pages.py) đọc thẳng
# source-code/ml/ (mô hình, biểu đồ, metrics) và dataset/ml/ (bảng kết quả), không cần chép file.
import os
import pandas as pd
from quy_tac import gan_loai_sp, DATASET

os.chdir(os.path.dirname(os.path.abspath(__file__)))
P = DATASET

sp = pd.read_csv(P + "products_model.csv", usecols=["url", "source", "name", "price_original", "is_hsd"])
sp["loai_sp"] = gan_loai_sp(sp["name"])
gia = pd.read_csv(P + "gia_du_doan.csv", usecols=["url", "gia_du_doan", "lech", "gia_bat_thuong"])
hh = pd.read_csv(P + "het_hang_du_doan.csv")
bt = pd.read_csv(P + "anomalies.csv", usecols=["url", "iqr", "iso", "iso_score", "lof", "so_phuong_phap"])
kq = sp.merge(gia, on="url", how="left").merge(hh, on="url", how="left").merge(bt, on="url", how="left")
# Hàng cận hạn không có trong tập huấn luyện giá -> dự đoán trực tiếp ("giá gốc nên có")
kq["gia_theo"] = "out_of_fold"
thieu = kq.gia_du_doan.isna()
if thieu.any():
    from du_doan import du_doan_gia
    tho = pd.read_csv(P + "products_model.csv").set_index("url").loc[kq.url[thieu]].reset_index()
    kq.loc[thieu, "gia_du_doan"] = du_doan_gia(tho).values
    kq.loc[thieu, "gia_theo"] = "du_doan_truc_tiep"
kq["chenh_lech_pct"] = ((kq.price_original / kq.gia_du_doan - 1) * 100).round(1)
kq["gia_du_doan"] = kq.gia_du_doan.round(-3)
# Bỏ các cột web đã có, tránh trùng tên khi ghép
kq = kq.drop(columns=["name", "price_original", "source"]).rename(columns={"theo": "het_hang_theo"})
assert kq.url.is_unique
kq.to_csv(P + "san_pham_ml.csv", index=False, encoding="utf-8-sig")

print("Da tao", P + "san_pham_ml.csv")
print("san_pham_ml.csv:", len(kq), "dong |", "co gia du doan:", kq.gia_du_doan.notna().sum(),
      "| co xs het hang:", kq.xs_het_hang.notna().sum(), "| co diem bat thuong:", kq.so_phuong_phap.notna().sum())
