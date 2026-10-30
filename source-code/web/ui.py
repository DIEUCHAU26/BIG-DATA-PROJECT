from html import escape
import pandas as pd
import streamlit as st

from data_loader import LABELS

PALETTE = {
    "rose": ("#D6336C", "#FFE3EE"),
    "plum": ("#7048A8", "#EEE5FA"),
    "teal": ("#1A9E8F", "#D9F5F1"),
    "gold": ("#D98E04", "#FFF1CC"),
    "coral": ("#F0634A", "#FFE5DF"),
    "blue": ("#3E7BDB", "#E1ECFC"),
}
CHART_COLORS = ["#D6336C", "#7048A8", "#1A9E8F", "#E9A21B", "#F0634A", "#3E7BDB"]

CSS = """
<style>
:root {
    --ink: #2D1B33;  --muted: #7A6A80;  --rose: #D6336C;  --plum: #7048A8;
    --line: #F4DCE7; --soft: #FFF5F9;
    --nav-grad: linear-gradient(105deg, #4B2A7B 0%, #8E2A8F 42%, #D6336C 100%);  /* nền navbar: tím -> hồng */
    --nav-dark: #4B2A7B;  /* màu chữ của nút khi rê chuột vào */
    /* Màu banner tiêu đề mỗi trang (nhạt): đổi 3 dòng này là đổi mọi banner */
    --hdr-grad: linear-gradient(120deg, #EFE6FB 0%, #F9D8E8 58%, #FFE9F1 100%);
    --hdr-title: #4B2A7B;
    --hdr-sub: #8A3F68;
}
footer {visibility: hidden;}
.stApp {background: linear-gradient(180deg, #FFF3F8 0, #FFFFFF 380px);}
/* Tăng cỡ chữ mặc định để nội dung dễ đọc hơn. */
html, body, [class*="st-"], [data-testid="stMarkdownContainer"] p,
[data-testid="stWidgetLabel"] p, [data-testid="stCaptionContainer"] {
    font-size: 1.05rem;
}
h1, h2, h3, h4 {color: var(--ink); letter-spacing: -.01em;}
h3 {font-size: 1.25rem !important; margin-top: .6rem;}

/* ---------- MẶC ĐỊNH = ĐIỆN THOẠI ---------- */
.block-container {padding: 4.5rem 1rem 2rem 1rem; max-width: 1200px;}

/* Ẩn thanh header mặc định của Streamlit: web dùng thanh điều hướng riêng (xem khối NAVBAR bên dưới) */
header[data-testid="stHeader"] {display: none !important;}

/* Nút bấm to, dễ chạm bằng ngón tay, rộng bằng khung chứa */
.stButton > button, .stDownloadButton > button,
[data-testid="stFormSubmitButton"] > button {
    width: 100%; min-height: 46px; border-radius: 12px; font-weight: 600;
    transition: transform .08s ease, box-shadow .15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-1px); box-shadow: 0 6px 14px rgba(214, 51, 108, .22);
}

/* ---------- NAVBAR 1 HÀNG: [logo + tên web] [3 nhóm chức năng] ...... [tài khoản] ---------- */
/* Đổi màu navbar: sửa biến --nav-grad ở khối :root phía trên */
.st-key-topnav {
    position: fixed; top: 0; left: 0; right: 0; z-index: 1000000;
    background: var(--nav-grad); box-shadow: 0 4px 16px rgba(75, 42, 123, .30);
}

/* Xếp mọi thứ trong navbar thành MỘT HÀNG ngang, không xuống dòng */
.st-key-nav_row, .st-key-nav_row > [data-testid="stVerticalBlock"] {
    display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important;
    align-items: center !important; gap: .4rem !important;
}
.st-key-nav_row {padding: .5rem .8rem; overflow-x: auto; scrollbar-width: none;}
.st-key-nav_row [data-testid="stElementContainer"],
.st-key-nav_row [data-testid="stMarkdownContainer"] {width: auto !important; flex: 0 0 auto;}
.st-key-nav_row [data-testid="stPopover"] {width: auto !important;}

/* Tên web (logo + chữ) nằm bên trái */
.brand {
    display: flex; align-items: center; gap: .6rem; color: #fff;
    padding-right: .9rem; margin-right: .3rem; border-right: 1px solid rgba(255, 255, 255, .35);
}
.brand img {height: 40px; width: auto; border-radius: 10px;}
.brand-text {display: flex; flex-direction: column; line-height: 1.15;}
.brand-text b {font-size: 1.05rem; letter-spacing: .03em; text-transform: uppercase; color: #fff; white-space: nowrap;}
.brand-text span {font-size: .74rem; color: #FFD9E8; white-space: nowrap;}

/* Bấm vào logo / tên web để về trang chủ: liên kết vô hình phủ kín khu vực .brand */
.st-key-brand {position: relative; width: auto !important; flex: 0 0 auto;}
.st-key-nav_row [data-testid="stLayoutWrapper"]:has(.st-key-brand),
.st-key-nav_row [data-testid="stElementContainer"]:has(.st-key-brand) {width: auto !important; flex: 0 0 auto;}
.st-key-brand [data-testid="stElementContainer"]:has(a) {
    position: absolute !important; inset: 0; width: 100% !important; height: 100% !important;
    margin: 0 !important; z-index: 5;
}
.st-key-brand a {display: block; width: 100%; height: 100%; padding: 0; opacity: 0; cursor: pointer;}
.st-key-brand .brand {transition: opacity .15s ease;}
.st-key-brand:hover .brand {opacity: .85;}

/* 3 nhóm chức năng + nút tài khoản: cùng kiểu nút bo tròn trong suốt trên nền tím hồng */
.st-key-nav_row button {
    width: auto; min-height: 2.4rem; padding: 0 .85rem; border-radius: 999px;
    background: rgba(255, 255, 255, .14) !important; color: #fff !important;
    border: 1px solid rgba(255, 255, 255, .5) !important;
    box-shadow: none !important; transform: none !important;
}
.st-key-nav_row button p {
    color: inherit !important; margin: 0 !important; white-space: nowrap;
    font-size: .95rem !important; font-weight: 700 !important;
}
.st-key-nav_row button:hover, .st-key-nav_row button[aria-expanded="true"] {
    background: #fff !important; color: var(--nav-dark) !important; border-color: #fff !important;
}

/* Tài khoản nằm sát bên phải */
.st-key-account_bar {margin-left: auto !important; width: auto !important; flex: 0 0 auto;}
.st-key-nav_row [data-testid="stLayoutWrapper"]:has(.st-key-account_bar),
.st-key-nav_row [data-testid="stElementContainer"]:has(.st-key-account_bar) {margin-left: auto !important; width: auto !important;}
.st-key-account_bar button {background: rgba(255, 255, 255, .24) !important;}
.st-key-account_bar button p {max-width: 11rem; overflow: hidden; text-overflow: ellipsis;}

/* Các trang trong hộp sổ xuống */
[data-testid="stPopoverBody"] a p {font-size: 1rem; font-weight: 600;}

.role-badge {
    display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: .75rem; font-weight: 700;
    background: #FFE3EE; color: var(--rose);
}

/* Banner tiêu đề mỗi trang */
.page-header {
    position: relative; overflow: hidden;
    background: var(--hdr-grad); border: 1px solid var(--line);
    border-radius: 18px; padding: 18px 20px; margin-bottom: 18px;
    box-shadow: 0 8px 20px rgba(112, 72, 168, .10);
}
.page-header::after {
    content: ""; position: absolute; right: -40px; top: -60px; width: 220px; height: 220px;
    border-radius: 50%; background: radial-gradient(circle, rgba(255,255,255,.75), rgba(255,255,255,0) 70%);
}
.page-header h1 {color: var(--hdr-title); margin: 0; padding: 0; font-size: 1.5rem; line-height: 1.3;}
.page-header p {color: var(--hdr-sub); margin: 4px 0 0 0; font-size: 1rem;}

/* Thẻ số liệu: lưới 2 cột trên điện thoại */
.card-grid {
    display: grid; grid-template-columns: repeat(2, 1fr);
    gap: 10px; margin-bottom: 16px;
}
.card {
    position: relative; background: #fff; border: 1px solid var(--line);
    border-radius: 16px; padding: 12px 14px 12px 16px; overflow: hidden;
    box-shadow: 0 4px 14px rgba(112, 72, 168, .07);
}
.card::before {content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 5px; background: var(--accent);}
.card::after {
    content: ""; position: absolute; right: -24px; top: -24px; width: 80px; height: 80px;
    border-radius: 50%; background: var(--tint); opacity: .8;
}
.card-label {color: var(--muted); font-size: .9rem; font-weight: 600; position: relative; z-index: 1;}
.card-value {
    font-size: clamp(1.05rem, 4.6vw, 1.9rem); font-weight: 800; color: var(--ink);
    overflow-wrap: anywhere; position: relative; z-index: 1; line-height: 1.25;
}
.card-sub {color: var(--accent); font-size: .86rem; font-weight: 600; position: relative; z-index: 1;}

/* Bảng, biểu đồ, thẻ chứa */
[data-testid="stDataFrame"] {border: 1px solid var(--line); border-radius: 12px; overflow: hidden;}
[data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"] {
    background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 8px;
}
[data-testid="stTabs"] button[role="tab"] {font-weight: 600; font-size: 1rem;}

/* Màn hình đăng nhập */
.login-title {text-align: center; margin: 8px 0 16px 0;}
.login-title .logo {
    width: 64px; height: 64px; margin: 0 auto 10px auto; border-radius: 20px; font-size: 2rem;
    display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, #4B2A7B, #D6336C, #F2789F);
    box-shadow: 0 10px 22px rgba(214, 51, 108, .35);
}
.login-title h2 {
    margin: 0; font-size: 1.5rem;
    background: linear-gradient(90deg, #7048A8, #D6336C);
    -webkit-background-clip: text; color: transparent;
}
.login-title p {color: var(--muted); font-size: .9rem; margin: 4px 0 0 0;}
.db-chip {
    display: inline-block; margin-top: 8px; padding: 2px 10px; border-radius: 999px;
    font-size: .72rem; font-weight: 700; background: #D9F5F1; color: #137a6e;
}

/* ---------- MÀN HÌNH LỚN (máy tính, máy tính bảng) ---------- */
@media (max-width: 767px) {
    .brand {padding-right: .4rem; margin-right: 0; border-right: 0;}
    .brand img {height: 34px;}
    .brand-text {display: none;}
    .st-key-nav_row {padding: .45rem .6rem; gap: .3rem !important;}
    .st-key-nav_row button {padding: 0 .55rem; min-height: 2.2rem;}
    .st-key-nav_row button p {font-size: .8rem !important;}
    .st-key-account_bar button p {display: none;}  /* điện thoại: chỉ giữ biểu tượng tài khoản */
}

@media (min-width: 768px) {
    .block-container {padding: 5rem 2rem 2rem 2rem;}
    .stButton > button, .stDownloadButton > button,
    [data-testid="stFormSubmitButton"] > button {width: auto;}
    /* Navbar máy tính: nút menu to, cân xứng với thanh */
    .st-key-nav_row {padding: .7rem 2rem; gap: .9rem !important;}
    .brand {padding-right: 1.3rem; margin-right: .6rem;}
    .brand img {height: 48px;}
    .brand-text b {font-size: 1.2rem;}
    .brand-text span {font-size: .8rem;}
    .st-key-nav_row button {min-height: 3.1rem; padding: 0 1.5rem; border-width: 1.5px !important;}
    .st-key-nav_row button p {font-size: 1.12rem !important;}
    .page-header {padding: 24px 30px; margin-bottom: 22px;}
    .page-header h1 {font-size: 1.75rem;}
    .page-header p {font-size: .97rem;}
    .card-grid {grid-template-columns: repeat(var(--cot, auto-fit), minmax(190px, 1fr)); gap: 14px;}
    .card {padding: 16px 20px 16px 22px;}
    .card-label {font-size: .86rem;}
}
</style>
"""


