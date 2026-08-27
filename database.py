"""SQLAlchemy connection configuration and empty schema creation."""
from __future__ import annotations
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from models import Base

SQLALCHEMY_DATABASE_URL = "postgresql://admin:matkhau_xinfu@localhost:5432/contract_verifier_db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

def create_empty_database() -> None:
    """Create schema only. No users, contracts or audit logs are seeded."""
    Base.metadata.create_all(bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
