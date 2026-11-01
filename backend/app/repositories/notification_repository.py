"""Avisos internos consultados siempre junto con el ámbito actual de la review."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notification import ReviewNotification
from app.models.review import Review


class NotificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _visible(self, tenant_id: int):
        return (
            select(
                ReviewNotification.id, ReviewNotification.review_id, ReviewNotification.creada_en,
                Review.autor, func.substr(Review.contenido, 1, 180).label("extracto"),
            )
            .join(Review, Review.id == ReviewNotification.review_id)
            .where(ReviewNotification.tenant_id == tenant_id, Review.tenant_id == tenant_id, Review.prioridad == "Alta")
        )

    def list_for_tenant(self, tenant_id: int, *, limit: int, offset: int) -> tuple[list[dict], int]:
        visible = self._visible(tenant_id)
        total = self.db.scalar(select(func.count()).select_from(visible.subquery())) or 0
        rows = self.db.execute(
            visible.order_by(ReviewNotification.creada_en.desc(), ReviewNotification.id.desc()).limit(limit).offset(offset)
        ).mappings()
        return [dict(row) for row in rows], total

    def add_for_high_review(self, review_id: int, tenant_id: int) -> ReviewNotification | None:
        """Prepara el aviso sin confirmar la transacción del llamador."""
        available = self.db.scalar(select(Review.id).where(
            Review.id == review_id, Review.tenant_id == tenant_id, Review.prioridad == "Alta",
        ))
        if available is None:
            return None
        notification = ReviewNotification(review_id=review_id, tenant_id=tenant_id)
        self.db.add(notification)
        self.db.flush()
        return notification
