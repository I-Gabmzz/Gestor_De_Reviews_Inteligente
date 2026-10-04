import pytest
from sqlalchemy import select

from app.core.security import get_password_hash, verify_password
from app.models.tenant import Tenant
from app.models.user import User


def auth_headers(client, correo: str) -> dict[str, str]:
    response = client[0].post(
        "/api/v1/auth/login",
        json={"correo": correo, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_tenant_crea_usuario_en_su_tenant_con_respuesta_segura(client, seed_users):
    test_client, session_factory = client
    payload = {
        "nombre": "  Nueva Persona  ",
        "correo": "Nueva@Example.com",
        "password": "clave-inicial",
    }

    response = test_client.post(
        "/api/v1/users",
        headers=auth_headers(client, "tenant@example.com"),
        json=payload,
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "tenant_id", "nombre", "correo", "rol", "estado"}
    assert body["tenant_id"] == 10
    assert body["nombre"] == "Nueva Persona"
    assert body["correo"] == "nueva@example.com"
    assert body["rol"] == "usuario_negocio"
    assert body["estado"] == "activo"
    assert "password" not in response.text
    assert "password_hash" not in response.text

    with session_factory() as db:
        user = db.scalar(select(User).where(User.correo == "nueva@example.com"))
        assert user is not None
        assert user.id == body["id"]
        assert user.tenant_id == 10
        assert user.rol == "usuario_negocio"
        assert user.estado == "activo"
        assert user.password_hash != payload["password"]
        assert verify_password(payload["password"], user.password_hash)


def test_admin_de_otro_tenant_crea_solo_en_su_tenant(client, seed_users):
    test_client, session_factory = client
    with session_factory() as db:
        db.add(Tenant(id=20, nombre="Segundo tenant", estado="activo"))
        db.add(
            User(
                tenant_id=20,
                nombre="Admin B",
                correo="admin-b@example.com",
                password_hash=get_password_hash("secret123"),
                rol="admin_tenant",
                estado="activo",
            )
        )
        db.commit()

    response = test_client.post(
        "/api/v1/users",
        headers=auth_headers(client, "admin-b@example.com"),
        json={"nombre": "Persona B", "correo": "persona-b@example.com", "password": "secret123"},
    )

    assert response.status_code == 201
    assert response.json()["tenant_id"] == 20


def test_correo_duplicado_globalmente_devuelve_conflicto(client, seed_users):
    test_client, session_factory = client
    response = test_client.post(
        "/api/v1/users",
        headers=auth_headers(client, "tenant@example.com"),
        json={"nombre": "Duplicado", "correo": "GENERAL@example.com", "password": "secret123"},
    )

    assert response.status_code == 409
    with session_factory() as db:
        assert db.scalar(select(User).where(User.nombre == "Duplicado")) is None


@pytest.mark.parametrize("correo", ["usuario@example.com", "general@example.com"])
def test_roles_no_autorizados_no_pueden_crear(client, seed_users, correo):
    test_client, session_factory = client
    response = test_client.post(
        "/api/v1/users",
        headers=auth_headers(client, correo),
        json={"nombre": "Prohibido", "correo": "prohibido@example.com", "password": "secret123"},
    )

    assert response.status_code == 403
    with session_factory() as db:
        assert db.scalar(select(User).where(User.correo == "prohibido@example.com")) is None


def test_creacion_sin_autenticacion_es_rechazada(client):
    response = client[0].post(
        "/api/v1/users",
        json={"nombre": "Sin acceso", "correo": "sin-acceso@example.com", "password": "secret123"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize("extra", [{"tenant_id": 20}, {"rol": "admin_general"}, {"estado": "inactivo"}])
def test_campos_de_autoridad_en_payload_son_rechazados(client, seed_users, extra):
    test_client, session_factory = client
    response = test_client.post(
        "/api/v1/users",
        headers=auth_headers(client, "tenant@example.com"),
        json={"nombre": "No crear", "correo": "no-crear@example.com", "password": "secret123", **extra},
    )

    assert response.status_code == 422
    with session_factory() as db:
        assert db.scalar(select(User).where(User.correo == "no-crear@example.com")) is None


@pytest.mark.parametrize(
    "payload",
    [
        {"correo": "nuevo@example.com", "password": "secret123"},
        {"nombre": "Nuevo", "password": "secret123"},
        {"nombre": "Nuevo", "correo": "nuevo@example.com"},
        {"nombre": "   ", "correo": "nuevo@example.com", "password": "secret123"},
        {"nombre": "Nuevo", "correo": "correo-invalido", "password": "secret123"},
        {"nombre": "Nuevo", "correo": "nuevo@example.com", "password": ""},
    ],
)
def test_campos_obligatorios_y_correo_valido(client, seed_users, payload):
    response = client[0].post(
        "/api/v1/users",
        headers=auth_headers(client, "tenant@example.com"),
        json=payload,
    )

    assert response.status_code == 422
