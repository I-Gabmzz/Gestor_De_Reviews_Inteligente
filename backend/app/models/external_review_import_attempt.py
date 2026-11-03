"""Admission metadata only: no review payloads, credentials or provider tokens."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, column, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.external_review_connection import opaque_string


class ExternalReviewImportAttempt(Base):
    __tablename__ = "external_review_import_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "source", "business_data_id"],
            ["external_review_connections.tenant_id", "external_review_connections.source", "external_review_connections.business_data_id"],
            name="fk_external_import_connection",
        ),
        UniqueConstraint("tenant_id", "source", "business_data_id", "active", name="uq_external_import_active"),
        CheckConstraint("reserved_requests BETWEEN 1 AND 5", name="ck_external_import_budget"),
        # Compile TRUE as 1 on SQLite: an extra column named "true" cannot
        # change this CHECK. PostgreSQL retains its native boolean literal.
        CheckConstraint(
            column("active").is_(None) | (column("active") == true()),
            name="ck_external_import_active",
        ),
        CheckConstraint(
            "(state = 'running' AND active IS NOT NULL) OR "
            "(state = 'unknown' AND active IS NOT NULL) OR "
            "(state = 'finished' AND active IS NULL)", name="ck_external_import_state",
        ),
        Index("ix_external_import_started", "started_at"),
    )

    operation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(opaque_string(100), nullable=False)
    business_data_id: Mapped[str] = mapped_column(opaque_string(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reserved_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    state: Mapped[str] = mapped_column(opaque_string(16), nullable=False)
