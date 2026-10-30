# Web phân tích mỹ phẩm

Chạy `run_web.bat`. Cấu hình riêng nằm trong `.streamlit/secrets.toml`:

```toml
MONGO_URI = "<connection string>"
MONGO_DB = "DATA"
MONGO_PRODUCTS_COLLECTION = "product_clean"
```

## Dữ liệu và tài khoản

- MongoDB là nguồn dữ liệu chính. Thêm/sửa/xóa trên web ghi trực tiếp vào collection cấu hình; file Excel không tự thay đổi.
- Mỗi lần tải trang lấy dữ liệu hiện tại; các hàm trên cùng lượt tải dùng chung một bản chụp. Thay đổi bên ngoài Atlas xuất hiện khi tải lại trang. Mô hình cache theo nội dung dữ liệu, không theo bộ đếm cục bộ.
- Quản lý sản phẩm tìm kiếm trên MongoDB, tối đa 100 dòng/trang. Tìm kiếm phía trên áp dụng trên toàn bộ collection; ô chọn sửa/xóa áp dụng trên trang kết quả hiện tại.
- Tài khoản còn dùng mật khẩu demo được chuyển sang mật khẩu ngẫu nhiên trong `.streamlit/initial_accounts.json`. File này chỉ lưu trên máy và được Git bỏ qua. Không chia sẻ file. Có thể đổi mật khẩu trong menu tài khoản.
- Tài khoản bị xóa, đổi mật khẩu hoặc hạ quyền được kiểm tra lại ở mỗi lượt tải và trước thao tác quản lý. Mật khẩu mới cần ít nhất 10 ký tự.

## Sao lưu và thay thế dữ liệu

- Bấm **Chuẩn bị bản sao lưu**, rồi tải `.json.gz`. Bản sao dùng BSON Extended JSON để giữ kiểu ngày giờ.
- Phục hồi phải có ID duy nhất, các trường hợp lệ và ít nhất một quản trị viên. Sản phẩm rỗng được phép nếu bản sao có người dùng hợp lệ.
- Trước phục hồi/nạp Excel, phiên bản hiện tại được lưu vào `backups/`. Thay thế MongoDB chạy trong một giao dịch: lỗi giữa chừng sẽ hoàn tác. Cần MongoDB Atlas hoặc replica set hỗ trợ giao dịch.
- Nhật ký thay đổi nằm trong collection `audit_log`; quản trị viên có thể xem 100 sự kiện gần nhất ở trang sao lưu. Không ghi hash mật khẩu vào nhật ký.
- `migrate_to_mongo.py` mặc định chỉ kiểm tra. `--apply` chỉ cho nhập vào database đích trống; không ghi đè dữ liệu đang dùng. `reload_data.py` hướng dẫn chuyển sang luồng quản trị có xác thực.
- `repair_volumes.py` chỉ đối chiếu URL và nguồn với Excel. `--apply` lưu bản sao rồi khôi phục đơn vị trong giao dịch; không đoán đơn vị cho dữ liệu không khớp.

## Mô hình học máy

Các trang trong nhóm **Mô hình** (phân khúc thương hiệu, dự đoán giá, dự đoán hết hàng, phát hiện bất thường) nằm trong `ml_pages.py`. Chúng đọc mô hình và biểu đồ ở `../ml/` và bảng kết quả ở `../../dataset/ml/`, nên giữ nguyên cấu trúc thư mục của repo. Xem `../ml/README.md` để huấn luyện lại.

## Kiểm thử

```powershell
.\venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\venv\Scripts\python.exe -B tests/integration_mongo.py
```

Kiểm thử tích hợp cần kết nối Atlas; tạo database `web_test_*` riêng và dọn sau khi hoàn tất. Không dùng collection sản phẩm thật để thử xóa/phục hồi.

Các phiên bản thư viện đã kiểm tra được khóa trong `requirements.txt`.
