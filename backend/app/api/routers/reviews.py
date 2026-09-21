from fastapi import APIRouter

from app.services.review_service import get_review_placeholder

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("")
def reviews_placeholder() -> dict[str, str]:
    return get_review_placeholder()
