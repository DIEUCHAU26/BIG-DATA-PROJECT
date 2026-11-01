import html
import re
import unicodedata
from pathlib import Path

import pandas as pd

# ==========================================
# 1. CẤU HÌNH ĐƯỜNG DẪN
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "cleaning_output" / "products_merged.xlsx"
OUTPUT_FILE = BASE_DIR / "cleaning_output" / "products_final.xlsx"
REPORT_FILE = BASE_DIR / "cleaning_output" / "final_cleaning_report.xlsx"

# ==========================================
# 2. ĐỌC DỮ LIỆU
# ==========================================
df = pd.read_excel(INPUT_FILE)

initial_row_count = len(df)
initial_column_count = len(df.columns)

print("=" * 55)
print("LÀM SẠCH DỮ LIỆU SẢN PHẨM")
print("=" * 55)
print(f"Số dòng ban đầu: {initial_row_count:,}")
print(f"Số cột ban đầu: {initial_column_count}")

# Kiểm tra các cột bắt buộc
required_columns = [
    "product_code",
    "review_count",
    "url",
    "price",
    "price_original",
    "discount_pct",
    "rating",
]

missing_columns = [
    col for col in required_columns
    if col not in df.columns
]

if missing_columns:
    raise ValueError(
        f"File đầu vào thiếu các cột bắt buộc: {missing_columns}"
    )

# Chuẩn hóa các ô chỉ chứa khoảng trắng thành giá trị thiếu
for col in df.select_dtypes(include=["object", "string"]).columns:
    df[col] = df[col].replace(r"^\s*$", pd.NA, regex=True)


# ==========================================
# 2.1. CHUẨN HÓA ORIGIN
# ==========================================
origin_aliases = {
    "đức": "Đức",
    "ðức": "Đức",
    "germany": "Đức",
    "malaysia": "Malaysia",
    "pháp": "Pháp",
    "france": "Pháp",
    "úc": "Úc",
    "australia": "Úc",
    "mỹ": "Mỹ",
    "usa": "Mỹ",
    "united states": "Mỹ",
    "việt nam": "Việt Nam",
    "vietnam": "Việt Nam",
    "nhật": "Nhật Bản",
    "nhật bản": "Nhật Bản",
    "japan": "Nhật Bản",
    "canada": "Canada",
    "đài loan": "Đài Loan",
    "taiwan": "Đài Loan",
    "anh quốc": "Anh",
    "anh": "Anh",
    "united kingdom": "Anh",
    "cộng hòa belarus": "Belarus",
    "belarus": "Belarus",
}

invalid_origins = {
    "nơi sản xuất",
    "dubai",
    "ả rập",
    (
        "pháp nhưng sản xuất tại indonesia. "
        "chưa sử dụng nên chưa đánh giá được chất lượng"
    ),
}


def normalize_origin(value):
    """Chuẩn hóa tên quốc gia và xử lý origin không hợp lệ."""

    if pd.isna(value):
        return pd.NA

    original_value = str(value).strip()
    normalized_value = re.sub(r"\s+", " ", original_value)

    key = normalized_value.casefold().rstrip(".").strip()

    if not key or key in invalid_origins:
        return pd.NA

    # Xử lý tên quốc gia kèm giải thích trong ngoặc
    # Ví dụ: Mỹ (thuộc tập đoàn Unilever của Mỹ)
    if "(" in normalized_value:
        country = normalized_value.split("(", 1)[0].strip()
        country_key = country.casefold().rstrip(".").strip()

        if country_key in origin_aliases:
            return origin_aliases[country_key]

    # Chuẩn hóa các tên quốc gia đã xác định
    if key in origin_aliases:
        return origin_aliases[key]

    # Giữ nguyên các giá trị khác chưa xác định là sai
    return normalized_value


if "origin" in df.columns:
    df["origin"] = df["origin"].apply(normalize_origin)

    print("\n--- CHUẨN HÓA ORIGIN ---")
    print("Đã chuẩn hóa các tên quốc gia không đồng nhất.")
    print("Các giá trị origin nghi vấn được chuyển thành giá trị thiếu.")
else:
    print("\nCẢNH BÁO: Không tìm thấy cột origin.")


# ==========================================
# 2.2. LOẠI SẢN PHẨM CÓ GIÁ DƯỚI 1.000 ĐỒNG
# ==========================================
df["price"] = pd.to_numeric(df["price"], errors="coerce")

before_price_filter = len(df)

