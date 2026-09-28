from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_tenant_id, get_current_user, get_db
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthenticatedUser
from app.schemas.user import UserList
from app.services.user_service import UserAccessDeniedError, UserService

router = APIRouter(prefix="/users", tags=["users"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
CurrentTenantId = Annotated[int, Depends(get_current_tenant_id)]


@router.get("", response_model=UserList, status_code=status.HTTP_200_OK)
def list_users(db: DatabaseSession, current_user: CurrentUser, tenant_id: CurrentTenantId) -> UserList:
    try:
        return UserService(UserRepository(db)).list_for_current_user(current_user, tenant_id)
    except UserAccessDeniedError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
