from datetime import date

from app.models.review import Review
from app.repositories.review_repository import ReviewRepository
from app.schemas.auth import AuthenticatedUser
from app.services.tenant_context_service import resolve_tenant_id

class ReviewNotFoundError(Exception):
    def __init__(self, review_id: int) -> None:
        super().__init__(f"Review con id {review_id} no encontrada")


class ReviewFilterValidationError(ValueError):
    """Los criterios de consulta no cumplen el contrato de HU-10."""


class ReviewService:
    """Casos de uso de consulta de reviews aislados por tenant."""

    def __init__(self, repository: ReviewRepository) -> None:
        self.repository = repository

    def list_by_tenant(
        self,
        tenant_id: int,
        busqueda: str | None = None,
        *,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
        puntuacion: int | None = None,
        estado: str | None = None,
        fuente: str | None = None,
    ) -> list[Review]:
        for field, value in (("fecha_desde", fecha_desde), ("fecha_hasta", fecha_hasta)):
            if value is not None and type(value) is not date:
                raise ReviewFilterValidationError(f"{field} debe ser una fecha")
        if (
            fecha_desde is not None
            and fecha_hasta is not None
            and fecha_desde > fecha_hasta
        ):
            raise ReviewFilterValidationError("fecha_desde no puede ser posterior a fecha_hasta")
        if puntuacion is not None and (
            type(puntuacion) is not int or not 1 <= puntuacion <= 5
        ):
            raise ReviewFilterValidationError("puntuacion debe ser un entero entre 1 y 5")
        if estado is not None and estado not in ("nueva", "en_revision", "atendida"):
            raise ReviewFilterValidationError("estado debe ser nueva, en_revision o atendida")
        if fuente is not None and not isinstance(fuente, str):
            raise ReviewFilterValidationError("fuente debe ser texto")

        normalized_search = busqueda.strip() if busqueda is not None else None
        normalized_source = fuente.strip() if fuente is not None else None
        return self.repository.list_by_tenant(
            tenant_id,
            busqueda=normalized_search or None,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            puntuacion=puntuacion,
            estado=estado,
            fuente=normalized_source or None,
        )

    def get_by_id(self, review_id: int, tenant_id: int) -> Review:
        review = self.repository.get_by_id_for_tenant(review_id, tenant_id)
        if review is None:
            raise ReviewNotFoundError(review_id)
        return review

    def get_by_id_for_current_user(
        self,
        review_id: int,
        current_user: AuthenticatedUser,
    ) -> Review | None:
        """Mantiene el contrato de HU-02 para sus validaciones de aislamiento."""
        tenant_id = resolve_tenant_id(current_user)
        return self.repository.get_by_id_for_tenant(review_id, tenant_id)
