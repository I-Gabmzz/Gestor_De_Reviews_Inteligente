from fastapi import APIRouter

from app.services.tenant_service import get_tenant_placeholder

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("")
def tenants_placeholder() -> dict[str, str]:
    return get_tenant_placeholder()
