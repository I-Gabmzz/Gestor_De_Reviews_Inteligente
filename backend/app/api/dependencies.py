"""Dependencias compartidas de autenticación para futuras rutas protegidas."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.connection import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthenticatedUser


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
