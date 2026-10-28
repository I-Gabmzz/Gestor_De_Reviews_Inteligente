import re
from datetime import date
from http import HTTPStatus
from typing import Annotated, Literal, NoReturn

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Response, status
from pydantic import BeforeValidator
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_tenant_roles
from app.api.routers.imports import UploadedReviewFile, import_reviews_for_tenant
from app.repositories.review_repository import ReviewRepository
from app.schemas.classification import ClassificationRequest
from app.schemas.review import (
    ReviewList,
    ReviewManualCreate,
    ReviewManualRegistration,
    ReviewRead,
    ReviewStatusUpdate,
    ReviewUpdate,
)
from app.services.review_service import (
    ReviewFilterValidationError,
    ReviewNotFoundError,
    ReviewService,
)
from app.services.review_export_service import serialize_reviews_csv
from app.services.ai_provider import (
    AIError, AIBlockedResponseError, AIConfigurationError, AICredentialsError,
    AIInputError, AIInvalidResponseError, AIQuotaError, AIRequestError,
    AITimeoutError, AIUnavailableError,
)
from app.services.classification_service import (
    ClassificationService, ClassificationContentError, ClassificationConflictError,
    ClassificationPersistenceError,
)


router = APIRouter(prefix="/reviews", tags=["reviews"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentTenantId = Annotated[int, Depends(require_tenant_roles("usuario_negocio", "admin_tenant"))]
ClassificationTenantId = Annotated[
    int, Depends(require_tenant_roles("usuario_negocio", "admin_tenant"))
]


def get_classification_service(db: DatabaseSession) -> ClassificationService:
    return ClassificationService(ReviewRepository(db))


CLASSIFICATION_HTTP_ERRORS = {
    ClassificationContentError: 422,
    AIInputError: 422,
    AIBlockedResponseError: 422,
    ClassificationConflictError: 409,
    ClassificationPersistenceError: 500,
    AIInvalidResponseError: 502,
    AIRequestError: 502,
    AIConfigurationError: 503,
    AICredentialsError: 503,
    AIQuotaError: 503,
    AIUnavailableError: 503,
    AITimeoutError: 504,
}


@router.post(
    "/{review_id}/clasificacion",
    response_model=ReviewRead,
    status_code=status.HTTP_200_OK,
    summary="Clasificar una review del negocio autenticado",
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
def classify_review(
    review_id: Annotated[int, Path(gt=0)],
    tenant_id: ClassificationTenantId,
    service: Annotated[ClassificationService, Depends(get_classification_service)],
    payload: Annotated[ClassificationRequest | None, Body()] = None,
) -> ReviewRead:
    """Usa el contenido guardado; el cuerpo opcional no admite campos."""
    try:
        return service.classify(review_id, tenant_id)
    except ReviewNotFoundError as error:
        raise_not_found(error)
    except AIError as error:
        http_status = CLASSIFICATION_HTTP_ERRORS.get(type(error))
        detail = str(error) if http_status is not None else AIError.message
        raise HTTPException(status_code=http_status or 502, detail=detail) from None


def validate_query_date(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise ValueError("La fecha debe usar el formato YYYY-MM-DD")
    return value


QueryDate = Annotated[date, BeforeValidator(validate_query_date)]


def get_service(db: Session) -> ReviewService:
    return ReviewService(ReviewRepository(db))


def raise_not_found(error: ReviewNotFoundError) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(error),
    ) from error


def raise_invalid_filters(error: ReviewFilterValidationError) -> NoReturn:
    raise HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        detail=str(error),
    ) from error


def prepare_manual_review_registration(
    review: ReviewManualCreate,
    tenant_id: CurrentTenantId,
) -> ReviewManualRegistration:
    """Prepara los datos de servidor sin aceptar valores del cliente para esos campos."""

    return ReviewManualRegistration(
        tenant_id=tenant_id,
        autor=review.autor,
        contenido=review.contenido,
        fecha=review.fecha,
        puntuacion=review.puntuacion,
    )


@router.post("", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
def create_manual_review(
    review: ReviewManualCreate,
    db: DatabaseSession,
    tenant_id: CurrentTenantId,
) -> ReviewRead:
    registration = prepare_manual_review_registration(review, tenant_id)
    return get_service(db).create_manual(registration)


@router.post("/import", status_code=status.HTTP_200_OK)
async def import_reviews(
    file: UploadedReviewFile,
    db: DatabaseSession,
    tenant_id: CurrentTenantId,
) -> dict:
    return await import_reviews_for_tenant(file=file, tenant_id=tenant_id, db=db)


@router.get("", response_model=ReviewList, status_code=status.HTTP_200_OK)
def list_reviews(
    db: DatabaseSession,
    tenant_id: CurrentTenantId,
    busqueda: Annotated[str | None, Query(description="Texto parcial del contenido")] = None,
    fecha_desde: Annotated[QueryDate | None, Query(description="Desde el dia YYYY-MM-DD")] = None,
    fecha_hasta: Annotated[
        QueryDate | None, Query(description="Hasta el dia YYYY-MM-DD inclusive")
    ] = None,
    puntuacion: Annotated[int | None, Query(ge=1, le=5)] = None,
    estado: Annotated[Literal["nueva", "en_revision", "atendida"] | None, Query()] = None,
    fuente: Annotated[str | None, Query(description="Fuente exacta, sin catalogo cerrado")] = None,
) -> ReviewList:
    try:
        reviews = get_service(db).list_by_tenant(
            tenant_id,
            busqueda=busqueda,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            puntuacion=puntuacion,
            estado=estado,
            fuente=fuente,
        )
    except ReviewFilterValidationError as error:
        raise_invalid_filters(error)
    return ReviewList(items=reviews, total=len(reviews))


@router.get("/export", response_class=Response, status_code=status.HTTP_200_OK)
def export_reviews(
    db: DatabaseSession,
    tenant_id: CurrentTenantId,
    busqueda: Annotated[str | None, Query(description="Texto parcial del contenido")] = None,
    fecha_desde: Annotated[QueryDate | None, Query(description="Desde el dia YYYY-MM-DD")] = None,
    fecha_hasta: Annotated[
        QueryDate | None, Query(description="Hasta el dia YYYY-MM-DD inclusive")
    ] = None,
    puntuacion: Annotated[int | None, Query(ge=1, le=5)] = None,
    estado: Annotated[Literal["nueva", "en_revision", "atendida"] | None, Query()] = None,
    fuente: Annotated[str | None, Query(description="Fuente exacta, sin catalogo cerrado")] = None,
) -> Response:
    try:
        reviews = get_service(db).list_by_tenant(
            tenant_id,
            busqueda=busqueda,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            puntuacion=puntuacion,
            estado=estado,
            fuente=fuente,
        )
    except ReviewFilterValidationError as error:
        raise_invalid_filters(error)
    return Response(
        content=serialize_reviews_csv(reviews),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="reviews_{date.today():%Y%m%d}.csv"'
        },
    )


@router.get(
    "/{review_id}",
    response_model=ReviewRead,
    status_code=status.HTTP_200_OK,
)
def get_review(
    review_id: int,
    db: DatabaseSession,
    tenant_id: CurrentTenantId,
) -> ReviewRead:
    try:
        return get_service(db).get_by_id(review_id, tenant_id)
    except ReviewNotFoundError as error:
        raise_not_found(error)


@router.patch(
    "/{review_id}",
    response_model=ReviewRead,
    status_code=status.HTTP_200_OK,
)
def update_review(
    review_id: int,
    data: ReviewUpdate,
    db: DatabaseSession,
    tenant_id: CurrentTenantId,
) -> ReviewRead:
    try:
        return get_service(db).update(review_id, tenant_id, data)
    except ReviewNotFoundError as error:
        raise_not_found(error)


@router.patch(
    "/{review_id}/status",
    response_model=ReviewRead,
    status_code=status.HTTP_200_OK,
)
def update_review_status(
    review_id: int,
    data: ReviewStatusUpdate,
    db: DatabaseSession,
    tenant_id: CurrentTenantId,
) -> ReviewRead:
    try:
        return get_service(db).update_review_status(review_id, tenant_id, data.estado)
    except ReviewNotFoundError as error:
        raise_not_found(error)
