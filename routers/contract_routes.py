"""Contract upload, SHA-256 verification, clauses and audit history."""
from __future__ import annotations
import hashlib, hmac, os, secrets
from pathlib import Path
from time import perf_counter
from typing import Annotated
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from auth import check_admin_role, get_current_user
from database import get_db
from models import Contract, ContractClause, User, VerificationLog
from schemas import ClauseCreate, ClauseResponse, ContractResponse, VerificationLogResponse, VerificationResponse

router = APIRouter(prefix="/api/contracts", tags=["contracts"])
MAX_FILE_SIZE = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}
CHUNK_SIZE = 1024 * 1024
STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT", "storage"))

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

@router.post("", response_model=ContractResponse, status_code=201)
async def upload(file: Annotated[UploadFile, File(...)], current: User = Depends(get_current_user), contract_type: Annotated[str | None, Header()] = None, db: Session = Depends(get_db)):
    filename = Path(file.filename or "").name; ext = Path(filename).suffix.lower()
    if not filename or ext not in ALLOWED_EXTENSIONS: raise HTTPException(415, "Unsupported contract file type")
    contract_id, key = uuid4(), STORAGE_ROOT / "contracts" / str(uuid4()) / (secrets.token_hex(16) + ext)
    size, digest = await _save_upload(file, key)
    contract = Contract(id=contract_id, uploaded_by=current.id, original_filename=filename, storage_key=str(key), mime_type=file.content_type or "application/octet-stream", file_size_bytes=size, sha256_hash=digest, contract_type=contract_type)
    db.add(contract); db.commit(); db.refresh(contract)
    return contract

@router.get("/{contract_id}", response_model=ContractResponse)
def detail(contract_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    if not contract: raise HTTPException(404, "Contract not found")
    _owned(contract, current)
    return contract

@router.post("/{contract_id}/verify", response_model=VerificationResponse)
async def verify(contract_id: UUID, file: UploadFile | None = File(default=None), current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    if not contract: raise HTTPException(404, "Contract not found")
    _owned(contract, current); started = perf_counter(); contract.status = "verifying"
    try:
        digest = hashlib.sha256()
        if file is not None:
            while chunk := await file.read(CHUNK_SIZE): digest.update(chunk)
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
    log = VerificationLog(id=uuid4(), contract_id=contract.id, requested_by=current.id, expected_sha256=contract.sha256_hash, actual_sha256=actual, result=result, error_code=error_code, duration_ms=duration)
    db.add(log); db.commit()
    return VerificationResponse(contract_id=contract.id, expected_sha256=contract.sha256_hash, actual_sha256=actual, result=result, verification_log_id=log.id, duration_ms=duration)

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
