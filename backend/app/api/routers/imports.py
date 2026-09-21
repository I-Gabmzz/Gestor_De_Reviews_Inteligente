from fastapi import APIRouter

from app.services.import_service import get_import_placeholder

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("")
def imports_placeholder() -> dict[str, str]:
    return get_import_placeholder()
