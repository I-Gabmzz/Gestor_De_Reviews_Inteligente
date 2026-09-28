import re
from datetime import date
from http import HTTPStatus
from typing import Annotated, Literal, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BeforeValidator
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_tenant_id, get_db
from app.api.routers.imports import UploadedReviewFile, import_reviews_for_tenant
from app.repositories.review_repository import ReviewRepository
from app.schemas.review import ReviewList, ReviewRead
from app.services.review_service import (
    ReviewFilterValidationError,
    ReviewNotFoundError,
    ReviewService,
)


router = APIRouter(prefix="/reviews", tags=["reviews"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentTenantId = Annotated[int, Depends(get_current_tenant_id)]


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
