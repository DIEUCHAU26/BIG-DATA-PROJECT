
from pathlib import Path
import pandas as pd

# ==========================================
# 1. KHAI BÁO ĐƯỜNG DẪN
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "raw_products.xlsx"
OUTPUT_DIR = BASE_DIR / "cleaning_output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "cocolux_cleaned.xlsx"
REPORT_FILE = OUTPUT_DIR / "cocolux_cleaning_report.xlsx"

# ==========================================
# 2. ĐỌC DỮ LIỆU COCOLUX
# ==========================================

df = pd.read_excel(INPUT_FILE, sheet_name="cocolux")

initial_rows = len(df)
initial_columns = len(df.columns)

print("=" * 50)
print("BẮT ĐẦU LÀM SẠCH DỮ LIỆU COCOLUX")
print("=" * 50)
print("Số dòng ban đầu:", initial_rows)
print("Số cột ban đầu:", initial_columns)

# Thống kê giá trị thiếu trước khi xử lý
missing_before = df.isna().sum()

# ==========================================
# 3. XÓA SẢN PHẨM THIẾU PRICE HOẶC PRODUCT_CODE
# ==========================================

missing_price = df["price"].isna()
missing_product_code = df["product_code"].isna()

print("\nSố sản phẩm thiếu price:", int(missing_price.sum()))
print(
    "Số sản phẩm thiếu product_code:",
    int(missing_product_code.sum())
)

# Xóa sản phẩm nếu thiếu ít nhất một trong hai trường
remove_mask = missing_price | missing_product_code
removed_products = df.loc[remove_mask].copy()

print("Tổng số sản phẩm bị xóa:", len(removed_products))

if not removed_products.empty:
    print("\nDanh sách sản phẩm bị xóa:")
    print(
        removed_products[
            ["name", "price", "product_code"]
        ].to_string(index=False)
    )

df = df.loc[~remove_mask].copy()

print("Số sản phẩm còn lại:", len(df))

# ==========================================
# 4. CHUẨN HÓA DỮ LIỆU
# ==========================================

# Loại bỏ khoảng trắng thừa ở các cột văn bản
text_columns = [
    "source",
    "category_group",
    "category",
    "url",
    "name",
    "brand",
    "volume",
    "origin",
    "skin_type",
]

for col in text_columns:
    if col in df.columns:
        df[col] = df[col].map(
            lambda value: (
                value.strip() if isinstance(value, str)
                else value
            )
        )

# Chuyển các cột số về kiểu dữ liệu số
numeric_columns = [
    "price",
    "price_original",
    "discount_pct",
    "rating",
    "review_count",
    "in_stock",
]

for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# Chuẩn hóa product_code thành chuỗi
# Giữ mã sản phẩm không bị hiển thị dạng số thập phân
def normalize_product_code(value):
    if pd.isna(value):
        return pd.NA

    if isinstance(value, (int, float)) and float(value).is_integer():
        return str(int(value))

    return str(value).strip()


if "product_code" in df.columns:
    df["product_code"] = df["product_code"].map(
        normalize_product_code
    )

# ==========================================
# 5. KIỂM TRA GIÁ TRỊ BẤT THƯỜNG
# ==========================================

issues = []

def record_issues(mask, column, description):
    """Ghi nhận các giá trị bất thường, không tự ý sửa."""
    for idx in df.index[mask]:
        issues.append({
            "row_index": idx,
            "url": df.at[idx, "url"] if "url" in df.columns else None,
            "name": df.at[idx, "name"] if "name" in df.columns else None,
            "column": column,
            "issue": description,
            "value": df.at[idx, column],
        })


# Giá bán âm
if "price" in df.columns:
    mask = df["price"].notna() & (df["price"] < 0)
    record_issues(mask, "price", "Giá bán âm")

# Giá gốc âm
if "price_original" in df.columns:
    mask = (
        df["price_original"].notna()
        & (df["price_original"] < 0)
    )
    record_issues(mask, "price_original", "Giá gốc âm")

# Rating ngoài khoảng 0 đến 5
if "rating" in df.columns:
    mask = (
        df["rating"].notna()
        & ~df["rating"].between(0, 5)
    )
    record_issues(mask, "rating", "Rating ngoài khoảng 0-5")

