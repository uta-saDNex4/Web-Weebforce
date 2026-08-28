# ContractGuard Frontend

Frontend React/Vinext cho dự án ContractGuard.

## Chạy trên máy

1. Sao chép `.env.example` thành `.env.local`.
2. Đặt `NEXT_PUBLIC_API_BASE_URL` thành địa chỉ backend.
3. Cài package và chạy:

```bash
npm install
npm run dev
```

Mở địa chỉ được terminal hiển thị. Backend cần bật CORS cho origin của frontend.

## API đang sử dụng

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/contracts`
- `POST /api/contracts/{contract_id}/verify`
- `GET /api/contracts/{contract_id}/verifications`
