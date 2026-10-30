"""6 trang dashboard dựng lại theo báo cáo Power BI của nhóm (file CK.pbix).

  1. Tổng quan thị trường        4. Thương hiệu và xuất xứ
  2. Thống kê & Min-Max          5. Giá và khuyến mãi
  3. So sánh Hasaki – Cocolux    6. Đánh giá và tồn kho

Cách đọc file này (từ trên xuống):
  - CẤU HÌNH       : các nhóm phân khúc (cột tính toán trong Power BI). Khác thì sửa ở đây.
  - chi_so()       : các thước đo (measure) như Total Products, Avg Price, In Stock Rate...
  - bo_loc()       : bộ lọc giống slicer của Power BI (đặt trong mục "Bộ lọc dữ liệu").
  - ve / cot_doc / thanh_ngang : các hàm vẽ biểu đồ dùng chung.
  - page_...()     : mỗi trang dashboard là một hàm.
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from data_loader import LABELS, MUC_GIAM, get_data
from ui import CHART_COLORS, cards, fmt_int, fmt_vnd, page_header

# =====================================================================
# CẤU HÌNH: các nhóm phân khúc (calculated column trong Power BI)
# Các mốc dưới đây là suy ra từ nhãn trong báo cáo. Nếu DAX của nhóm khác thì sửa ở đây.
# =====================================================================
PHAN_KHUC_GIA = ["Bình dân (<100K)", "Trung cấp (100-300K)", "Cao cấp (300-700K)", "Hạng sang (>700K)"]
MOC_PHAN_KHUC_GIA = [0, 100_000, 300_000, 700_000, np.inf]

NHOM_DANH_GIA = ["Chưa có đánh giá", "Dưới 4.0", "4.0 – 4.5", "4.5 – 4.8", "4.8 – 5.0"]
MOC_DANH_GIA = [0, 4.0, 4.5, 4.8, 5.01]

MOC_GIA_100K = [0] + list(range(100_000, 1_600_000, 100_000)) + [np.inf]  # cột "price (bins)": mỗi bin rộng 100K
NHAN_GIA_100K = [f"{a // 1000}–{b // 1000}K" for a, b in zip(MOC_GIA_100K[:-2], MOC_GIA_100K[1:-1])]
NHAN_GIA_100K.append(f"Trên {MOC_GIA_100K[-2] // 1000}K")

# Màu theo nguồn: Hasaki xanh lá (theo logo), Cocolux hồng
SOURCE_COLOR = {"Hasaki": CHART_COLORS[2], "Cocolux": CHART_COLORS[0]}
STOCK_COLOR = {"Còn hàng": CHART_COLORS[2], "Hết hàng": CHART_COLORS[0]}

# Tên hiển thị của các cột trên trục, chú thích, tooltip
NHAN = {
    **LABELS,
    "n": "Số sản phẩm", "price_segment": "Phân khúc giá", "stock_status": "Tồn kho",
    "muc_giam": "Mức giảm giá", "rating_band": "Nhóm đánh giá", "khoang_gia_100k": "Khoảng giá",
    "luot": "Tổng lượt đánh giá", "gia_tb": "Giá bán TB (đ)", "diem_tb": "Đánh giá có trọng số",
}


# =====================================================================
# DỮ LIỆU + THƯỚC ĐO
# =====================================================================
def lay_du_lieu():
    """Lấy dữ liệu và thêm các cột phân khúc dùng trong dashboard."""
    d = get_data().copy()
    d["price_segment"] = pd.cut(d["price"], MOC_PHAN_KHUC_GIA, labels=PHAN_KHUC_GIA, right=False)
    nhom = pd.cut(d["rating"], MOC_DANH_GIA, labels=NHOM_DANH_GIA[1:], right=False).astype(object)
    d["rating_band"] = pd.Categorical(nhom.fillna(NHOM_DANH_GIA[0]), categories=NHOM_DANH_GIA, ordered=True)
    d["muc_giam"] = pd.Categorical(d["muc_giam"], categories=MUC_GIAM, ordered=True)
    d["stock_status"] = np.where(d["in_stock"] == 1, "Còn hàng", "Hết hàng")
    d["khoang_gia_100k"] = pd.cut(d["price"], MOC_GIA_100K, labels=NHAN_GIA_100K, right=False)
    return d


def diem_trong_so(d):
    """Weighted Rating: điểm đánh giá trung bình, sản phẩm nhiều lượt đánh giá có trọng số lớn hơn."""
    c = d[d["rating"].notna() & (d["review_count"] > 0)]
    if c.empty:
        return d["rating"].mean()
    return (c["rating"] * c["review_count"]).sum() / c["review_count"].sum()


def chi_so(d):
    """Các thước đo (measure) của Power BI, tính trên bảng d (đã lọc)."""
    return {
        "tong_sp": len(d),
        "tong_thuong_hieu": d["brand"].nunique(),
        "gia_tb": d["price"].mean(),
        "gia_trung_vi": d["price"].median(),
        "gia_min": d["price"].min(),
        "gia_max": d["price"].max(),
        "giam_tb": d["discount_pct"].mean(),
        "giam_max": d["discount_pct"].max(),
        "con_hang": d["in_stock"].mean() * 100,
        "danh_gia_tb": d["rating"].mean(),
        "tong_luot_dg": d["review_count"].sum(),
        "luot_dg_max": d["review_count"].max(),
        "co_danh_gia": d["rating"].notna().mean() * 100,
        "diem_trong_so": diem_trong_so(d),
    }


def sao(x):
    return "—" if pd.isna(x) else f"{x:.2f} ★"


def dem(d, cot):
    """Đếm số sản phẩm theo cột. Cột phân khúc giữ đúng thứ tự phân khúc, cột khác xếp giảm dần."""
    la_phan_khuc = isinstance(d[cot].dtype, pd.CategoricalDtype)
    t = d[cot].value_counts(sort=not la_phan_khuc).rename_axis(cot).reset_index(name="n")
    t[cot] = t[cot].astype(str)
    return t


# =====================================================================
# BỘ LỌC (slicer của Power BI)
# =====================================================================
BO_LOC = {  # cột -> (nhãn, kiểu, bước nhảy). Kiểu "chon" = chọn nhiều giá trị, "khoang" = kéo khoảng số
    "nguon": ("Nguồn", "chon", None),
    "brand": ("Thương hiệu", "chon", None),
    "xuat_xu": ("Xuất xứ", "chon", None),
    "category": ("Danh mục", "chon", None),
    "stock_status": ("Tồn kho", "chon", None),
    "price": ("Giá bán (đ)", "khoang", 1000),
    "rating": ("Đánh giá", "khoang", 0.1),
    "discount_pct": ("Mức giảm (%)", "khoang", 1),
    "review_count": ("Lượt đánh giá", "khoang", 1),
}


def bo_loc(d, key, cot_loc):
    """Vẽ các ô lọc trong một mục "Bộ lọc dữ liệu" (mặc định thu gọn cho vừa điện thoại) và trả về bảng đã lọc.
    Không chọn gì = lấy tất cả. Muốn mở sẵn: đổi expanded=False thành True."""
    if d.empty:
        return d
    goc = d
    with st.expander("Bộ lọc dữ liệu", expanded=False):
        o = st.columns(len(cot_loc))
        for hop, cot in zip(o, cot_loc):
            nhan, kieu, buoc = BO_LOC[cot]
            if kieu == "chon":
                tuy_chon = sorted(goc[cot].dropna().astype(str).unique())
                if cot == "xuat_xu":
                    tuy_chon = [x for x in tuy_chon if x != "Không rõ"]
                chon = hop.multiselect(nhan, tuy_chon, key=f"{key}_{cot}", placeholder="Tất cả")
                if chon:
                    d = d[d[cot].astype(str).isin(chon)]
            else:
                if cot == "rating":
                    lo, hi = 0.0, 5.0
                else:  # làm tròn mốc để khớp bước nhảy của thanh trượt
                    lo = int(goc[cot].min() // buoc * buoc)
                    hi = int(-(-goc[cot].max() // buoc) * buoc)
                if lo >= hi:
                    continue
                khoang = hop.slider(nhan, lo, hi, (lo, hi), step=buoc, key=f"{key}_{cot}")
                if tuple(khoang) != (lo, hi):  # chỉ lọc khi người dùng đã kéo thanh trượt
                    d = d[d[cot].between(*khoang)]
    return d


# =====================================================================
# HÀM VẼ BIỂU ĐỒ DÙNG CHUNG
# =====================================================================
def ve(fig, cao=330, legend=True):
    """Áp bảng màu của web rồi hiển thị biểu đồ."""
    fig.update_layout(
        height=cao, margin=dict(l=8, r=8, t=8, b=8), showlegend=legend, colorway=CHART_COLORS,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(size=12),
        legend=dict(orientation="h", yanchor="top", y=-0.18, x=0, title_text=""),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def cot_doc(t, x, y, mau=0, cao=330, **kw):
    """Biểu đồ cột đứng. Muốn chia màu theo nhóm: truyền color="tên cột"."""
    if "color" not in kw:
        kw["color_discrete_sequence"] = [CHART_COLORS[mau]]
    fig = px.bar(t, x=x, y=y, labels=NHAN, **kw)
    ve(fig, cao=cao, legend="color" in kw)


def thanh_ngang(t, x, y, mau=0, cao=330, **kw):
    """Biểu đồ thanh ngang, dòng đầu tiên nằm trên cùng (hợp với bảng xếp hạng)."""
    if "color" not in kw:
        kw["color_discrete_sequence"] = [CHART_COLORS[mau]]
    fig = px.bar(t, x=x, y=y, orientation="h", labels=NHAN, **kw)
    fig.update_layout(yaxis=dict(autorange="reversed", title=None))
    ve(fig, cao=cao, legend="color" in kw)


def thanh_san_pham(t, cot, mau=0, them=(), **kw):
    """Thanh ngang xếp hạng sản phẩm: t là bảng top N. Rê chuột để xem tên đầy đủ, nguồn, thương hiệu."""
    t = t.assign(ten=[f"{i + 1:02d}. {str(n)[:40]}" for i, n in enumerate(t["name"])])
    hover = {"ten": False, "nguon": True, "brand": True, **{c: True for c in them}}
    thanh_ngang(t, cot, "ten", mau=mau, cao=380, hover_name="name", hover_data=hover, **kw)


def khong_co_du_lieu(d):
    if d.empty:
        st.info("Không có sản phẩm nào khớp bộ lọc đã chọn.")
        return True
    return False


# =====================================================================
# TRANG 1: TỔNG QUAN THỊ TRƯỜNG
# =====================================================================
def page_tong_quan():
    page_header("Tổng quan")
    d = bo_loc(lay_du_lieu(), "tq", ["nguon", "category", "price"])
    if khong_co_du_lieu(d):
        return
    m = chi_so(d)
    cards([
        ("Sản phẩm", fmt_int(m["tong_sp"]), "rose"),
        ("Giá trung bình", fmt_vnd(m["gia_tb"]), "plum"),
        ("Thương hiệu", fmt_int(m["tong_thuong_hieu"]), "teal"),
        ("Còn hàng", f"{m['con_hang']:.1f}%", "blue"),
    ], cot=4)

    trai, phai = st.columns(2)
    with trai:
        st.subheader("Sản phẩm theo nguồn")
        fig = px.pie(dem(d, "nguon"), names="nguon", values="n", hole=0.55, color="nguon",
                     color_discrete_map=SOURCE_COLOR, labels=NHAN)
        fig.update_traces(textinfo="percent+label")
        ve(fig, cao=300, legend=False)
    with phai:
        st.subheader("Sản phẩm theo nhóm ngành hàng")
        thanh_ngang(dem(d, "category_group"), "n", "category_group", mau=1, cao=300)

    with st.expander("Xem thêm: giảm giá và xuất xứ"):
        trai, phai = st.columns(2)
        with trai:
            st.subheader("Mức giảm giá")
            cot_doc(dem(d, "muc_giam"), "muc_giam", "n", mau=4, cao=280)
        with phai:
            st.subheader("Xuất xứ phổ biến")
            co_xuat_xu = d[d["xuat_xu"] != "Không rõ"]
            thanh_ngang(dem(co_xuat_xu, "xuat_xu").head(10), "n", "xuat_xu", mau=2, cao=280)
            st.caption(f"Bỏ qua {fmt_int(len(d) - len(co_xuat_xu))} sản phẩm chưa rõ xuất xứ.")


# =====================================================================
# TRANG 2: THỐNG KÊ & MIN-MAX
# =====================================================================
THONG_KE_NHOM = {  # tên cột hiển thị -> (cột, hàm tính)
    "Giá thấp nhất": ("price", "min"),
    "Giá trung vị": ("price", "median"),
    "Giá cao nhất": ("price", "max"),
    "Giảm giá TB (%)": ("discount_pct", "mean"),
    "Giảm giá cao nhất (%)": ("discount_pct", "max"),
    "Đánh giá TB": ("rating", "mean"),
    "Tổng lượt đánh giá": ("review_count", "sum"),
    "Số sản phẩm": ("price", "size"),
}


def bang_thong_ke_nhom(d):
    """Bảng giống ma trận của Power BI: hàng = nhóm ngành hàng, cột = từng thước đo x từng nguồn."""
    def tinh(x):
        return x.groupby("category_group").agg(**{ten: kieu for ten, kieu in THONG_KE_NHOM.items()})

    cac_phan = {ng: tinh(g) for ng, g in d.groupby("nguon")}
    cac_phan["Tất cả"] = tinh(d)
    bang = pd.concat(cac_phan, axis=1).swaplevel(axis=1)  # cột: (thước đo, nguồn)
    cot = [(ten, ng) for ten in THONG_KE_NHOM for ng in cac_phan]
    bang = bang[cot].round(1)
    bang.index.name = "Nhóm ngành hàng"
    return bang


def page_thong_ke():
    page_header("Thống kê & Min-Max")
    d = lay_du_lieu()
    if khong_co_du_lieu(d):
        return
    m = chi_so(d)
    thuong_hieu = d["brand"].value_counts()
    cards([
        ("Thương hiệu nhiều sản phẩm nhất", thuong_hieu.index[0], "plum", f"{fmt_int(thuong_hieu.iloc[0])} sản phẩm"),
        ("Giá thấp nhất", fmt_vnd(m["gia_min"]), "teal"),
        ("Giá cao nhất", fmt_vnd(m["gia_max"]), "rose"),
        ("Giảm giá cao nhất", f"{m['giam_max']}%", "coral"),
        ("Lượt đánh giá nhiều nhất", fmt_int(m["luot_dg_max"]), "gold"),
    ])

    st.subheader("Sản phẩm nổi bật")
    dong = []
    for tieu_chi, i in [("Đắt nhất", d["price"].idxmax()), ("Rẻ nhất", d["price"].idxmin()),
                        ("Giảm giá sâu nhất", d["discount_pct"].idxmax()),
                        ("Nhiều lượt đánh giá nhất", d["review_count"].idxmax())]:
        r = d.loc[i]
        dong.append({"Tiêu chí": tieu_chi, "Sản phẩm": r["name"], "Thương hiệu": r["brand"], "Nguồn": r["nguon"],
                     "Giá bán (đ)": int(r["price"]), "Giảm giá (%)": int(r["discount_pct"]),
                     "Lượt đánh giá": int(r["review_count"])})
    st.dataframe(pd.DataFrame(dong), width="stretch", hide_index=True)

    st.subheader("Bảng thống kê theo nhóm ngành hàng")
    st.dataframe(bang_thong_ke_nhom(d), width="stretch")

    trai, phai = st.columns(2)
    with trai:
        st.subheader("Top 10 sản phẩm đắt nhất")
        thanh_san_pham(d.nlargest(10, "price"), "price", mau=0)
        st.subheader("Top 10 sản phẩm rẻ nhất")
        thanh_san_pham(d.nsmallest(10, "price"), "price", mau=2)
    with phai:
        st.subheader("Top 10 sản phẩm giảm sâu")
        thanh_san_pham(d.nlargest(10, "discount_pct"), "discount_pct", mau=4, them=["price_original", "price"])
        st.subheader("Top 10 sản phẩm có nhiều đánh giá nhất")
        thanh_san_pham(d.nlargest(10, "review_count"), "review_count", mau=3, them=["rating"])


# =====================================================================
# TRANG 3: SO SÁNH HASAKI VÀ COCOLUX
# =====================================================================
def bieu_do_gia_va_giam(d):
    """Cột = giá trung vị, đường = giảm giá trung bình, mỗi nguồn một khung (như Power BI)."""
    nguon_ds = sorted(d["nguon"].unique())
    fig = make_subplots(rows=len(nguon_ds), cols=1, specs=[[{"secondary_y": True}] for _ in nguon_ds],
                        subplot_titles=nguon_ds, vertical_spacing=0.2)
    for i, ng in enumerate(nguon_ds, start=1):
        g = (d[d["nguon"] == ng].groupby("category_group")
             .agg(gia=("price", "median"), giam=("discount_pct", "mean"), dg=("rating", "mean"), n=("price", "size"))
             .reset_index())
        fig.add_trace(go.Bar(
            x=g["category_group"], y=g["gia"], name="Giá trung vị (đ)", marker_color=CHART_COLORS[1],
            customdata=g[["dg", "n"]], showlegend=(i == 1),
            hovertemplate="%{x}<br>Giá trung vị: %{y:,.0f} đ<br>Đánh giá TB: %{customdata[0]:.2f}"
                          "<br>Số sản phẩm: %{customdata[1]}<extra></extra>"),
            row=i, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(
            x=g["category_group"], y=g["giam"], mode="lines+markers", name="Giảm giá TB (%)",
            line=dict(color=CHART_COLORS[4], width=3), showlegend=(i == 1)),
            row=i, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Giá trung vị (đ)", secondary_y=False)
    fig.update_yaxes(title_text="Giảm giá TB (%)", secondary_y=True)
    ve(fig, cao=290 * len(nguon_ds))


def page_so_sanh():
    page_header("So sánh Hasaki và Cocolux", "Giá, mức giảm giá, phân khúc và tồn kho theo từng nguồn")
    d = bo_loc(lay_du_lieu(), "ss", ["nguon", "price", "discount_pct", "brand", "category"])
    if khong_co_du_lieu(d):
        return
    m = chi_so(d)

    trai, phai = st.columns(2)
    with trai:
        st.subheader("Giá trung bình theo nhóm ngành hàng")
        t = d.groupby(["category_group", "nguon"], as_index=False)["price"].mean().round(0)
        cot_doc(t, "category_group", "price", color="nguon", barmode="group", color_discrete_map=SOURCE_COLOR)
    with phai:
        st.subheader("Tỷ lệ tồn kho")
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=round(m["con_hang"], 1), number={"suffix": "% còn hàng"},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": CHART_COLORS[2]},
                   "steps": [{"range": [0, 50], "color": "#FFE5DF"}, {"range": [50, 80], "color": "#FFF1CC"},
                             {"range": [80, 100], "color": "#D9F5F1"}]}))
        ve(fig, cao=300, legend=False)

    st.subheader("Biến động giá trung vị và mức giảm giá theo ngành hàng")
    bieu_do_gia_va_giam(d)

    trai, phai = st.columns(2)
    with trai:
        st.subheader("Tỷ lệ giảm giá trung bình theo nhóm ngành hàng")
        t = d.groupby(["category_group", "nguon"], as_index=False)["discount_pct"].mean().round(1)
        thanh_ngang(t, "discount_pct", "category_group", color="nguon", barmode="group",
                    color_discrete_map=SOURCE_COLOR)
    with phai:
        st.subheader("Phân bổ sản phẩm theo phân khúc giá")
        t = d.groupby(["nguon", "price_segment"], observed=True).size().reset_index(name="n")
        t["price_segment"] = t["price_segment"].astype(str)
        thanh_ngang(t, "n", "nguon", color="price_segment", barmode="group",
                    category_orders={"price_segment": PHAN_KHUC_GIA})


# =====================================================================
# TRANG 4: THƯƠNG HIỆU VÀ XUẤT XỨ
# =====================================================================
def bang_thuong_hieu(d):
    """Mỗi dòng = một thương hiệu trong một nguồn. Chỉ giữ thương hiệu có hơn 10 sản phẩm (như Power BI)."""
    x = d.assign(
        tich=d["rating"].fillna(0) * d["review_count"],
        luot_co_dg=d["review_count"].where(d["rating"].notna(), 0),
    )
    g = x.groupby(["brand", "nguon"]).agg(
        n=("price", "size"), gia_tb=("price", "mean"), luot=("review_count", "sum"),
        tich=("tich", "sum"), luot_co_dg=("luot_co_dg", "sum"),
    ).reset_index()
    g = g[g["n"] > 10].copy()
    g["diem_tb"] = (g["tich"] / g["luot_co_dg"]).where(g["luot_co_dg"] > 0)
    g["kich_thuoc"] = g["luot"].clip(lower=1)
    return g.dropna(subset=["diem_tb"])


def page_thuong_hieu():
    page_header("Thương hiệu và xuất xứ", "Thương hiệu nổi bật, thị phần và cơ cấu theo quốc gia xuất xứ")
    d = bo_loc(lay_du_lieu(), "th", ["nguon", "brand", "xuat_xu", "category", "review_count"])
    if khong_co_du_lieu(d):
        return
    co_xuat_xu = d[d["xuat_xu"] != "Không rõ"]

    trai, phai = st.columns(2)
    with trai:
        st.subheader("Top thương hiệu có nhiều sản phẩm nhất")
        thanh_ngang(dem(d, "brand").head(15), "n", "brand", mau=1, cao=420)
    with phai:
        st.subheader("Cơ cấu nhóm ngành hàng theo quốc gia xuất xứ")
        top_xx = dem(co_xuat_xu, "xuat_xu").head(10)["xuat_xu"]
        t = (co_xuat_xu[co_xuat_xu["xuat_xu"].isin(top_xx)]
             .groupby(["xuat_xu", "category_group"]).size().reset_index(name="n"))
        thanh_ngang(t, "n", "xuat_xu", color="category_group", cao=420,
                    category_orders={"xuat_xu": list(top_xx)})

    st.subheader("Tương quan giá – đánh giá – lượt review theo thương hiệu")
    g = bang_thuong_hieu(d)
    if g.empty:
        st.info("Không có thương hiệu nào có hơn 10 sản phẩm với bộ lọc hiện tại.")
    else:
        fig = px.scatter(g, x="gia_tb", y="diem_tb", size="kich_thuoc", color="nguon", hover_name="brand",
                         hover_data={"n": True, "luot": True, "kich_thuoc": False}, size_max=40,
                         color_discrete_map=SOURCE_COLOR, labels=NHAN)
        ve(fig, cao=400)
        st.caption("Mỗi bong bóng là một thương hiệu có hơn 10 sản phẩm. Kích thước = tổng lượt đánh giá.")

    trai, phai = st.columns(2)
    with trai:
        st.subheader("Thị phần số lượng sản phẩm giữa các thương hiệu (top 20)")
        fig = px.treemap(dem(d, "brand").head(20), path=["brand"], values="n", color="n",
                         color_continuous_scale=["#F9D8E8", CHART_COLORS[0]], labels=NHAN)
        fig.update_coloraxes(showscale=False)
        ve(fig, cao=380, legend=False)
    with phai:
        st.subheader("Tỷ trọng sản phẩm theo quốc gia xuất xứ")
        fig = px.pie(dem(co_xuat_xu, "xuat_xu"), names="xuat_xu", values="n", hole=0.5, labels=NHAN)
        fig.update_traces(textinfo="percent")
        ve(fig, cao=380)


# =====================================================================
# TRANG 5: GIÁ VÀ KHUYẾN MÃI
# =====================================================================
def page_gia_khuyen_mai():
    page_header("Giá và khuyến mãi", "Quan hệ giữa giá bán và mức giảm, phân khúc giá và phân bố giá")
    d = bo_loc(lay_du_lieu(), "gk", ["nguon", "price", "discount_pct", "category", "xuat_xu"])
    d = d[d["price"] >= 1000]  # bỏ bản ghi giá nhập sai (xem trang Chất lượng dữ liệu)
    if khong_co_du_lieu(d):
        return

    st.subheader("Tương quan giá bán và tỷ lệ chiết khấu (100 sản phẩm giá cao nhất)")
    fig = px.scatter(d.nlargest(100, "price"), x="price", y="discount_pct", color="nguon", hover_name="name",
                     hover_data={"brand": True}, color_discrete_map=SOURCE_COLOR, labels=NHAN)
    ve(fig, cao=360)

    st.subheader("Tỷ lệ giảm giá trung bình theo danh mục sản phẩm")
    t = d.groupby("category", as_index=False)["discount_pct"].mean().round(1).sort_values("discount_pct", ascending=False)
    cot_doc(t, "category", "discount_pct", mau=4)

    trai, phai = st.columns(2)
    with trai:
        st.subheader("Tần suất phân bổ giá sản phẩm")
        t = d["khoang_gia_100k"].value_counts(sort=False).rename_axis("khoang_gia_100k").reset_index(name="n")
        t["khoang_gia_100k"] = t["khoang_gia_100k"].astype(str)
        cot_doc(t, "khoang_gia_100k", "n", mau=3)
    with phai:
        st.subheader("Cơ cấu số lượng sản phẩm theo phân khúc giá")
        t = d.groupby(["price_segment", "nguon"], observed=True).size().reset_index(name="n")
        t["price_segment"] = t["price_segment"].astype(str)
        cot_doc(t, "price_segment", "n", color="nguon", color_discrete_map=SOURCE_COLOR,
                category_orders={"price_segment": PHAN_KHUC_GIA})


# =====================================================================
# TRANG 6: ĐÁNH GIÁ VÀ TỒN KHO
# =====================================================================
def page_danh_gia_ton_kho():
    page_header("Đánh giá và tồn kho", "Mức độ được đánh giá, lượt review và tình trạng còn hàng")
    d = bo_loc(lay_du_lieu(), "dg", ["nguon", "review_count", "stock_status", "category", "xuat_xu"])
    if khong_co_du_lieu(d):
        return
    m = chi_so(d)

    trai, phai = st.columns([1, 2])
    with trai:
        cards([("Tỷ lệ sản phẩm có đánh giá", f"{m['co_danh_gia']:.1f}%", "gold",
                f"{fmt_int(d['rating'].notna().sum())} / {fmt_int(len(d))} sản phẩm")])
    with phai:
        st.subheader("Phân bổ sản phẩm theo phân khúc đánh giá")
        cot_doc(dem(d, "rating_band"), "rating_band", "n", mau=3, cao=260)

    st.subheader("Tổng số lượng đánh giá theo sản phẩm (top 20)")
    thanh_san_pham(d.nlargest(20, "review_count"), "review_count", color="rating",
                   color_continuous_scale=["#F9D8E8", CHART_COLORS[1]])

    trai, phai = st.columns(2)
    with trai:
        st.subheader("Tỷ lệ trạng thái tồn kho theo nhóm ngành hàng")
        t = d.groupby(["category_group", "stock_status"]).size().reset_index(name="n")
        # Tính phần trăm trước để tương thích với các phiên bản Plotly không hỗ trợ `barnorm`.
        t["ty_le"] = t["n"] / t.groupby("category_group")["n"].transform("sum") * 100
        fig = px.bar(t, y="category_group", x="ty_le", color="stock_status", orientation="h",
                     color_discrete_map=STOCK_COLOR, labels={**NHAN, "ty_le": "Tỷ lệ (%)"},
                     custom_data=["n"])
        fig.update_traces(hovertemplate="%{y}<br>%{fullData.name}: %{x:.1f}%<br>Số sản phẩm: %{customdata[0]}<extra></extra>")
        fig.update_layout(xaxis_ticksuffix="%", xaxis_title=None, yaxis_title=None, xaxis_range=[0, 100])
        ve(fig)
    with phai:
        st.subheader("Tổng số lượng đánh giá theo nguồn bán")
        t = d.groupby("nguon", as_index=False)["review_count"].sum()
        cot_doc(t, "nguon", "review_count", color="nguon", color_discrete_map=SOURCE_COLOR)

    st.subheader("Top sản phẩm hết hàng có nhiều lượt đánh giá nhất")
    het_hang = d[d["stock_status"] == "Hết hàng"]
    if het_hang.empty:
        st.info("Không có sản phẩm hết hàng nào với bộ lọc hiện tại.")
    else:
        thanh_san_pham(het_hang.nlargest(10, "review_count"), "review_count", mau=0, them=["price", "rating"])
