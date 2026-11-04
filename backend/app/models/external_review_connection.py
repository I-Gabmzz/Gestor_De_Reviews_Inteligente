"""Asociación Google administrada exclusivamente por administración general."""

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, false
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def opaque_string(length: int) -> String:
    """Igualdad exacta, incluidos mayúsculas y espacios, en ambos motores."""
    return String(length).with_variant(String(length, collation="BINARY"), "sqlite").with_variant(
        String(length, collation="C"), "postgresql"
    )


class ExternalReviewConnection(Base):
    __tablename__ = "external_review_connections"
    __table_args__ = (
        CheckConstraint("source = 'Google'", name="ck_external_connection_source"),
        CheckConstraint("length(business_data_id) BETWEEN 1 AND 128", name="ck_external_connection_business"),
        CheckConstraint(
            "NOT persistence_enabled OR "
            "(approval_reference IS NOT NULL AND length(trim(approval_reference)) > 0)",
            name="ck_external_connection_approval",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    source: Mapped[str] = mapped_column(opaque_string(100), primary_key=True)
    business_data_id: Mapped[str] = mapped_column(opaque_string(128), primary_key=True)
    persistence_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    approval_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
