"""Integración HTTP de los permisos y cambios de rol aprobados en T4."""

from datetime import datetime

import pytest

from app.core.security import get_password_hash
from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User


def headers_for(client, correo: str) -> dict[str, str]:
    response = client[0].post(
        "/api/v1/auth/login", json={"correo": correo, "password": "secret123"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def change_role(client, user_id: int, role: str, headers: dict[str, str]):
    return client[0].patch(
        f"/api/v1/users/{user_id}/role", json={"rol": role}, headers=headers
    )


def test_admin_change_persists_and_old_token_uses_current_role(client, seed_users):
    operative_headers = headers_for(client, "usuario@example.com")
    general_headers = headers_for(client, "general@example.com")
    assert client[0].get("/api/v1/users", headers=operative_headers).status_code == 403

    promoted = change_role(client, 1, "admin_tenant", general_headers)
    assert promoted.status_code == 200
    assert promoted.json()["rol"] == "admin_tenant"
    assert promoted.json()["tenant_id"] == 10
    assert set(promoted.json()) == {"id", "tenant_id", "nombre", "correo", "rol", "estado"}
    with client[1]() as db:
        assert db.get(User, 1).rol == "admin_tenant"

    # El token se emitió cuando la cuenta era usuario_negocio.
    assert client[0].get("/api/v1/users", headers=operative_headers).status_code == 200

    demoted = change_role(client, 1, "usuario_negocio", general_headers)
    assert demoted.status_code == 200
    assert client[0].get("/api/v1/users", headers=operative_headers).status_code == 403
    with client[1]() as db:
        assert db.get(User, 1).rol == "usuario_negocio"


@pytest.mark.parametrize("correo", ["usuario@example.com", "tenant@example.com"])
def test_direct_role_change_without_permission_does_not_write(client, seed_users, correo):
    denied = change_role(client, 1, "admin_tenant", headers_for(client, correo))
    assert denied.status_code == 403
    with client[1]() as db:
        assert db.get(User, 1).rol == "usuario_negocio"


def test_invalid_transition_and_authority_fields_do_not_write(client, seed_users):
    general_headers = headers_for(client, "general@example.com")
    assert change_role(client, 1, "usuario_negocio", general_headers).status_code == 422
    assert change_role(client, 3, "admin_tenant", general_headers).status_code == 403
    response = client[0].patch(
        "/api/v1/users/1/role",
        json={"rol": "admin_tenant", "tenant_id": 20},
        headers=general_headers,
    )
    assert response.status_code == 422
    with client[1]() as db:
        assert db.get(User, 1).rol == "usuario_negocio"
        assert db.get(User, 1).tenant_id == 10
        assert db.get(User, 3).rol == "admin_general"


def test_ordinary_users_and_tenants_keep_hu03_contracts(client, seed_users):
    tenant_headers = headers_for(client, "tenant@example.com")
    operative_headers = headers_for(client, "usuario@example.com")
    general_headers = headers_for(client, "general@example.com")

    created = client[0].post(
        "/api/v1/users",
        json={"nombre": "Nueva persona", "correo": "nueva@example.com", "password": "secret123"},
        headers=tenant_headers,
    )
    assert created.status_code == 201
    assert created.json()["rol"] == "usuario_negocio"
    assert created.json()["tenant_id"] == 10
    assert client[0].get("/api/v1/users", headers=tenant_headers).json()["total"] == 4
    assert client[0].patch(
        "/api/v1/users/1", json={"nombre": "Nombre vigente"}, headers=tenant_headers
    ).status_code == 200
    assert client[0].patch(
        "/api/v1/users/1", json={"rol": "admin_tenant"}, headers=tenant_headers
    ).status_code == 422
    assert client[0].patch(
        "/api/v1/users/1", json={"tenant_id": 20}, headers=tenant_headers
    ).status_code == 422
    assert client[0].get("/api/v1/users", headers=operative_headers).status_code == 403
    assert client[0].get("/api/v1/users", headers=general_headers).status_code == 403
    assert client[0].get("/api/v1/tenants", headers=tenant_headers).status_code == 403
    assert client[0].get("/api/v1/tenants", headers=general_headers).status_code == 200
    with client[1]() as db:
        assert db.get(User, 1).nombre == "Nombre vigente"
        assert db.get(User, 1).rol == "usuario_negocio"
        assert db.get(User, 1).tenant_id == 10


def test_operational_routes_reject_general_and_preserve_tenant_scope(client, seed_users):
    with client[1]() as db:
        db.add(Tenant(id=20, nombre="Segundo tenant", estado="activo"))
        db.add(User(
            tenant_id=20, nombre="Usuario B", correo="usuario-b@example.com",
            password_hash=get_password_hash("secret123"), rol="usuario_negocio", estado="activo",
        ))
        db.add(Review(
            id=201, tenant_id=20, autor="Persona B", contenido="Privada B",
            fecha=datetime(2026, 9, 21), fuente="Google", puntuacion=4, estado="nueva",
        ))
        db.commit()
    operative_headers = headers_for(client, "usuario@example.com")
    general_headers = headers_for(client, "general@example.com")

    assert client[0].get("/api/v1/reviews", headers=operative_headers).json()["total"] == 0
    assert client[0].get("/api/v1/reviews/201", headers=operative_headers).status_code == 404
    assert client[0].patch(
        "/api/v1/reviews/201", json={"contenido": "Intrusión"}, headers=operative_headers
    ).status_code == 404
    assert client[0].get("/api/v1/dashboard", headers=operative_headers).json()["total_reviews"] == 0
    for path in ("/api/v1/reviews", "/api/v1/dashboard"):
        assert client[0].get(path, headers=general_headers).status_code == 403
    csv_file = {"file": ("reviews.csv", b"contenido,fecha,puntuacion\nPrueba,2026-09-21,5\n", "text/csv")}
    for path in ("/api/v1/reviews/import", "/api/v1/imports/upload"):
        assert client[0].post(path, headers=general_headers, files=csv_file).status_code == 403
    with client[1]() as db:
        assert db.get(Review, 201).contenido == "Privada B"


def test_inactive_tenant_blocks_existing_token_on_operational_routes(client, seed_users):
    headers = headers_for(client, "usuario@example.com")
    with client[1]() as db:
        db.get(Tenant, 10).estado = "inactivo"
        db.commit()
    for path in ("/api/v1/reviews", "/api/v1/dashboard"):
        assert client[0].get(path, headers=headers).status_code == 403
    assert client[0].post(
        "/api/v1/auth/login",
        json={"correo": "usuario@example.com", "password": "secret123"},
    ).status_code == 403
    with client[1]() as db:
        db.get(Tenant, 10).estado = "activo"
        db.commit()
    assert client[0].get("/api/v1/reviews", headers=headers).status_code == 200
