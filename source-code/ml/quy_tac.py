# Luật và tham số dùng chung cho huấn luyện và web.
# Sửa luật ở đây, KHÔNG viết lại luật trong script khác.
import json, os
import numpy as np, pandas as pd

# ===== Đường dẫn =====
# Code ở <repo>/source-code/ml/, dữ liệu ML ở <repo>/dataset/ml/ (thư mục riêng, không lẫn dữ liệu phần khác)
THU_MUC_ML = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.normpath(os.path.join(THU_MUC_ML, "..", "..", "dataset", "ml")) + os.sep

# ===== Tham số =====
SO_BRAND_TOP = 150            # số thương hiệu giữ tên khi one-hot, còn lại gộp "Khác"
NGUONG_Z_GIA = 3              # |z| của phần dư giá vượt ngưỡng này là giá bất thường
CONTAMINATION = 0.02          # tỷ lệ bất thường giả định cho Isolation Forest / LOF
RANDOM_STATE = 42

# ===== Phân loại sản phẩm theo tên =====
# Thứ tự quan trọng: luật đứng trước thắng.
LUAT_LOAI_SP = [
    ("ve_sinh_pn",    r"băng vệ sinh|tampon|gel vệ sinh"),
    ("dao_cao",       r"dao cạo|lưỡi dao"),
    ("thiet_bi",      r"máy |bàn chải điện"),
    ("kem_danh_rang", r"đánh răng"),
    ("long_mi_gia",   r"lông mi"),
    ("khan_giay",     r"khăn|giấy|bông tẩy trang"),
    # Không dùng "bông " chung chung: bắt nhầm "xà bông", "bông hoa", son "đầu bông"
    ("phu_kien",      r"\bcọ\b|bông phấn|bông mút|bông cushion|(?<!xà )bông tắm|bông rửa|bông đắp"
                      r"|bông giọt|bông trang điểm|bông bọt|lược|kềm|bấm móng|cây nặn|nặn mụn"),
    ("mat_na_toc",    r"mặt nạ tóc|mặt nạ ủ tóc|hair mask|ủ tóc|hấp tóc"),
    ("mat_na",        r"mặt nạ|mask|miếng dán"),
    ("tay_trang",     r"tẩy trang"),
    ("rua_mat",       r"sữa rửa mặt|gel rửa mặt|rửa mặt"),
    ("chong_nang",    r"chống nắng"),
    ("toner",         r"toner|nước cân bằng|nước hoa hồng"),
    ("trang_diem",    r"chì kẻ|phấn|kem nền|cushion|che khuyết|má hồng|mascara"),
    ("serum",         r"serum|tinh chất|essence|ampoule"),
    ("nuoc_hoa",      r"nước hoa|eau de|edp|edt|xịt thơm|body mist"),
    # \b để không bắt "Johnson", "Philips"
    ("son",           r"\bson\b|\blip"),
    ("dau_goi_xa",    r"dầu gội|dầu xả|gội xả"),
    ("sua_tam",       r"sữa tắm|xà phòng|xà bông|muối tắm"),
    ("kem",           r"kem "),
]
# Nhóm "nhỏ mắt" chỉ có 2 sản phẩm: không đủ để học, để rơi vào "khac"

# Số lượng đếm được: "8 Miếng", "90 Tờ", "10 mặt nạ"...
REGEX_SO_LUONG = (r"(\d+)\s*(?:miếng|tờ|mặt nạ|cái|gói|viên|chiếc|pcs|pack|hộp|chai"
                  r"|tuýp|lọ|túi|ống|món|cây|lưỡi|cặp)")
REGEX_BO = r"(?:combo|set|bộ)\s*(\d+)"

# Cờ lấy từ tên và dung tích: PHẢI giống 0_lam_sach.py (dữ liệu huấn luyện được tạo từ đó)
REGEX_HSD = r"\[HSD"
REGEX_COMBO = r"(?i)combo|^bộ "
REGEX_MINI = r"(?i)\[mini\]"
# Dung tích "50ml", "5,9g", "1.2l", "1kg", "100gr" -> (số, đơn vị); l/kg quy về ml/g
REGEX_VOLUME = r"(\d+(?:[.,]\d+)?)\s*(ml|kg|gr|g|l)\b"
QUY_DOI_DON_VI = {"ml": ("ml", 1), "l": ("ml", 1000), "g": ("g", 1), "gr": ("g", 1), "kg": ("g", 1000)}


def chuan_hoa_brand(brand: pd.Series) -> pd.Series:
    """Thương hiệu viết HOA hết, bỏ khoảng trắng thừa: 'Beyond', 'BEYOND ' -> 'BEYOND'.
    Hasaki và Cocolux viết hoa/thường khác nhau nên phải thống nhất trước khi gom theo brand."""
    s = brand.astype("object")
    return s.where(s.isna(), s.astype(str).str.split().str.join(" ").str.upper())


def gan_loai_sp(ten: pd.Series) -> pd.Series:
    ten = ten.str.lower()
    dk = [ten.str.contains(m, regex=True) for _, m in LUAT_LOAI_SP]
    return pd.Series(np.select(dk, [l for l, _ in LUAT_LOAI_SP], "khac"), index=ten.index)


def dem_so_luong(ten: pd.Series) -> pd.Series:
    ten = ten.str.lower()
    sl = pd.to_numeric(ten.str.extract(REGEX_SO_LUONG)[0], errors="coerce")
    bo = pd.to_numeric(ten.str.extract(REGEX_BO)[0], errors="coerce")
    return sl.fillna(bo)


def ghi_metrics(key, gia_tri, file="models/metrics.json"):
    """Ghi chỉ số của một mô hình vào metrics.json, giữ nguyên key của mô hình khác."""
    os.makedirs(os.path.dirname(file), exist_ok=True)
    data = {}
    if os.path.exists(file):
        with open(file, encoding="utf-8") as f:
            data = json.load(f)
    data[key] = gia_tri
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
