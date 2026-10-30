import os
import pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN
from sklearn.metrics import silhouette_score, davies_bouldin_score, adjusted_rand_score
from quy_tac import ghi_metrics, DATASET, RANDOM_STATE

P, F = DATASET, "figures/"
os.makedirs(F, exist_ok=True)
os.makedirs("bieu_do", exist_ok=True)    
pd.set_option("display.width", 250)

df = pd.read_csv(P + "products_model.csv")

# Phân cụm riêng từng sàn: hai sàn khác nhau về chính sách giảm giá, số đánh giá và tỷ lệ hết hàng
# Cocolux gần như không có hàng hết (99,97% còn hàng) nên bỏ đặc trưng het_hang.
SAN = {
    "hasaki": {"K": 4, "loc": (df.source == "hasaki") & (df.is_hsd == 0), "dung_het_hang": True},
    "cocolux": {"K": 4, "loc": df.source == "cocolux", "dung_het_hang": False},
}

MO_TA = {"log_so_sp": ("ít sản phẩm", "nhiều sản phẩm"), "log_gia": ("giá rẻ", "giá cao"),
         "giam_gia": ("ít giảm giá", "giảm giá sâu"), "het_hang": ("ít hết hàng", "hay hết hàng"),
         "log_danh_gia": ("ít đánh giá", "nhiều đánh giá"), "combo": ("ít combo", "nhiều combo")}


