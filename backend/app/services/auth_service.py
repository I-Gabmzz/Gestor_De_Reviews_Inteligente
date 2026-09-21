from fastapi import HTTPException, status

from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthenticatedUser, LoginRequest, TokenResponse


INVALID_CREDENTIALS = "Credenciales inválidas"
INACTIVE_USER = "El usuario está inactivo"


class AuthService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def authenticate(self, credentials: LoginRequest) -> TokenResponse:
        user = self.user_repository.get_by_correo(str(credentials.correo).lower())
        if user is None or not verify_password(credentials.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_CREDENTIALS,
                headers={"WWW-Authenticate": "Bearer"},
            )
        if user.estado.lower() != "activo":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=INACTIVE_USER)

        authenticated_user = self._to_authenticated_user(user)
        access_token = create_access_token(
            subject=str(user.id), rol=authenticated_user.rol, tenant_id=authenticated_user.tenant_id
        )
        return TokenResponse(access_token=access_token, user=authenticated_user)

    @staticmethod
    def _to_authenticated_user(user: User) -> AuthenticatedUser:
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
