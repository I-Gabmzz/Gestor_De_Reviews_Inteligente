"""API de resumen de reviews, aislada de las otras operaciones de análisis."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path

from app.api.dependencies import get_db, require_tenant_roles
from app.repositories.review_repository import ReviewRepository
from app.schemas.review import ReviewRead
from app.schemas.summary import SummaryRequest
from app.services.ai_provider import (
    AIError, AIBlockedResponseError, AIConfigurationError, AICredentialsError,
    AIInputError, AIInvalidResponseError, AIQuotaError, AIRequestError,
    AITimeoutError, AIUnavailableError,
)
from app.services.review_service import ReviewNotFoundError
from app.services.summary_service import (
    SummaryService, SummaryContentError, SummaryConflictError, SummaryPersistenceError,
)
from sqlalchemy.orm import Session


router = APIRouter(prefix="/reviews", tags=["reviews"])
SummaryTenantId = Annotated[int, Depends(require_tenant_roles("usuario_negocio", "admin_tenant"))]


def get_summary_service(db: Annotated[Session, Depends(get_db)]) -> SummaryService:
    return SummaryService(ReviewRepository(db))


SUMMARY_HTTP_ERRORS = {
    SummaryContentError: 422,
    AIInputError: 422,
    AIBlockedResponseError: 422,
    SummaryConflictError: 409,
    SummaryPersistenceError: 500,
    AIInvalidResponseError: 502,
    AIRequestError: 502,
    AIConfigurationError: 503,
    AICredentialsError: 503,
    AIQuotaError: 503,
    AIUnavailableError: 503,
    AITimeoutError: 504,
}


@router.post(
    "/{review_id}/resumen",
    response_model=ReviewRead,
    summary="Generar y guardar un resumen de una review del negocio autenticado",
    responses={code: {"description": description} for code, description in {
        401: "Token ausente o inválido",
        403: "Usuario, rol o negocio no autorizado",
        404: "Review no disponible en el negocio autenticado",
        409: "La review cambió durante el análisis",
        422: "Solicitud o contenido no analizable",
        500: "Error de persistencia",
        502: "Respuesta no válida del proveedor",
        503: "Servicio de IA no disponible",
        504: "Tiempo de espera agotado",
    }.items()},
)
def summarize_review(
    review_id: Annotated[int, Path(gt=0)],
    tenant_id: SummaryTenantId,
    service: Annotated[SummaryService, Depends(get_summary_service)],
    payload: Annotated[SummaryRequest | None, Body()] = None,
) -> ReviewRead:
    """Usa la review guardada; no acepta contenido ni campos de autoridad."""
    try:
        return service.summarize(review_id, tenant_id)
    except ReviewNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except AIError as error:
        http_status = SUMMARY_HTTP_ERRORS.get(type(error))
        detail = error.message if http_status is not None else AIError.message
        raise HTTPException(status_code=http_status or 502, detail=detail) from None