def phan_cum(san, cfg):
    K, ten_san = cfg["K"], san.capitalize()
    print(f"\n{'#' * 20} {ten_san} {'#' * 20}")
    h = df[cfg["loc"]]

    # 1. Gộp theo thương hiệu
    brand = h.groupby("brand").agg(
        so_san_pham=("name", "size"),
        gia_tb=("price_original", "median"),
        giam_gia_tb=("discount_pct", "mean"),
        ti_le_het_hang=("in_stock", lambda s: 1 - s.mean()),
        danh_gia_tb=("review_count", "mean"),
        ti_le_combo=("is_combo", "mean"),
    )
    brand = brand[brand.so_san_pham >= 5].copy()
    print("So thuong hieu:", len(brand))

    # 2. Log và chuẩn hóa
    X = pd.DataFrame({
        "log_so_sp": np.log(brand.so_san_pham), "log_gia": np.log(brand.gia_tb),
        "giam_gia": brand.giam_gia_tb, "het_hang": brand.ti_le_het_hang,
        "log_danh_gia": np.log1p(brand.danh_gia_tb), "combo": brand.ti_le_combo,
    }, index=brand.index)
    if not cfg["dung_het_hang"]:
        X = X.drop(columns="het_hang")
    Xs = StandardScaler().fit_transform(X)

    # 3. Chọn K
    print("\nK, inertia, silhouette, davies-bouldin")
    chon_k = []
    for k in range(2, 9):
        km = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE).fit(Xs)
        chon_k.append((k, km.inertia_, silhouette_score(Xs, km.labels_), davies_bouldin_score(Xs, km.labels_)))
        print(k, round(km.inertia_, 1), round(chon_k[-1][2], 3), round(chon_k[-1][3], 3))
    ck = pd.DataFrame(chon_k, columns=["k", "inertia", "silhouette", "davies_bouldin"])

    fig, ax = plt.subplots(1, 3, figsize=(14, 3.8))
    for a, c, t in zip(ax, ["inertia", "silhouette", "davies_bouldin"],
                       ["Elbow (inertia, thấp hơn tốt hơn)", "Silhouette (cao hơn tốt hơn)",
                        "Davies-Bouldin (thấp hơn tốt hơn)"]):
        a.plot(ck.k, ck[c], "o-"); a.axvline(K, color="r", ls="--", lw=1)
        a.set(xlabel="K", title=t); a.grid(alpha=0.3)
    fig.suptitle(f"Chọn K - {ten_san}")
    fig.tight_layout(); fig.savefig(F + f"phan_cum_{san}_chon_k.png", dpi=150); plt.close(fig)

    # 4. Chạy K-Means
    km = KMeans(n_clusters=K, n_init=10, random_state=RANDOM_STATE).fit(Xs)
    brand["cum"] = km.labels_

    # Đặt tên cụm tự động từ tâm cụm (đã chuẩn hóa): 2 đặc điểm lệch khỏi trung bình nhiều nhất
    tam = pd.DataFrame(km.cluster_centers_, columns=X.columns)
    ten_cum = {}
    for c, r in tam.iterrows():
        noi_bat = r.abs().sort_values(ascending=False).index[:2]
        ten_cum[c] = ", ".join(MO_TA[f][int(r[f] > 0)] for f in noi_bat).capitalize()
    # Hai cụm trùng tên (cùng 2 đặc điểm nổi bật) thì thêm số cụm để không lẫn khi groupby / vẽ
    trung = pd.Series(ten_cum).duplicated(keep=False)
    ten_cum = {c: f"{t} (cụm {c})" if trung[c] else t for c, t in ten_cum.items()}
    brand["ten_cum"] = brand.cum.map(ten_cum)

    print("\nSo thuong hieu moi cum:")
    print(brand.ten_cum.value_counts())
    print("\nTrung vi moi cum:")
    ho_so = brand.groupby("ten_cum").median(numeric_only=True).drop(columns="cum").round(3)
    print(ho_so.to_string())
    print("\nVi du thuong hieu (nhieu san pham nhat) moi cum:")
    vi_du = brand.sort_values("so_san_pham", ascending=False).groupby("ten_cum").head(5)
    for t, g in vi_du.groupby("ten_cum"):
        print(f"  {t}: {', '.join(g.index)}")

    # Hình: PCA 2D và heatmap tâm cụm
    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    Z = pca.fit_transform(Xs)
    pd.DataFrame({"brand": brand.index, "pc1": Z[:, 0].round(4), "pc2": Z[:, 1].round(4),
                  "ten_cum": brand.ten_cum.values, "so_san_pham": brand.so_san_pham.values}).to_csv(
        f"bieu_do/phan_cum_{san}_pca.csv", index=False, encoding="utf-8-sig")
    tam.round(3).assign(ten_cum=[ten_cum[c] for c in tam.index]).to_csv(
        f"bieu_do/phan_cum_{san}_ho_so.csv", index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(9, 6.5))
    for c in range(K):
        m = km.labels_ == c
        ax.scatter(Z[m, 0], Z[m, 1], s=18, alpha=0.7, label=ten_cum[c])
    for b in vi_du.groupby("ten_cum").head(2).index:
        i = brand.index.get_loc(b)
        ax.annotate(b, Z[i], fontsize=8, xytext=(3, 3), textcoords="offset points")
    ax.set(xlabel=f"PC1 ({pca.explained_variance_ratio_[0]:.0%})",
           ylabel=f"PC2 ({pca.explained_variance_ratio_[1]:.0%})",
           title=f"Phân cụm thương hiệu {ten_san} (K-Means, K={K}) trên mặt phẳng PCA")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(F + f"phan_cum_{san}_pca.png", dpi=150); plt.close(fig)

    tam.index = [ten_cum[c] for c in tam.index]
    fig, ax = plt.subplots(figsize=(9, 3.5))
    im = ax.imshow(tam.values, cmap="RdBu_r", vmin=-2, vmax=2, aspect="auto")
    ax.set_xticks(range(len(tam.columns)), tam.columns, rotation=20)
    ax.set_yticks(range(len(tam)), tam.index)
    for i in range(tam.shape[0]):
        for j in range(tam.shape[1]):
            ax.text(j, i, f"{tam.iat[i, j]:.1f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label="Độ lệch chuẩn so với trung bình")
    ax.set_title(f"Hồ sơ từng cụm - {ten_san} (tâm cụm đã chuẩn hóa)")
    fig.tight_layout(); fig.savefig(F + f"phan_cum_{san}_ho_so.png", dpi=150); plt.close(fig)
    print("\nDa luu 3 hinh vao figures/")

    # 5. So sánh Hierarchical và DBSCAN
    agg = AgglomerativeClustering(n_clusters=K, linkage="ward").fit(Xs)
    print("\nK-Means (hang) so voi Hierarchical (cot):")
    print(pd.crosstab(km.labels_, agg.labels_))
    ari = adjusted_rand_score(km.labels_, agg.labels_)
    sil_km, sil_agg = silhouette_score(Xs, km.labels_), silhouette_score(Xs, agg.labels_)
    print("Silhouette K-Means:", round(sil_km, 3), "| Hierarchical:", round(sil_agg, 3),
          "| ARI giua 2 cach:", round(ari, 3))

    db = DBSCAN(eps=1.3, min_samples=5).fit(Xs)
    print("\nDBSCAN (-1 la nhieu):")
    print(pd.Series(db.labels_).value_counts())

    # 6. Xuất file
    brand.to_csv(P + f"phan_cum_thuong_hieu_{san}.csv", encoding="utf-8-sig")
    print(f"\nXong, da luu {P}phan_cum_thuong_hieu_{san}.csv")
    return {
        "so_thuong_hieu": len(brand), "k": K, "dac_trung": list(X.columns),
        "silhouette_kmeans": round(sil_km, 3),
        "silhouette_hierarchical": round(sil_agg, 3), "ari_kmeans_hierarchical": round(ari, 3),
        "dbscan_nhieu": int((db.labels_ == -1).sum()),
        "cum": {t: int(n) for t, n in brand.ten_cum.value_counts().items()},
        "chon_k": ck.round(3).to_dict(orient="records"),
    }


ghi_metrics("phan_cum", {san: phan_cum(san, cfg) for san, cfg in SAN.items()})
