import os
import pandas as pd, numpy as np, joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import (train_test_split, cross_val_score, cross_val_predict,
                                     StratifiedKFold)
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler, TargetEncoder
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (classification_report, confusion_matrix, roc_auc_score,
                             precision_recall_curve, RocCurveDisplay, PrecisionRecallDisplay,
                             ConfusionMatrixDisplay)
import sklearn
from datetime import datetime
from sklearn.metrics import roc_curve
from quy_tac import ghi_metrics, DATASET, SO_BRAND_TOP, RANDOM_STATE
from dac_trung import dac_trung_het_hang, COT_HET_HANG

P, F, B = DATASET, "figures/", "bieu_do/"
RECALL_MUC_TIEU = 0.8
for d in ["models", F, B]:
    os.makedirs(d, exist_ok=True)
skf = StratifiedKFold(5, shuffle=True, random_state=RANDOM_STATE)

df = pd.read_csv(P + "products_model.csv")
h = df[df.source == "hasaki"].copy()
h["het_hang"] = 1 - h["in_stock"]
top = h.brand.value_counts().index[:SO_BRAND_TOP].tolist()
X_all = dac_trung_het_hang(h, top)        # dac_trung.py: web dùng đúng hàm này khi dự đoán

# Hàng cận hạn [HSD] gần như luôn hết (xả kho) -> tách riêng, không cho mô hình học
ty_le_hsd = h.groupby("is_hsd").het_hang.mean()
print("Ty le het hang: hang thuong", round(ty_le_hsd[0], 3), "| hang can han", round(ty_le_hsd[1], 3))

cat_cols = ["category_group", "brand_top", "unit", "origin"]
num_cols = ["log_price_original", "discount_pct", "log_reviews", "log_vol", "is_combo", "is_mini"]
te_cols = ["brand_te"]
assert cat_cols + num_cols + te_cols == COT_HET_HANG
prep = ColumnTransformer([
    ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
    ("num", StandardScaler(), num_cols),
    ("te", TargetEncoder(cv=skf), te_cols),
])

# Tham chiếu: AUC nếu để cả hàng cận hạn (như bản cũ) -> cao "ảo" nhờ is_hsd
ref = Pipeline([("prep", ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
        ("num", StandardScaler(), num_cols + ["is_hsd"])])),
    ("model", RandomForestClassifier(n_estimators=300, min_samples_leaf=3, class_weight="balanced",
                                     random_state=RANDOM_STATE, n_jobs=-1))])
auc_co_hsd = cross_val_score(ref, X_all.assign(is_hsd=h.is_hsd), h.het_hang,
                             scoring="roc_auc", cv=skf).mean()
print("CV AUC neu gom ca hang can han (tham chieu):", round(auc_co_hsd, 3))

hsd = h[h.is_hsd == 1]
h = h[h.is_hsd == 0]
print("So san pham Hasaki (hang thuong):", len(h), "| ty le het hang:", round(h.het_hang.mean(), 3))
X, y = X_all.loc[h.index], h["het_hang"]
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)

models = {
    "LogisticRegression": LogisticRegression(max_iter=2000, class_weight="balanced"),
    "GradientBoosting": HistGradientBoostingClassifier(class_weight="balanced",
                                                       random_state=RANDOM_STATE),
    "RandomForest": RandomForestClassifier(n_estimators=300, min_samples_leaf=3,
                                           class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1),
}

ket_qua, pipes = {}, {}
for name, m in models.items():
    pipe = Pipeline([("prep", prep), ("model", m)])
    cv = cross_val_score(pipe, X_train, y_train, scoring="roc_auc", cv=skf)
    pipe.fit(X_train, y_train)
    proba = pipe.predict_proba(X_test)[:, 1]
    ket_qua[name] = {"cv_auc": round(cv.mean(), 3), "test_auc": round(roc_auc_score(y_test, proba), 3)}
    pipes[name] = pipe
    print(f"{name:20s} CV AUC: {ket_qua[name]['cv_auc']} | test AUC: {ket_qua[name]['test_auc']}")

best = max(ket_qua, key=lambda k: ket_qua[k]["cv_auc"])
pipe = pipes[best]
print("\nMo hinh tot nhat:", best)

# Chọn ngưỡng trên dự đoán cross-validation của tập train (không nhìn tập test):
# ngưỡng cao nhất mà recall vẫn >= RECALL_MUC_TIEU
proba_cv = cross_val_predict(pipe, X_train, y_train, cv=skf, method="predict_proba")[:, 1]
pr, rc, th = precision_recall_curve(y_train, proba_cv)
nguong = float(th[rc[:-1] >= RECALL_MUC_TIEU].max())
print(f"Nguong chon: {nguong:.3f} (recall muc tieu {RECALL_MUC_TIEU})")

proba = pipe.predict_proba(X_test)[:, 1]
for ten, t in [("0.5", 0.5), ("da chon", nguong)]:
    pred = (proba >= t).astype(int)
    print(f"\n===== Test, nguong {ten} =====")
    print("Ma tran nham lan (hang = that, cot = doan; 0 = con hang, 1 = het hang):")
    print(confusion_matrix(y_test, pred))
    print(classification_report(y_test, pred, target_names=["Con hang", "Het hang"]))
