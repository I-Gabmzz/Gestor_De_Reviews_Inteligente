from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.repositories.tenant_repository import TenantRepository
from app.schemas.tenant import TenantCreate, TenantList, TenantRead, TenantUpdate
from app.services.tenant_service import TenantNotFoundError, TenantService

router = APIRouter(prefix="/tenants", tags=["tenants"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def get_service(db: Session) -> TenantService:
    return TenantService(TenantRepository(db))


def raise_not_found(error: TenantNotFoundError) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(error),
    ) from error


@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(data: TenantCreate, db: DatabaseSession) -> TenantRead:
    return get_service(db).create(data)


@router.get("", response_model=TenantList, status_code=status.HTTP_200_OK)
def list_tenants(db: DatabaseSession) -> TenantList:
    tenants = get_service(db).list_all()
    return TenantList(items=tenants, total=len(tenants))


@router.get(
    "/{tenant_id}",
    response_model=TenantRead,
    status_code=status.HTTP_200_OK,
)
def get_tenant(tenant_id: int, db: DatabaseSession) -> TenantRead:
    try:
        return get_service(db).get_by_id(tenant_id)
    except TenantNotFoundError as error:
        raise_not_found(error)


@router.patch(
    "/{tenant_id}",
    response_model=TenantRead,
    status_code=status.HTTP_200_OK,
)
def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    db: DatabaseSession,
) -> TenantRead:
    try:
        return get_service(db).update(tenant_id, data)
    except TenantNotFoundError as error:
        raise_not_found(error)
