"""Protected, synchronous import; no public provisioning or activation endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import bearer_scheme, get_current_user
from app.core.external_import_config import ExternalImportSettings
from app.db.connection import SessionLocal
from app.schemas.auth import AuthenticatedUser
from app.schemas.external_review_import import (
    ExternalReviewImportAccessErrorResponse, ExternalReviewImportAuthErrorResponse,
    ExternalReviewImportErrorResponse, ExternalReviewImportRequest,
    ExternalReviewImportResponse, ExternalReviewImportUnprocessableResponse,
)
from app.services.external_review_import_service import ExternalReviewImportError, ExternalReviewImportService


router = APIRouter(prefix="/integrations/google/reviews", tags=["external reviews"])


def get_external_import_sessions() -> sessionmaker:
    return SessionLocal


ImportSessions = Annotated[sessionmaker, Depends(get_external_import_sessions)]


def get_external_import_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    sessions: ImportSessions,
) -> AuthenticatedUser:
    # Reuse authentication, but close its session BEFORE the handler can do HTTP.
    with sessions() as db:
        user = get_current_user(credentials, db)
    if user.rol not in ("usuario_negocio", "admin_tenant"):
        raise HTTPException(status_code=403, detail="El rol no está autorizado")
    return user


def get_external_import_service(sessions: ImportSessions) -> ExternalReviewImportService:
    try:
        policy = ExternalImportSettings()
    except ValidationError:
        error = ExternalReviewImportError("policy_unavailable")
        raise HTTPException(status_code=error.http_status, detail=error.detail.model_dump()) from None
    return ExternalReviewImportService(sessions, policy)


@router.post("/import", response_model=ExternalReviewImportResponse, responses={
    401: {"model": ExternalReviewImportAuthErrorResponse, "description": "Autenticación ausente o inválida"},
    403: {"model": ExternalReviewImportAccessErrorResponse, "description": "Acceso o habilitación rechazados"},
    404: {"model": ExternalReviewImportErrorResponse, "description": "Conexión no disponible para el tenant"},
    409: {"model": ExternalReviewImportErrorResponse, "description": "Operación pendiente, adquisición incompleta o conflicto"},
    422: {"model": ExternalReviewImportUnprocessableResponse, "description": "Validación de solicitud (lista) o rechazo funcional (objeto)"},
    429: {"model": ExternalReviewImportErrorResponse, "description": "Presupuesto local agotado"},
    500: {"model": ExternalReviewImportAccessErrorResponse, "description": "Fallo interno o configuración inválida del usuario"},
    502: {"model": ExternalReviewImportErrorResponse, "description": "Respuesta o identidad del proveedor no verificable"},
    503: {"model": ExternalReviewImportErrorResponse, "description": "Política, esquema, admisión, proveedor o persistencia no disponibles"},
    504: {"model": ExternalReviewImportErrorResponse, "description": "Timeout del proveedor"},
})
def import_external_reviews(
    request: ExternalReviewImportRequest,
    user: Annotated[AuthenticatedUser, Depends(get_external_import_user)],
    service: Annotated[ExternalReviewImportService, Depends(get_external_import_service)],
) -> ExternalReviewImportResponse:
    try:
        return service.import_reviews(user, request.business_data_id)
    except ExternalReviewImportError as error:
        raise HTTPException(status_code=error.http_status, detail=error.detail.model_dump()) from None
