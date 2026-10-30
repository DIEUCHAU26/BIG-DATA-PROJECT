# Chạy toàn bộ pipeline theo đúng thứ tự, lưu log từng bước vào logs/
#   python chay_tat_ca.py          -> chạy tất cả
#   python chay_tat_ca.py 2 4      -> chỉ chạy bước 2 và 4
import os, sys, subprocess, time
from datetime import datetime

# Thứ tự quan trọng: 4_bat_thuong đọc gia_du_doan.csv do 2_dinh_gia tạo ra
BUOC = [
    ("0", "0_lam_sach.py"),
    ("1", "1_phan_khuc.py"),
    ("2", "2_dinh_gia.py"),
    ("3", "3_het_hang.py"),
    ("4", "4_bat_thuong.py"),
    ("5", "5_kiem_tra.py"),
    ("6", "kiem_tra_du_doan.py"),   # du_doan.py (web dùng) phải khớp 100% với mô hình
    ("7", "xuat_sang_web.py"),      # ghép kết quả thành dataset/ml/san_pham_ml.csv cho web
]

os.chdir(os.path.dirname(os.path.abspath(__file__)))
chon = sys.argv[1:] or [b for b, _ in BUOC]
log_dir = os.path.join("logs", datetime.now().strftime("%Y%m%d_%H%M%S"))
os.makedirs(log_dir, exist_ok=True)
env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

tong = time.time()
for b, file in BUOC:
    if b not in chon:
        continue
    print(f"\n{'=' * 20} Buoc {b}: {file} {'=' * 20}", flush=True)
    t = time.time()
    log_file = os.path.join(log_dir, file.replace(".py", ".log"))
    with open(log_file, "w", encoding="utf-8") as log:
        p = subprocess.Popen([sys.executable, file], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             env=env, encoding="utf-8", errors="replace")
        for dong in p.stdout:          # vừa in ra màn hình vừa ghi log
            print(dong, end="", flush=True)
            log.write(dong)
        p.wait()
    if p.returncode != 0:
        print(f"\n>>> LOI o buoc {b} ({file}), dung lai. Xem log: {log_file}")
        sys.exit(p.returncode)
    print(f">>> Xong buoc {b} trong {time.time() - t:.0f}s")

print(f"\nHoan tat trong {time.time() - tong:.0f}s. Log luu tai: {log_dir}")
