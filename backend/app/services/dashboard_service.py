from app.repositories.review_repository import ReviewRepository
from app.schemas.dashboard import DashboardResponse


class DashboardService:
    def __init__(self, review_repository: ReviewRepository) -> None:
        self.review_repository = review_repository

    def get_dashboard_for_tenant(self, tenant_id: int) -> DashboardResponse:
        return DashboardResponse(
            reviews_recientes=self.review_repository.list_recent_by_tenant(tenant_id),
            **self.review_repository.dashboard_metrics_by_tenant(tenant_id),
        )
