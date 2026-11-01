
from pathlib import Path

import pandas as pd


# =========================
# 1. KHAI BÁO ĐƯỜNG DẪN
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "cleaning_output" / "products_final.xlsx"
OUTPUT_DIR = BASE_DIR / "cleaning_output"
REPORT_FILE = OUTPUT_DIR / "final_data_quality_report.xlsx"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# 2. ĐỌC DỮ LIỆU
# =========================

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Không tìm thấy file dữ liệu: {INPUT_FILE}"
    )

df = pd.read_excel(INPUT_FILE)

print("=" * 60)
print("KIỂM TRA CHẤT LƯỢNG DỮ LIỆU SẢN PHẨM")
print("=" * 60)

print(f"\nFile: {INPUT_FILE.name}")
print(f"Số dòng: {len(df):,}")
print(f"Số cột: {len(df.columns)}")


# =========================
# 3. KIỂM TRA GIÁ TRỊ THIẾU
# =========================

missing_count = df.isna().sum()
missing_percent = (missing_count / len(df) * 100).round(2)

missing_report = pd.DataFrame({
    "column": df.columns,
    "missing_count": missing_count.reindex(df.columns).values,
    "missing_percent": missing_percent.reindex(df.columns).values,
    "data_type": df.dtypes.astype(str).reindex(df.columns).values
})

missing_report = missing_report.sort_values(
    "missing_count",
    ascending=False
)

print("\n--- GIÁ TRỊ THIẾU ---")
print(
    missing_report[
        missing_report["missing_count"] > 0
    ].to_string(index=False)
)


# =========================
# 4. KIỂM TRA TRÙNG LẶP
# =========================

duplicate_rows = int(df.duplicated().sum())

if "url" in df.columns:
    duplicate_urls = int(
        df["url"].dropna().duplicated().sum()
    )
else:
    duplicate_urls = None

if "product_code" in df.columns:
    duplicate_codes = int(
        df["product_code"].dropna().duplicated().sum()
    )
else:
    duplicate_codes = None

print("\n--- KIỂM TRA TRÙNG LẶP ---")
print(f"Dòng trùng hoàn toàn: {duplicate_rows:,}")
print(f"URL trùng: {duplicate_urls}")
print(f"Mã sản phẩm trùng: {duplicate_codes}")


# =========================
# 5. KIỂM TRA GIÁ TRỊ BẤT THƯỜNG
# =========================

anomaly_results = []


def add_anomaly(issue, mask, description):
    """Ghi nhận các dòng có dấu hiệu bất thường."""
    mask = mask.fillna(False)

    count = int(mask.sum())

    anomaly_results.append({
        "issue": issue,
        "count": count,
        "description": description
    })

    print(f"{issue}: {count:,} dòng")


# Chuyển tạm các cột số sang dạng numeric để kiểm tra.
# Không ghi đè dữ liệu trong DataFrame gốc.

numeric_columns = [
    "price",
    "price_original",
    "discount_pct",
    "rating",
    "review_count",
    "in_stock"
]

numeric_data = {}

for col in numeric_columns:
    if col in df.columns:
        numeric_data[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )


print("\n--- KIỂM TRA BẤT THƯỜNG ---")

if "price" in numeric_data:
    add_anomaly(
        "Giá hiện tại <= 0",
        numeric_data["price"].notna()
        & (numeric_data["price"] <= 0),
        "Giá hiện tại phải lớn hơn 0."
    )

if "price_original" in numeric_data:
    add_anomaly(
        "Giá gốc <= 0",
        numeric_data["price_original"].notna()
        & (numeric_data["price_original"] <= 0),
        "Giá gốc bằng 0 hoặc âm cần được kiểm tra."
    )

if "price" in numeric_data and "price_original" in numeric_data:
    current_price = numeric_data["price"]
    original_price = numeric_data["price_original"]

    add_anomaly(
        "Giá gốc thấp hơn giá hiện tại",
        current_price.notna()
        & original_price.notna()
        & (original_price < current_price),
        "Kiểm tra trường hợp giá gốc thấp hơn giá hiện tại."
    )

if "discount_pct" in numeric_data:
    discount = numeric_data["discount_pct"]

    add_anomaly(
        "Giảm giá ngoài khoảng 0-100%",
        discount.notna()
        & ((discount < 0) | (discount > 100)),
        "Phần trăm giảm giá phải nằm trong khoảng 0-100."
    )

if "rating" in numeric_data:
    rating = numeric_data["rating"]

    add_anomaly(
        "Điểm đánh giá ngoài khoảng 0-5",
        rating.notna()
        & ((rating < 0) | (rating > 5)),
        "Điểm đánh giá phải nằm trong khoảng 0-5."
    )

if "review_count" in numeric_data:
    reviews = numeric_data["review_count"]

    add_anomaly(
        "Số lượt đánh giá âm",
        reviews.notna() & (reviews < 0),
        "Số lượt đánh giá không được âm."
    )

    add_anomaly(
        "Số lượt đánh giá không phải số nguyên",
        reviews.notna()
        & ((reviews % 1) != 0),
        "Kiểm tra số lượt đánh giá có phần thập phân."
    )

if "in_stock" in numeric_data:
    stock = numeric_data["in_stock"]

    add_anomaly(
        "Số lượng tồn kho âm",
        stock.notna() & (stock < 0),
        "Số lượng tồn kho không được âm."
    )


