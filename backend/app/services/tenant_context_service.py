from app.schemas.auth import AuthenticatedUser


class TenantContextError(Exception):
    """El usuario autenticado no tiene contexto de tenant interno."""


def resolve_tenant_id(current_user: AuthenticatedUser) -> int:
    if current_user.rol == "admin_general" or current_user.tenant_id is None:
        raise TenantContextError("El usuario no pertenece a un tenant")
    return current_user.tenant_id
