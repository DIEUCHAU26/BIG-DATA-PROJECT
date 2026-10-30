import pandas as pd, numpy as np
from quy_tac import DATASET

df = pd.read_excel(DATASET + "products_clean.xlsx")
df = df.drop_duplicates(subset=["source", "name"])      # bỏ tên trùng (còn 12 dòng)

# lít -> ml để cùng thang với các sản phẩm khác
df["vol"]  = df["volume_value"] * df["volume_unit"].map({"l": 1000}).fillna(1)
df["unit"] = df["volume_unit"].replace({"l": "ml"}).fillna("khong_ro")

# Cờ 0/1 lấy từ tên sản phẩm
df["is_hsd"]   = df["name"].str.contains(r"\[HSD", regex=True).astype(int)
df["is_combo"] = df["name"].str.contains(r"(?i)combo|^bộ ", regex=True).astype(int)
df["is_mini"]  = df["name"].str.contains(r"(?i)\[mini\]", regex=True).astype(int)
df.loc[df["is_combo"] == 1, "vol"] = np.nan             # combo: dung tích không so sánh được

# Các cột dẫn xuất
df["price_per_unit"]     = df["price"] / df["vol"]      # giá trên 1 ml hoặc 1 g
df["has_reviews"]        = (df["review_count"] > 0).astype(int)
df["log_price"]          = np.log(df["price"])
df["log_price_original"] = np.log(df["price_original"])
df["log_reviews"]        = np.log1p(df["review_count"])

df.to_csv(DATASET + "products_model.csv", index=False, encoding="utf-8-sig")
print(df.shape)
