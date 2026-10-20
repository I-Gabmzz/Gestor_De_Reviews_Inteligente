"""Detección de tema con la autorización operativa vigente de HU-04."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_tenant_roles
from app.repositories.review_repository import ReviewRepository
from app.schemas.review import ReviewRead
from app.schemas.topic import TopicRequest
from app.services.ai_provider import (
    AIError, AIBlockedResponseError, AIConfigurationError, AICredentialsError,
    AIInputError, AIInvalidResponseError, AIQuotaError, AIRequestError,
    AITimeoutError, AIUnavailableError,
)
from app.services.review_service import ReviewNotFoundError
from app.services.topic_service import (
    TopicService, TopicContentError, TopicConflictError, TopicPersistenceError,
)


router = APIRouter(prefix="/reviews", tags=["reviews"])
DatabaseSession = Annotated[Session, Depends(get_db)]
TopicTenantId = Annotated[
    int, Depends(require_tenant_roles("usuario_negocio", "admin_tenant"))
]


def get_topic_service(db: DatabaseSession) -> TopicService:
    return TopicService(ReviewRepository(db))


TOPIC_HTTP_ERRORS = {
    TopicContentError: 422,
    AIInputError: 422,
    AIBlockedResponseError: 422,
    TopicConflictError: 409,
    TopicPersistenceError: 500,
    AIInvalidResponseError: 502,
    AIRequestError: 502,
    AIConfigurationError: 503,
    AICredentialsError: 503,
    AIQuotaError: 503,
    AIUnavailableError: 503,
    AITimeoutError: 504,
}


@router.post(
    "/{review_id}/tema",
    response_model=ReviewRead,
    status_code=status.HTTP_200_OK,
    summary="Detectar el tema principal de una review del negocio autenticado",
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
def detect_topic(
    review_id: Annotated[int, Path(gt=0)],
    tenant_id: TopicTenantId,
    service: Annotated[TopicService, Depends(get_topic_service)],
    payload: Annotated[TopicRequest | None, Body()] = None,
) -> ReviewRead:
    """No admite tenant, contenido ni resultados proporcionados por el cliente."""
    try:
        return service.detect(review_id, tenant_id)
    except ReviewNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except AIError as error:
        http_status = TOPIC_HTTP_ERRORS.get(type(error))
        detail = str(error) if http_status is not None else AIError.message
        raise HTTPException(status_code=http_status or 502, detail=detail) from None
