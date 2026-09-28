from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_tenant_id, get_db
from app.api.routers.imports import UploadedReviewFile, import_reviews_for_tenant
from app.repositories.review_repository import ReviewRepository
from app.schemas.review import ReviewList, ReviewManualCreate, ReviewManualRegistration, ReviewRead
from app.services.review_service import ReviewNotFoundError, ReviewService


router = APIRouter(prefix="/reviews", tags=["reviews"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentTenantId = Annotated[int, Depends(get_current_tenant_id)]


def get_service(db: Session) -> ReviewService:
    return ReviewService(ReviewRepository(db))


def raise_not_found(error: ReviewNotFoundError) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(error),
    ) from error


def prepare_manual_review_registration(
    review: ReviewManualCreate,
    tenant_id: CurrentTenantId,
) -> ReviewManualRegistration:
    """Construye los datos de servidor que T3 enviará a la persistencia.

    El tenant y los valores de operación no proceden del payload del cliente.
    T3 conectará este adaptador con ReviewService y ReviewRepository para
    publicar POST /api/v1/reviews con respuesta 201.
    """

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
def list_reviews(db: DatabaseSession, tenant_id: CurrentTenantId) -> ReviewList:
    reviews = get_service(db).list_by_tenant(tenant_id)
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
