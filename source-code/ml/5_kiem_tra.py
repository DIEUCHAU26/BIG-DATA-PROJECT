import pandas as pd
from quy_tac import DATASET
a = pd.read_csv(DATASET + "gia_bat_thuong.csv")
print("Tong so bi gan co:", len(a))
print("Mat na      :", a.name.str.contains("mặt nạ", case=False).sum())
print("Bang ve sinh:", a.name.str.contains("băng vệ sinh", case=False).sum())
print("\nSo lan lap lai cua cung 1 gia du doan:")
print(a.gia_du_doan.round().value_counts().head(8))