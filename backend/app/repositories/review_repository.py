"""Repositorio de acceso a datos para la entidad Review.

TASK 3318: Persistencia de reviews importadas.
"""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.review import Review


class ReviewRepository:
    """Estructura para el acceso a datos de reviews."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id_for_tenant(self, review_id: int, tenant_id: int) -> Review | None:
        """Obtiene una reseña por id verificando el tenant_id."""
        statement = select(Review).where(
            Review.id == review_id,
            Review.tenant_id == tenant_id,
        )
        return self.db.scalar(statement)

    def create_many(self, reviews: list[Review]) -> list[Review]:
        """Inserta masivamente una lista de objetos Review en la base de datos.

        Args:
            reviews: Lista de instancias del modelo SQLAlchemy Review.

        Returns:
            Lista de objetos Review insertados con sus IDs asignados.

        Raises:
            SQLAlchemyError: Si ocurre un error de persistencia o integridad transaccional.
        """
        if not reviews:
            return []

        try:
            self.db.add_all(reviews)
            self.db.commit()
            for review in reviews:
                self.db.refresh(review)
            return reviews
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise exc
