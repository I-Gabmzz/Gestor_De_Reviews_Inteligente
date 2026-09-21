from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db
from app.core.security import get_password_hash
from app.db.base import Base
from app.main import app
from app.models.user import User


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    test_session = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(engine)

    with test_session() as db:
        db.add(
            User(
                tenant_id=None,
                nombre="Administrador general de prueba",
                correo="general-crud@example.com",
                password_hash=get_password_hash("secret123"),
                rol="admin_general",
                estado="activo",
            )
        )
        db.commit()

    def override_get_db() -> Iterator[Session]:
        with test_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)

    login_response = test_client.post(
        "/api/v1/auth/login",
        json={"correo": "general-crud@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200
    test_client.headers["Authorization"] = (
        f"Bearer {login_response.json()['access_token']}"
    )

    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()
        engine.dispose()


def create_tenant(
    client: TestClient,
    nombre: str = "Negocio de prueba",
    estado: str | None = None,
):
    payload = {"nombre": nombre}
    if estado is not None:
        payload["estado"] = estado
    return client.post("/api/v1/tenants", json=payload)


def test_crear_tenant_devuelve_201_identificador_y_persiste(
    client: TestClient,
) -> None:
    response = create_tenant(client)

    assert response.status_code == 201
    created = response.json()
    assert isinstance(created["id"], int)
    assert created["nombre"] == "Negocio de prueba"
    assert created["estado"] == "activo"

    persisted = client.get(f"/api/v1/tenants/{created['id']}")
    assert persisted.status_code == 200
    assert persisted.json() == created


def test_listar_tenants_devuelve_items_y_total(client: TestClient) -> None:
    first = create_tenant(client, nombre="Primero").json()
    second = create_tenant(client, nombre="Segundo", estado="inactivo").json()

    response = client.get("/api/v1/tenants")

    assert response.status_code == 200
    assert response.json() == {"items": [first, second], "total": 2}


def test_consultar_tenant_existente(client: TestClient) -> None:
    created = create_tenant(client).json()

    response = client.get(f"/api/v1/tenants/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


@pytest.mark.parametrize("method", ["get", "patch"])
def test_tenant_inexistente_devuelve_404(
    client: TestClient,
    method: str,
) -> None:
    if method == "get":
        response = client.get("/api/v1/tenants/999")
    else:
        response = client.patch(
            "/api/v1/tenants/999",
            json={"nombre": "No existe"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant con id 999 no encontrado"}


def test_patch_modifica_solo_el_nombre(client: TestClient) -> None:
    created = create_tenant(client).json()

    response = client.patch(
        f"/api/v1/tenants/{created['id']}",
        json={"nombre": "Nombre actualizado"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": created["id"],
        "nombre": "Nombre actualizado",
        "estado": "activo",
    }


def test_patch_desactiva_y_reactiva_tenant(client: TestClient) -> None:
    created = create_tenant(client).json()
    url = f"/api/v1/tenants/{created['id']}"

    deactivated = client.patch(url, json={"estado": "inactivo"})
    reactivated = client.patch(url, json={"estado": "activo"})

    assert deactivated.status_code == 200
    assert deactivated.json()["estado"] == "inactivo"
    assert reactivated.status_code == 200
    assert reactivated.json()["estado"] == "activo"


@pytest.mark.parametrize(
    ("method", "url", "payload"),
    [
        ("post", "/api/v1/tenants", {"nombre": "Inválido", "estado": "otro"}),
        ("patch", "/api/v1/tenants/1", {"estado": "otro"}),
    ],
)
def test_rechaza_estados_invalidos(
    client: TestClient,
    method: str,
    url: str,
    payload: dict[str, str],
) -> None:
    if method == "patch":
        create_tenant(client)

    response = client.request(method, url, json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]


def test_patch_no_permite_modificar_id(client: TestClient) -> None:
    created = create_tenant(client).json()

    response = client.patch(
        f"/api/v1/tenants/{created['id']}",
        json={"id": 999},
    )

    assert response.status_code == 422
    persisted = client.get(f"/api/v1/tenants/{created['id']}")
    assert persisted.status_code == 200
    assert persisted.json()["id"] == created["id"]


def test_no_existe_eliminacion_fisica(client: TestClient) -> None:
    created = create_tenant(client).json()

    response = client.delete(f"/api/v1/tenants/{created['id']}")

    assert response.status_code == 405
