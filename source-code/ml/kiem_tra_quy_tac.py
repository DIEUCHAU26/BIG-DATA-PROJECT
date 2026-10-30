# Chạy sau mỗi lần sửa quy_tac.py: xem mẫu tên trong từng nhóm để phát hiện bắt nhầm
import sys
import pandas as pd
from quy_tac import gan_loai_sp, DATASET

pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 90)

df = pd.read_csv(DATASET + "products_model.csv")
df = df[df.is_hsd == 0].copy()
df["loai_sp"] = gan_loai_sp(df["name"])

nhom = sys.argv[1:] or sorted(df.loai_sp.unique())
print(df.loai_sp.value_counts(), "\n")
for l in nhom:
    d = df[df.loai_sp == l]
    print(f"===== {l} ({len(d)}) =====")
    print(d.sample(min(5, len(d)), random_state=0)[["name", "price_original"]].to_string(), "\n")
