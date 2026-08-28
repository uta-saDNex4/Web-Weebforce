"""Import the three Excel datasets into the Docker PostgreSQL database.

The importer is deliberately idempotent: rows created by a previous import
are removed for the dedicated import user before the Excel rows are inserted.
It never inserts seed users other than the documented import account.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import bcrypt
import pandas as pd
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Contract, ContractClause, LegalReference, RiskRule, User, VerificationLog

DATABASE_URL = "postgresql://admin:matkhau_xinfu@localhost:5432/contract_verifier_db"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
IMPORT_EMAIL = "excel-import@contract-verifier.local"
IMPORT_PASSWORD = "change-this-import-password"

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def text(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip()

def non_negative_number(value: object, field: str) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be numeric: {value!r}") from None
    if number < 0:
        raise ValueError(f"{field} must not be negative: {number}")
    return number

def row_hash(row: dict[str, object]) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

def get_or_create_import_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == IMPORT_EMAIL))
    if user:
        return user
    user = User(id=uuid4(), email=IMPORT_EMAIL, password_hash=bcrypt.hashpw(IMPORT_PASSWORD.encode(), bcrypt.gensalt()).decode(), full_name="Excel Importer", role="admin", is_active=True, created_at=utc_now(), updated_at=utc_now())
    db.add(user); db.flush()
    return user

def import_rental_tests(db: Session, user: User) -> int:
    frame = pd.read_excel(DATA_DIR / "test_set_labeled.xlsx")
    required = ["district", "address", "area_m2", "base_rent", "standard_deposit", "electricity_rate", "water_rate", "reference"]
    missing = [column for column in required if column not in frame.columns]
    if missing: raise ValueError(f"test_set_labeled.xlsx missing columns: {missing}")
    count = 0
    for raw in frame[required].to_dict(orient="records"):
        row = {key: (value.item() if hasattr(value, "item") else value) for key, value in raw.items()}
        now = utc_now(); contract_id = uuid4(); digest = row_hash(row)
        serialized = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        contract = Contract(id=contract_id, uploaded_by=user.id, original_filename=f"excel_rental_{count + 1:04d}.json", storage_key=f"imports/test_set_labeled/{contract_id}.json", mime_type="application/json", file_size_bytes=len(serialized) or 1, sha256_hash=digest, contract_type="thuê trọ", status="uploaded", created_at=now, updated_at=now)
        clause = ContractClause(id=uuid4(), contract_id=contract_id, clause_type="rental_pricing", clause_order=1, title=f"Giá thuê {text(row['address'])}", content=None, dynamic_metadata={"gia_thue": non_negative_number(row["base_rent"], "base_rent"), "tien_coc": non_negative_number(row["standard_deposit"], "standard_deposit"), "tien_dien": non_negative_number(row["electricity_rate"], "electricity_rate"), "tien_nuoc": non_negative_number(row["water_rate"], "water_rate"), "district": text(row["district"]), "address": text(row["address"]), "area_m2": float(row["area_m2"]), "reference": text(row["reference"])}, created_at=now, updated_at=now)
        db.add_all([contract, clause]); count += 1
    return count

def import_references(db: Session) -> tuple[int, int]:
    legal = pd.read_excel(DATA_DIR / "legal_references.xlsx")
    risk = pd.read_excel(DATA_DIR / "risk_rules_master.xlsx")
    legal_required = ["clause_category", "rule_name", "standard_value", "unit", "reference"]
    risk_required = ["target_section", "keyword_trigger", "risk_level", "default_warning_message"]
    if missing := [c for c in legal_required if c not in legal.columns]: raise ValueError(f"legal_references.xlsx missing columns: {missing}")
    if missing := [c for c in risk_required if c not in risk.columns]: raise ValueError(f"risk_rules_master.xlsx missing columns: {missing}")
    now = utc_now()
    for row in legal[legal_required].to_dict(orient="records"):
        db.add(LegalReference(id=uuid4(), clause_category=text(row["clause_category"]), rule_name=text(row["rule_name"]), standard_value=text(row["standard_value"]), unit=text(row["unit"]), reference=text(row["reference"]), created_at=now, updated_at=now))
    for row in risk[risk_required].to_dict(orient="records"):
        db.add(RiskRule(id=uuid4(), target_section=text(row["target_section"]), keyword_trigger=text(row["keyword_trigger"]), risk_level=text(row["risk_level"]).lower(), default_warning_message=text(row["default_warning_message"]), created_at=now, updated_at=now))
    return len(legal), len(risk)

def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        user = get_or_create_import_user(db)
        old_contract_ids = db.scalars(select(Contract.id).where(Contract.uploaded_by == user.id)).all()
        if old_contract_ids:
            db.execute(delete(VerificationLog).where(VerificationLog.contract_id.in_(old_contract_ids)))
            db.execute(delete(ContractClause).where(ContractClause.contract_id.in_(old_contract_ids)))
            db.execute(delete(Contract).where(Contract.id.in_(old_contract_ids)))
        db.execute(delete(LegalReference)); db.execute(delete(RiskRule))
        rental_count = import_rental_tests(db, user)
        legal_count, risk_count = import_references(db)
        db.commit()
        print(f"Imported {rental_count} contracts, {rental_count} contract clauses, {legal_count} legal references and {risk_count} risk rules.")

if __name__ == "__main__":
    main()
