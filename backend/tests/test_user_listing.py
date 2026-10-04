import pytest

from app.core.security import get_password_hash
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthenticatedUser
from app.services.user_service import UserService


def auth_headers(client, correo: str) -> dict[str, str]:
    response = client[0].post(
        "/api/v1/auth/login",
        json={"correo": correo, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def two_tenants(client, seed_users):
    _, session_factory = client
    with session_factory() as db:
        db.add(Tenant(id=20, nombre="Tenant B", estado="activo"))
        db.add_all(
            [
                User(
                    tenant_id=20,
                    nombre="Administrador B",
                    correo="admin-b@example.com",
                    password_hash=get_password_hash("secret123"),
                    rol="admin_tenant",
                    estado="activo",
                ),
                User(
                    tenant_id=20,
                    nombre="Usuario B",
                    correo="usuario-b@example.com",
                    password_hash=get_password_hash("secret123"),
                    rol="usuario_negocio",
                    estado="inactivo",
                ),
            ]
        )
        db.commit()


def test_admin_tenant_obtiene_usuarios_de_su_tenant(client, two_tenants):
    response = client[0].get(
        "/api/v1/users",
        headers=auth_headers(client, "tenant@example.com"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert {user["correo"] for user in body["items"]} == {
        "usuario@example.com",
        "tenant@example.com",
        "inactive@example.com",
    }
    assert {user["estado"] for user in body["items"]} == {"activo", "inactivo"}
    assert all(user["tenant_id"] == 10 for user in body["items"])


def test_tenant_enviado_en_query_no_expone_usuarios_ajenos(client, two_tenants):
    response = client[0].get(
        "/api/v1/users?tenant_id=20",
        headers=auth_headers(client, "tenant@example.com"),
    )

    assert response.status_code == 200
    assert all(user["tenant_id"] == 10 for user in response.json()["items"])
    assert "admin-b@example.com" not in {user["correo"] for user in response.json()["items"]}


def test_admin_de_otro_tenant_solo_obtiene_sus_usuarios(client, two_tenants):
    response = client[0].get(
        "/api/v1/users",
        headers=auth_headers(client, "admin-b@example.com"),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert all(user["tenant_id"] == 20 for user in response.json()["items"])


@pytest.mark.parametrize("correo", ["usuario@example.com", "general@example.com"])
def test_roles_no_autorizados_no_obtienen_usuarios(client, seed_users, correo):
    response = client[0].get("/api/v1/users", headers=auth_headers(client, correo))

    assert response.status_code == 403
    assert "items" not in response.json()


def test_consulta_sin_autenticacion_es_rechazada(client):
    response = client[0].get("/api/v1/users")

    assert response.status_code == 401
    assert response.json() == {"detail": "Token inválido o ausente"}


def test_respuesta_no_incluye_password_hash(client, seed_users):
    response = client[0].get(
        "/api/v1/users",
        headers=auth_headers(client, "tenant@example.com"),
    )

    assert response.status_code == 200
    assert "password_hash" not in response.text
    assert all(
        set(user) == {"id", "tenant_id", "nombre", "correo", "rol", "estado"}
        for user in response.json()["items"]
    )


def test_tenant_sin_usuarios_devuelve_coleccion_vacia(client):
    _, session_factory = client
    with session_factory() as db:
        db.add(Tenant(id=30, nombre="Tenant vacío", estado="activo"))
        db.commit()

        current_user = AuthenticatedUser(
            id=999,
            correo="admin-vacio@example.com",
            rol="admin_tenant",
            tenant_id=30,
        )
        result = UserService(UserRepository(db)).list_for_current_user(current_user, 30)

    assert result.items == []
    assert result.total == 0
