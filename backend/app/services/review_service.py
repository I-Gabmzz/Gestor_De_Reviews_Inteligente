from app.models.review import Review
from app.repositories.review_repository import ReviewRepository
from app.schemas.auth import AuthenticatedUser
from app.schemas.review import ReviewStatus, ReviewUpdate
from app.services.tenant_context_service import resolve_tenant_id


class ReviewNotFoundError(Exception):
    def __init__(self, review_id: int) -> None:
        super().__init__(f"Review con id {review_id} no encontrada")


class ReviewService:
    """Casos de uso de reviews aislados por tenant."""

    def __init__(self, repository: ReviewRepository) -> None:
        self.repository = repository

    def list_by_tenant(self, tenant_id: int) -> list[Review]:
        return self.repository.list_by_tenant(tenant_id)

    def get_by_id(self, review_id: int, tenant_id: int) -> Review:
        review = self.repository.get_by_id_for_tenant(review_id, tenant_id)
        if review is None:
            raise ReviewNotFoundError(review_id)
        return review

    def update(self, review_id: int, tenant_id: int, data: ReviewUpdate) -> Review:
        review = self.get_by_id(review_id, tenant_id)
        return self.repository.update(review, data.model_dump(exclude_unset=True))

    def update_review_status(
        self,
        review_id: int,
        tenant_id: int,
        new_status: ReviewStatus,
    ) -> Review:
        status = ReviewStatus(new_status)
        review = self.get_by_id(review_id, tenant_id)
        return self.repository.update_status(review, status)

    def get_by_id_for_current_user(
        self,
        review_id: int,
        current_user: AuthenticatedUser,
    ) -> Review | None:
        """Mantiene el contrato de HU-02 para sus validaciones de aislamiento."""
        tenant_id = resolve_tenant_id(current_user)
        return self.repository.get_by_id_for_tenant(review_id, tenant_id)
