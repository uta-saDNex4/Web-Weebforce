# AGENTS.md — Contract Verifier

Tài liệu này định nghĩa cấu trúc database rỗng và luồng tính năng cốt lõi cho
ứng dụng web xác thực hợp đồng. Database rỗng nghĩa là chỉ tạo schema, index,
constraint và quan hệ; không tạo user, hợp đồng hoặc log seed.

## 1. Phạm vi dữ liệu

Thư mục `data/` hiện gồm:

- `legal_references.xlsx`: dữ liệu tham chiếu pháp lý.
- `risk_rules_master.xlsx`: bộ quy tắc rủi ro.
- `test_set_labeled.xlsx`: tập kiểm thử đã gán nhãn.
- `sample_contracts/`: hợp đồng mẫu được phân loại theo các thư mục `ctv`,
  `intern`, `khóa học`, `thuê chung cư`, `thuê trọ`, `trả góp`, `vay tiêu dùng`.

Các file trên là nguồn dữ liệu/tham chiếu ngoài phạm vi schema tối thiểu bên
dưới. Không lưu nội dung workbook vào ba bảng này nếu chưa có yêu cầu riêng.
Các loại hợp đồng mẫu được lưu trong cột `contract_type` để hỗ trợ lọc và
thống kê, không dùng tên thư mục làm khóa chính.

## 2. Nguyên tắc database

- Dùng UUID cho khóa chính; thời gian lưu ở UTC.
- Tất cả hash SHA-256 lưu dưới dạng chuỗi hexadecimal thường, đúng 64 ký tự.
- Không lưu mật khẩu dạng plaintext; chỉ lưu `password_hash` do thư viện
  password hashing chuyên dụng tạo ra (Argon2id hoặc bcrypt).
- File gốc nên được lưu ở object storage hoặc filesystem riêng; database chỉ
  lưu metadata và địa chỉ tham chiếu (`storage_key`).
- Mọi cột trạng thái dùng tập giá trị hữu hạn ở tầng database hoặc application;
  API phải từ chối giá trị không hợp lệ.
- `verification_logs` là audit log append-only: không cập nhật hoặc xóa log
  trong nghiệp vụ thông thường.

## 3. Schema rỗng

### 3.1. `users`

Lưu tài khoản thực hiện tải lên và xác thực.

| Cột | Kiểu | Bắt buộc | Mô tả |
|---|---|---:|---|
| `id` | UUID | Có | Khóa chính. |
| `email` | VARCHAR(320) | Có | Email đăng nhập, unique, nên chuẩn hóa lowercase. |
| `password_hash` | VARCHAR(255) | Có | Hash mật khẩu Argon2id/bcrypt. |
| `full_name` | VARCHAR(255) | Không | Tên hiển thị. |
| `role` | VARCHAR(32) | Có | `user` hoặc `admin`; mặc định `user`. |
| `is_active` | BOOLEAN | Có | Mặc định `true`; tài khoản bị vô hiệu hóa không được upload. |
| `created_at` | TIMESTAMP WITH TIME ZONE | Có | Thời điểm tạo tài khoản. |
| `updated_at` | TIMESTAMP WITH TIME ZONE | Có | Thời điểm cập nhật gần nhất. |

Ràng buộc: `PRIMARY KEY (id)`, `UNIQUE (email)`, `CHECK (role IN
('user', 'admin'))`.

### 3.2. `contracts`

Lưu metadata của từng file hợp đồng đã tải lên và giá trị chuẩn dùng để đối
chiếu.

| Cột | Kiểu | Bắt buộc | Mô tả |
|---|---|---:|---|
| `id` | UUID | Có | Khóa chính. |
| `uploaded_by` | UUID | Có | Khóa ngoại tới `users.id`. |
| `original_filename` | VARCHAR(255) | Có | Tên file do người dùng cung cấp, chỉ dùng hiển thị. |
| `storage_key` | VARCHAR(1024) | Có | Đường dẫn/key nội bộ tới file đã lưu. |
| `mime_type` | VARCHAR(127) | Có | MIME type đã kiểm tra. |
| `file_size_bytes` | BIGINT | Có | Kích thước file; phải lớn hơn 0 và trong giới hạn hệ thống. |
| `sha256_hash` | CHAR(64) | Có | SHA-256 của đúng byte file đã lưu. |
| `contract_type` | VARCHAR(64) | Không | Ví dụ: `ctv`, `intern`, `khóa học`, `thuê chung cư`, `thuê trọ`, `trả góp`, `vay tiêu dùng`. |
| `status` | VARCHAR(32) | Có | `uploaded`, `verifying`, `verified`, `mismatch`, `failed`; mặc định `uploaded`. |
| `created_at` | TIMESTAMP WITH TIME ZONE | Có | Thời điểm hoàn tất lưu file/metadata. |
| `updated_at` | TIMESTAMP WITH TIME ZONE | Có | Thời điểm cập nhật trạng thái gần nhất. |

