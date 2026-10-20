from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash
from app.models.user import User
from app.repositories.tenant_repository import TenantRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthenticatedUser
from app.schemas.user import AdminRoleChange, UserCreate, UserList, UserRead, UserUpdate
from app.services.authorization_service import (
    AuthorizationDeniedError,
    InvalidRoleTransitionError,
    require_role,
    require_tenant_scope,
    validate_role_transition,
)


class UserAccessDeniedError(Exception):
    """El usuario no puede gestionar el directorio del tenant."""


class UserAlreadyExistsError(Exception):
    """El correo ya está registrado globalmente."""

    def __init__(self) -> None:
        super().__init__("El correo ya está registrado")


class UserNotFoundError(Exception):
    """El usuario no existe dentro del tenant autorizado."""


class UserInvalidRoleTransitionError(Exception):
    """El cambio solicitado no es una transición administrativa válida."""


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    @staticmethod
    def _require_tenant_admin(current_user: AuthenticatedUser, tenant_id: int) -> None:
        try:
            require_tenant_scope(current_user, tenant_id, "admin_tenant")
        except AuthorizationDeniedError as exc:
            raise UserAccessDeniedError("Se requiere el rol admin_tenant del tenant") from exc

    def list_for_current_user(
        self,
        current_user: AuthenticatedUser,
        tenant_id: int,
    ) -> UserList:
        self._require_tenant_admin(current_user, tenant_id)

        users = self.repository.list_by_tenant(tenant_id)
        items = [UserRead.model_validate(user) for user in users]
        return UserList(items=items, total=len(items))

    def create_for_current_user(
        self,
        data: UserCreate,
        current_user: AuthenticatedUser,
        tenant_id: int,
    ) -> UserRead:
        self._require_tenant_admin(current_user, tenant_id)

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

    def update_for_current_user(
        self,
        user_id: int,
        data: UserUpdate,
        current_user: AuthenticatedUser,
        tenant_id: int,
    ) -> UserRead:
        self._require_tenant_admin(current_user, tenant_id)

        user = self.repository.get_by_id_and_tenant(user_id, tenant_id)
        if user is None:
            raise UserNotFoundError("Usuario no encontrado")
        if user.rol != "usuario_negocio":
            raise UserAccessDeniedError("Solo se pueden editar cuentas operativas")

        changes = data.model_dump(exclude_unset=True)
        if "correo" in changes:
            correo = str(changes["correo"]).lower()
            existing = self.repository.get_by_correo(correo)
            if existing is not None and existing.id != user.id:
                raise UserAlreadyExistsError()
            changes["correo"] = correo

        try:
            updated = self.repository.update(user, changes)
        except IntegrityError as error:
            if "correo" in changes:
                existing = self.repository.get_by_correo(changes["correo"])
                if existing is not None and existing.id != user.id:
                    raise UserAlreadyExistsError() from error
            raise
        return UserRead.model_validate(updated)

    def change_role_for_admin(
        self,
        user_id: int,
        data: AdminRoleChange,
        current_user: AuthenticatedUser,
    ) -> UserRead:
        """Cambia un rol de tenant solo con la identidad vigente del administrador global."""

        actor = self.repository.get_by_id(current_user.id)
        if actor is None or actor.estado != "activo" or actor.tenant_id is not None:
            raise UserAccessDeniedError("Se requiere el rol admin_general")
        try:
            require_role(actor, "admin_general")
        except AuthorizationDeniedError as exc:
            raise UserAccessDeniedError("Se requiere el rol admin_general") from exc
        target = self.repository.get_by_id(user_id)
        if target is None:
            raise UserNotFoundError("Usuario no encontrado")
        try:
            validate_role_transition(actor, target, data.rol)
        except AuthorizationDeniedError as exc:
            raise UserAccessDeniedError(str(exc)) from exc
        except InvalidRoleTransitionError as exc:
            raise UserInvalidRoleTransitionError(str(exc)) from exc
        if TenantRepository(self.repository.db).get_by_id(target.tenant_id) is None:
            raise UserInvalidRoleTransitionError("El tenant no existe")
        return UserRead.model_validate(self.repository.update_role(target, data.rol))
