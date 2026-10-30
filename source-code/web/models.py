
import compat

compat.patch_threadpoolctl()  
import numpy as np 
import pandas as pd 
import streamlit as st
from sklearn.cluster import KMeans 
from sklearn.compose import ColumnTransformer 
from sklearn.ensemble import IsolationForest, RandomForestRegressor 
from sklearn.linear_model import Ridge 
from sklearn.metrics import mean_absolute_error, r2_score, silhouette_score 
from sklearn.model_selection import train_test_split 
from sklearn.pipeline import Pipeline 
from sklearn.preprocessing import OneHotEncoder, StandardScaler 

FEATURES = {
    "Giá bán": ("price", True),
    "Giá niêm yết": ("price_original", True),
    "Mức giảm giá": ("discount_pct", False),
    "Lượt đánh giá": ("review_count", True),
    "Dung tích": ("dung_tich", True),
}


def _matrix(df, names):
    """Bảng số đã lấy log (cho cột lệch phải như giá) và điền giá trị thiếu bằng trung vị."""
    cols = {}
    for n in names:
        col, use_log = FEATURES[n]
        s = df[col].astype(float)
        s = s.replace([np.inf, -np.inf], np.nan)
        s = s.fillna(s.median() if s.notna().any() else 0.0)
        cols[n] = np.log1p(s.clip(lower=0)) if use_log else s
    return pd.DataFrame(cols, index=df.index)


# ============================ 1. PHÂN CỤM ============================
@st.cache_data(max_entries=8, show_spinner=False)
def run_kmeans(df, names, k):
    """Trả về (nhãn cụm 0..k-1, điểm silhouette, inertia)."""
    X = StandardScaler().fit_transform(_matrix(df, names))
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    sil = float("nan")
    if 1 < len(np.unique(km.labels_)) < len(X):
        try:
            sil = silhouette_score(X, km.labels_, sample_size=min(3000, len(X)), random_state=42)
        except ValueError:
            pass
    return km.labels_, float(sil), float(km.inertia_)


@st.cache_data(max_entries=8, show_spinner=False)
def elbow(df, names, ks=range(2, 9)):
    X = StandardScaler().fit_transform(_matrix(df, names))
    return {k: float(KMeans(n_clusters=k, n_init=5, random_state=42).fit(X).inertia_) for k in ks}


# ============================ 2. DỰ ĐOÁN GIÁ NIÊM YẾT ============================
CAT_FEATURES = ["source", "category_group", "category", "brand_top", "xuat_xu"]
NUM_FEATURES = ["dung_tich", "la_combo", "la_mini"]
TOP_BRANDS = 40


def _prepare_price_frame(df, top_brands):
    d = pd.DataFrame(index=df.index)
    d["source"] = df["source"].fillna("")
    d["category_group"] = df["category_group"].fillna("")
    d["category"] = df["category"].fillna("")
    d["brand_top"] = df["brand"].where(df["brand"].isin(top_brands), "Khác").fillna("Khác")
    d["xuat_xu"] = df["xuat_xu"].fillna("Không rõ")
    d["dung_tich"] = np.log1p(df["dung_tich"].astype(float))  # thiếu thì để NaN rồi điền trung vị trong pipeline
    ten = df["name"].fillna("").str.lower()
    d["la_combo"] = ten.str.contains(r"combo|\bset\b|bộ |\bkit\b|\+", regex=True).astype(float)
    d["la_mini"] = ten.str.contains(r"mini|travel|sample|dùng thử", regex=True).astype(float)
    return d


