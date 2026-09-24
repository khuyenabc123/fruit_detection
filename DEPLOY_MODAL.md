# Deploy model và trang test lên Modal

Gói này dùng checkpoint 7 lớp `backend/weights/fruit_yolov8s_7class.pt` (22.528.298 byte). Backend và React chạy cùng một URL; máy cá nhân không cần cài PyTorch.

## Chuẩn bị

1. Tạo tài khoản Modal Starter tại [modal.com](https://modal.com/) và đăng nhập.
2. Trong **Usage & Billing**, đặt hạn mức chi tiêu ngoài tín dụng miễn phí theo mức bạn chấp nhận. Modal hiện cấp tín dụng tính toán hằng tháng cho Starter, nhưng có thể tính phí khi vượt hạn mức.
3. Từ thư mục gốc dự án, build frontend và cài **chỉ** Modal CLI trong môi trường riêng:

```bash
cd frontend
npm ci
npm run build
cd ..
python3 -m venv .deploy-venv
.deploy-venv/bin/pip install modal
.deploy-venv/bin/modal token new
```

Lệnh `modal token new` mở trình duyệt để xác thực tài khoản Modal trên máy này. Không gửi token cho người khác và không ghi token vào repo.

## Deploy

```bash
.deploy-venv/bin/modal deploy modal_app.py
```

Modal sẽ build môi trường Python/PyTorch trên cloud và tải model + giao diện từ repo này. URL được in ở cuối lệnh deploy.

- Mở `https://<url>.modal.run/` để tải ảnh và thử model.
- Mở `https://<url>.modal.run/docs` để thử API.
- Kiểm tra `https://<url>.modal.run/health` để xác nhận `model_loaded: true` và `model_classes` có 7 lớp.
- Gọi API trực tiếp:

```bash
curl -F "file=@fruit.jpg" "https://<url>.modal.run/detect?conf_threshold=0.25"
```

Giới hạn ảnh 12 MB. Lần gọi đầu có thể chậm do container cloud khởi động. Cấu hình giới hạn tối đa một container và tự giảm về 0 khi rảnh để giảm mức tiêu thụ tín dụng. URL và model sẽ tồn tại sau khi tắt máy, nhưng tài nguyên vẫn tính theo lượt sử dụng và hạn mức tài khoản.

## Phát triển giao diện tại máy

Trang React dùng `/detect` và `/health`. Vite chuyển hai đường dẫn này sang backend ở `127.0.0.1:8000` khi chạy `npm run dev`. Nếu dùng frontend tách riêng, đặt `VITE_API_BASE_URL` lúc build rồi cấu hình CORS phù hợp trên backend.
