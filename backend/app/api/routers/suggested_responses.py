"""Generación explícita de borradores; sin publicación ni envío al cliente."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_tenant_roles
from app.repositories.review_repository import ReviewRepository
from app.schemas.review import ReviewRead
from app.schemas.suggested_response_request import SuggestedResponseRequest
from app.services.ai_provider import (
    AIError, AIBlockedResponseError, AIConfigurationError, AICredentialsError,
    AIInputError, AIInvalidResponseError, AIQuotaError, AIRequestError,
    AITimeoutError, AIUnavailableError,
)
from app.services.review_service import ReviewNotFoundError
from app.services.suggested_response_analysis_service import (
    SuggestedResponseAnalysisService, SuggestedResponseConflictError,
    SuggestedResponsePersistenceError,
)
from app.services.suggested_response_service import (
    SuggestedResponseContentError, SuggestedResponsePrivacyError,
)


router = APIRouter(prefix="/reviews", tags=["reviews"])
SuggestionTenantId = Annotated[
    int, Depends(require_tenant_roles("usuario_negocio", "admin_tenant"))
]


def get_suggested_response_service(
    db: Annotated[Session, Depends(get_db)],
) -> SuggestedResponseAnalysisService:
    return SuggestedResponseAnalysisService(ReviewRepository(db))


SUGGESTED_RESPONSE_HTTP_ERRORS = {
    SuggestedResponseContentError: 422,
    SuggestedResponsePrivacyError: 422,
    AIInputError: 422,
    AIBlockedResponseError: 422,
    SuggestedResponseConflictError: 409,
    SuggestedResponsePersistenceError: 500,
    AIInvalidResponseError: 502,
    AIRequestError: 502,
    AIConfigurationError: 503,
    AICredentialsError: 503,
    AIQuotaError: 503,
    AIUnavailableError: 503,
    AITimeoutError: 504,
}


@router.post(
    "/{review_id}/respuesta-sugerida",
    response_model=ReviewRead,
    summary="Generar y guardar una sugerencia de respuesta sin enviarla al cliente",
    responses={code: {"description": description} for code, description in {
        401: "Token ausente o inválido",
        403: "Usuario, rol o negocio no autorizado",
        404: "Review no disponible en el negocio autenticado",
        409: "La review o sugerencia cambió durante la generación",
        422: "Solicitud o contenido no compatible con una sugerencia segura",
        500: "Error de persistencia",
        502: "Respuesta no válida del proveedor",
        503: "Servicio de IA no disponible",
        504: "Tiempo de espera agotado",
    }.items()},
)
def generate_suggested_response(
    review_id: Annotated[int, Path(gt=0)],
    tenant_id: SuggestionTenantId,
    service: Annotated[SuggestedResponseAnalysisService, Depends(get_suggested_response_service)],
    payload: Annotated[SuggestedResponseRequest | None, Body()] = None,
) -> ReviewRead:
    try:
        return service.generate_for_review(review_id, tenant_id)
    except ReviewNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except AIError as error:
        http_status = SUGGESTED_RESPONSE_HTTP_ERRORS.get(type(error))
        detail = error.message if http_status is not None else AIError.message
        raise HTTPException(status_code=http_status or 502, detail=detail) from None
