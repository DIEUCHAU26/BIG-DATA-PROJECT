"""
Sửa cột brand trực tiếp trên file Excel products_clean.xlsx:
  1. Chuẩn hóa brand về chữ HOA (Cocoon / COCOON -> COCOON), gộp các biến thể.
  2. Sửa 2 sản phẩm có brand "Blog làm đẹp" theo product_code.

Chỉ các ô ở cột brand bị thay đổi; mọi cột khác giữ nguyên.
File gốc được sao lưu thành products_clean_backup.xlsx trước khi ghi.

Cách chạy (đặt file này trong thư mục scripts/):
    python scripts/fix_brand.py
    python scripts/fix_brand.py duong/dan/toi/products_clean.xlsx
"""

import html
import re
import shutil
import sys
import unicodedata
from pathlib import Path

from openpyxl import load_workbook

# ==========================================
# 1. CẤU HÌNH
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent

# Mặc định: cleaning_output/products_clean.xlsx (có thể truyền đường dẫn khác)
INPUT_FILE = (
    Path(sys.argv[1]).expanduser().resolve()
    if len(sys.argv) > 1
    else BASE_DIR / "cleaning_output" / "products_clean.xlsx"
)
BACKUP_FILE = INPUT_FILE.with_name(INPUT_FILE.stem + "_backup.xlsx")

# True: sao lưu file gốc thành products_clean_backup.xlsx trước khi ghi
# False: ghi thẳng, không tạo thêm file nào
MAKE_BACKUP = True

BRAND_COLUMN = "brand"
CODE_COLUMN = "product_code"

# Sản phẩm sửa riêng theo mã sản phẩm (brand "Blog làm đẹp")
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


# ==========================================
# 2. HÀM CHUẨN HÓA
# ==========================================
def make_brand_key(value):
    """Tạo khóa so sánh: bỏ dấu, bỏ ký tự đặc biệt, chữ thường."""
    text = unicodedata.normalize("NFD", str(value))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[^a-z0-9]", "", text.lower())


def normalize_brand(value):
    """Giải mã &amp;, thống nhất dấu nháy, bỏ khoảng trắng thừa, viết HOA."""
    if value is None:
        return None

    text = html.unescape(str(value))                 # &amp; -> &
    text = text.replace("’", "'").replace("`", "'")  # dấu nháy cong -> thẳng
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return None

    return brand_manual.get(make_brand_key(text), text.upper())


def code_to_text(value):
    """Đưa mã sản phẩm về chuỗi: 422277481.0 -> 422277481."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return re.sub(r"\.0$", "", str(value).strip())


# ==========================================
# 3. ĐỌC FILE
# ==========================================
if not INPUT_FILE.exists():
    sys.exit(
        f"LỖI: Không tìm thấy file {INPUT_FILE}\n"
        "Hãy đặt products_clean.xlsx vào thư mục cleaning_output/ "
        "hoặc truyền đường dẫn: python fix_brand.py <đường_dẫn>"
    )

print("=" * 55)
print("SỬA BRAND TRÊN FILE EXCEL")
print("=" * 55)
print(f"File: {INPUT_FILE}")

wb = load_workbook(INPUT_FILE)
ws = wb.active

headers = {
    str(cell.value).strip(): cell.column
    for cell in ws[1]
    if cell.value is not None
}

for required in (BRAND_COLUMN, CODE_COLUMN):
    if required not in headers:
        sys.exit(f"LỖI: Không tìm thấy cột '{required}'. Các cột hiện có: {list(headers)}")

brand_col = headers[BRAND_COLUMN]
code_col = headers[CODE_COLUMN]

# ==========================================
# 4. KIỂM TRA 2 MÃ SẢN PHẨM TRƯỚC KHI SỬA
# ==========================================
rows_by_code = {code: [] for code in brand_fix_by_code}

for row in range(2, ws.max_row + 1):
    code = code_to_text(ws.cell(row=row, column=code_col).value)
    if code in rows_by_code:
        rows_by_code[code].append(row)

for code, rows in rows_by_code.items():
    if len(rows) != 1:
        sys.exit(
            f"LỖI: Mã {code} cần khớp đúng 1 dòng, nhưng hiện khớp {len(rows)} dòng. "
            "Dừng để tránh sửa nhầm dữ liệu (file chưa bị thay đổi)."
        )

# ==========================================
# 5. SỬA BRAND
# ==========================================
brand_changed = 0
brands_before = set()
brands_after = set()

for row in range(2, ws.max_row + 1):
    cell = ws.cell(row=row, column=brand_col)
    old_value = cell.value
    new_value = normalize_brand(old_value)

    if old_value is not None:
        brands_before.add(str(old_value))

    if new_value != old_value:
        cell.value = new_value
        brand_changed += 1

# Sửa theo mã sản phẩm (ghi đè kết quả ở trên)
brand_fixed_by_code = 0

for code, new_brand in brand_fix_by_code.items():
    row = rows_by_code[code][0]
    cell = ws.cell(row=row, column=brand_col)

    print(f"Mã {code}: '{cell.value}' -> '{new_brand}'")

    if cell.value != new_brand:
        cell.value = new_brand
        brand_fixed_by_code += 1

for row in range(2, ws.max_row + 1):
    value = ws.cell(row=row, column=brand_col).value
    if value is not None:
        brands_after.add(str(value))

# ==========================================
# 6. KIỂM TRA SAU KHI SỬA
# ==========================================
remaining_blog = sum(1 for b in brands_after if b.upper() == "BLOG LÀM ĐẸP")
remaining_not_upper = sum(1 for b in brands_after if b != b.upper())

key_groups = {}
for b in brands_after:
    key_groups.setdefault(make_brand_key(b), set()).add(b)
remaining_variant_groups = sum(1 for v in key_groups.values() if len(v) > 1)

print("\n--- KẾT QUẢ ---")
print(f"Số brand khác nhau trước khi sửa: {len(brands_before):,}")
print(f"Số brand khác nhau sau khi sửa:   {len(brands_after):,}")
print(f"Số ô brand được thay đổi (HOA/gộp): {brand_changed:,}")
print(f"Số sản phẩm Blog làm đẹp đã sửa:  {len(brand_fix_by_code)}")
print(f"Brand 'BLOG LÀM ĐẸP' còn lại:     {remaining_blog}")
print(f"Brand chưa viết HOA còn lại:      {remaining_not_upper}")
print(f"Nhóm brand còn biến thể:          {remaining_variant_groups}")

# ==========================================
# 7. SAO LƯU VÀ GHI FILE
# ==========================================
if MAKE_BACKUP:
    shutil.copy2(INPUT_FILE, BACKUP_FILE)
    print(f"\nĐã sao lưu file gốc: {BACKUP_FILE}")

try:
    wb.save(INPUT_FILE)
except PermissionError:
    sys.exit(
        "LỖI: Không ghi được file. Hãy đóng products_clean.xlsx trong Excel rồi chạy lại."
    )

print(f"Đã lưu kết quả vào: {INPUT_FILE}")
print("\nHOÀN TẤT!")