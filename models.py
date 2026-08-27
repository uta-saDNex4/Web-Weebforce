"""SQLAlchemy models for the empty Contract Verifier database."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Uuid, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Contract(Base):
    """Minimal contract table needed by the clause foreign key.

    The upload implementation can extend this model with the remaining columns
    from AGENTS.md as the repository moves away from its temporary in-memory
    storage.
    """

    __tablename__ = "contracts"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)


class ContractClause(Base):
    """A flexible, ordered clause belonging to a contract."""

    __tablename__ = "contract_clauses"
    __table_args__ = (UniqueConstraint("contract_id", "clause_order", name="uq_contract_clause_order"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    contract_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    clause_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    clause_order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON is portable across SQLite/PostgreSQL; PostgreSQL can use JSONB later.
    # Expected rental metadata keys include gia_thue, tien_coc, tien_dien,
    # tien_nuoc and dien_tich. Additional keys are allowed per clause_type.
    dynamic_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