bao_cao = classification_report(y_test, (proba >= nguong).astype(int), output_dict=True)
mtnl = confusion_matrix(y_test, (proba >= nguong).astype(int))

# Gói mô hình: kèm top_brands, ngưỡng và quy tắc cho hàng cận hạn
joblib.dump({"model": pipe, "ten_mo_hinh": best, "top_brands": top, "cot_dau_vao": COT_HET_HANG,
             "nguong": nguong, "ty_le_het_hang_can_han": float(ty_le_hsd[1]),
             "phien_ban_sklearn": sklearn.__version__, "huan_luyen_luc": datetime.now().isoformat(timespec="seconds"),
             "chi_so": ket_qua[best]},
            "models/model_het_hang.joblib", compress=3)
print(f"Da luu models/model_het_hang.joblib ({best})")

# Xác suất hết hàng cho từng sản phẩm Hasaki: hàng thường lấy dự đoán out-of-fold
# (mỗi sản phẩm được đoán bởi mô hình KHÔNG học nó), hàng cận hạn theo quy tắc
oof = cross_val_predict(pipe, X, y, cv=skf, method="predict_proba")[:, 1]
xs = pd.concat([
    pd.DataFrame({"url": h.url, "xs_het_hang": oof.round(4), "theo": "mo_hinh"}),
    pd.DataFrame({"url": hsd.url, "xs_het_hang": round(float(ty_le_hsd[1]), 4), "theo": "quy_tac_can_han"}),
])
xs["du_doan_het_hang"] = xs.xs_het_hang >= nguong
xs.to_csv(P + "het_hang_du_doan.csv", index=False, encoding="utf-8-sig")
print("Da luu dataset/het_hang_du_doan.csv:", len(xs), "san pham")

fpr, tpr, _ = roc_curve(y_test, proba)
pr_t, rc_t, _ = precision_recall_curve(y_test, proba)
lay = lambda n: np.unique(np.linspace(0, n - 1, min(n, 200)).astype(int))   # tối đa 200 điểm
pd.concat([
    pd.DataFrame({"duong": "ROC", "x": fpr, "y": tpr}).iloc[lay(len(fpr))],
    pd.DataFrame({"duong": "PR", "x": rc_t, "y": pr_t}).iloc[lay(len(rc_t))],
]).round(4).to_csv(B + "het_hang_roc_pr.csv", index=False, encoding="utf-8-sig")

# ===== Hình cho báo cáo =====
fig, ax = plt.subplots(1, 3, figsize=(15, 4.5))
ConfusionMatrixDisplay.from_predictions(y_test, (proba >= nguong).astype(int), ax=ax[0],
                                        display_labels=["Còn hàng", "Hết hàng"], colorbar=False)
ax[0].set_title(f"Ma trận nhầm lẫn (ngưỡng {nguong:.2f})")
RocCurveDisplay.from_predictions(y_test, proba, ax=ax[1], name=best)
ax[1].set_title("ROC (tập test)")
PrecisionRecallDisplay.from_predictions(y_test, proba, ax=ax[2], name=best)
ax[2].set_title("Precision–Recall (tập test)")
fig.tight_layout(); fig.savefig(F + "het_hang_danh_gia.png", dpi=150); plt.close(fig)

pi = permutation_importance(pipe, X_test, y_test, scoring="roc_auc", n_repeats=5,
                            random_state=RANDOM_STATE, n_jobs=-1)
imp = pd.Series(pi.importances_mean, index=X_test.columns).sort_values()
print("\nMuc do quan trong (giam AUC khi xao tron cot):")
print(imp.sort_values(ascending=False).round(3))
fig, ax = plt.subplots(figsize=(7, 4.5))
imp.plot.barh(ax=ax)
ax.set(xlabel="Mức giảm AUC khi xáo trộn cột", title="Mức độ quan trọng của đặc trưng (hết hàng)")
fig.tight_layout(); fig.savefig(F + "het_hang_feature_importance.png", dpi=150); plt.close(fig)
print("Da luu 2 hinh vao figures/")

ghi_metrics("het_hang", {
    "mo_hinh_chon": best, "so_mau": len(h), "cac_mo_hinh": ket_qua,
    "cv_auc_neu_gom_hang_can_han": round(auc_co_hsd, 3),
    "ty_le_het_hang_can_han": round(float(ty_le_hsd[1]), 3),
    "nguong": round(nguong, 3),
    "test_tai_nguong": {"precision": round(bao_cao["1"]["precision"], 3),
                        "recall": round(bao_cao["1"]["recall"], 3),
                        "f1": round(bao_cao["1"]["f1-score"], 3)},
    "ma_tran_nham_lan": {"nhan": ["Còn hàng", "Hết hàng"], "gia_tri": mtnl.tolist()},
    "feature_importance": imp.sort_values(ascending=False).round(4).to_dict(),
})
