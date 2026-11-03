"""Lectura de avisos internos por los roles operativos del negocio autenticado."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_tenant_roles
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import NotificationList


router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])
NotificationTenantId = Annotated[int, Depends(require_tenant_roles("usuario_negocio", "admin_tenant"))]


@router.get("", response_model=NotificationList, summary="Consultar avisos de prioridad Alta del negocio autenticado")
def list_notifications(
    db: Annotated[Session, Depends(get_db)],
    tenant_id: NotificationTenantId,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationList:
    try:
        items, total = NotificationRepository(db).list_for_tenant(tenant_id, limit=limit, offset=offset)
        return NotificationList(items=items, total=total)
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="No fue posible consultar los avisos de prioridad") from None
