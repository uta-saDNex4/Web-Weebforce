# ContractGuard Frontend

Frontend React/Vinext cho dự án ContractGuard.

## Chạy trên máy

1. Sao chép `.env.example` thành `.env.local` trong thư mục `frontend/`.
2. Nếu frontend và backend tách domain, đặt `NEXT_PUBLIC_API_BASE_URL` thành địa chỉ backend. Nếu chạy qua Docker Compose cùng origin, có thể để trống vì frontend sẽ proxy `/api` sang backend.
3. Cài package và chạy:

```bash
npm install
npm run dev
```

Mở địa chỉ được terminal hiển thị. Backend cần bật CORS cho origin của frontend.

Khi chạy backend trực tiếp trên máy, đặt `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
trong `.env.local` trước khi chạy frontend (hoặc build). Giá trị là origin backend,
không thêm `/api`. Proxy mặc định trên máy dùng `http://localhost:8000`; Dockerfile
đặt `http://backend:8000`. Có thể đổi qua `BACKEND_INTERNAL_URL` trong `.env.local`
hoặc môi trường tiến trình frontend. Khởi động lại dev/build sau khi đổi biến.

Trên PowerShell nếu `npm.ps1` bị chặn, dùng `npm.cmd ci` và `npm.cmd run dev`.
Khi dev server đang chạy, dùng `node tests/dev-smoke.test.mjs` để kiểm tra HTTP
của trang và các module frontend. Đặt `FRONTEND_TEST_URL` nếu dùng cổng khác 3000.

## API đang sử dụng

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/contracts`
- `POST /api/contracts/{contract_id}/verify`
- `GET /api/contracts/{contract_id}/verifications` (chỉ admin)

Upload hợp đồng dùng multipart field `file`, header `contract-type` và Bearer token.
Chấp nhận PDF, DOC, DOCX, TXT có kích thước lớn hơn 0 và tối đa 20 MiB.
Xác minh gửi POST không kèm file để backend đọc lại file đã lưu.

Backend hiện trả `risk_label=processing` và chưa cung cấp endpoint đọc kết quả AI
chạy nền. Frontend hiển thị kết quả SHA-256 và thông báo chưa có kết quả AI;
không coi điểm 0 tạm thời là kết luận an toàn.
