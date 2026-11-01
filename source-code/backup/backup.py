import subprocess
import datetime
from pathlib import Path

# Lấy ngày giờ hiện tại theo định dạng YYYYMMDD_HHMM
ngay = datetime.datetime.now().strftime("%Y%m%d_%H%M")

# Tạo đường dẫn thư mục lưu trữ backup
thu_muc = Path("./backup1") / ngay

# Tạo thư mục nếu chưa tồn tại
thu_muc.mkdir(parents=True, exist_ok=True)

# Cấu hình danh sách lệnh mongodump
lenh = [
    "mongodump",
    "--uri=mongodb+srv://24126195_db_user:nhom5cuoiki@cluster0.4rjebel.mongodb.net/DATA",
    "--db=DATA",
    f"--out={thu_muc}"
]

try:
    # Chạy lệnh hệ thống
    subprocess.run(lenh, check=True)
    print("Sao lưu thành công!")
    print("Đường dẫn thư mục lưu trữ:", thu_muc.resolve())

except subprocess.CalledProcessError as e:
    print("Sao lưu thất bại!")
    print("Chi tiết lỗi:", e)
