import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.tenant import Tenant
from app.models.user import User


def auth_headers(client, correo: str) -> dict[str, str]:
    response = client[0].post(
        "/api/v1/auth/login",
        json={"correo": correo, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def user_ids(client, seed_users):
    _, session_factory = client
    with session_factory() as db:
        db.add(Tenant(id=20, nombre="Segundo tenant", estado="activo"))
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
                    estado="activo",
                ),
            ]
        )
        db.commit()
        return {user.correo: user.id for user in db.scalars(select(User))}


def patch_user(client, user_id: int, payload: dict, actor: str = "tenant@example.com"):
    return client[0].patch(
        f"/api/v1/users/{user_id}",
        headers=auth_headers(client, actor),
        json=payload,
    )


def test_admin_tenant_actualiza_nombre_y_persiste_sin_cambiar_otros_campos(client, user_ids):
    user_id = user_ids["usuario@example.com"]
    response = patch_user(client, user_id, {"nombre": "  Nombre actualizado  "})

    assert response.status_code == 200
    assert response.json()["nombre"] == "Nombre actualizado"
    assert response.json()["correo"] == "usuario@example.com"
    assert response.json()["estado"] == "activo"
    assert response.json()["rol"] == "usuario_negocio"
    with client[1]() as db:
        user = db.get(User, user_id)
        assert user.nombre == "Nombre actualizado"
        assert user.tenant_id == 10


def test_admin_tenant_actualiza_correo_valido_y_persiste(client, user_ids):
    user_id = user_ids["usuario@example.com"]
    response = patch_user(client, user_id, {"correo": "Nuevo@Example.com"})

    assert response.status_code == 200
    assert response.json()["correo"] == "nuevo@example.com"
    with client[1]() as db:
        assert db.get(User, user_id).correo == "nuevo@example.com"


@pytest.mark.parametrize(
    ("correo", "nuevo_estado"),
    [
        ("inactive@example.com", "activo"),
        ("usuario@example.com", "inactivo"),
    ],
)
def test_admin_tenant_activa_o_desactiva_y_persiste(client, user_ids, correo, nuevo_estado):
    user_id = user_ids[correo]
    response = patch_user(client, user_id, {"estado": nuevo_estado})

    assert response.status_code == 200
    assert response.json()["estado"] == nuevo_estado
    with client[1]() as db:
        assert db.get(User, user_id).estado == nuevo_estado


def test_admin_tenant_no_modifica_usuario_de_otro_tenant(client, user_ids):
    user_id = user_ids["usuario-b@example.com"]
    response = patch_user(client, user_id, {"nombre": "Invasión"})

    assert response.status_code == 404
    with client[1]() as db:
        assert db.get(User, user_id).nombre == "Usuario B"


@pytest.mark.parametrize("actor", ["usuario@example.com", "general@example.com"])
def test_roles_no_autorizados_no_pueden_editar(client, user_ids, actor):
    response = patch_user(client, user_ids["inactive@example.com"], {"nombre": "Prohibido"}, actor)

    assert response.status_code == 403
    with client[1]() as db:
        assert db.get(User, user_ids["inactive@example.com"]).nombre == "Usuario inactivo"


def test_solicitud_sin_autenticacion_es_rechazada(client, user_ids):
    response = client[0].patch(
        f"/api/v1/users/{user_ids['usuario@example.com']}",
        json={"nombre": "Sin permiso"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize("correo", ["inactive@example.com", "usuario-b@example.com"])
def test_correo_duplicado_globalmente_devuelve_409(client, user_ids, correo):
    user_id = user_ids["usuario@example.com"]
    response = patch_user(client, user_id, {"correo": correo})

    assert response.status_code == 409
    with client[1]() as db:
        assert db.get(User, user_id).correo == "usuario@example.com"


def test_repetir_el_mismo_correo_del_usuario_es_valido(client, user_ids):
    response = patch_user(client, user_ids["usuario@example.com"], {"correo": "USUARIO@example.com"})

    assert response.status_code == 200
    assert response.json()["correo"] == "usuario@example.com"


@pytest.mark.parametrize(
    "extra",
    [
        {"rol": "admin_general"},
        {"tenant_id": 20},
        {"tenant": 20},
        {"password": "otra-clave"},
        {"password_hash": "hash"},
        {"id": 999},
    ],
)
def test_campos_fuera_de_alcance_son_rechazados(client, user_ids, extra):
    user_id = user_ids["usuario@example.com"]
    response = patch_user(client, user_id, {"nombre": "No aplicar", **extra})

    assert response.status_code == 422
    with client[1]() as db:
        user = db.get(User, user_id)
        assert user.nombre == "Usuario negocio"
        assert user.rol == "usuario_negocio"
        assert user.tenant_id == 10


def test_respuesta_de_actualizacion_no_expone_password_hash(client, user_ids):
    response = patch_user(client, user_ids["usuario@example.com"], {"nombre": "Respuesta segura"})

    assert response.status_code == 200
    assert set(response.json()) == {"id", "tenant_id", "nombre", "correo", "rol", "estado"}
    assert "password" not in response.text
    assert "password_hash" not in response.text


@pytest.mark.parametrize(
    "payload",
    [
        {"estado": "pendiente"},
        {"nombre": "   "},
        {"nombre": None},
        {"correo": "invalido"},
        {"correo": None},
        {"estado": None},
        {},
    ],
)
def test_datos_invalidos_y_patch_vacio_devuelven_422(client, user_ids, payload):
    user_id = user_ids["usuario@example.com"]
    response = patch_user(client, user_id, payload)

    assert response.status_code == 422
    with client[1]() as db:
        user = db.get(User, user_id)
        assert user.nombre == "Usuario negocio"
        assert user.correo == "usuario@example.com"
        assert user.estado == "activo"


def test_usuario_inexistente_devuelve_404(client, user_ids):
    response = patch_user(client, 9999, {"nombre": "No existe"})

    assert response.status_code == 404


def test_admin_de_tenant_b_puede_editar_solo_su_usuario(client, user_ids):
    response = patch_user(
        client,
        user_ids["usuario-b@example.com"],
        {"nombre": "Usuario B actualizado"},
        "admin-b@example.com",
    )

    assert response.status_code == 200
    assert response.json()["tenant_id"] == 20
