"""API de solución de reviews, aislada de las otras operaciones de análisis."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path

from app.api.dependencies import get_db, require_tenant_roles
from app.repositories.review_repository import ReviewRepository
from app.schemas.review import ReviewRead
from app.schemas.solution import SolutionRequest
from app.services.ai_provider import (
    AIError, AIBlockedResponseError, AIConfigurationError, AICredentialsError,
    AIInputError, AIInvalidResponseError, AIQuotaError, AIRequestError,
    AITimeoutError, AIUnavailableError,
)
from app.services.review_service import ReviewNotFoundError
from app.services.solution_service import (
    SolutionService, SolutionContentError, SolutionConflictError, SolutionPersistenceError,
)
from sqlalchemy.orm import Session


router = APIRouter(prefix="/reviews", tags=["reviews"])
SolutionTenantId = Annotated[int, Depends(require_tenant_roles("usuario_negocio", "admin_tenant"))]


def get_solution_service(db: Annotated[Session, Depends(get_db)]) -> SolutionService:
    return SolutionService(ReviewRepository(db))


SOLUTION_HTTP_ERRORS = {
    SolutionContentError: 422,
    AIInputError: 422,
    AIBlockedResponseError: 422,
    SolutionConflictError: 409,
    SolutionPersistenceError: 500,
    AIInvalidResponseError: 502,
    AIRequestError: 502,
    AIConfigurationError: 503,
    AICredentialsError: 503,
    AIQuotaError: 503,
    AIUnavailableError: 503,
    AITimeoutError: 504,
}


@router.post(
    "/{review_id}/solucion",
    response_model=ReviewRead,
    summary="Generar y guardar una solución de una review del negocio autenticado",
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
def suggest_review(
    review_id: Annotated[int, Path(gt=0)],
    tenant_id: SolutionTenantId,
    service: Annotated[SolutionService, Depends(get_solution_service)],
    payload: Annotated[SolutionRequest | None, Body()] = None,
) -> ReviewRead:
    """Usa la review guardada; no acepta contenido ni campos de autoridad."""
    try:
        return service.suggest(review_id, tenant_id)
    except ReviewNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except AIError as error:
        http_status = SOLUTION_HTTP_ERRORS.get(type(error))
        detail = error.message if http_status is not None else AIError.message
        raise HTTPException(status_code=http_status or 502, detail=detail) from None
