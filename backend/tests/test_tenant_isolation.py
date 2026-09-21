from datetime import datetime

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.dependencies import get_current_tenant_id, get_current_user
from app.core.security import get_password_hash
from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.review_repository import ReviewRepository
from app.schemas.auth import AuthenticatedUser
from app.services.review_service import ReviewService

TENANT_CRUD_OPERATIONS = [
    ("post", "/api/v1/tenants", {"nombre": "No autorizado"}),
    ("get", "/api/v1/tenants", None),
    ("get", "/api/v1/tenants/10", None),
    ("patch", "/api/v1/tenants/10", {"nombre": "No autorizado"}),
]


def login(client, correo: str) -> tuple[str, AuthenticatedUser]:
    test_client, session_factory = client
    response = test_client.post(
        "/api/v1/auth/login",
        json={"correo": correo, "password": "secret123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    with session_factory() as db:
        current_user = get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
            db,
        )

    return token, current_user


@pytest.fixture()
def isolation_data(client, seed_users):
    _, session_factory = client
    with session_factory() as db:
        db.add(Tenant(id=20, nombre="Tenant B", estado="activo"))
        db.add(
            User(
                tenant_id=20,
                nombre="Usuario Tenant B",
                correo="usuario-b@example.com",
                password_hash=get_password_hash("secret123"),
                rol="usuario_negocio",
                estado="activo",
            )
        )
        db.add_all(
            [
                Review(
                    id=101,
                    tenant_id=10,
                    autor="Cliente A",
                    contenido="Review del Tenant A",
                    fecha=datetime(2026, 1, 1),
                    fuente="manual",
                    puntuacion=5,
                    estado="nueva",
                ),
                Review(
                    id=202,
                    tenant_id=20,
                    autor="Cliente B",
                    contenido="Review del Tenant B",
                    fecha=datetime(2026, 1, 2),
                    fuente="manual",
                    puntuacion=4,
                    estado="nueva",
                ),
            ]
        )
        db.commit()

    return {
        "tenant_a": 10,
        "tenant_b": 20,
        "review_a": 101,
        "review_b": 202,
    }


@pytest.mark.parametrize(
    "correo",
    ["usuario@example.com", "tenant@example.com"],
)
def test_usuario_de_negocio_y_admin_tenant_obtienen_su_contexto(
    client,
    seed_users,
    correo: str,
) -> None:
    _, current_user = login(client, correo)

    assert get_current_tenant_id(current_user) == 10


def test_tenant_enviado_por_cliente_no_sustituye_contexto_autenticado(
    client,
    isolation_data,
) -> None:
    _, current_user = login(client, "usuario@example.com")
    tenant_id_enviado = isolation_data["tenant_b"]

    tenant_id_autorizado = get_current_tenant_id(current_user)
    _, session_factory = client

    with session_factory() as db:
        foreign = ReviewService(ReviewRepository(db)).get_by_id_for_current_user(
            isolation_data["review_b"],
            current_user,
        )

    assert tenant_id_enviado == 20
    assert tenant_id_autorizado == 10
    assert tenant_id_autorizado != tenant_id_enviado
    assert foreign is None


@pytest.mark.parametrize(
    ("correo", "own_review", "foreign_review"),
    [
        ("usuario@example.com", "review_a", "review_b"),
        ("usuario-b@example.com", "review_b", "review_a"),
    ],
)
def test_review_de_otro_tenant_no_es_visible(
    client,
    isolation_data,
    correo: str,
    own_review: str,
    foreign_review: str,
) -> None:
    _, current_user = login(client, correo)
    tenant_id = get_current_tenant_id(current_user)
    _, session_factory = client

    with session_factory() as db:
        service = ReviewService(ReviewRepository(db))
        own = service.get_by_id_for_current_user(
            isolation_data[own_review],
            current_user,
        )
        foreign = service.get_by_id_for_current_user(
            isolation_data[foreign_review],
            current_user,
        )

    assert own is not None
    assert own.tenant_id == tenant_id
    assert foreign is None


def test_admin_general_conserva_tenant_null_sin_contexto_interno(
    client,
    seed_users,
) -> None:
    _, current_user = login(client, "general@example.com")

    assert current_user.tenant_id is None
    with pytest.raises(HTTPException) as error:
        get_current_tenant_id(current_user)
    assert error.value.status_code == 403


def test_admin_general_puede_utilizar_crud_administrativo_tenants(
    client,
    seed_users,
) -> None:
    token, _ = login(client, "general@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    test_client = client[0]

    created = test_client.post(
        "/api/v1/tenants",
        json={"nombre": "Tenant administrado"},
        headers=headers,
    )
    assert created.status_code == 201
    tenant_id = created.json()["id"]

    assert test_client.get("/api/v1/tenants", headers=headers).status_code == 200
    assert test_client.get(
        f"/api/v1/tenants/{tenant_id}",
        headers=headers,
    ).status_code == 200
    updated = test_client.patch(
        f"/api/v1/tenants/{tenant_id}",
        json={"estado": "inactivo"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["estado"] == "inactivo"


@pytest.mark.parametrize(
    "correo",
    ["usuario@example.com", "tenant@example.com"],
)
@pytest.mark.parametrize(
    ("method", "url", "payload"),
    TENANT_CRUD_OPERATIONS,
)
def test_roles_de_tenant_no_pueden_usar_crud_global(
    client,
    seed_users,
    correo: str,
    method: str,
    url: str,
    payload: dict[str, str] | None,
) -> None:
    token, _ = login(client, correo)

    response = client[0].request(
        method,
        url,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Se requiere el rol admin_general"}


@pytest.mark.parametrize(
    ("method", "url", "payload"),
    TENANT_CRUD_OPERATIONS,
)
def test_crud_tenants_rechaza_solicitud_sin_autenticacion(
    client,
    method: str,
    url: str,
    payload: dict[str, str] | None,
) -> None:
    response = client[0].request(method, url, json=payload)

    assert response.status_code == 401
    assert response.json() == {"detail": "Token inválido o ausente"}