# Giữ sản phẩm thiếu giá để không tự động xóa dữ liệu chưa xác định.
# Chỉ loại sản phẩm có giá xác định và thấp hơn 1.000 đồng.
df = df[
    df["price"].isna() | (df["price"] >= 1000)
].copy()

removed_low_price = before_price_filter - len(df)

print("\n--- XỬ LÝ GIÁ SẢN PHẨM ---")
print(
    "Số sản phẩm bị xóa do giá dưới 1.000 đồng: "
    f"{removed_low_price:,}"
)


# ==========================================
# 2.3. CHUẨN HÓA MÃ SẢN PHẨM VÀ URL
# ==========================================
# Chuyển mã thành chuỗi, loại bỏ khoảng trắng và hậu tố .0.
# Ví dụ: 422277481.0 -> 422277481
df["_product_code_check"] = (
    df["product_code"]
    .astype("string")
    .str.strip()
    .str.replace(r"\.0$", "", regex=True)
)

# Chuẩn hóa URL để so sánh chính xác hơn
df["url"] = (
    df["url"]
    .astype("string")
    .str.strip()
)


# ==========================================
# 2.4. CHUẨN HÓA BRAND (VIẾT HOA) VÀ SỬA BRAND "BLOG LÀM ĐẸP"
# ==========================================
# Brand sửa riêng theo mã sản phẩm (ghi đè sau khi chuẩn hóa)
brand_fix_by_code = {
    "5701943010402": "PERSPIREX",   # Lăn Khử Mùi Perspirex Antiperspirant Roll-On 20ml
    "8935293108923": "BESILKI",     # Tẩy Tế Bào Chết Besilki Arabica Coffee & Milky Protein
}

# Các nhóm brand khác nhau về dấu/ký tự (không chỉ hoa/thường):
# key (bỏ dấu, bỏ ký tự đặc biệt, chữ thường) -> tên chuẩn viết HOA
brand_manual = {
    "loreal": "L'ORÉAL",             # L'Oreal / L'Oréal
    "banobagi": "BANOBAGI",          # Banobagi / BANO:BAGI
    "jmsolution": "JM SOLUTION",     # JM SOLUTION / JMsolution
    "kissme": "KISS ME",             # KISS ME / Kissme
    "onthebody": "ON: THE BODY",     # On: The Body / ON:THE BODY
    "dolcegabbana": "DOLCE & GABBANA",
    "rogergallet": "ROGER & GALLET",
    "realbarrier": "REAL BARRIER",
    "sonatural": "SO NATURAL",
    "abonne": "A BONNE",             # A Bonne / A BONNÉ
    "foodaholic": "FOOD A HOLIC",
    "dprogram": "D PROGRAM",
    "cetaphilbaby": "CETAPHIL",      # dòng sản phẩm -> thương hiệu (xóa dòng này nếu muốn giữ)
}


def make_brand_key(value):
    """Tạo khóa so sánh: bỏ dấu, bỏ ký tự đặc biệt, chữ thường."""
    text = unicodedata.normalize("NFD", str(value))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[^a-z0-9]", "", text.lower())


def normalize_brand(value):
    """Giải mã &amp;, thống nhất dấu nháy, bỏ khoảng trắng thừa, viết HOA."""
    if pd.isna(value):
        return pd.NA

    text = html.unescape(str(value))                 # &amp; -> &
    text = text.replace("’", "'").replace("`", "'")  # dấu nháy cong -> thẳng
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return pd.NA

    return brand_manual.get(make_brand_key(text), text.upper())


if "brand" in df.columns:
    brand_before = df["brand"].astype("string")

    # (a) Chuẩn hóa và viết HOA toàn bộ brand
    df["brand"] = df["brand"].apply(normalize_brand)

    # (b) Sửa brand theo mã sản phẩm (ghi đè kết quả ở bước a)
    brand_fixed_by_code = 0

    for code, new_brand in brand_fix_by_code.items():
        mask = df["_product_code_check"].eq(code).fillna(False)

        if mask.sum() != 1:
            raise ValueError(
                f"Mã {code}: cần khớp đúng 1 dòng để sửa brand, "
                f"nhưng hiện khớp {int(mask.sum())} dòng."
            )

        df.loc[mask, "brand"] = new_brand
        brand_fixed_by_code += 1

    brand_changed = int(
        (
            brand_before.fillna("")
            != df["brand"].astype("string").fillna("")
        ).sum()
    )

    # (c) Kiểm tra sau chuẩn hóa
    remaining_blog = int(
        df["brand"].astype("string").str.upper().eq("BLOG LÀM ĐẸP").sum()
    )

    key_groups = (
        df["brand"].dropna()
        .groupby(df["brand"].dropna().map(make_brand_key))
        .nunique()
    )
    remaining_variant_groups = int((key_groups > 1).sum())

    print("\n--- CHUẨN HÓA BRAND ---")
    print(f"Số dòng brand được thay đổi: {brand_changed:,}")
    print(f"Số dòng sửa theo product_code: {brand_fixed_by_code}")
    print(f"Số brand 'BLOG LÀM ĐẸP' còn lại: {remaining_blog}")
    print(f"Số nhóm brand còn biến thể: {remaining_variant_groups}")
    print(f"Số brand khác nhau sau chuẩn hóa: {df['brand'].nunique():,}")