# Số lượt đánh giá âm
if "review_count" in df.columns:
    mask = (
        df["review_count"].notna()
        & (df["review_count"] < 0)
    )
    record_issues(
        mask,
        "review_count",
        "Số lượt đánh giá âm"
    )

# Phần trăm giảm giá ngoài khoảng 0 đến 100
if "discount_pct" in df.columns:
    mask = (
        df["discount_pct"].notna()
        & ~df["discount_pct"].between(0, 100)
    )
    record_issues(
        mask,
        "discount_pct",
        "Phần trăm giảm giá ngoài khoảng 0-100"
    )

# ==========================================
# 6. LOẠI BỎ CỘT TOÀN GIÁ TRỊ THIẾU
# ==========================================

removed_columns = []

for col in df.columns.tolist():
    if df[col].isna().all():
        removed_columns.append(col)
        df.drop(columns=[col], inplace=True)
        print(f"Đã loại bỏ cột {col} vì toàn bộ giá trị đều thiếu.")

# ==========================================
# 7. TỔNG HỢP KẾT QUẢ
# ==========================================

missing_after = df.isna().sum()

summary = pd.DataFrame({
    "Chỉ tiêu": [
        "Số dòng ban đầu",
        "Số cột ban đầu",
        "Số sản phẩm thiếu price",
        "Số sản phẩm thiếu product_code",
        "Tổng số sản phẩm bị xóa",
        "Số dòng sau làm sạch",
        "Số cột sau làm sạch",
        "Số dòng trùng hoàn toàn còn lại",
        "Số URL trùng còn lại",
        "Số trường hợp bất thường được phát hiện",
    ],
    "Giá trị": [
        initial_rows,
        initial_columns,
        int(missing_price.sum()),
        int(missing_product_code.sum()),
        len(removed_products),
        len(df),
        len(df.columns),
        int(df.duplicated().sum()),
        int(df["url"].duplicated().sum())
        if "url" in df.columns else 0,
        len(issues),
    ],
})

missing_report = pd.DataFrame({
    "Tên cột": missing_before.index,
    "Số giá trị thiếu ban đầu": missing_before.values,
    "Số giá trị thiếu sau làm sạch": [
        int(missing_after[col])
        if col in missing_after.index else 0
        for col in missing_before.index
    ],
})

removed_columns_report = pd.DataFrame({
    "Cột đã loại bỏ": removed_columns
})

issues_report = pd.DataFrame(
    issues,
    columns=[
        "row_index",
        "url",
        "name",
        "column",
        "issue",
        "value",
    ],
)

# ==========================================
# 8. XUẤT FILE DỮ LIỆU VÀ BÁO CÁO
# ==========================================

df.to_excel(OUTPUT_FILE, index=False)

with pd.ExcelWriter(REPORT_FILE) as writer:
    summary.to_excel(
        writer,
        sheet_name="Tong_quan",
        index=False
    )

    missing_report.to_excel(
        writer,
        sheet_name="Gia_tri_thieu",
        index=False
    )

    removed_columns_report.to_excel(
        writer,
        sheet_name="Cot_da_loai",
        index=False
    )

    issues_report.to_excel(
        writer,
        sheet_name="Bat_thuong",
        index=False
    )

# ==========================================
# 9. IN KẾT QUẢ CUỐI CÙNG
# ==========================================

print("\n" + "=" * 50)
print("KẾT QUẢ LÀM SẠCH COCOLUX")
print("=" * 50)

print(f"Số dòng ban đầu: {initial_rows}")
print(f"Số sản phẩm bị xóa: {len(removed_products)}")
print(f"Số dòng còn lại: {len(df)}")
print(f"Số cột còn lại: {len(df.columns)}")
print("Số dòng trùng hoàn toàn:", int(df.duplicated().sum()))

if "url" in df.columns:
    print("Số URL trùng:", int(df["url"].duplicated().sum()))

print("\nSố giá trị thiếu sau làm sạch:")
print(df.isna().sum().to_string())

print("\nSố trường hợp bất thường được phát hiện:", len(issues))
print("File dữ liệu:", OUTPUT_FILE)
print("File báo cáo:", REPORT_FILE)
print("\nHOÀN TẤT LÀM SẠCH COCOLUX!")
