import os
import pandas as pd, numpy as np, joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import (train_test_split, cross_val_score, cross_val_predict,
                                     learning_curve, KFold)
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler, TargetEncoder
from sklearn.pipeline import Pipeline
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, r2_score
import sklearn
from datetime import datetime
from quy_tac import ghi_metrics, DATASET, SO_BRAND_TOP, NGUONG_Z_GIA, RANDOM_STATE
from dac_trung import dac_trung_gia, COT_GIA

P, F, B = DATASET, "figures/", "bieu_do/"
for d in ["models", F, B]:
    os.makedirs(d, exist_ok=True)
kf = KFold(5, shuffle=True, random_state=RANDOM_STATE)

df = pd.read_csv(P + "products_model.csv")
df = df[df.is_hsd == 0].copy()
top = df.brand.value_counts().index[:SO_BRAND_TOP].tolist()

# Đặc trưng tạo bằng dac_trung.py: web dùng đúng hàm này khi dự đoán
cat_cols = ["source", "category_group", "category", "brand_top", "unit", "origin", "loai_sp"]
num_cols = ["log_vol", "vol_missing", "is_combo", "is_mini", "log_sl"]
te_cols = ["brand_te"]
assert cat_cols + num_cols + te_cols == COT_GIA
X, y = dac_trung_gia(df, top), df["log_price_original"]
df["loai_sp"] = X["loai_sp"]
print(df.loai_sp.value_counts())
print("So san pham:", len(df))
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE)
print("Train:", len(X_train), "Test:", len(X_test))

# TargetEncoder: mỗi thương hiệu thành giá log trung bình (có co về trung bình chung,
# tự cross-fit bên trong nên không rò rỉ nhãn)
prep = ColumnTransformer([
    ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
    ("num", StandardScaler(), num_cols),
    ("te", TargetEncoder(cv=kf), te_cols),
])

models = {
    "Ridge": Ridge(alpha=1.0),
    "GradientBoosting": HistGradientBoostingRegressor(random_state=RANDOM_STATE),
    "RandomForest": RandomForestRegressor(n_estimators=300, min_samples_leaf=2,
                                          random_state=RANDOM_STATE, n_jobs=-1),
}

ket_qua, pipes = {}, {}
for name, m in models.items():
    pipe = Pipeline([("prep", prep), ("model", m)])
    cv = cross_val_score(pipe, X_train, y_train, scoring="r2", cv=kf)
    pipe.fit(X_train, y_train)
    pred = pipe.predict(X_test)
    r2_train = r2_score(y_train, pipe.predict(X_train))
    sai_lech_tv = np.median(np.abs(np.exp(pred) / np.exp(y_test) - 1)) * 100
    mae = mean_absolute_error(np.exp(y_test), np.exp(pred))
    ket_qua[name] = {"cv_r2": round(cv.mean(), 3), "train_r2": round(r2_train, 3),
                     "test_r2": round(r2_score(y_test, pred), 3), "mae": round(mae),
                     "sai_lech_trung_vi_pct": round(sai_lech_tv, 1)}
    pipes[name] = pipe
    print(f"\n{name}")
    print("  CV R2:", ket_qua[name]["cv_r2"], "| train R2:", ket_qua[name]["train_r2"],
          "| test R2:", ket_qua[name]["test_r2"])
    print("  MAE (d):", ket_qua[name]["mae"], "| sai lech trung vi (%):", ket_qua[name]["sai_lech_trung_vi_pct"])

# Chọn mô hình theo CV R2 (không dùng test để chọn)
best = max(ket_qua, key=lambda k: ket_qua[k]["cv_r2"])
pipe = pipes[best]
# Gói mô hình: kèm danh sách top_brands để web tạo lại đúng cột brand_top
joblib.dump({"model": pipe, "ten_mo_hinh": best, "top_brands": top, "cot_dau_vao": COT_GIA,
             "phien_ban_sklearn": sklearn.__version__, "huan_luyen_luc": datetime.now().isoformat(timespec="seconds"),
             "chi_so": ket_qua[best]},
            "models/model_dinh_gia.joblib", compress=3)
print(f"\nMo hinh tot nhat: {best} -> da luu models/model_dinh_gia.joblib")

# ===== Hình cho báo cáo (và dữ liệu để web tự vẽ) =====
pred = pipe.predict(X_test)
pd.DataFrame({"gia_that": np.exp(y_test).round(), "gia_du_doan": np.exp(pred).round(),
              "loai_sp": X_test["loai_sp"]}).to_csv(B + "dinh_gia_test.csv", index=False, encoding="utf-8-sig")
