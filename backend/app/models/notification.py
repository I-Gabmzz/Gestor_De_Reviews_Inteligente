"""Evento interno de prioridad Alta asociado a una review y a su negocio."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReviewNotification(Base):
    __tablename__ = "review_notifications"
    __table_args__ = (
        UniqueConstraint("tenant_id", "review_id", name="uq_review_notification_per_tenant"),
        Index("ix_review_notifications_tenant_created", "tenant_id", "creada_en", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
