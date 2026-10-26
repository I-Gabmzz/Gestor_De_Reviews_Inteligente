"""Coordina la generación de T2 y su escritura condicionada para T3."""

from sqlalchemy.exc import SQLAlchemyError

from app.models.review import Review
from app.repositories.review_repository import ReviewRepository
from app.services.ai_provider import AIError
from app.services.review_service import ReviewNotFoundError
from app.services.suggested_response_service import SuggestedResponseService


class SuggestedResponseConflictError(AIError):
    code = "review_changed"
    message = "La review o su sugerencia cambió durante la generación; actualiza y vuelve a intentarlo"


class SuggestedResponsePersistenceError(AIError):
    code = "persistence"
    message = "No fue posible acceder a la respuesta sugerida de la review"


class SuggestedResponseAnalysisService:
    def __init__(
        self,
        repository: ReviewRepository,
        generator: SuggestedResponseService | None = None,
    ) -> None:
        self.repository = repository
        self.generator = generator if generator is not None else SuggestedResponseService()

    def generate_for_review(self, review_id: int, tenant_id: int) -> Review:
        """El endpoint autoriza; el contenido y la versión se leen de la review del tenant."""
        try:
            review = self.repository.get_by_id_for_tenant(review_id, tenant_id)
        except SQLAlchemyError:
            raise SuggestedResponsePersistenceError() from None
        if review is None:
            raise ReviewNotFoundError(review_id)
        content = review.contenido
        version = review.respuesta_sugerida_version
        result = self.generator.generate(content)
        try:
            saved = self.repository.save_suggested_response(
                review_id, tenant_id, result,
                expected_content=content, expected_version=version,
            )
        except SQLAlchemyError:
            raise SuggestedResponsePersistenceError() from None
        if saved is None:
            raise SuggestedResponseConflictError()
        return saved
