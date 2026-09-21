from app.models.review import Review
from app.repositories.review_repository import ReviewRepository
from app.schemas.auth import AuthenticatedUser
from app.services.tenant_context_service import resolve_tenant_id


def get_review_placeholder() -> dict[str, str]:
    """Placeholder para la futura Historia de Usuario de reviews."""
    return {"message": "Not implemented"}


class ReviewService:
    """Operación interna mínima para validar aislamiento; no expone HU-07."""

    def __init__(self, repository: ReviewRepository) -> None:
        self.repository = repository

    def get_by_id_for_current_user(
        self,
        review_id: int,
        current_user: AuthenticatedUser,
    ) -> Review | None:
        tenant_id = resolve_tenant_id(current_user)
        return self.repository.get_by_id_for_tenant(review_id, tenant_id)
