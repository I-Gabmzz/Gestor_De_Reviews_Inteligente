from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_tenant_id, get_db
from app.repositories.review_repository import ReviewRepository
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentTenantId = Annotated[int, Depends(get_current_tenant_id)]


def get_dashboard_service(db: DatabaseSession) -> DashboardService:
    return DashboardService(ReviewRepository(db))


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    tenant_id: CurrentTenantId,
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
) -> DashboardResponse:
    return service.get_dashboard_for_tenant(tenant_id)
