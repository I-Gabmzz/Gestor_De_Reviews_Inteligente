from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthenticatedUser
from app.schemas.user import UserCreate, UserList, UserRead


class UserAccessDeniedError(Exception):
    """El usuario no puede gestionar el directorio del tenant."""


class UserAlreadyExistsError(Exception):
    """El correo ya está registrado globalmente."""

    def __init__(self) -> None:
        super().__init__("El correo ya está registrado")


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def list_for_current_user(
        self,
        current_user: AuthenticatedUser,
        tenant_id: int,
    ) -> UserList:
        if current_user.rol != "admin_tenant" or current_user.tenant_id != tenant_id:
            raise UserAccessDeniedError("Se requiere el rol admin_tenant del tenant")

        users = self.repository.list_by_tenant(tenant_id)
        items = [UserRead.model_validate(user) for user in users]
        return UserList(items=items, total=len(items))

    def create_for_current_user(
        self,
        data: UserCreate,
        current_user: AuthenticatedUser,
        tenant_id: int,
    ) -> UserRead:
        if current_user.rol != "admin_tenant" or current_user.tenant_id != tenant_id:
            raise UserAccessDeniedError("Se requiere el rol admin_tenant del tenant")

        correo = str(data.correo).lower()
        if self.repository.get_by_correo(correo) is not None:
            raise UserAlreadyExistsError()

        user = User(
            tenant_id=tenant_id,
            nombre=data.nombre,
            correo=correo,
            password_hash=get_password_hash(data.password),
            rol="usuario_negocio",
            estado="activo",
        )
        try:
            created = self.repository.create(user)
        except IntegrityError as error:
            if self.repository.get_by_correo(correo) is not None:
                raise UserAlreadyExistsError() from error
            raise
        return UserRead.model_validate(created)
