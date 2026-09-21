from fastapi import APIRouter

from app.services.auth_service import get_auth_placeholder

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("")
def auth_placeholder() -> dict[str, str]:
    return get_auth_placeholder()
