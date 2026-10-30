# Kiểm tra du_doan.py: dự đoán từ dữ liệu THÔ (như web gửi vào) phải khớp với
# dự đoán từ dữ liệu huấn luyện (products_model.csv). Chạy sau mỗi lần huấn luyện lại.
import numpy as np, pandas as pd
from du_doan import du_doan_gia, du_doan_het_hang, nap_mo_hinh
from dac_trung import dac_trung_gia, dac_trung_het_hang
from quy_tac import DATASET

tho = pd.read_excel(DATASET + "products_clean.xlsx").drop(columns=["volume_value", "volume_unit"])  # như web: chỉ có 'volume'
tho = tho.drop_duplicates(subset=["source", "name"]).reset_index(drop=True)   # giống 0_lam_sach.py
mau = pd.read_csv(DATASET + "products_model.csv")
assert (tho.url.values == mau.url.values).all()

# 1. Giá
goi = nap_mo_hinh("dinh_gia")
a = du_doan_gia(tho).values
b = np.exp(goi["model"].predict(dac_trung_gia(mau, goi["top_brands"])))
print("Dinh gia : khop", np.isclose(a, b).mean() * 100, "% tren", len(a), "san pham")

# 2. Hết hàng (Hasaki)
goi = nap_mo_hinh("het_hang")
h = mau.source == "hasaki"
a = du_doan_het_hang(tho[h]).xs_het_hang.values
b = goi["model"].predict_proba(dac_trung_het_hang(mau[h], goi["top_brands"]))[:, 1]
b = np.where(mau[h].is_hsd == 1, goi["ty_le_het_hang_can_han"], b)
print("Het hang : khop", np.isclose(a, b).mean() * 100, "% tren", len(a), "san pham")

# 3. Một dòng dạng dict, thiếu dung tích / xuất xứ (như form trên web)
print(du_doan_gia({"source": "hasaki", "category_group": "Chăm sóc da", "category": "Chăm sóc da mặt",
                   "name": "Cây Nặn Mụn Suri Inox 2 Đầu", "brand": "Suri"}).round(-3).iloc[0])