def apply_style():
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title, subtitle=""):
    detail = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f'<div class="page-header"><h1>{title}</h1>{detail}</div>',
        unsafe_allow_html=True,
    )


def cards(items, cot=None):
    """Hàng thẻ số liệu: mỗi thẻ là (nhãn, giá trị, màu) hoặc (nhãn, giá trị, màu, dòng phụ).
    cot = số thẻ mỗi hàng trên máy tính (bỏ trống = tự chia). Điện thoại luôn 2 thẻ mỗi hàng."""
    html = ""
    for item in items:
        label, value, color = item[:3]
        sub = item[3] if len(item) > 3 else ""
        label, value, sub = escape(str(label)), escape(str(value)), escape(str(sub))
        main, light = PALETTE[color]
        html += (
            f'<div class="card" style="--accent:{main};--tint:{light}">'
            f'<div class="card-label">{label}</div>'
            f'<div class="card-value">{value}</div>'
            + (f'<div class="card-sub">{sub}</div>' if sub else "")
            + "</div>"
        )
    kieu = f' style="--cot:{cot}"' if cot else ""
    st.markdown(f'<div class="card-grid"{kieu}>{html}</div>', unsafe_allow_html=True)


def flash(msg, kind="success"):
    """Nhớ một thông báo để hiện sau khi trang tải lại (st.rerun)."""
    st.session_state["_flash"] = (kind, msg)


