import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.dependencies import require_roles, require_tenant_roles
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthenticatedUser
from app.schemas.user import AdminRoleChange, UserUpdate
from app.services.user_service import (
    UserAccessDeniedError,
    UserInvalidRoleTransitionError,
    UserService,
)


def context(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(id=user.id, correo=user.correo, rol=user.rol, tenant_id=user.tenant_id)


def test_role_and_tenant_dependencies_use_authenticated_context(client, seed_users):
    with client[1]() as db:
        tenant_admin = context(db.get(User, 2))
        general_admin = context(db.get(User, 3))

    assert require_roles("admin_tenant")(tenant_admin) == tenant_admin
    assert require_tenant_roles("admin_tenant")(tenant_admin) == 10
    with pytest.raises(HTTPException) as denied:
        require_roles("admin_general")(tenant_admin)
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as denied:
        require_tenant_roles("admin_tenant")(general_admin)
    assert denied.value.status_code == 403


def test_ordinary_update_and_admin_role_schema_reject_authority_fields():
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"nombre": "Ejemplo", "rol": "admin_tenant"})
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"nombre": "Ejemplo", "tenant_id": 20})
    with pytest.raises(ValidationError):
        AdminRoleChange.model_validate({"rol": "admin_general"})
    with pytest.raises(ValidationError):
        AdminRoleChange.model_validate({"rol": "admin_tenant", "tenant_id": 10})


def test_only_current_admin_general_can_promote_and_demote(client, seed_users):
    with client[1]() as db:
        service = UserService(UserRepository(db))
        general = context(db.get(User, 3))
        target = db.get(User, 1)

        promoted = service.change_role_for_admin(target.id, AdminRoleChange(rol="admin_tenant"), general)
        assert promoted.rol == "admin_tenant"
        assert promoted.tenant_id == 10
        assert db.get(User, target.id).rol == "admin_tenant"

        demoted = service.change_role_for_admin(target.id, AdminRoleChange(rol="usuario_negocio"), general)
        assert demoted.rol == "usuario_negocio"
        assert db.get(User, target.id).rol == "usuario_negocio"


def test_role_change_denies_other_actor_and_invalid_transitions(client, seed_users):
    with client[1]() as db:
        service = UserService(UserRepository(db))
        general = context(db.get(User, 3))
        tenant_admin = context(db.get(User, 2))
        target = db.get(User, 1)

        with pytest.raises(UserAccessDeniedError):
            service.change_role_for_admin(target.id, AdminRoleChange(rol="admin_tenant"), tenant_admin)
        with pytest.raises(UserInvalidRoleTransitionError):
            service.change_role_for_admin(target.id, AdminRoleChange(rol="usuario_negocio"), general)
        with pytest.raises(UserAccessDeniedError):
            service.change_role_for_admin(general.id, AdminRoleChange(rol="admin_tenant"), general)
        assert db.get(User, target.id).rol == "usuario_negocio"

        # El rol aportado en el contexto no sustituye al registro vigente de BD.
        forged = AuthenticatedUser(
            id=tenant_admin.id,
            correo=tenant_admin.correo,
            rol="admin_general",
            tenant_id=None,
        )
        with pytest.raises(UserAccessDeniedError):
            service.change_role_for_admin(target.id, AdminRoleChange(rol="admin_tenant"), forged)


def test_ordinary_user_update_cannot_edit_admin_tenant(client, seed_users):
    login = client[0].post(
        "/api/v1/auth/login", json={"correo": "tenant@example.com", "password": "secret123"}
    )
    response = client[0].patch(
        "/api/v1/users/2",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json={"nombre": "No permitido"},
    )
    assert response.status_code == 403
    with client[1]() as db:
        assert db.get(User, 2).nombre == "Administrador tenant"


def test_inactive_tenant_blocks_login_and_existing_token_until_reactivation(client, seed_users):
    login = client[0].post(
        "/api/v1/auth/login", json={"correo": "tenant@example.com", "password": "secret123"}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    with client[1]() as db:
        tenant = db.get(Tenant, 10)
        tenant.estado = "inactivo"
        db.commit()

    denied_login = client[0].post(
        "/api/v1/auth/login", json={"correo": "tenant@example.com", "password": "secret123"}
    )
    assert denied_login.status_code == 403
    assert client[0].get("/api/v1/users", headers=headers).status_code == 403

    with client[1]() as db:
        assert db.get(User, 2).estado == "activo"
        tenant = db.get(Tenant, 10)
        tenant.estado = "activo"
        db.commit()

    assert client[0].get("/api/v1/users", headers=headers).status_code == 200