# =========================
# 6. KIỂM TRA GIẢM GIÁ
# =========================

discount_details = []

required_price_columns = {
    "price",
    "price_original",
    "discount_pct"
}

if required_price_columns.issubset(df.columns):
    current_price = numeric_data["price"]
    original_price = numeric_data["price_original"]
    recorded_discount = numeric_data["discount_pct"]

    valid_prices = (
        current_price.notna()
        & original_price.notna()
        & (original_price > 0)
        & (current_price > 0)
        & (original_price >= current_price)
    )

    # Tính lại phần trăm giảm giá từ hai mức giá.
    calculated_discount = (
        (original_price - current_price)
        / original_price
        * 100
    )

    comparable = valid_prices & recorded_discount.notna()

    difference = (
        recorded_discount - calculated_discount
    ).abs()

    mismatch = comparable & (difference > 1)

    discount_details = [
        {
            "metric": "Sản phẩm có đủ giá hợp lệ để đối chiếu",
            "value": int(valid_prices.sum()),
            "note": "Có giá hiện tại và giá gốc hợp lệ."
        },
        {
            "metric": "Sản phẩm có đủ dữ liệu để so sánh giảm giá",
            "value": int(comparable.sum()),
            "note": "Có giá hợp lệ và phần trăm giảm giá."
        },
        {
            "metric": "Giảm giá lệch trên 1 điểm phần trăm",
            "value": int(mismatch.sum()),
            "note": "Cần xem lại cách tính hoặc dữ liệu nguồn."
        }
    ]

    print("\n--- ĐỐI CHIẾU PHẦN TRĂM GIẢM GIÁ ---")

    for item in discount_details:
        print(f"{item['metric']}: {item['value']:,}")


# =========================
# 7. KIỂM TRA CÁC TRƯỜNG BẮT BUỘC
# =========================

required_columns = [
    "name",
    "brand",
    "product_code",
    "price",
    "url",
    "category",
    "source"
]

required_results = []

for col in required_columns:
    if col not in df.columns:
        required_results.append({
            "column": col,
            "missing_count": None,
            "status": "THIẾU CỘT"
        })
        continue

    values = df[col]

    if values.dtype == "object" or isinstance(
        values.dtype, pd.StringDtype
    ):
        blank_mask = values.astype("string").str.strip().eq("")
        missing_mask = values.isna() | blank_mask
    else:
        missing_mask = values.isna()

    count = int(missing_mask.sum())

    required_results.append({
        "column": col,
        "missing_count": count,
        "status": "ĐẠT" if count == 0 else "CẦN KIỂM TRA"
    })

print("\n--- CÁC TRƯỜNG BẮT BUỘC ---")
print(pd.DataFrame(required_results).to_string(index=False))


# =========================
# 8. KIỂM TRA Ô CHỈ CHỨA KHOẢNG TRẮNG
# =========================

blank_results = []

for col in df.select_dtypes(include=["object", "string"]).columns:
    blank_count = int(
        (
            df[col].notna()
            & df[col].astype("string").str.strip().eq("")
        ).sum()
    )

    if blank_count > 0:
        blank_results.append({
            "column": col,
            "blank_count": blank_count
        })

print("\n--- Ô CHỈ CHỨA KHOẢNG TRẮNG ---")

if blank_results:
    print(pd.DataFrame(blank_results).to_string(index=False))
else:
    print("Không phát hiện ô chỉ chứa khoảng trắng.")


# =========================
# 9. TỔNG HỢP KẾT QUẢ
# =========================

summary = pd.DataFrame([
    {"metric": "Tổng số sản phẩm", "value": len(df)},
    {"metric": "Tổng số cột", "value": len(df.columns)},
    {"metric": "Dòng trùng hoàn toàn", "value": duplicate_rows},
    {"metric": "URL trùng", "value": duplicate_urls},
    {"metric": "Mã sản phẩm trùng", "value": duplicate_codes},
    {
        "metric": "Tổng số ô thiếu",
        "value": int(df.isna().sum().sum())
    },
    {
        "metric": "Số cột có giá trị thiếu",
        "value": int((df.isna().sum() > 0).sum())
    }
])

anomaly_report = pd.DataFrame(anomaly_results)

required_report = pd.DataFrame(required_results)

blank_report = pd.DataFrame(
    blank_results,
    columns=["column", "blank_count"]
)

discount_report = pd.DataFrame(
    discount_details,
    columns=["metric", "value", "note"]
)


# =========================
# 10. XUẤT BÁO CÁO EXCEL
# =========================

with pd.ExcelWriter(REPORT_FILE, engine="openpyxl") as writer:
    summary.to_excel(
        writer,
        sheet_name="Summary",
        index=False
    )

    missing_report.to_excel(
        writer,
        sheet_name="Missing Values",
        index=False
    )

    anomaly_report.to_excel(
        writer,
        sheet_name="Anomalies",
        index=False
    )

    required_report.to_excel(
        writer,
        sheet_name="Required Fields",
        index=False
    )

    blank_report.to_excel(
        writer,
        sheet_name="Blank Cells",
        index=False
    )

    discount_report.to_excel(
        writer,
        sheet_name="Discount Check",
        index=False
    )

print("\n" + "=" * 60)
print("HOÀN TẤT KIỂM TRA DỮ LIỆU")
print(f"Báo cáo được lưu tại:\n{REPORT_FILE}")
print("=" * 60)