else:
    brand_changed = 0
    brand_fixed_by_code = 0
    print("\nCẢNH BÁO: Không tìm thấy cột brand.")


# ==========================================
# 3. XỬ LÝ DỮ LIỆU THIẾU
# ==========================================
missing_product_code = df["_product_code_check"].isna()
missing_review_count = df["review_count"].isna()

# Chỉ loại sản phẩm thiếu mã sản phẩm
removed_missing_code = df[missing_product_code].copy()

df_clean = df[~missing_product_code].copy()

print("\n--- XỬ LÝ DỮ LIỆU THIẾU ---")
print(f"Sản phẩm thiếu mã: {int(missing_product_code.sum()):,}")
print(f"Sản phẩm thiếu review_count: {int(missing_review_count.sum()):,}")
print(f"Sản phẩm bị loại do thiếu mã: {len(removed_missing_code):,}")


# ==========================================
# 4. XỬ LÝ 6 MÃ SẢN PHẨM TRÙNG ĐÃ KIỂM TRA
# ==========================================
# Mỗi mã được chọn một URL để giữ lại.
# Những mã khác không nằm trong danh sách này không bị tự động xóa.

preferred_urls = {
    "422277481":
        "https://hasaki.vn/san-pham/dau-xa-rejoice-sieu-mem-muot-3-trong-1-300ml-moi-197587.html",

    "422416654":
        "https://hasaki.vn/san-pham/sua-rua-mat-cetaphil-diu-lanh-cho-da-dau-nhay-cam-500ml-127084.html",

    "6974606402909":
        "https://cocolux.com/son-kem-mooekiss-velvet-lip-mud-v09-i.6974606402909",

    "6974606403166":
        "https://cocolux.com/son-kem-mooekiss-velvet-lip-mud-v15-i.6974606403166",

    "6975242809664":
        "https://cocolux.com/che-khuyet-diem-judydoll-traceless-clouch-concealer-02-i.6975242809664",

    "8809711718738":
        "https://cocolux.com/mat-na-mat-jmsolution-honey-luminous-royal-propolis-eye-patch-90g-mau-den-i.8809711718738",
}

# Kiểm tra URL được chọn có tồn tại duy nhất
for code, url in preferred_urls.items():
    matched = df_clean[
        (df_clean["_product_code_check"] == code)
        & (df_clean["url"] == url)
    ]

    if len(matched) != 1:
        raise ValueError(
            f"Mã {code}: URL được chọn phải khớp đúng 1 dòng, "
            f"nhưng hiện khớp {len(matched)} dòng. "
            "Dừng để tránh xóa nhầm dữ liệu. "
            "Hãy kiểm tra product_code và URL trong file đầu vào."
        )

target_codes = set(preferred_urls.keys())

# Xác định các dòng thuộc 6 nhóm mã cần xử lý
target_mask = df_clean["_product_code_check"].isin(target_codes)

# Chọn dòng cần giữ theo URL đã xác định
keep_preferred_mask = pd.Series(
    False,
    index=df_clean.index,
    dtype=bool
)

for code, url in preferred_urls.items():
    keep_preferred_mask |= (
        (df_clean["_product_code_check"] == code)
        & (df_clean["url"] == url)
    )

# Sản phẩm ngoài 6 nhóm mã vẫn được giữ nguyên
keep_mask = (~target_mask) | keep_preferred_mask

removed_duplicate_codes = df_clean[~keep_mask].copy()
df_final = df_clean[keep_mask].copy()

print("\n--- XỬ LÝ MÃ SẢN PHẨM TRÙNG ---")
print(f"Số mã được kiểm tra: {len(preferred_urls)}")
print(f"Số dòng bị loại do trùng mã: {len(removed_duplicate_codes):,}")


