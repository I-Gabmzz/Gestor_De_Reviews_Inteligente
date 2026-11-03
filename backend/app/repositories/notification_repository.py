"""Avisos internos consultados siempre junto con el ámbito actual de la review."""

from datetime import datetime, timezone

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import CompileError
from sqlalchemy.orm import Session

from app.models.notification import ReviewNotification
from app.models.review import Review


def high_notification_insert(dialect_name: str, review_id: int, tenant_id: int):
    """Inserción condicional e idempotente en los motores usados por el proyecto."""
    factories = {"sqlite": sqlite_insert, "postgresql": postgresql_insert}
    if dialect_name not in factories:
        raise CompileError("El motor no admite la inserción idempotente de avisos")
    return factories[dialect_name](ReviewNotification).from_select(
        ["tenant_id", "review_id", "creada_en"],
        select(literal(tenant_id), Review.id, literal(datetime.now(timezone.utc))).where(
            Review.id == review_id, Review.tenant_id == tenant_id, Review.prioridad == "Alta",
        ),
    ).on_conflict_do_nothing(index_elements=["tenant_id", "review_id"])


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
        """Crea o recupera el mismo aviso; no hace commit ni actualiza su fecha."""
        self.db.execute(high_notification_insert(self.db.get_bind().dialect.name, review_id, tenant_id))
        return self.db.scalar(select(ReviewNotification).join(Review, Review.id == ReviewNotification.review_id).where(
            ReviewNotification.review_id == review_id, ReviewNotification.tenant_id == tenant_id,
            Review.tenant_id == tenant_id, Review.prioridad == "Alta",
        ))