Ràng buộc: `PRIMARY KEY (id)`, `FOREIGN KEY (uploaded_by) REFERENCES users(id)`;
`CHECK (sha256_hash ~ '^[0-9a-f]{64}$')`, `CHECK (file_size_bytes > 0)` và
`CHECK` cho các giá trị `status`. Không unique `sha256_hash`, vì nhiều người
có thể tải lên cùng một file; có thể thêm index trên hash để tìm nhanh.

### 3.3. `verification_logs`

Lưu từng lần yêu cầu xác thực, kể cả kết quả thành công, không khớp hoặc lỗi.

| Cột | Kiểu | Bắt buộc | Mô tả |
|---|---|---:|---|
| `id` | UUID | Có | Khóa chính. |
| `contract_id` | UUID | Có | Khóa ngoại tới `contracts.id`. |
| `requested_by` | UUID | Có | Khóa ngoại tới `users.id`. |
| `expected_sha256` | CHAR(64) | Có | Hash chuẩn được dùng lúc đối chiếu. |
| `actual_sha256` | CHAR(64) | Có | Hash tính lại từ file tại thời điểm xác thực. |
| `result` | VARCHAR(32) | Có | `matched`, `mismatched`, `failed`. |
| `error_code` | VARCHAR(64) | Không | Mã lỗi máy đọc được nếu `result = failed`. |
| `error_message` | TEXT | Không | Mô tả lỗi an toàn, không chứa secret hoặc nội dung nhạy cảm. |
| `duration_ms` | INTEGER | Không | Thời gian xử lý, không âm. |
| `created_at` | TIMESTAMP WITH TIME ZONE | Có | Thời điểm ghi nhận lần xác thực. |

Ràng buộc: `PRIMARY KEY (id)`, khóa ngoại tới `contracts.id` và `users.id`;
`CHECK` cho hash và `result`; `CHECK (duration_ms IS NULL OR duration_ms >= 0)`.
Nên giữ log khi hợp đồng bị xóa bằng cách dùng soft delete cho hợp đồng hoặc
chính sách `ON DELETE RESTRICT`; không cascade xóa audit log.

### 3.4. `contract_clauses`

Lưu các điều khoản đi kèm hợp đồng theo cấu trúc linh hoạt. Các trường ổn định
được chuẩn hóa thành cột riêng; các tham số thay đổi theo từng loại điều khoản
được lưu trong `dynamic_metadata` để không phải thay đổi schema khi phát sinh
loại hợp đồng mới.

| Cột | Kiểu | Bắt buộc | Mô tả |
|---|---|---:|---|
| `id` | UUID | Có | Khóa chính. |
| `contract_id` | UUID | Có | Khóa ngoại tới `contracts.id`. |
| `clause_type` | VARCHAR(64) | Có | Loại điều khoản, ví dụ `payment`, `interest`, `due_date`, `termination`; nên dùng danh mục được kiểm soát ở tầng application. |
| `clause_order` | INTEGER | Có | Thứ tự điều khoản trong hợp đồng, bắt đầu từ 1. |
| `title` | VARCHAR(255) | Không | Tên hiển thị của điều khoản. |
| `content` | TEXT | Không | Nội dung văn bản của điều khoản, nếu cần lưu bản diễn giải. |
| `dynamic_metadata` | JSONB (hoặc JSON) | Có | Tham số động như `amount`, `currency`, `interest_rate`, `interest_period`, `due_date`; mặc định `{}`. |
| `created_at` | TIMESTAMP WITH TIME ZONE | Có | Thời điểm tạo điều khoản. |
| `updated_at` | TIMESTAMP WITH TIME ZONE | Có | Thời điểm cập nhật gần nhất. |

Ràng buộc: `PRIMARY KEY (id)`, `FOREIGN KEY (contract_id) REFERENCES
contracts(id)`, `CHECK (clause_order > 0)`, và `dynamic_metadata` phải là một
JSON object hợp lệ (không phải mảng hoặc giá trị scalar). Nên tạo
`UNIQUE (contract_id, clause_order)` để tránh trùng thứ tự. Không hard-code
các key bên trong `dynamic_metadata`; validation kiểu dữ liệu, đơn vị tiền tệ,
lãi suất và định dạng ngày phải do application xử lý theo `clause_type`.

Ví dụ cấu trúc `dynamic_metadata`:

```json
{
  "amount": 15000000,
  "currency": "VND",
  "interest_rate": 1.2,
  "interest_period": "monthly",
  "due_date": "2026-12-31"
}
```

### 3.5. Index khuyến nghị

- `users(email)` unique.
- `contracts(uploaded_by, created_at DESC)`.
- `contracts(sha256_hash)`.
- `contracts(status, created_at DESC)`.
- `verification_logs(contract_id, created_at DESC)`.
- `verification_logs(requested_by, created_at DESC)`.
- `contract_clauses(contract_id, clause_order)` unique.
- `contract_clauses(clause_type)`.
- `contract_clauses USING GIN (dynamic_metadata)` nếu dùng PostgreSQL và cần
  tìm kiếm theo các tham số JSON.

## 4. Feature Flow — tải file và đối chiếu SHA-256

### A. Tải file

1. Người dùng đăng nhập; server kiểm tra session/token và `users.is_active`.
2. Client gửi `multipart/form-data` tới endpoint upload. Server áp dụng giới
   hạn kích thước, allowlist phần mở rộng/MIME, tên file an toàn và rate limit.
3. Server không tin `Content-Type` do client gửi: kiểm tra signature/magic bytes,
   chống path traversal, lưu file vào vùng tạm riêng và quét malware nếu có.
4. Server đọc file theo dạng binary và tính `SHA-256` theo stream từ byte đầu
   đến byte cuối. Không hash tên file, nội dung đã parse, hoặc bản text đã
   normalize.
5. Server ghi file vào storage bất biến với key ngẫu nhiên, rồi trong một
   transaction tạo bản ghi `contracts` gồm metadata, `sha256_hash` và trạng thái
   `uploaded`. Chỉ trả response thành công sau khi cả file và metadata đã bền
   vững; lỗi giữa chừng phải dọn file mồ côi.
6. API trả `contract_id`, `sha256_hash`, `status` và metadata an toàn; không trả
   đường dẫn filesystem nội bộ.

### B. Đối chiếu mã hash

1. Người dùng chọn `contract_id` và gửi yêu cầu verify. Server kiểm tra quyền
   sở hữu/quyền admin, lấy `storage_key` và khóa bản ghi hoặc dùng cơ chế chống
   chạy trùng để tránh hai job cập nhật trạng thái sai thứ tự.
2. Chuyển `contracts.status` sang `verifying`, đọc đúng file từ storage và tính
   lại SHA-256 theo stream. Nếu file không tồn tại/không đọc được, ghi log
   `failed` và chuyển trạng thái `failed`.
3. So sánh constant-time giữa `actual_sha256` và `expected_sha256` đã lưu. Không
   so sánh hash của dữ liệu do client gửi thay cho việc đọc lại file server.
4. Nếu bằng nhau, ghi `verification_logs.result = matched` và chuyển contract
   sang `verified`. Nếu khác, ghi `result = mismatched` và chuyển sang `mismatch`.
   Cả hai nhánh đều lưu cả expected/actual hash và thời gian xử lý.
5. Trả kết quả rõ ràng cho UI: `matched` là file đúng với hash chuẩn;
   `mismatched` là file khác hoặc đã bị thay đổi; `failed` là không thể xác thực.
   Không hiển thị stack trace hay thông tin storage cho người dùng.

### C. Tính nhất quán và bảo mật

- Ghi log xác thực và cập nhật trạng thái trong cùng transaction khi có thể.
- Hash phải được tính lại mỗi lần verify; không coi kết quả cũ là bằng chứng cho
  file hiện tại nếu file storage có thể bị thay thế.
- Dùng HTTPS, kiểm soát quyền truy cập theo user, chống upload file độc hại,
  giới hạn tài nguyên và audit các thao tác quản trị.
- Không ghi password, token, dữ liệu hợp đồng nhạy cảm hoặc nội dung file vào
  log ứng dụng.

## 5. Hợp đồng API tối thiểu (tham khảo)

- `POST /api/contracts` — upload file; trả metadata và hash SHA-256.
- `GET /api/contracts/:id` — xem metadata khi có quyền.
- `POST /api/contracts/:id/verify` — chạy đối chiếu và tạo verification log.
- `POST /api/contracts/{id}/clauses` — lưu một hoặc nhiều điều khoản động của
  hợp đồng, gồm `clause_type`, `clause_order`, nội dung và `dynamic_metadata`.
- `GET /api/contracts/:id/verifications` — xem lịch sử xác thực khi có quyền.

Tên endpoint chỉ là quy ước; khi triển khai phải giữ nguyên ý nghĩa trạng thái,
quyền truy cập và quy tắc hash ở trên.