# ==========================================
# 5. XỬ LÝ GIÁ VÀ PHẦN TRĂM GIẢM GIÁ
# ==========================================
# Chỉ xử lý trường hợp cả giá gốc và phần trăm giảm giá đều thiếu.
# Không tự động thay thế nếu chỉ thiếu một trong hai trường.

no_discount_mask = (
    df_final["price_original"].isna()
    & df_final["discount_pct"].isna()
)

filled_no_discount = int(no_discount_mask.sum())

df_final.loc[no_discount_mask, "price_original"] = (
    df_final.loc[no_discount_mask, "price"]
)

df_final.loc[no_discount_mask, "discount_pct"] = 0

print("\n--- XỬ LÝ SẢN PHẨM KHÔNG KHUYẾN MÃI ---")
print(
    "Số sản phẩm được điền giá gốc bằng giá bán "
    f"và discount_pct = 0: {filled_no_discount:,}"
)


# ==========================================
# 5.1. XỬ LÝ RATING CỦA SẢN PHẨM CHƯA CÓ ĐÁNH GIÁ
# ==========================================
df_final["review_count"] = pd.to_numeric(
    df_final["review_count"],
    errors="coerce"
)

df_final["rating"] = pd.to_numeric(
    df_final["rating"],
    errors="coerce"
)

# Sản phẩm có 0 lượt đánh giá không có rating thực tế
rating_condition = (
    (df_final["review_count"] == 0)
    & df_final["rating"].notna()
)

rating_changed = int(rating_condition.sum())

df_final.loc[rating_condition, "rating"] = pd.NA

print("\n--- XỬ LÝ RATING ---")
print(
    "Số sản phẩm có 0 lượt đánh giá được chuyển rating "
    f"thành giá trị thiếu: {rating_changed:,}"
)


# ==========================================
# 5.2. XỬ LÝ TRẠNG THÁI TỒN KHO
# ==========================================
# Quy ước:
# 1 = Còn hàng
# 0 = Tạm hết hàng / hết hàng
#
# Lưu ý: Chỉ chuyển giá trị thiếu hoặc không hợp lệ thành 0.
# Các giá trị hợp lệ khác 0 và 1 sẽ gây lỗi để tránh âm thầm
# phân loại sai trạng thái tồn kho.

missing_stock_count = 0

if "in_stock" in df_final.columns:
    stock_before = pd.to_numeric(
        df_final["in_stock"],
        errors="coerce"
    )

    missing_stock_count = int(stock_before.isna().sum())

    invalid_stock_mask = (
        stock_before.notna()
        & ~stock_before.isin([0, 1])
    )

    if invalid_stock_mask.any():
        invalid_values = (
            stock_before[invalid_stock_mask]
            .unique()
            .tolist()
        )

        raise ValueError(
            "Cột in_stock có giá trị ngoài quy ước 0/1: "
            f"{invalid_values}. Hãy kiểm tra trước khi tiếp tục."
        )

    df_final["in_stock"] = stock_before.fillna(0).astype(int)

    print("\n--- XỬ LÝ IN_STOCK ---")
    print(
        "Số dòng in_stock trống hoặc không hợp lệ "
        f"được chuyển thành 0: {missing_stock_count:,}"
    )
    print("Quy ước: 1 = còn hàng; 0 = tạm hết hàng/hết hàng.")
else:
    print("\nCẢNH BÁO: Không tìm thấy cột in_stock.")


# ==========================================
# 6. XÓA CỘT KHÔNG SỬ DỤNG
# ==========================================
removed_columns = [
    col for col in ["skin_type"]
    if col in df_final.columns
]

if removed_columns:
    df_final = df_final.drop(columns=removed_columns)

print("\n--- XÓA CỘT KHÔNG SỬ DỤNG ---")
print(f"Các cột đã xóa: {removed_columns if removed_columns else 'Không có'}")


# ==========================================
# 7. KIỂM TRA SAU LÀM SẠCH
# ==========================================
# Đếm trước khi xóa cột phụ
duplicate_code_count = int(
    df_final["_product_code_check"]
    .duplicated(keep=False)
    .sum()
)

duplicate_url_count = int(
    df_final["url"].duplicated().sum()
)

exact_duplicate_count = int(
    df_final.drop(
        columns=["_product_code_check"],
        errors="ignore"
    ).duplicated().sum()
)

# Xóa cột phụ khỏi dữ liệu đầu ra và báo cáo
df_final = df_final.drop(
    columns=["_product_code_check"],
    errors="ignore"
)

removed_missing_code = removed_missing_code.drop(
    columns=["_product_code_check"],
    errors="ignore"
)

