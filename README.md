# Web-Weebforce — Contract Verifier

Backend FastAPI xác thực hợp đồng bằng SHA-256, quản lý điều khoản hợp đồng và tra cứu rủi ro từ dữ liệu pháp lý Việt Nam. Dự án sử dụng PostgreSQL Docker, SQLAlchemy ORM, bcrypt và JWT.

## Kiến trúc

```text
main.py                       FastAPI, CORS và router
database.py                   PostgreSQL, session và tạo schema
models.py                     SQLAlchemy models và constraints
schemas.py                    Pydantic request/response schemas
auth.py                       bcrypt, JWT và RBAC dependency
routers/auth_routes.py        Đăng ký, đăng nhập, tài khoản
routers/contract_routes.py    Upload, verify, clauses, audit history
import_excel.py               Import Excel vào PostgreSQL
data/                         Excel, nguồn tham khảo và hợp đồng mẫu
```

## Tính năng

- Đăng ký và đăng nhập bằng JSON hoặc OAuth2 Password Form.
- JWT access token với thời hạn cấu hình.
- Băm mật khẩu bằng bcrypt, không lưu plaintext.
- Upload hợp đồng tối đa 20 MiB, hỗ trợ PDF/DOC/DOCX/TXT.
- Tính SHA-256 trên đúng byte file theo stream.
- Verify lại file và ghi audit log append-only.
- Xem metadata hợp đồng.
- Quản lý `contract_clauses` bằng JSON metadata.
- RBAC: chỉ Admin được thêm, sửa, xóa clause và xem lịch sử verification.
- Import dữ liệu pháp lý và risk rules từ Excel.

## Yêu cầu

- Python 3.11+
- PostgreSQL 14+ (khuyến nghị chạy Docker)
- `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg2-binary`, `pandas`, `openpyxl`, `bcrypt`, `python-multipart`

## PostgreSQL Docker

```bash
docker run --name contract-verifier-postgres \
  -e POSTGRES_USER=admin \
  -e POSTGRES_PASSWORD=matkhau_xinfu \
  -e POSTGRES_DB=contract_verifier_db \
  -p 5432:5432 -d postgres:16
```

Chuỗi kết nối mặc định:

```text
postgresql://admin:matkhau_xinfu@localhost:5432/contract_verifier_db
```

## Cài đặt và chạy

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
pip install fastapi uvicorn sqlalchemy psycopg2-binary pandas openpyxl bcrypt python-multipart
uvicorn main:app --reload
```

Khi khởi động, `Base.metadata.create_all()` tự tạo schema và index cần thiết. Logic này chỉ tạo cấu trúc, không seed user hoặc hợp đồng.

API docs: <http://localhost:8000/docs>

## Import Excel

```bash
python import_excel.py
```

Importer đọc `test_set_labeled.xlsx` để tạo hợp đồng mẫu và `contract_clauses.dynamic_metadata` gồm `gia_thue`, `tien_coc`, `tien_dien`, `tien_nuoc`; đọc `legal_references.xlsx` vào `legal_references`; và đọc `risk_rules_master.xlsx` vào `risk_rules`.

Mỗi bản ghi được sinh UUID 36 ký tự và timestamp UTC. Import có thể chạy lại; dữ liệu do import user sở hữu sẽ được thay thế để tránh nhân bản.

Tài khoản import mặc định cho development:

```text
Email: excel-import@contract-verifier.local
Password: change-this-import-password
```

Phải đổi hoặc loại bỏ tài khoản này trước production.

## API chính

| Method | Endpoint | Mục đích | Quyền |
|---|---|---|---|
| GET | `/health` | Health check | Công khai |
| POST | `/api/users/register` | Đăng ký | Công khai |
| POST | `/api/users/login` | Đăng nhập JSON/form | Công khai |
| GET | `/api/auth/me` | User hiện tại | JWT |
| POST | `/api/contracts` | Upload hợp đồng | JWT |
| GET | `/api/contracts/{id}` | Xem metadata | Chủ sở hữu/Admin |
| POST | `/api/contracts/{id}/verify` | Verify SHA-256 | Chủ sở hữu/Admin |
| POST | `/api/contracts/{id}/clauses` | Thêm clause | Admin |
| PUT | `/api/contracts/{id}/clauses/{clause_id}` | Sửa clause | Admin |
| DELETE | `/api/contracts/{id}/clauses/{clause_id}` | Xóa clause | Admin |
| GET | `/api/contracts/{id}/verifications` | Xem audit history | Admin |

Header xác thực:

```text
Authorization: Bearer <access_token>
```

## Bảo mật và giới hạn hiện tại

- Production cần bổ sung kiểm tra magic bytes, malware scanning và rate limit.
- File gốc nên đặt trong object storage bất biến; database chỉ lưu `storage_key`.
- Không ghi password, token, nội dung hợp đồng nhạy cảm hoặc stack trace vào log.
- Đặt `SECRET_KEY` riêng qua biến môi trường trước production.
- CORS wildcard chỉ phù hợp development; production phải giới hạn origin.
- Dữ liệu trong `data/` là dữ liệu tham khảo/test, không thay thế tư vấn pháp lý.

## Nguồn dữ liệu

Dữ liệu được lập từ [Thư viện Pháp luật](https://thuvienphapluat.vn/), [Cổng thông tin Chính phủ](https://vanban.chinhphu.vn/), [Bộ Tư pháp](https://vbpl.moj.gov.vn/), [BHXH Việt Nam](https://baohiemxahoi.gov.vn/), [EVN](https://www.evn.com.vn/) và các nguồn báo chí được ghi trong workbook hoặc `SOURCE_INDEX.md` của từng folder.

Các file `.url` trong `data/sample_contracts/` trỏ tới nguồn gốc để kiểm tra phiên bản mới nhất. Việc công chứng phụ thuộc loại giao dịch và yêu cầu pháp luật/thỏa thuận cụ thể; cần kiểm tra với tổ chức công chứng khi cần.
