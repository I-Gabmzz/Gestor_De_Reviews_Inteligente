"""Reglas reutilizables de autorización aprobadas para HU-04."""

from app.models.user import User
from app.repositories.tenant_repository import TenantRepository
from app.schemas.auth import AuthenticatedUser, UserRole


class AuthorizationDeniedError(Exception):
    """El actor no puede realizar la operación solicitada."""


class InvalidRoleTransitionError(Exception):
    """La transición de rol no forma parte de las operaciones aprobadas."""


def require_role(current_user: AuthenticatedUser, *allowed_roles: UserRole) -> None:
    if current_user.rol not in allowed_roles:
        raise AuthorizationDeniedError("El rol no está autorizado")


def require_tenant_scope(
    current_user: AuthenticatedUser,
    tenant_id: int,
    *allowed_roles: UserRole,
) -> None:
    require_role(current_user, *allowed_roles)
    if current_user.tenant_id != tenant_id:
        raise AuthorizationDeniedError("El tenant no está autorizado")


def require_active_tenant(user: User, tenants: TenantRepository) -> None:
    """Consulta el estado vigente; así también invalida el uso de tokens previos."""

    if user.rol == "admin_general":
        return
    tenant = tenants.get_by_id(user.tenant_id) if user.tenant_id is not None else None
    if tenant is None or tenant.estado != "activo":
        raise AuthorizationDeniedError("El tenant está inactivo o no existe")


def validate_role_transition(actor: User, target: User, new_role: UserRole) -> None:
    """Solo AG puede promover o degradar una cuenta de tenant ajena."""

    if actor.estado != "activo" or actor.rol != "admin_general" or actor.tenant_id is not None:
        raise AuthorizationDeniedError("Se requiere el rol admin_general")
    if actor.id == target.id:
        raise AuthorizationDeniedError("No se permite cambiar el propio rol")
    if target.tenant_id is None:
        raise InvalidRoleTransitionError("La cuenta no pertenece a un tenant")
    if (target.rol, new_role) not in {
        ("usuario_negocio", "admin_tenant"),
        ("admin_tenant", "usuario_negocio"),
    }:
        raise InvalidRoleTransitionError("La transición de rol no está permitida")
