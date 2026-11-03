"""Identidad original independiente de los campos editables de Review."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.external_review_connection import opaque_string


class ExternalReviewIdentity(Base):
    __tablename__ = "external_review_identities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source", "business_data_id", "external_review_id", name="uq_external_review_identity"),
        ForeignKeyConstraint(
            ["review_id", "tenant_id"], ["reviews.id", "reviews.tenant_id"],
            name="fk_external_identity_review_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "source", "business_data_id"],
            ["external_review_connections.tenant_id", "external_review_connections.source", "external_review_connections.business_data_id"],
            name="fk_external_identity_connection",
        ),
        CheckConstraint("length(external_review_id) BETWEEN 1 AND 512", name="ck_external_identity_id_length"),
        CheckConstraint("length(import_fingerprint) = 67 AND substr(import_fingerprint, 1, 3) = 'v1:'", name="ck_external_identity_fingerprint"),
    )

    review_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    tenant_id: Mapped[int] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(opaque_string(100), nullable=False)
    business_data_id: Mapped[str] = mapped_column(opaque_string(128), nullable=False)
    external_review_id: Mapped[str] = mapped_column(opaque_string(512), nullable=False)
    import_fingerprint: Mapped[str] = mapped_column(String(67), nullable=False)
