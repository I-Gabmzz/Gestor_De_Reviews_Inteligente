from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthenticatedUser
from app.schemas.user import UserList, UserRead


class UserAccessDeniedError(Exception):
    """El usuario no puede consultar el directorio del tenant."""


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
