import os
import pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from quy_tac import ghi_metrics, DATASET, CONTAMINATION, RANDOM_STATE

P, F = DATASET, "figures/"
os.makedirs(F, exist_ok=True)
pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 60)

df = pd.read_csv(P + "products_model.csv")
# Bỏ hàng cận hạn: giảm 95-99% là xả kho thật, không phải bất thường
df = df[df.is_hsd == 0]
# Phần dư mô hình giá (từ 2_dinh_gia.py): giá cao/thấp hơn mức "nên có"
g = pd.read_csv(P + "gia_du_doan.csv")[["source", "name", "gia_du_doan", "lech"]]
df = df.merge(g, on=["source", "name"], how="left")

d = df[df.price_per_unit.notna() & df.lech.notna()].copy()
d["log_ppu"] = np.log(d.price_per_unit)
print("So san pham (hang thuong, co gia tren don vi):", len(d))

# 1. IQR theo nhóm hàng và đơn vị
def iqr_flag(s):
    q1, q3 = s.quantile([0.25, 0.75]); k = 1.5 * (q3 - q1)
    return (s < q1 - k) | (s > q3 + k)

d["iqr_gia"]  = d.groupby(["category_group", "unit"])["log_ppu"].transform(iqr_flag)
d["iqr_giam"] = d.groupby("source")["discount_pct"].transform(iqr_flag)
d["iqr"] = d.iqr_gia | d.iqr_giam

# 2. Isolation Forest và 3. LOF
feats = ["log_ppu", "discount_pct", "log_reviews", "lech"]
Xs = StandardScaler().fit_transform(d[feats])

iso = IsolationForest(n_estimators=300, contamination=CONTAMINATION, random_state=RANDOM_STATE).fit(Xs)
d["iso"] = iso.predict(Xs) == -1
d["iso_score"] = -iso.score_samples(Xs)

d["lof"] = LocalOutlierFactor(n_neighbors=20, contamination=CONTAMINATION).fit_predict(Xs) == -1

# Số phương pháp cùng gắn cờ: >= 2 là "bất thường chắc chắn"
d["so_phuong_phap"] = d[["iqr", "iso", "lof"]].sum(axis=1)

print("\nSo san pham bi gan co:")
print("  IQR (gia hoac muc giam):", d.iqr.sum())
print("  Isolation Forest       :", d.iso.sum())
print("  LOF                    :", d.lof.sum())
print("  Iso va LOF trung nhau  :", (d.iso & d.lof).sum())
print("  >= 2 phuong phap       :", (d.so_phuong_phap >= 2).sum())
print("  Ca 3 phuong phap       :", (d.so_phuong_phap == 3).sum())

cot_xem = ["source", "name", "price", "price_original", "gia_du_doan", "discount_pct", "so_phuong_phap"]
print("\nTop 10 bat thuong theo Isolation Forest:")
top10 = d[d.iso].sort_values("iso_score", ascending=False).head(10)
print(top10[cot_xem].round(0).to_string())

# File để kiểm tra thủ công: mở URL rồi điền cột ket_luan (loi_du_lieu / gia_la_that / bao_nham)
top10[cot_xem + ["url"]].assign(ket_luan="", ghi_chu="").to_csv(
    P + "kiem_tra_thu_cong.csv", index=False, encoding="utf-8-sig")

cot = ["source", "brand", "category_group", "name", "price", "price_original", "gia_du_doan",
       "lech", "discount_pct", "review_count", "price_per_unit", "iqr", "iso", "iso_score", "lof",
       "so_phuong_phap", "url"]
d[cot].to_csv(P + "anomalies.csv", index=False, encoding="utf-8-sig")
print("\nDa luu dataset/anomalies.csv va dataset/kiem_tra_thu_cong.csv")

# ===== Hình cho báo cáo =====
to_hop = d[["iqr", "iso", "lof"]].apply(
    lambda r: " + ".join(k.upper() for k in ["iqr", "iso", "lof"] if r[k]), axis=1)
dem = to_hop[to_hop != ""].value_counts().sort_values()
fig, ax = plt.subplots(figsize=(7, 4))
dem.plot.barh(ax=ax)
ax.set(xlabel="Số sản phẩm", title="Sản phẩm bị gắn cờ theo tổ hợp phương pháp")
fig.tight_layout(); fig.savefig(F + "bat_thuong_to_hop.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
ax[0].hist(d.iso_score, bins=60)
ax[0].axvline(d[d.iso].iso_score.min(), color="r", ls="--", label="Ngưỡng Isolation Forest")
ax[0].set(xlabel="Điểm bất thường", ylabel="Số sản phẩm", title="Phân bố điểm Isolation Forest")
ax[0].legend()
thuong = d[d.so_phuong_phap == 0]
ax[1].scatter(thuong.discount_pct, thuong.log_ppu, s=4, alpha=0.25, c="grey", label="Bình thường")
for n, mau in [(1, "orange"), (2, "red"), (3, "darkred")]:
    s = d[d.so_phuong_phap == n]
    ax[1].scatter(s.discount_pct, s.log_ppu, s=12, c=mau, label=f"{n} phương pháp")
ax[1].set(xlabel="Mức giảm giá (%)", ylabel="log(giá / ml hoặc g)", title="Sản phẩm bị gắn cờ")
ax[1].legend(fontsize=8)
fig.tight_layout(); fig.savefig(F + "bat_thuong_phan_bo.png", dpi=150); plt.close(fig)
print("Da luu 2 hinh vao figures/")

ghi_metrics("bat_thuong", {
    "so_mau": len(d), "dac_trung": feats, "contamination": CONTAMINATION,
    "so_gan_co": {"iqr": int(d.iqr.sum()), "iso": int(d.iso.sum()), "lof": int(d.lof.sum()),
                  "tu_2_phuong_phap": int((d.so_phuong_phap >= 2).sum()),
                  "ca_3": int((d.so_phuong_phap == 3).sum())},
})