def show_flash():
    item = st.session_state.pop("_flash", None)
    if item:
        getattr(st, item[0])(item[1])


# ----------------------------- ĐỊNH DẠNG SỐ -----------------------------
def fmt_int(x):
    """12345 -> '12.345' (kiểu Việt Nam)."""
    return f"{x:,.0f}".replace(",", ".")


def fmt_vnd(x):
    return fmt_int(x) + " đ"


def show_table(df, height=None, hide_index=True, **kwargs):
    """Hiện bảng với tên cột tiếng Việt; cột Link bấm được."""
    shown = df.rename(columns=LABELS)
    config = dict(kwargs.pop("column_config", {}) or {})
    if "url" in df.columns:
        config[LABELS["url"]] = st.column_config.LinkColumn(LABELS["url"], display_text="Mở")
    if height:
        kwargs["height"] = height
    st.dataframe(shown, width="stretch", hide_index=hide_index, column_config=config, **kwargs)


def bar(series_or_df, horizontal=False, color=None, height=320):
    """Biểu đồ cột với bảng màu của web."""
    n = 1 if isinstance(series_or_df, pd.Series) else series_or_df.shape[1]
    color = color or (CHART_COLORS[0] if n == 1 else CHART_COLORS[:n])
    st.bar_chart(series_or_df, color=color, horizontal=horizontal, height=height)
