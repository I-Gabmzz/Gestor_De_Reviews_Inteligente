from app.repositories.review_repository import ReviewRepository
from app.schemas.dashboard import DashboardResponse


class DashboardService:
    def __init__(self, review_repository: ReviewRepository) -> None:
        self.review_repository = review_repository

    def get_dashboard_for_tenant(self, tenant_id: int) -> DashboardResponse:
        return DashboardResponse(
            total_reviews=self.review_repository.count_by_tenant(tenant_id),
            promedio_puntuacion=self.review_repository.average_score_by_tenant(tenant_id),
            reviews_nuevas=self.review_repository.count_new_by_tenant(tenant_id),
            reviews_recientes=self.review_repository.list_recent_by_tenant(tenant_id),
        )
