"""Contract upload, SHA-256 verification, clauses and audit history."""
from __future__ import annotations
import hashlib, hmac, os, secrets, threading
from fastapi import BackgroundTasks
from ..ai_engine import ai_analyze_contract_context
from pathlib import Path
from time import perf_counter
from typing import Annotated
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..auth import check_admin_role, get_current_user
from ..database import get_db
from ..models import Contract, ContractClause, ContractImage, LegalReference, User, VerificationLog
from ..schemas import ClauseCreate, ClauseResponse, ContractImageResponse, ContractResponse, VerificationLogResponse, VerificationResponse

router = APIRouter(prefix="/api/contracts", tags=["contracts"])
MAX_FILE_SIZE = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}
CHUNK_SIZE = 1024 * 1024
PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT", str(PROJECT_ROOT / "storage")))
SECURE_STORAGE_ROOT = Path(os.getenv("SECURE_STORAGE_ROOT", str(PROJECT_ROOT / "secure_storage")))
MAX_IMAGE_SIZE = 10 * 1024 * 1024
_legal_reference_cache: list[dict[str, str]] | None = None
_legal_reference_cache_lock = threading.Lock()
_ai_analysis_cache: dict[UUID, dict] = {}
_ai_analysis_cache_lock = threading.Lock()

def _get_legal_reference_cache(db: Session) -> list[dict[str, str]]:
    """Load legal references once per process; clear/reload requires restart."""
    global _legal_reference_cache
    if _legal_reference_cache is None:
        with _legal_reference_cache_lock:
            if _legal_reference_cache is None:
                rows = db.scalars(select(LegalReference).order_by(LegalReference.id)).all()
                _legal_reference_cache = [{"rule_name": row.rule_name, "standard_value": row.standard_value, "reference": row.reference} for row in rows]
    return _legal_reference_cache

def _run_ai_analysis(log_id: UUID, contract_text: str, metadata: dict) -> None:
    report = ai_analyze_contract_context(contract_text, metadata)
    with _ai_analysis_cache_lock:
        _ai_analysis_cache[log_id] = report

def _background_hash_check(path: str, expected: str) -> None:
    """Re-read large stored files after response to detect storage tampering."""
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as stored_file:
            while chunk := stored_file.read(CHUNK_SIZE): digest.update(chunk)
        hmac.compare_digest(digest.hexdigest(), expected)
    except OSError:
        return

async def _save_upload(file: UploadFile, key: Path) -> tuple[int, str]:
    key.parent.mkdir(parents=True, exist_ok=True)
    digest, size = hashlib.sha256(), 0
    try:
        with key.open("wb") as output:
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_FILE_SIZE: raise HTTPException(413, "File exceeds the 20 MiB limit")
                digest.update(chunk); output.write(chunk)
    except Exception:
        key.unlink(missing_ok=True); raise
    if size == 0: key.unlink(missing_ok=True); raise HTTPException(400, "File must not be empty")
    return size, digest.hexdigest()

def _owned(contract: Contract, user: User):
    if contract.uploaded_by != user.id and user.role != "admin": raise HTTPException(403, "Not allowed to access this contract")

async def _save_image(file: UploadFile, target: Path) -> tuple[int, str]:
    target.parent.mkdir(parents=True, exist_ok=True); digest = hashlib.sha256(); size = 0
    try:
        with target.open("wb") as output:
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_IMAGE_SIZE: raise HTTPException(413, "Image exceeds the 10 MiB limit")
                digest.update(chunk); output.write(chunk)
    except Exception:
        target.unlink(missing_ok=True); raise
    if size == 0: target.unlink(missing_ok=True); raise HTTPException(400, "Image must not be empty")
    return size, digest.hexdigest()

@router.post("", response_model=ContractResponse, status_code=201)
async def upload(file: Annotated[UploadFile, File(...)], background_tasks: BackgroundTasks, current: User = Depends(get_current_user), contract_type: Annotated[str | None, Header()] = None, db: Session = Depends(get_db)):
    filename = Path(file.filename or "").name; ext = Path(filename).suffix.lower()
    if not filename or ext not in ALLOWED_EXTENSIONS: raise HTTPException(415, "Unsupported contract file type")
    contract_id, key = uuid4(), STORAGE_ROOT / "contracts" / str(uuid4()) / (secrets.token_hex(16) + ext)
    size, digest = await _save_upload(file, key)
    contract = Contract(id=contract_id, uploaded_by=current.id, original_filename=filename, storage_key=str(key), mime_type=file.content_type or "application/octet-stream", file_size_bytes=size, sha256_hash=digest, contract_type=contract_type)
    db.add(contract)
    try:
        db.commit(); db.refresh(contract)
    except Exception:
        db.rollback(); os.remove(str(key))
        raise HTTPException(500, "Unable to persist contract metadata") from None
    background_tasks.add_task(_background_hash_check, str(key), digest)
    return contract

