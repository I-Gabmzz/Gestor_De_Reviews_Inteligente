"""Flujos integrados de permisos de HU-04 con dos tenants independientes."""

from datetime import datetime

import pytest

from app.core.security import create_access_token, get_password_hash
from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User


def auth(client, correo: str) -> dict[str, str]:
    response = client[0].post(
        "/api/v1/auth/login", json={"correo": correo, "password": "secret123"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def two_tenants(client, seed_users):
    with client[1]() as db:
        db.add(Tenant(id=20, nombre="Negocio B", estado="activo"))
        db.add_all([
            User(
                tenant_id=20, nombre="Usuario B", correo="usuario-b@example.com",
                password_hash=get_password_hash("secret123"), rol="usuario_negocio", estado="activo",
            ),
            User(
                tenant_id=20, nombre="Administrador B", correo="admin-b@example.com",
                password_hash=get_password_hash("secret123"), rol="admin_tenant", estado="activo",
            ),
            Review(
                id=101, tenant_id=10, autor="Cliente A", contenido="Solo A",
                fecha=datetime(2026, 10, 1), fuente="manual", puntuacion=5, estado="nueva",
            ),
            Review(
                id=202, tenant_id=20, autor="Cliente B", contenido="Solo B",
                fecha=datetime(2026, 10, 2), fuente="manual", puntuacion=4, estado="nueva",
            ),
        ])
        db.commit()
        return {"user_b": db.query(User).filter_by(correo="usuario-b@example.com").one().id}


@pytest.mark.parametrize(
    ("correo", "reviews", "dashboard", "users", "tenants"),
    [
        ("usuario@example.com", 200, 200, 403, 403),
        ("tenant@example.com", 200, 200, 200, 403),
        ("general@example.com", 403, 403, 403, 200),
    ],
)
def test_direct_http_role_matrix(client, seed_users, correo, reviews, dashboard, users, tenants):
    headers = auth(client, correo)
    for path, expected in (
        ("/api/v1/reviews", reviews),
        ("/api/v1/dashboard", dashboard),
        ("/api/v1/users", users),
        ("/api/v1/tenants", tenants),
    ):
        assert client[0].get(path, headers=headers).status_code == expected, path


def test_two_tenant_reviews_users_import_and_role_flow(client, two_tenants):
    user_a = auth(client, "usuario@example.com")
    admin_a = auth(client, "tenant@example.com")
    user_b = auth(client, "usuario-b@example.com")
    general = auth(client, "general@example.com")
    b_id = two_tenants["user_b"]

    for headers, own_id, other_id in ((user_a, 101, 202), (user_b, 202, 101)):
        own = client[0].get(f"/api/v1/reviews/{own_id}", headers=headers)
        assert own.status_code == 200
        assert client[0].get(f"/api/v1/reviews/{other_id}", headers=headers).status_code == 404
        assert client[0].patch(
            f"/api/v1/reviews/{other_id}", json={"contenido": "Intrusión"}, headers=headers
        ).status_code == 404
        assert client[0].patch(
            f"/api/v1/reviews/{other_id}/status", json={"estado": "atendida"}, headers=headers
        ).status_code == 404

    assert client[0].get(
        "/api/v1/reviews?tenant_id=20", headers=user_a
    ).json()["items"][0]["id"] == 101
    assert client[0].post(
        "/api/v1/reviews",
        json={"contenido": "No crear", "fecha": "2026-10-03T10:00:00", "puntuacion": 5,
              "tenant_id": 20},
        headers=user_a,
    ).status_code == 422

    imported = client[0].post(
        "/api/v1/imports/upload?tenant_id=20",
        headers=user_a,
        files={"file": ("reviews.csv",
                        b"autor,contenido,fecha,fuente,puntuacion\nAna,Importada A,2026-10-03,Google,5\n",
                        "text/csv")},
    )
    assert imported.status_code == 200
    assert imported.json()["filas_guardadas"] == 1
    assert client[0].get("/api/v1/dashboard", headers=user_a).json()["total_reviews"] == 2
    assert client[0].get("/api/v1/dashboard", headers=user_b).json()["total_reviews"] == 1
    assert client[0].get("/api/v1/reviews", headers=user_b).json()["total"] == 1

    listed_a = client[0].get("/api/v1/users?tenant_id=20", headers=admin_a)
    assert listed_a.status_code == 200
    assert {item["tenant_id"] for item in listed_a.json()["items"]} == {10}
    assert client[0].patch(
        f"/api/v1/users/{b_id}", json={"nombre": "Intrusión"}, headers=admin_a
    ).status_code == 404
    assert client[0].post(
        "/api/v1/users",
        json={"nombre": "No crear", "correo": "no-crear@example.com",
              "password": "secret123", "tenant_id": 20},
        headers=admin_a,
    ).status_code == 422

    promoted = client[0].patch(
        f"/api/v1/users/{b_id}/role", json={"rol": "admin_tenant"}, headers=general
    )
    assert promoted.status_code == 200
    assert promoted.json()["tenant_id"] == 20
    assert client[0].get("/api/v1/users", headers=user_b).status_code == 200
    assert client[0].patch(
        "/api/v1/users/1", json={"nombre": "Intrusión"}, headers=user_b
    ).status_code == 404
    assert client[0].patch(
        f"/api/v1/users/{b_id}/role", json={"rol": "usuario_negocio"}, headers=user_b
    ).status_code == 403
    with client[1]() as db:
        assert db.get(User, b_id).rol == "admin_tenant"
        assert db.get(User, b_id).tenant_id == 20
        assert db.get(User, 1).nombre == "Usuario negocio"
        assert db.get(Review, 101).contenido == "Solo A"
        assert db.get(Review, 202).contenido == "Solo B"

    assert client[0].patch(
        f"/api/v1/users/{b_id}/role", json={"rol": "usuario_negocio"}, headers=general
    ).status_code == 200
    assert client[0].get("/api/v1/users", headers=user_b).status_code == 403
    with client[1]() as db:
        assert db.get(User, b_id).rol == "usuario_negocio"


def test_signed_jwt_claims_cannot_override_database_role_or_tenant(client, two_tenants):
    operative_claiming_general = {"Authorization": "Bearer " + create_access_token(
        subject="1", rol="admin_general", tenant_id=None
    )}
    general_claiming_operative = {"Authorization": "Bearer " + create_access_token(
        subject="3", rol="usuario_negocio", tenant_id=20
    )}
    assert client[0].get("/api/v1/tenants", headers=operative_claiming_general).status_code == 403
    assert client[0].patch(
        f"/api/v1/users/{two_tenants['user_b']}/role",
        json={"rol": "admin_tenant"}, headers=operative_claiming_general,
    ).status_code == 403
    reviews = client[0].get("/api/v1/reviews?tenant_id=20", headers=operative_claiming_general)
    assert reviews.status_code == 200
    assert [item["id"] for item in reviews.json()["items"]] == [101]
    assert client[0].get("/api/v1/tenants", headers=general_claiming_operative).status_code == 200
    assert client[0].get("/api/v1/reviews", headers=general_claiming_operative).status_code == 403
    with client[1]() as db:
        assert db.get(User, two_tenants["user_b"]).rol == "usuario_negocio"


def test_inactive_tenant_blocks_old_tokens_without_affecting_other_tenant(client, two_tenants):
    admin_a = auth(client, "tenant@example.com")
    user_a = auth(client, "usuario@example.com")
    user_b = auth(client, "usuario-b@example.com")
    general = auth(client, "general@example.com")
    assert client[0].patch(
        "/api/v1/tenants/10", json={"estado": "inactivo"}, headers=general
    ).status_code == 200

    for path, headers in (
        ("/api/v1/users", admin_a),
        ("/api/v1/reviews", user_a),
        ("/api/v1/dashboard", user_a),
    ):
        assert client[0].get(path, headers=headers).status_code == 403
    assert client[0].post(
        "/api/v1/reviews/import", headers=user_a,
        files={"file": ("reviews.csv", b"contenido,fecha,puntuacion\nIntento,2026-10-03,5\n", "text/csv")},
    ).status_code == 403
    assert client[0].post(
        "/api/v1/auth/login",
        json={"correo": "usuario@example.com", "password": "secret123"},
    ).status_code == 403
    assert client[0].get("/api/v1/reviews", headers=user_b).status_code == 200
    assert client[0].post(
        "/api/v1/auth/login",
        json={"correo": "usuario-b@example.com", "password": "secret123"},
    ).status_code == 200
    assert client[0].patch(
        "/api/v1/tenants/10", json={"estado": "activo"}, headers=general
    ).status_code == 200
    assert client[0].get("/api/v1/reviews", headers=user_a).status_code == 200
    with client[1]() as db:
        assert db.get(Review, 101).contenido == "Solo A"
        assert db.get(Review, 202).contenido == "Solo B"
        assert db.get(User, 1).estado == "activo"
