"""Dependencias compartidas de sesión y autenticación."""

from collections.abc import Generator
from typing import Annotated, Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.connection import SessionLocal
from app.repositories.tenant_repository import TenantRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthenticatedUser, UserRole
from app.services.authorization_service import (
    AuthorizationDeniedError,
    require_active_tenant,
    require_role,
    require_tenant_scope,
)
from app.services.tenant_context_service import TenantContextError, resolve_tenant_id


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthenticatedUser:
    """Devuelve el contexto actual con id, rol y tenant_id."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o ausente",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError, OverflowError) as exc:
        raise unauthorized from exc

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise unauthorized
    if user.estado.lower() != "activo":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El usuario está inactivo")
    try:
        require_active_tenant(user, TenantRepository(db))
    except AuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    try:
        return AuthenticatedUser(
            id=user.id,
            correo=user.correo,
            rol=user.rol,
            tenant_id=user.tenant_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="La configuración del usuario no es válida",
        ) from exc


def require_admin_general(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    try:
        require_role(current_user, "admin_general")
    except AuthorizationDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere el rol admin_general",
        ) from exc
    return current_user


def require_roles(*allowed_roles: UserRole) -> Callable[..., AuthenticatedUser]:
    """Dependencia de rol reutilizable para las rutas que se protejan en T4."""

    def dependency(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        try:
            require_role(current_user, *allowed_roles)
        except AuthorizationDeniedError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        return current_user

    return dependency


def require_tenant_roles(*allowed_roles: UserRole) -> Callable[..., int]:
    """Dependencia que fija el ámbito al tenant autenticado y exige un rol."""

    def dependency(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> int:
        try:
            tenant_id = resolve_tenant_id(current_user)
            require_tenant_scope(current_user, tenant_id, *allowed_roles)
        except (TenantContextError, AuthorizationDeniedError) as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        return tenant_id

    return dependency


def get_current_tenant_id(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> int:
    try:
        return resolve_tenant_id(current_user)
    except TenantContextError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
