"""Repositorio de acceso a datos para la entidad Review."""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.review import Review


class ReviewRepository:
    """Centraliza la lectura y escritura de reviews."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_tenant(self, tenant_id: int) -> list[Review]:
        statement = (
            select(Review)
            .where(Review.tenant_id == tenant_id)
            .order_by(Review.fecha.desc(), Review.id.desc())
        )
        return list(self.db.scalars(statement))

    def get_by_id_for_tenant(self, review_id: int, tenant_id: int) -> Review | None:
        statement = select(Review).where(
            Review.id == review_id,
            Review.tenant_id == tenant_id,
        )
        return self.db.scalar(statement)

    def create_many(self, reviews: list[Review]) -> list[Review]:
        """Inserta una lista de reviews en una sola transacción."""
        if not reviews:
            return []

        try:
            self.db.add_all(reviews)
            self.db.commit()
            for review in reviews:
                self.db.refresh(review)
            return reviews
        except SQLAlchemyError:
            self.db.rollback()
            raise