fig, ax = plt.subplots(figsize=(6, 6))
ax.scatter(np.exp(y_test), np.exp(pred), s=6, alpha=0.4)
lim = [np.exp(y).min(), np.exp(y).max()]
ax.plot(lim, lim, "r--", lw=1)
ax.set(xscale="log", yscale="log", xlabel="Giá thật (đ)", ylabel="Giá dự đoán (đ)",
       title=f"{best}: giá thật và giá dự đoán (tập test)")
fig.tight_layout(); fig.savefig(F + "dinh_gia_that_vs_doan.png", dpi=150); plt.close(fig)

pi = permutation_importance(pipe, X_test, y_test, scoring="r2", n_repeats=5,
                            random_state=RANDOM_STATE, n_jobs=-1)
imp = pd.Series(pi.importances_mean, index=X_test.columns).sort_values()
fig, ax = plt.subplots(figsize=(7, 5))
imp.plot.barh(ax=ax)
ax.set(xlabel="Mức giảm R² khi xáo trộn cột", title="Mức độ quan trọng của đặc trưng (định giá)")
fig.tight_layout(); fig.savefig(F + "dinh_gia_feature_importance.png", dpi=150); plt.close(fig)

sz, tr, va = learning_curve(pipe, X, y, train_sizes=[0.1, 0.2, 0.35, 0.5, 0.7, 0.85, 1.0],
                            cv=kf, scoring="r2", shuffle=True, random_state=RANDOM_STATE)
fig, ax = plt.subplots(figsize=(6, 4))
ax.plot(sz, tr.mean(1), "o-", label="Train")
ax.plot(sz, va.mean(1), "o-", label="Cross-validation")
ax.set(xlabel="Số mẫu huấn luyện", ylabel="R²", title="Đường cong học (định giá)")
ax.legend(); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(F + "dinh_gia_learning_curve.png", dpi=150); plt.close(fig)

# ===== Phần dư mô hình giá (cho Mô hình 4) =====
df["gia_du_doan"] = np.exp(cross_val_predict(pipe, X, y, cv=kf))
df["lech"] = np.log(df.price_original / df.gia_du_doan)
z = (df.lech - df.lech.mean()) / df.lech.std()
df["gia_bat_thuong"] = z.abs() > NGUONG_Z_GIA

ty_le = (df.gia_du_doan / df.price_original).groupby(df.loai_sp).median().sort_values()
ty_le.rename("ty_le_doan_that").to_csv(B + "dinh_gia_sai_lech_loai_sp.csv", encoding="utf-8-sig")
fig, ax = plt.subplots(figsize=(7, 6))
ty_le.plot.barh(ax=ax)
ax.axvline(1, color="r", ls="--", lw=1)
ax.set(xlabel="Giá dự đoán / giá thật (trung vị)", title="Sai lệch theo loại sản phẩm")
fig.tight_layout(); fig.savefig(F + "dinh_gia_sai_lech_loai_sp.png", dpi=150); plt.close(fig)
print("Da luu 4 hinh vao figures/")

print("\nSo san pham gia bat thuong:", df.gia_bat_thuong.sum())
print("  Dat hon du doan:", (df.gia_bat_thuong & (df.lech > 0)).sum())
print("  Re hon du doan :", (df.gia_bat_thuong & (df.lech < 0)).sum())

cot = ["source", "name", "brand", "loai_sp", "price_original", "gia_du_doan", "lech", "url"]
df[cot + ["gia_bat_thuong"]].to_csv(P + "gia_du_doan.csv", index=False, encoding="utf-8-sig")
df[df.gia_bat_thuong][cot].sort_values("lech").to_csv(
    P + "gia_bat_thuong.csv", index=False, encoding="utf-8-sig")
print("Da luu dataset/gia_du_doan.csv va dataset/gia_bat_thuong.csv")

ghi_metrics("dinh_gia", {
    "mo_hinh_chon": best, "so_mau": len(df), "cac_mo_hinh": ket_qua,
    "so_gia_bat_thuong": int(df.gia_bat_thuong.sum()), "nguong_z": NGUONG_Z_GIA,
    "feature_importance": imp.sort_values(ascending=False).round(4).to_dict(),
    "learning_curve": [{"so_mau": int(s), "train_r2": round(float(a), 3), "cv_r2": round(float(b), 3)}
                       for s, a, b in zip(sz, tr.mean(1), va.mean(1))],
})
