from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_tenant_roles
from app.repositories.review_repository import ReviewRepository
from app.repositories.tenant_repository import TenantRepository
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentTenantId = Annotated[int, Depends(require_tenant_roles("usuario_negocio", "admin_tenant"))]


def get_dashboard_service(db: DatabaseSession) -> DashboardService:
    return DashboardService(ReviewRepository(db))


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    tenant_id: CurrentTenantId,
    db: DatabaseSession,
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
) -> DashboardResponse:
    dashboard = service.get_dashboard_for_tenant(tenant_id)
    tenant = TenantRepository(db).get_by_id(tenant_id)
    return dashboard.model_copy(update={"nombre_negocio": tenant.nombre if tenant else None})
