
from pathlib import Path
import pandas as pd

# ==========================================
# 1. KHAI BÁO ĐƯỜNG DẪN
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "cleaning_output"

HASAKI_FILE = INPUT_DIR / "hasaki_cleaned.xlsx"
COCOLUX_FILE = INPUT_DIR / "cocolux_cleaned.xlsx"

OUTPUT_FILE = INPUT_DIR / "products_merged.xlsx"
REPORT_FILE = INPUT_DIR / "merge_report.xlsx"

# ==========================================
# 2. ĐỌC DỮ LIỆU
# ==========================================

hasaki = pd.read_excel(HASAKI_FILE)
cocolux = pd.read_excel(COCOLUX_FILE)

print("=" * 55)
print("BẮT ĐẦU CHUẨN HÓA VÀ GỘP DỮ LIỆU")
print("=" * 55)

print("\nHASAKI")
print("Số dòng:", len(hasaki))
print("Số cột:", len(hasaki.columns))

print("\nCOCOLUX")
print("Số dòng:", len(cocolux))
print("Số cột:", len(cocolux.columns))

# ==========================================
# 3. KIỂM TRA CẤU TRÚC CỘT
# ==========================================

hasaki_columns = set(hasaki.columns)
cocolux_columns = set(cocolux.columns)

only_hasaki = sorted(hasaki_columns - cocolux_columns)
only_cocolux = sorted(cocolux_columns - hasaki_columns)

print("\nCác cột chỉ có ở Hasaki:", only_hasaki)
print("Các cột chỉ có ở Cocolux:", only_cocolux)

# Hợp nhất cấu trúc cột.
# Cột không có ở một nguồn sẽ được bổ sung giá trị thiếu.
all_columns = list(hasaki.columns)

for col in cocolux.columns:
    if col not in all_columns:
        all_columns.append(col)

hasaki = hasaki.reindex(columns=all_columns)
cocolux = cocolux.reindex(columns=all_columns)

# ==========================================
# 4. CHUẨN HÓA KIỂU DỮ LIỆU
# ==========================================

# Các cột số cần có cùng kiểu dữ liệu
numeric_columns = [
    "price",
    "price_original",
    "discount_pct",
    "rating",
    "review_count",
    "in_stock",
]

for col in numeric_columns:
    if col in all_columns:
        hasaki[col] = pd.to_numeric(
            hasaki[col],
            errors="coerce"
        )
        cocolux[col] = pd.to_numeric(
            cocolux[col],
            errors="coerce"
        )

# Các cột văn bản cần thống nhất kiểu dữ liệu
text_columns = [
    "source",
    "category_group",
    "category",
    "url",
    "name",
    "brand",
    "product_code",
    "volume",
    "origin",
    "skin_type",
    "scraped_at",
]

for col in text_columns:
    if col in all_columns:
        hasaki[col] = hasaki[col].astype("string")
        cocolux[col] = cocolux[col].astype("string")

# ==========================================
# 5. GỘP HAI NGUỒN
# ==========================================

merged = pd.concat(
    [hasaki, cocolux],
    ignore_index=True,
    sort=False
)

expected_rows = len(hasaki) + len(cocolux)

print("\n===== KẾT QUẢ GỘP =====")
print("Tổng dòng dự kiến:", expected_rows)
print("Tổng dòng sau gộp:", len(merged))
print("Tổng số cột:", len(merged.columns))

# Kiểm tra nguồn dữ liệu
print("\nSố sản phẩm theo nguồn:")
print(merged["source"].value_counts(dropna=False).to_string())

# ==========================================
# 6. KIỂM TRA CHẤT LƯỢNG DỮ LIỆU
# ==========================================

# Không tự động xóa sản phẩm trùng.
# Chỉ thống kê để đánh giá trước khi quyết định xử lý.
duplicate_rows = int(merged.duplicated().sum())

duplicate_urls = (
    int(merged["url"].duplicated().sum())
    if "url" in merged.columns else 0
)

missing_report = pd.DataFrame({
    "Tên cột": merged.columns,
    "Số giá trị thiếu": [
        int(merged[col].isna().sum())
        for col in merged.columns
    ],
    "Tỷ lệ thiếu (%)": [
        round(merged[col].isna().mean() * 100, 2)
        for col in merged.columns
    ],
})

source_report = (
    merged["source"]
    .value_counts(dropna=False)
    .rename_axis("Nguồn")
    .reset_index(name="Số sản phẩm")
)

summary = pd.DataFrame({
    "Chỉ tiêu": [
        "Số dòng Hasaki",
        "Số dòng Cocolux",
        "Tổng dòng dự kiến",
        "Tổng dòng sau gộp",
        "Số cột sau gộp",
        "Số dòng trùng hoàn toàn",
        "Số URL trùng",
    ],
    "Giá trị": [
        len(hasaki),
        len(cocolux),
        expected_rows,
        len(merged),
        len(merged.columns),
        duplicate_rows,
        duplicate_urls,
    ],
})

# ==========================================
# 7. XUẤT FILE
# ==========================================

merged.to_excel(
    OUTPUT_FILE,
    index=False
)

with pd.ExcelWriter(REPORT_FILE) as writer:
    summary.to_excel(
        writer,
        sheet_name="Tong_quan",
        index=False
    )

    source_report.to_excel(
        writer,
        sheet_name="Theo_nguon",
        index=False
    )

    missing_report.to_excel(
        writer,
        sheet_name="Gia_tri_thieu",
        index=False
    )

# ==========================================
# 8. IN KẾT QUẢ CUỐI CÙNG
# ==========================================

print("\n===== KIỂM TRA SAU GỘP =====")
print("Số dòng trùng hoàn toàn:", duplicate_rows)
print("Số URL trùng:", duplicate_urls)

print("\nSố giá trị thiếu theo cột:")
print(merged.isna().sum().to_string())

print("\nFile dữ liệu tổng hợp:", OUTPUT_FILE)
print("File báo cáo:", REPORT_FILE)

if len(merged) != expected_rows:
    print("CẢNH BÁO: Số dòng sau gộp không khớp dự kiến!")
else:
    print("\nĐã gộp đủ số dòng từ hai nguồn.")

print("\nHOÀN TẤT!")
