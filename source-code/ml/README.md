# Phần học máy

Bốn mô hình trên dữ liệu sản phẩm Hasaki và Cocolux. Code ở thư mục này, dữ liệu ở `dataset/ml/` (thư mục riêng, không lẫn dữ liệu phần khác).

| Bước | File | Việc làm | Kết quả |
|---|---|---|---|
| 0 | `0_lam_sach.py` | Bỏ tên trùng, đổi lít sang ml, tạo cờ combo, mini, HSD và các cột dẫn xuất | `dataset/ml/products_model.csv` |
| 1 | `1_phan_khuc.py` | **Phân cụm thương hiệu** (K-Means, chạy riêng từng sàn) | `dataset/ml/phan_cum_thuong_hieu_{hasaki,cocolux}.csv` |
| 2 | `2_dinh_gia.py` | **Dự đoán giá niêm yết** (Random Forest, Ridge, Gradient Boosting) | `models/model_dinh_gia.joblib`, `dataset/ml/gia_du_doan.csv` |
| 3 | `3_het_hang.py` | **Dự đoán hết hàng** (chỉ Hasaki) | `models/model_het_hang.joblib`, `dataset/ml/het_hang_du_doan.csv` |
| 4 | `4_bat_thuong.py` | **Phát hiện bất thường** (IQR, Isolation Forest, LOF) | `dataset/ml/anomalies.csv` |
| 5, 6 | `5_kiem_tra.py`, `kiem_tra_du_doan.py` | Kiểm tra kết quả, và dự đoán từ dữ liệu thô khớp 100% với huấn luyện | |
| 7 | `xuat_sang_web.py` | Ghép kết quả theo `url` | `dataset/ml/san_pham_ml.csv` |

`quy_tac.py` chứa luật và tham số dùng chung, `dac_trung.py` tạo đặc trưng, `du_doan.py` dự đoán cho sản phẩm bất kỳ.

## Chạy lại

```powershell
cd source-code/ml
python chay_tat_ca.py          # tất cả các bước, log lưu ở logs/
python chay_tat_ca.py 2 4      # chỉ bước 2 và 4
```

Đầu vào là `dataset/ml/products_clean.xlsx` (đã chuẩn hóa brand viết hoa, kg đã đổi sang g). Cần `scikit-learn==1.9.1`, đúng phiên bản đã dùng để lưu mô hình.

## Dùng trong web

Các trang "Mô hình" của web nằm ở `source-code/web/ml_pages.py`. Web đọc trực tiếp mô hình và biểu đồ ở đây, bảng kết quả ở `dataset/ml/`, không cần chép file. Sản phẩm mới thêm qua CRUD chưa có trong `san_pham_ml.csv` nên được dự đoán bằng `du_doan.py`.

```python
from du_doan import du_doan_gia, du_doan_het_hang
du_doan_gia(df_tho)        # giá niêm yết dự đoán (đ)
du_doan_het_hang(df_tho)   # xác suất hết hàng (Hasaki)
```

`df_tho` cần các cột: `source, category_group, category, name, brand, volume, origin`, thêm `price_original, discount_pct, review_count` cho dự đoán hết hàng. Brand được tự chuẩn hóa viết hoa.

## Thư mục

- `models/`: mô hình `.joblib` và `metrics.json` (mọi chỉ số).
- `figures/`: hình PNG cho báo cáo. `bieu_do/`: dữ liệu CSV để web tự vẽ biểu đồ.
- `document/`: kế hoạch và nhật ký thay đổi.