def train_price_model(df, kind="forest"):
    """Dự đoán GIÁ NIÊM YẾT từ nguồn, ngành hàng, thương hiệu, xuất xứ, dung tích.

    Dùng log(giá) làm mục tiêu vì giá lệch phải rất mạnh (từ vài chục nghìn đến vài triệu).
    Trả về dict gồm mô hình, các chỉ số trên tập kiểm tra (20%), độ quan trọng đặc trưng...
    """
    df = df[df["price_original"] > 0]
    if len(df) < 10:
        raise ValueError("Cần ít nhất 10 sản phẩm có giá niêm yết hợp lệ")
    train_index, test_index = train_test_split(df.index, test_size=0.2, random_state=42)
    top_brands = df.loc[train_index, "brand"].value_counts().head(TOP_BRANDS).index.tolist()
    X = _prepare_price_frame(df, top_brands)
    y = np.log1p(df["price_original"].astype(float))
    X_tr, X_te, y_tr, y_te = X.loc[train_index], X.loc[test_index], y.loc[train_index], y.loc[test_index]

    from sklearn.impute import SimpleImputer

    pre = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
            ("num", Pipeline([("fill", SimpleImputer(strategy="median", keep_empty_features=True)), ("sc", StandardScaler())]), NUM_FEATURES),
        ]
    )
    if kind == "forest":
        # n_jobs=1: tránh tạo tiến trình con (hay lỗi trên Windows khi đường dẫn có dấu)
        reg = RandomForestRegressor(n_estimators=120, min_samples_leaf=2, max_depth=22, random_state=42, n_jobs=1)
    else:
        reg = Ridge(alpha=1.0)
    model = Pipeline([("pre", pre), ("reg", reg)]).fit(X_tr, y_tr)

    pred_log = model.predict(X_te)
    actual, pred = np.expm1(y_te.values), np.expm1(pred_log)
    metrics = {
        "r2_log": float(r2_score(y_te, pred_log)),
        "mae": float(mean_absolute_error(actual, pred)),
        "mape_median": float(np.median(np.abs(pred - actual) / actual) * 100),
        "n_train": len(X_tr),
        "n_test": len(X_te),
    }

    importance = None
    if kind == "forest":
        ohe = model.named_steps["pre"].named_transformers_["cat"]
        sizes = [len(c) for c in ohe.categories_] + [1] * len(NUM_FEATURES)
        names = CAT_FEATURES + NUM_FEATURES
        raw = model.named_steps["reg"].feature_importances_
        edges = np.cumsum([0] + sizes)
        importance = pd.Series(
            {names[i]: float(raw[edges[i]:edges[i + 1]].sum()) for i in range(len(names))}
        ).sort_values(ascending=False)

    test = pd.DataFrame({"Thực tế": actual, "Dự đoán": pred})
    return {
        "model": model,
        "top_brands": top_brands,
        "metrics": metrics,
        "importance": importance,
        "test": test,
        "kind": kind,
    }


def predict_price(bundle, source, category_group, category, brand, xuat_xu, dung_tich, la_combo=False, la_mini=False):
    row = pd.DataFrame(
        [{
            "source": source,
            "category_group": category_group,
            "category": category,
            "brand_top": brand if brand in bundle["top_brands"] else "Khác",
            "xuat_xu": xuat_xu or "Không rõ",
            "dung_tich": np.log1p(dung_tich) if dung_tich and dung_tich > 0 else np.nan,
            "la_combo": float(la_combo),
            "la_mini": float(la_mini),
        }]
    )
    return float(np.expm1(bundle["model"].predict(row)[0]))


# ============================ 3. PHÁT HIỆN BẤT THƯỜNG ============================
ANOMALY_FEATURES = ["Giá bán", "Giá niêm yết", "Mức giảm giá", "Lượt đánh giá"]
@st.cache_data(max_entries=8, show_spinner=False)
def detect_anomalies(df, contamination):
    """Isolation Forest. Thêm cột 'diem' (càng thấp càng bất thường), 'bat_thuong' và 'ly_do'."""
    M = _matrix(df, ANOMALY_FEATURES)
    X = StandardScaler().fit_transform(M)
    forest = IsolationForest(contamination=contamination, random_state=42, n_jobs=1).fit(X)
    out = df.copy()
    out["diem"] = forest.score_samples(X).round(4)
    out["bat_thuong"] = forest.predict(X) == -1
    z = (M - M.median()) / M.std().replace(0, 1)
    top = z.abs().idxmax(axis=1)
    huong = np.where(z.values[np.arange(len(z)), [M.columns.get_loc(c) for c in top]] > 0, "cao", "thấp")
    out["ly_do"] = [f"{t} {h} bất thường" for t, h in zip(top, huong)]
    return out
