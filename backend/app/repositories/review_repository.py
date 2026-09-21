from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.review import Review


class ReviewRepository:
    """Acceso mínimo a reviews con aislamiento por tenant."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id_for_tenant(self, review_id: int, tenant_id: int) -> Review | None:
        statement = select(Review).where(
            Review.id == review_id,
            Review.tenant_id == tenant_id,
        )
        return self.db.scalar(statement)
