from fastapi import APIRouter

from app.services.user_service import get_user_placeholder

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def users_placeholder() -> dict[str, str]:
    return get_user_placeholder()
