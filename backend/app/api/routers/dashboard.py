from fastapi import APIRouter

from app.services.dashboard_service import get_dashboard_placeholder

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard_placeholder() -> dict[str, str]:
    return get_dashboard_placeholder()
