"""Minimal FastAPI API for contract upload and SHA-256 verification.

This starter implementation intentionally uses in-memory repositories. Replace
the dictionaries and byte storage with the three database tables and object
storage described in AGENTS.md before production use.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import re
import secrets
import uuid
from datetime import datetime, timezone
from os import getenv
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user
from models import Base, Contract, ContractClause


app = FastAPI(
    title="Contract Verifier API",
    description="Upload hợp đồng và xác thực bằng SHA-256.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}
CHUNK_SIZE = 1024 * 1024

# Temporary repositories. They are deliberately empty whenever the process starts.
USERS: dict[uuid.UUID, dict[str, Any]] = {}
USERS_BY_EMAIL: dict[str, uuid.UUID] = {}
CONTRACTS: dict[uuid.UUID, dict[str, Any]] = {}
FILE_STORAGE: dict[str, bytes] = {}
VERIFICATION_LOGS: list[dict[str, Any]] = []

DATABASE_URL = getenv("DATABASE_URL", "sqlite:///./contract_verifier.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
# Creates schema only; no seed rows are inserted.
Base.metadata.create_all(bind=engine)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    """Hash a password without storing it in plaintext.

    Production deployments should use Argon2id or bcrypt through a maintained
    password-hashing library. PBKDF2 keeps this standalone starter runnable.
    """

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, rounds_text, salt_hex, digest_hex = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(rounds_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
    return hmac.compare_digest(actual, expected)


class UserRegistration(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    full_name: str | None = Field(default=None, max_length=255)


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime


class ContractResponse(BaseModel):
    id: uuid.UUID
    original_filename: str
    mime_type: str
    file_size_bytes: int
    sha256_hash: str
    contract_type: str | None
    status: str
    created_at: datetime


class VerificationResponse(BaseModel):
    contract_id: uuid.UUID
    expected_sha256: str
    actual_sha256: str
    result: str
    verification_log_id: uuid.UUID
    duration_ms: int | None


class ClauseCreate(BaseModel):
    clause_type: str = Field(min_length=1, max_length=64)
    clause_order: int = Field(gt=0)
    title: str | None = Field(default=None, max_length=255)
    content: str | None = None
    dynamic_metadata: dict[str, Any] = Field(default_factory=dict)


class ClauseResponse(ClauseCreate):
    id: uuid.UUID
    contract_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class RentClauseVerificationResponse(BaseModel):
    contract_id: uuid.UUID
    file_sha256: str
    result: str
    warnings: list[dict[str, Any]]
    checked_fields: dict[str, dict[str, Any]]
    verification_log_id: uuid.UUID
    contract_status: str


current_user = get_current_user


async def read_and_hash(upload: UploadFile) -> tuple[bytes, str]:
    """Read an upload in chunks and calculate SHA-256 over its exact bytes."""

    chunks: list[bytes] = []
    total = 0
    digest = hashlib.sha256()
    while chunk := await upload.read(CHUNK_SIZE):
        total += len(chunk)
        if total > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File exceeds the 20 MiB limit")
        digest.update(chunk)
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail="File must not be empty")
    return b"".join(chunks), digest.hexdigest()


def extract_contract_text(content: bytes, filename: str) -> str:
    """Extract text from a UTF-8 text file or a PDF upload."""

    extension = Path(filename).suffix.lower()
    if extension == ".txt":
        return content.decode("utf-8-sig", errors="replace")
    if extension == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail="PDF extraction is unavailable; install the pypdf package",
            ) from exc
        try:
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="Unable to read PDF contract") from exc
    raise HTTPException(status_code=415, detail="Only PDF and TXT contracts are supported")


def canonical_money(value: Any) -> str | None:
    """Return a comparable integer amount in VND from common Vietnamese forms."""

    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else None

    raw = str(value).strip().lower().replace("₫", "").replace("đ", "")
    raw = raw.replace("vnd", "").replace("vnđ", "").strip()
    multiplier = 1
    if re.search(r"(?:triệu|tr)\b", raw):
        multiplier = 1_000_000
    elif re.search(r"(?:tỷ|ty|t)\b", raw):
        multiplier = 1_000_000_000
    number = re.search(r"\d+(?:[.,]\d+)*", raw)
    if not number:
        return None
    number_text = number.group(0)
    if multiplier != 1:
        number_text = number_text.replace(",", ".")
        try:
            return str(int(float(number_text) * multiplier))
        except ValueError:
            return None
    digits = re.sub(r"[^0-9]", "", number_text)
    return digits or None


def extract_rent_value(text: str, field: str) -> str | None:
    """Find a rent/deposit amount near its label in extracted contract text."""

    labels = {
        "gia_thue": r"(?:gia[_\-\s]*thue|giá[_\-\s]*thuê|tien[_\-\s]*thue|tiền[_\-\s]*thuê)",
        "tien_coc": r"(?:tien[_\-\s]*coc|tiền[_\-\s]*cọc|dat[_\-\s]*coc|đặt[_\-\s]*cọc)",
    }
    # Search the same line first so unrelated amounts elsewhere are not used.
    pattern = re.compile(
        rf"{labels[field]}[^\n\r]{{0,100}}?([0-9][0-9.,]*(?:\s*(?:triệu|tr|tỷ|ty|vnd|vnđ|đ))?)",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    return canonical_money(match.group(1)) if match else None


def clause_metadata_for_contract(contract_id: uuid.UUID) -> dict[str, Any]:
    """Read the expected rental values from contract_clauses.dynamic_metadata."""

    expected: dict[str, Any] = {}
    with Session(engine) as db:
        clauses = db.query(ContractClause).filter(ContractClause.contract_id == contract_id).all()
        for clause in clauses:
            metadata = clause.dynamic_metadata or {}
            for field in ("gia_thue", "tien_coc"):
                if field in metadata and field not in expected:
                    expected[field] = metadata[field]
    return expected


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/users/register", response_model=UserResponse, status_code=201)
def register_user(payload: UserRegistration) -> UserResponse:
    email = payload.email.strip().lower()
    if email in USERS_BY_EMAIL:
        raise HTTPException(status_code=409, detail="Email already registered")

    now = utc_now()
    user = {
        "id": uuid.uuid4(),
        "email": email,
        "password_hash": hash_password(payload.password),
        "full_name": payload.full_name,
        "role": "user",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    USERS[user["id"]] = user
    USERS_BY_EMAIL[email] = user["id"]
    return UserResponse.model_validate(user)


@app.post("/api/users/login", response_model=TokenResponse)
def login_user(payload: UserLogin) -> TokenResponse:
    email = payload.email.strip().lower()
    user_id = USERS_BY_EMAIL.get(email)
    user = USERS.get(user_id) if user_id else None
    if not user or not user.get("is_active") or not verify_password(
        payload.password, user["password_hash"]
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token({"sub": str(user["id"])})
    return TokenResponse(access_token=access_token)


@app.post("/api/contracts", response_model=ContractResponse, status_code=201)
async def upload_contract(
    current: Annotated[dict[str, Any], Depends(current_user)],
    file: Annotated[UploadFile, File(...)],
    contract_type: Annotated[str | None, Header()] = None,
) -> ContractResponse:
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()
    if not filename or extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported contract file type")

    content, sha256_hash = await read_and_hash(file)
    contract_id = uuid.uuid4()
    storage_key = f"contracts/{contract_id}/{secrets.token_hex(16)}{extension}"
    now = utc_now()
    contract = {
        "id": contract_id,
        "uploaded_by": current["id"],
        "original_filename": filename,
        "storage_key": storage_key,
        "mime_type": file.content_type or "application/octet-stream",
        "file_size_bytes": len(content),
        "sha256_hash": sha256_hash,
        "contract_type": contract_type,
        "status": "uploaded",
        "created_at": now,
        "updated_at": now,
    }
    FILE_STORAGE[storage_key] = content
    CONTRACTS[contract_id] = contract
    with Session(engine) as db:
        db.add(Contract(id=contract_id))
        db.commit()
    return ContractResponse.model_validate(contract)


@app.post(
    "/api/contracts/{contract_id}/clauses",
    response_model=ClauseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contract_clause(
    contract_id: uuid.UUID,
    payload: ClauseCreate,
    current: Annotated[dict[str, Any], Depends(current_user)],
) -> ClauseResponse:
    """Store one dynamic clause for an uploaded contract."""

    contract = CONTRACTS.get(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if contract["uploaded_by"] != current["id"] and current["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not allowed to edit this contract")

    clause = ContractClause(
        id=uuid.uuid4(),
        contract_id=contract_id,
        clause_type=payload.clause_type,
        clause_order=payload.clause_order,
        title=payload.title,
        content=payload.content,
        dynamic_metadata=payload.dynamic_metadata,
    )
    with Session(engine) as db:
        db.add(clause)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409, detail="Clause order already exists for this contract"
            ) from exc
        db.refresh(clause)

    return ClauseResponse(
        id=clause.id,
        contract_id=clause.contract_id,
        clause_type=clause.clause_type,
        clause_order=clause.clause_order,
        title=clause.title,
        content=clause.content,
        dynamic_metadata=clause.dynamic_metadata,
        created_at=clause.created_at,
        updated_at=clause.updated_at,
    )


@app.post(
    "/api/contracts/{contract_id}/verify-rent-clauses",
    response_model=RentClauseVerificationResponse,
)
async def verify_rent_clauses(
    contract_id: uuid.UUID,
    current: Annotated[dict[str, Any], Depends(current_user)],
    file: Annotated[UploadFile, File(...)],
) -> RentClauseVerificationResponse:
    """Compare rent and deposit values in an uploaded PDF/TXT contract.

    The expected values are read from ``contract_clauses.dynamic_metadata``.
    This endpoint verifies clause values, so the uploaded file's SHA-256 is
    recorded in the audit log but is not required to equal the stored contract
    hash (a re-exported PDF may have different bytes).
    """

    contract = CONTRACTS.get(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if contract["uploaded_by"] != current["id"] and current["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not allowed to verify this contract")

    filename = Path(file.filename or "").name
    if Path(filename).suffix.lower() not in {".pdf", ".txt"}:
        raise HTTPException(status_code=415, detail="Only PDF and TXT contracts are supported")

    started = perf_counter()
    content, file_sha256 = await read_and_hash(file)
    text = extract_contract_text(content, filename)
    expected_metadata = clause_metadata_for_contract(contract_id)
    warnings: list[dict[str, Any]] = []
    checked_fields: dict[str, dict[str, Any]] = {}

    for field, label in (("gia_thue", "Giá thuê"), ("tien_coc", "Tiền cọc")):
        expected = canonical_money(expected_metadata.get(field))
        actual = extract_rent_value(text, field)
        # Compare fixed encoded values with compare_digest; missing values are
        # also compared instead of short-circuiting on user-controlled input.
        expected_value = (expected or "").encode("utf-8")
        actual_value = (actual or "").encode("utf-8")
        matched = bool(expected and actual) and hmac.compare_digest(expected_value, actual_value)
        checked_fields[field] = {
            "label": label,
            "expected": expected_metadata.get(field),
            "actual": actual,
            "matched": matched,
        }
        if not expected:
            warnings.append({
                "field": field,
                "code": "EXPECTED_VALUE_MISSING",
                "message": f"Chưa có {label.lower()} mẫu trong dynamic_metadata.",
                "expected": expected_metadata.get(field),
                "actual": actual,
            })
        elif not actual:
            warnings.append({
                "field": field,
                "code": "VALUE_NOT_FOUND",
                "message": f"Không tìm thấy {label.lower()} trong file hợp đồng.",
                "expected": expected_metadata.get(field),
                "actual": None,
            })
        elif not matched:
            warnings.append({
                "field": field,
                "code": "VALUE_MISMATCH",
                "message": f"{label} trong hợp đồng không khớp dữ liệu mẫu.",
                "expected": expected_metadata.get(field),
                "actual": actual,
            })

    result = "matched" if not warnings else "mismatched"
    contract["status"] = "verified" if result == "matched" else "mismatch"
    contract["updated_at"] = utc_now()
    duration_ms = int((perf_counter() - started) * 1000)
    expected_contract_hash = contract["sha256_hash"]
    log = {
        "id": uuid.uuid4(),
        "contract_id": contract_id,
        "requested_by": current["id"],
        "expected_sha256": expected_contract_hash,
        "actual_sha256": file_sha256,
        "result": result,
        "error_code": None if result == "matched" else "RENT_CLAUSE_MISMATCH",
        "error_message": None if result == "matched" else "; ".join(
            warning["message"] for warning in warnings
        ),
        "duration_ms": duration_ms,
        "created_at": utc_now(),
    }
    VERIFICATION_LOGS.append(log)
    return RentClauseVerificationResponse(
        contract_id=contract_id,
        file_sha256=file_sha256,
        result=result,
        warnings=warnings,
        checked_fields=checked_fields,
        verification_log_id=log["id"],
        contract_status=contract["status"],
    )


@app.post("/api/contracts/{contract_id}/verify", response_model=VerificationResponse)
def verify_contract(
    contract_id: uuid.UUID,
    current: Annotated[dict[str, Any], Depends(current_user)],
) -> VerificationResponse:
    contract = CONTRACTS.get(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if contract["uploaded_by"] != current["id"] and current["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not allowed to verify this contract")

    started = perf_counter()
    contract["status"] = "verifying"
    content = FILE_STORAGE.get(contract["storage_key"])
    expected = contract["sha256_hash"]
    if content is None:
        result = "failed"
        actual = "0" * 64
        error_code = "FILE_NOT_FOUND"
        contract["status"] = "failed"
    else:
        actual = hashlib.sha256(content).hexdigest()
        result = "matched" if hmac.compare_digest(actual, expected) else "mismatched"
        error_code = None
        contract["status"] = "verified" if result == "matched" else "mismatch"

    duration_ms = int((perf_counter() - started) * 1000)
    contract["updated_at"] = utc_now()
    log = {
        "id": uuid.uuid4(),
        "contract_id": contract_id,
        "requested_by": current["id"],
        "expected_sha256": expected,
        "actual_sha256": actual,
        "result": result,
        "error_code": error_code,
        "duration_ms": duration_ms,
        "created_at": utc_now(),
    }
    VERIFICATION_LOGS.append(log)
    return VerificationResponse(
        contract_id=contract_id,
        expected_sha256=expected,
        actual_sha256=actual,
        result=result,
        verification_log_id=log["id"],
        duration_ms=duration_ms,
    )
