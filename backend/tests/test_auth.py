from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import get_current_user
from app.core.security import get_password_hash
from app.models.user import User


def test_login_returns_token_and_context(client, seed_users):
    response = client[0].post(
        "/api/v1/auth/login",
        json={"email": "USUARIO@example.com", "password": "secret123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"] == {
        "id": 1,
        "correo": "usuario@example.com",
        "rol": "usuario_negocio",
        "tenant_id": 10,
    }


def test_login_accepts_all_supported_roles(client, seed_users):
    for correo, rol, tenant_id in [
        ("tenant@example.com", "admin_tenant", 10),
        ("general@example.com", "admin_general", None),
    ]:
        response = client[0].post(
            "/api/v1/auth/login",
            json={"correo": correo, "password": "secret123"},
        )
        assert response.status_code == 200
        assert response.json()["user"]["rol"] == rol
        assert response.json()["user"]["tenant_id"] == tenant_id


def test_login_rejects_invalid_credentials_with_detail(client, seed_users):
    response = client[0].post(
        "/api/v1/auth/login",
        json={"correo": "usuario@example.com", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas"
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_rejects_inactive_user_with_detail(client, seed_users):
    response = client[0].post(
        "/api/v1/auth/login",
        json={"correo": "inactive@example.com", "password": "secret123"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "El usuario está inactivo"


def test_role_tenant_rule_is_enforced_by_database(client):
    _, session_factory = client
    with session_factory() as db:
        db.add(
            User(
                tenant_id=None,
                nombre="Configuración inválida",
                correo="invalid@example.com",
                password_hash=get_password_hash("secret123"),
                rol="admin_tenant",
                estado="activo",
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError("La regla rol/tenant_id no fue aplicada")


def test_get_current_user_exposes_context(client, seed_users):
    response = client[0].post(
        "/api/v1/auth/login",
        json={"correo": "general@example.com", "password": "secret123"},
    )
    db = client[1]()
    try:
        current_user = get_current_user(
            HTTPAuthorizationCredentials(
                scheme="Bearer", credentials=response.json()["access_token"]
            ),
            db,
        )
    finally:
        db.close()

    assert current_user.id == 3
    assert current_user.rol == "admin_general"
    assert current_user.tenant_id is None