@router.post("/upload-image", response_model=ContractImageResponse, status_code=201)
async def upload_image(file: Annotated[UploadFile, File(...)], contract_id: UUID | None = None, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if file.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(415, "Only image/jpeg and image/png are supported")
    if contract_id is not None:
        contract = db.get(Contract, contract_id)
        if not contract: raise HTTPException(404, "Contract not found")
        _owned(contract, current)
    filename = Path(file.filename or "image").name
    extension = ".jpg" if file.content_type == "image/jpeg" else ".png"
    image_id = uuid4(); target = SECURE_STORAGE_ROOT / "images" / str(image_id) / (secrets.token_hex(16) + extension)
    size, digest = await _save_image(file, target)
    image = ContractImage(id=image_id, uploaded_by=current.id, contract_id=contract_id, original_filename=filename, storage_key=str(target), mime_type=file.content_type, file_size_bytes=size, sha256_hash=digest)
    db.add(image)
    try: db.commit()
    except Exception:
        db.rollback()
        try: os.remove(str(target))
        except FileNotFoundError: pass
        raise HTTPException(500, "Unable to persist image metadata") from None
    db.refresh(image); return image

@router.get("/{contract_id}", response_model=ContractResponse)
def detail(contract_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    if not contract: raise HTTPException(404, "Contract not found")
    _owned(contract, current)
    return contract

@router.post("/{contract_id}/verify", response_model=VerificationResponse)
async def verify(contract_id: UUID, background_tasks: BackgroundTasks, file: UploadFile | None = File(default=None), current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contract = db.scalar(select(Contract).where(Contract.id == contract_id).with_for_update())
    if not contract: raise HTTPException(404, "Contract not found")
    _owned(contract, current); started = perf_counter(); contract.status = "verifying"
    analysis_text = ""
    try:
        digest = hashlib.sha256()
        if file is not None:
            captured = bytearray()
            while chunk := await file.read(CHUNK_SIZE):
                digest.update(chunk)
                if len(captured) < 512 * 1024: captured.extend(chunk[:512 * 1024 - len(captured)])
            analysis_text = bytes(captured).decode("utf-8", errors="ignore")
        elif Path(contract.storage_key).is_file():
            with Path(contract.storage_key).open("rb") as stored_file:
                while chunk := stored_file.read(CHUNK_SIZE): digest.update(chunk)
        else:
            raise FileNotFoundError(contract.storage_key)
        actual, result, error_code = digest.hexdigest(), None, None
        result = "matched" if hmac.compare_digest(actual, contract.sha256_hash) else "mismatched"
        contract.status = "verified" if result == "matched" else "mismatch"
    except OSError:
        actual, result, error_code = "0" * 64, "failed", "FILE_NOT_FOUND"; contract.status = "failed"
    duration = int((perf_counter() - started) * 1000)
    ai_metadata = {"contract_type": contract.contract_type}
    log = VerificationLog(id=uuid4(), contract_id=contract.id, requested_by=current.id, expected_sha256=contract.sha256_hash, actual_sha256=actual, result=result, error_code=error_code, duration_ms=duration)
    db.add(log); db.commit()
    background_tasks.add_task(_run_ai_analysis, log.id, analysis_text, ai_metadata)
    return VerificationResponse(contract_id=contract.id, expected_sha256=contract.sha256_hash, actual_sha256=actual, result=result, verification_log_id=log.id, duration_ms=duration, risk_score=0, risk_label="processing", ai_overview="AI đang phân tích văn cảnh ở background.", ai_findings=[])

@router.post("/{contract_id}/clauses", response_model=ClauseResponse, status_code=201)
def create_clause(contract_id: UUID, payload: ClauseCreate, current: User = Depends(check_admin_role), db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    if not contract: raise HTTPException(404, "Contract not found")
    _owned(contract, current); clause = ContractClause(id=uuid4(), contract_id=contract_id, **payload.model_dump())
    db.add(clause)
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409, "Clause order already exists for this contract")
    db.refresh(clause); return clause

@router.put("/{contract_id}/clauses/{clause_id}", response_model=ClauseResponse)
def update_clause(contract_id: UUID, clause_id: UUID, payload: ClauseCreate, current: User = Depends(check_admin_role), db: Session = Depends(get_db)):
    clause = db.get(ContractClause, clause_id)
    if not clause or clause.contract_id != contract_id: raise HTTPException(404, "Clause not found")
    clause.clause_type = payload.clause_type; clause.clause_order = payload.clause_order
    clause.title = payload.title; clause.content = payload.content; clause.dynamic_metadata = payload.dynamic_metadata
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409, "Clause order already exists for this contract")
    db.refresh(clause); return clause

@router.delete("/{contract_id}/clauses/{clause_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_clause(contract_id: UUID, clause_id: UUID, current: User = Depends(check_admin_role), db: Session = Depends(get_db)):
    clause = db.get(ContractClause, clause_id)
    if not clause or clause.contract_id != contract_id: raise HTTPException(404, "Clause not found")
    db.delete(clause); db.commit()

@router.get("/{contract_id}/verifications", response_model=list[VerificationLogResponse])
def verification_history(contract_id: UUID, current: User = Depends(check_admin_role), db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    if not contract: raise HTTPException(404, "Contract not found")
    _owned(contract, current)
    return db.scalars(select(VerificationLog).where(VerificationLog.contract_id == contract_id).order_by(VerificationLog.created_at.desc())).all()