removed_duplicate_codes = removed_duplicate_codes.drop(
    columns=["_product_code_check"],
    errors="ignore"
)


# ==========================================
# 8. XUẤT DỮ LIỆU CUỐI CÙNG
# ==========================================
# Giữ giá trị thiếu thực sự trong df_final để lập báo cáo.
# Chỉ chuyển thành chữ NULL trong bản xuất Excel.

df_export = df_final.copy()

for col in ["volume", "origin", "rating"]:
    if col in df_export.columns:
        df_export[col] = df_export[col].astype(object)
        df_export.loc[df_export[col].isna(), col] = "NULL"

if "in_stock" in df_export.columns:
    df_export["in_stock"] = df_export["in_stock"].astype(int)

# Đảm bảo thư mục đầu ra tồn tại
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

df_export.to_excel(OUTPUT_FILE, index=False)

print("\n--- XUẤT DỮ LIỆU ---")
print("Các ô thiếu trong volume, origin và rating được xuất thành chữ NULL.")
print("in_stock: 1 = còn hàng; 0 = tạm hết hàng/hết hàng.")


# ==========================================
# 9. TẠO BÁO CÁO LÀM SẠCH
# ==========================================
summary = pd.DataFrame({
    "Chỉ tiêu": [
        "Số sản phẩm ban đầu",
        "Số sản phẩm bị xóa do giá dưới 1.000 đồng",
        "Số sản phẩm thiếu product_code",
        "Số sản phẩm thiếu review_count",
        "Số sản phẩm bị loại do thiếu product_code",
        "Số sản phẩm bị loại do trùng mã đã kiểm tra",
        "Số sản phẩm được xử lý không khuyến mãi",
        "Số rating được chuyển thành giá trị thiếu do review_count = 0",
        "Số dòng in_stock thiếu/không hợp lệ được chuyển thành 0",
        "Số cột bị xóa",
        "Số dòng brand được chuẩn hóa (viết HOA)",
        "Số dòng brand sửa theo product_code (Blog làm đẹp)",
        "Số sản phẩm cuối cùng",
        "Số dòng trùng hoàn toàn còn lại",
        "Số URL trùng còn lại",
        "Số dòng thuộc nhóm mã sản phẩm trùng còn lại",
    ],
    "Giá trị": [
        initial_row_count,
        removed_low_price,
        int(missing_product_code.sum()),
        int(missing_review_count.sum()),
        len(removed_missing_code),
        len(removed_duplicate_codes),
        filled_no_discount,
        rating_changed,
        missing_stock_count if "in_stock" in df_final.columns else 0,
        len(removed_columns),
        brand_changed,
        brand_fixed_by_code,
        len(df_final),
        exact_duplicate_count,
        duplicate_url_count,
        duplicate_code_count,
    ]
})

# Báo cáo dữ liệu thiếu dựa trên df_final trước khi chuyển NULL
missing_summary = (
    df_final.isna()
    .sum()
    .rename("So_luong_thieu")
)

with pd.ExcelWriter(REPORT_FILE, engine="openpyxl") as writer:
    summary.to_excel(
        writer,
        sheet_name="Tong_quan",
        index=False
    )

    removed_missing_code.to_excel(
        writer,
        sheet_name="Thieu_product_code",
        index=False
    )

    removed_duplicate_codes.to_excel(
        writer,
        sheet_name="Trung_ma_bi_loai",
        index=False
    )

    missing_summary.to_frame().to_excel(
        writer,
        sheet_name="Du_lieu_thieu"
    )


# ==========================================
# 10. IN KẾT QUẢ
# ==========================================
print("\n" + "=" * 55)
print("KẾT QUẢ SAU LÀM SẠCH")
print("=" * 55)

print(f"Số dòng ban đầu: {initial_row_count:,}")
print(f"Số dòng bị xóa do giá dưới 1.000 đồng: {removed_low_price:,}")
print(f"Số dòng cuối cùng: {len(df_final):,}")
print(f"Số cột cuối cùng: {len(df_final.columns)}")
print(f"Số dòng trùng hoàn toàn còn lại: {exact_duplicate_count}")
print(f"Số URL trùng còn lại: {duplicate_url_count}")
print(f"Số dòng thuộc nhóm mã trùng còn lại: {duplicate_code_count}")

print(f"\nDữ liệu cuối cùng: {OUTPUT_FILE}")
print(f"Báo cáo làm sạch: {REPORT_FILE}")

print("\nSố lượng dữ liệu thiếu theo cột:")
print(df_final.isna().sum())

print("\nHOÀN TẤT!")