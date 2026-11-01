
import pandas as pd
from pathlib import Path

# ==========================================
# 1. KHAI BÁO ĐƯỜNG DẪN
# ==========================================
BASE_DIR = Path(r"D:\Hasaki_Project")

INPUT_FILE = BASE_DIR / "data" / "raw_products.xlsx"
OUTPUT_DIR = BASE_DIR / "cleaning_output"

OUTPUT_FILE = OUTPUT_DIR / "hasaki_cleaned.xlsx"
REPORT_FILE = OUTPUT_DIR / "hasaki_cleaning_report.xlsx"

# ==========================================
# 2. ĐỌC DỮ LIỆU GỐC
# ==========================================
if not INPUT_FILE.exists():
    raise FileNotFoundError(f"Không tìm thấy file: {INPUT_FILE}")

df = pd.read_excel(INPUT_FILE)

print("=" * 60)
print("LÀM SẠCH DỮ LIỆU HASAKI")
print("=" * 60)

print(f"Số dòng ban đầu: {len(df):,}")
print(f"Số cột ban đầu: {len(df.columns)}")

initial_rows = len(df)
initial_columns = len(df.columns)
initial_missing = df.isna().sum()

# ==========================================
# 3. CHUẨN HÓA KIỂU DỮ LIỆU
# ==========================================
df["review_count"] = pd.to_numeric(
    df["review_count"], errors="coerce"
)

# ==========================================
# 4. SỬA 4 GIÁ TRỊ REVIEW_COUNT BẤT THƯỜNG
# ==========================================
name_mask = df["name"].astype(str).str.contains(
    "Máy Sấy Tóc Philips",
    case=False,
    na=False
)

review_mask = df["review_count"].eq(39728743)

mask = name_mask & review_mask
fixed_count = int(mask.sum())

print(f"\nSố sản phẩm tìm thấy cần sửa: {fixed_count}")

if fixed_count != 4:
    raise ValueError(
        f"Chỉ tìm thấy {fixed_count}/4 sản phẩm cần sửa. "
        "Chương trình dừng để tránh thay đổi dữ liệu sai."
    )

print("\nCác sản phẩm được sửa:")
print(
    df.loc[mask, ["name", "review_count"]].to_string(index=False)
)

df.loc[mask, "review_count"] = 0

# ==========================================
# 5. LOẠI CỘT SOLD NẾU TOÀN BỘ GIÁ TRỊ TRỐNG
# ==========================================
removed_columns = []

if "sold" in df.columns and df["sold"].isna().all():
    df.drop(columns=["sold"], inplace=True)
    removed_columns.append("sold")
    print("\nĐã loại cột sold vì toàn bộ giá trị đều trống.")

# ==========================================
# 6. KIỂM TRA DỮ LIỆU SAU LÀM SẠCH
# ==========================================
final_missing = df.isna().sum()

missing_report = pd.DataFrame({
    "missing_before": initial_missing.reindex(df.columns).fillna(0).astype(int),
    "missing_after": final_missing.astype(int),
    "missing_percent_after": (
        final_missing / len(df) * 100
    ).round(2)
})

summary = pd.DataFrame({
    "Hạng mục": [
        "Số dòng ban đầu",
        "Số dòng sau làm sạch",
        "Số cột ban đầu",
        "Số cột sau làm sạch",
        "Số review_count đã sửa",
        "Số dòng trùng hoàn toàn",
        "Số URL trùng",
        "Số mã sản phẩm trùng",
        "Số review_count còn bằng 39728743",
        "Cột đã loại bỏ"
    ],
    "Kết quả": [
        initial_rows,
        len(df),
        initial_columns,
        len(df.columns),
        fixed_count,
        int(df.duplicated().sum()),
        int(df["url"].duplicated().sum()),
        int(df["product_code"].dropna().duplicated().sum()),
        int(df["review_count"].eq(39728743).sum()),
        ", ".join(removed_columns) if removed_columns else "Không"
    ]
})

# ==========================================
# 7. XUẤT FILE
# ==========================================
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df.to_excel(OUTPUT_FILE, index=False)

with pd.ExcelWriter(REPORT_FILE, engine="openpyxl") as writer:
    summary.to_excel(
        writer,
        sheet_name="Tong_quan",
        index=False
    )

    missing_report.to_excel(
        writer,
        sheet_name="Du_lieu_thieu"
    )

# ==========================================
# 8. HIỂN THỊ KẾT QUẢ
# ==========================================
print("\n" + "=" * 60)
print("KẾT QUẢ SAU LÀM SẠCH")
print("=" * 60)

print(f"Số dòng: {len(df):,}")
print(f"Số cột: {len(df.columns)}")
print(f"Số review_count đã sửa: {fixed_count}")
print(
    "Số review_count còn bất thường:",
    int(df["review_count"].eq(39728743).sum())
)

print("\nSố sản phẩm theo nguồn:")
print(df["source"].value_counts().to_string())

print("\nSố giá trị thiếu:")
print(final_missing.to_string())

print(f"\nFile dữ liệu: {OUTPUT_FILE}")
print(f"File báo cáo: {REPORT_FILE}")

print("\nHOÀN THÀNH LÀM SẠCH HASAKI!")