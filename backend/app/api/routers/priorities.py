"""Generación y persistencia de prioridad para el negocio autenticado."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_tenant_roles
from app.repositories.review_repository import ReviewRepository
from app.schemas.priority import PriorityRequest
from app.schemas.review import ReviewRead
from app.services.ai_provider import (
    AIError, AIBlockedResponseError, AIConfigurationError, AICredentialsError,
    AIInputError, AIInvalidResponseError, AIQuotaError, AIRequestError,
    AITimeoutError, AIUnavailableError,
)
from app.services.priority_service import (
    PriorityService, PriorityContentError, PriorityConflictError,
    PriorityPersistenceError, PriorityReadError,
)
from app.services.review_service import ReviewNotFoundError


router = APIRouter(prefix="/reviews", tags=["reviews"])
DatabaseSession = Annotated[Session, Depends(get_db)]
PriorityTenantId = Annotated[
    int, Depends(require_tenant_roles("usuario_negocio", "admin_tenant"))
]


def get_priority_service(db: DatabaseSession) -> PriorityService:
    return PriorityService(ReviewRepository(db))


PRIORITY_HTTP_ERRORS = {
    PriorityContentError: 422,
    AIInputError: 422,
    AIBlockedResponseError: 422,
    PriorityConflictError: 409,
    PriorityReadError: 500,
    PriorityPersistenceError: 500,
    AIInvalidResponseError: 502,
    AIRequestError: 502,
    AIConfigurationError: 503,
    AICredentialsError: 503,
    AIQuotaError: 503,
    AIUnavailableError: 503,
    AITimeoutError: 504,
}


@router.post(
    "/{review_id}/prioridad",
    response_model=ReviewRead,
    status_code=status.HTTP_200_OK,
    summary="Determinar y guardar la prioridad de una review del negocio autenticado",
    responses={code: {"description": description} for code, description in {
        401: "Token ausente o inválido",
        403: "Usuario, rol o negocio no autorizado",
        404: "Review no disponible en el negocio autenticado",
        409: "La review cambió durante el análisis",
        422: "Solicitud o contenido no analizable",
        500: "Error de lectura o persistencia",
        502: "Respuesta no válida del proveedor",
        503: "Servicio de IA no disponible",
        504: "Tiempo de espera agotado",
    }.items()},
)
def prioritize_review(
    review_id: Annotated[int, Path(gt=0)],
    tenant_id: PriorityTenantId,
    service: Annotated[PriorityService, Depends(get_priority_service)],
    payload: Annotated[PriorityRequest | None, Body()] = None,
) -> ReviewRead:
    """No admite prioridad manual ni tenant o contenido proporcionados por el cliente."""
    try:
        return service.prioritize(review_id, tenant_id)
    except ReviewNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except AIError as error:
        http_status = PRIORITY_HTTP_ERRORS.get(type(error))
        detail = str(error) if http_status is not None else AIError.message
        raise HTTPException(status_code=http_status or 502, detail=detail) from None
