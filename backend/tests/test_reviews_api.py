from datetime import datetime

import pytest

from app.core.security import get_password_hash
from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User


@pytest.fixture()
def seed_reviews(client, seed_users):
    _, session_factory = client
    with session_factory() as db:
        db.add(Tenant(id=20, nombre="Otro negocio", estado="activo"))
        db.add_all(
            [
                Review(
                    id=101,
                    tenant_id=10,
                    autor="Ana",
                    contenido="Review anterior",
                    fecha=datetime(2026, 9, 18),
                    fuente="Google",
                    puntuacion=4,
                    estado="nueva",
                ),
                Review(
                    id=102,
                    tenant_id=10,
                    autor="Luis",
                    contenido="Review reciente",
                    fecha=datetime(2026, 9, 20),
                    fuente="Facebook",
                    puntuacion=5,
                    estado="atendida",
                ),
                Review(
                    id=201,
                    tenant_id=20,
                    autor="Persona externa",
                    contenido="Review de otro tenant",
                    fecha=datetime(2026, 9, 21),
                    fuente="Google",
                    puntuacion=1,
                    estado="nueva",
                ),
            ]
        )
        db.commit()


def login(client, correo: str = "usuario@example.com") -> dict[str, str]:
    response = client[0].post(
        "/api/v1/auth/login",
        json={"correo": correo, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_listar_reviews_requiere_autenticacion(client) -> None:
    response = client[0].get("/api/v1/reviews")

    assert response.status_code == 401


def test_listar_reviews_devuelve_solo_el_tenant_autenticado(
    client,
    seed_reviews,
) -> None:
    response = client[0].get("/api/v1/reviews", headers=login(client))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [102, 101]
    assert {item["tenant_id"] for item in body["items"]} == {10}


def test_consultar_detalle_del_mismo_tenant(client, seed_reviews) -> None:
    response = client[0].get("/api/v1/reviews/101", headers=login(client))

    assert response.status_code == 200
    assert response.json()["contenido"] == "Review anterior"


@pytest.mark.parametrize("review_id", [201, 999])
def test_review_ajena_o_inexistente_devuelve_404(
    client,
    seed_reviews,
    review_id: int,
) -> None:
    response = client[0].get(
        f"/api/v1/reviews/{review_id}",
        headers=login(client),
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Review con id {review_id} no encontrada"
    }


def test_admin_general_sin_tenant_no_puede_consultar_reviews(
    client,
    seed_reviews,
) -> None:
    response = client[0].get(
        "/api/v1/reviews",
        headers=login(client, "general@example.com"),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "El usuario no pertenece a un tenant"}


@pytest.fixture
def seed_filter_reviews(client, seed_users):
    _, session_factory = client
    rows = [
        (101, "Servicio anterior", datetime(2026, 9, 26, 23, 59, 59, 999999), 5, "nueva", "Google"),
        (102, "Servicio inicio", datetime(2026, 9, 27), 5, "nueva", "Google"),
        (103, "Servicio lento revision", datetime(2026, 9, 27, 12), 4, "en_revision", "Facebook"),
        (104, "Servicio final", datetime(2026, 9, 27, 23, 59, 59, 999999), 5, "nueva", "Google"),
        (
            105, "Servicio final empate", datetime(2026, 9, 27, 23, 59, 59, 999999),
            5, "nueva", "Google",
        ),
        (106, "Producto posterior", datetime(2026, 9, 28), 3, "atendida", "Google"),
        (107, "Satisfaccion al 100%", datetime(2026, 9, 29), 2, "atendida", "CSV"),
        (108, "Satisfaccion al 1000", datetime(2026, 9, 29, 12), 1, "atendida", "CSV"),
        (109, "servicio_lento", datetime(2026, 9, 30), 4, "nueva", "google"),
        (110, "servicio lento", datetime(2026, 9, 30, 12), 4, "nueva", "google"),
    ]
    with session_factory() as db:
        db.add(Tenant(id=20, nombre="Otro negocio", estado="activo"))
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
                    id=review_id,
                    tenant_id=10,
                    autor="Cliente",
                    contenido=content,
                    fecha=fecha,
                    puntuacion=score,
                    estado=estado,
                    fuente=fuente,
                )
                for review_id, content, fecha, score, estado, fuente in rows
            ]
        )
        db.add(
            Review(
                id=201,
                tenant_id=20,
                autor="Cliente externo",
                contenido="Servicio exclusivo otro tenant",
                fecha=datetime(2026, 9, 27, 18),
                puntuacion=5,
                estado="nueva",
                fuente="Google",
            )
        )
        db.commit()


@pytest.mark.parametrize(
    ("params", "expected_ids"),
    [
        ({}, [110, 109, 108, 107, 106, 105, 104, 103, 102, 101]),
        ({"busqueda": "servicio"}, [110, 109, 105, 104, 103, 102, 101]),
        ({"busqueda": "  SERVICIO  "}, [110, 109, 105, 104, 103, 102, 101]),
        ({"busqueda": "servicio lento"}, [110, 103]),
        ({"busqueda": "inexistente"}, []),
        ({"busqueda": ""}, [110, 109, 108, 107, 106, 105, 104, 103, 102, 101]),
        ({"busqueda": "   "}, [110, 109, 108, 107, 106, 105, 104, 103, 102, 101]),
        ({"busqueda": "100%"}, [107]),
        ({"busqueda": "servicio_lento"}, [109]),
        ({"fecha_desde": "2026-09-27"}, [110, 109, 108, 107, 106, 105, 104, 103, 102]),
        ({"fecha_hasta": "2026-09-27"}, [105, 104, 103, 102, 101]),
        ({"fecha_desde": "2026-09-27", "fecha_hasta": "2026-09-28"}, [106, 105, 104, 103, 102]),
        ({"fecha_desde": "2026-09-27", "fecha_hasta": "2026-09-27"}, [105, 104, 103, 102]),
        ({"puntuacion": 5}, [105, 104, 102, 101]),
        ({"estado": "nueva"}, [110, 109, 105, 104, 102, 101]),
        ({"estado": "en_revision"}, [103]),
        ({"estado": "atendida"}, [108, 107, 106]),
        ({"fuente": "Google"}, [106, 105, 104, 102, 101]),
        ({"fuente": " Google "}, [106, 105, 104, 102, 101]),
        ({"fuente": "Inexistente"}, []),
        ({"fuente": ""}, [110, 109, 108, 107, 106, 105, 104, 103, 102, 101]),
        ({"fuente": "   "}, [110, 109, 108, 107, 106, 105, 104, 103, 102, 101]),
        ({"fuente": "google"}, [110, 109]),
        ({"fuente": "GOOGLE"}, []),
        ({"fuente": "Goo"}, []),
        ({"busqueda": "servicio", "estado": "en_revision"}, [103]),
        ({"puntuacion": 5, "fuente": "Google"}, [105, 104, 102, 101]),
        (
            {"fecha_desde": "2026-09-27", "fecha_hasta": "2026-09-27", "puntuacion": 5},
            [105, 104, 102],
        ),
        (
            {
                "busqueda": "servicio",
                "fecha_desde": "2026-09-27",
                "fecha_hasta": "2026-09-27",
                "puntuacion": 5,
                "estado": "nueva",
                "fuente": "Google",
            },
            [105, 104, 102],
        ),
        ({"estado": "atendida", "fuente": "Facebook"}, []),
    ],
)
def test_listado_http_busqueda_filtros_total_orden_y_tenant(
    client, seed_filter_reviews, params, expected_ids
) -> None:
    response = client[0].get("/api/v1/reviews", params=params, headers=login(client))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total"}
    assert [item["id"] for item in body["items"]] == expected_ids
    assert body["total"] == len(expected_ids)
    assert all(item["tenant_id"] == 10 for item in body["items"])
    for item in body["items"]:
        assert set(item) == {
            "id", "tenant_id", "autor", "contenido", "fecha", "fuente", "puntuacion",
            "estado", "categoria", "prioridad",
        }


@pytest.mark.parametrize(
    "params",
    [
        {"fecha_desde": "27-09-2026"},
        {"fecha_hasta": "2026-9-27"},
        {"fecha_desde": "2026-09-27T00:00:00"},
        {"fecha_hasta": "1790467200"},
        {"fecha_desde": "2026-02-30"},
        {"fecha_hasta": ""},
        {"fecha_desde": "2026-09-28", "fecha_hasta": "2026-09-27"},
        {"puntuacion": 0},
        {"puntuacion": 6},
        {"puntuacion": "4.5"},
        {"puntuacion": "texto"},
        {"puntuacion": ""},
        {"estado": "desconocido"},
        {"estado": "Nueva"},
        {"estado": "En revisión"},
        {"estado": "Atendida"},
        {"estado": ""},
    ],
)
def test_parametros_http_invalidos_devuelven_422(client, seed_users, params) -> None:
    response = client[0].get("/api/v1/reviews", params=params, headers=login(client))

    assert response.status_code == 422
    assert "detail" in response.json()
    if params == {"fecha_desde": "2026-09-28", "fecha_hasta": "2026-09-27"}:
        assert response.json() == {"detail": "fecha_desde no puede ser posterior a fecha_hasta"}


@pytest.mark.parametrize(
    ("correo", "tenant_id", "expected_ids"),
    [("usuario@example.com", 10, [105, 104, 102]), ("usuario-b@example.com", 20, [201])],
)
def test_combinacion_http_aisla_ambos_tenants(
    client, seed_filter_reviews, correo, tenant_id, expected_ids
) -> None:
    params = {
        "busqueda": "servicio",
        "fecha_desde": "2026-09-27",
        "fecha_hasta": "2026-09-27",
        "puntuacion": 5,
        "estado": "nueva",
        "fuente": "Google",
    }

    response = client[0].get("/api/v1/reviews", params=params, headers=login(client, correo))

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == expected_ids
    assert body["total"] == len(expected_ids)
    assert all(item["tenant_id"] == tenant_id for item in body["items"])


@pytest.mark.parametrize(
    ("params", "expected_ids"),
    [
        ({"tenant_id": 20}, [110, 109, 108, 107, 106, 105, 104, 103, 102, 101]),
        ({"tenant_id": 20, "busqueda": "exclusivo"}, []),
        (
            {"tenant_id": 20, "estado": "nueva", "puntuacion": 5, "fuente": "Google"},
            [105, 104, 102, 101],
        ),
    ],
)
def test_tenant_id_manual_no_cambia_contexto_http(
    client, seed_filter_reviews, params, expected_ids
) -> None:
    response = client[0].get("/api/v1/reviews", params=params, headers=login(client))

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == expected_ids
    assert body["total"] == len(expected_ids)
    assert all(item["tenant_id"] == 10 for item in body["items"])


def test_http_busqueda_y_filtros_requieren_autenticacion(client) -> None:
    response = client[0].get("/api/v1/reviews", params={"busqueda": "servicio", "estado": "nueva"})

    assert response.status_code == 401


def test_http_busqueda_y_filtros_sin_tenant_devuelven_403(client, seed_users) -> None:
    response = client[0].get(
        "/api/v1/reviews",
        params={"busqueda": "servicio", "estado": "nueva"},
        headers=login(client, "general@example.com"),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "El usuario no pertenece a un tenant"}


def test_openapi_expone_parametros_aprobados_y_review_list(client) -> None:
    response = client[0].get("/openapi.json")

    assert response.status_code == 200
    operation = response.json()["paths"]["/api/v1/reviews"]["get"]
    parameters = {param["name"]: param for param in operation["parameters"]}
    assert set(parameters) == {
        "busqueda", "fecha_desde", "fecha_hasta", "puntuacion", "estado", "fuente"
    }
    assert all(
        param["in"] == "query" and param["required"] is False
        for param in parameters.values()
    )
    schemas = {
        name: next(option for option in param["schema"]["anyOf"] if option["type"] != "null")
        for name, param in parameters.items()
    }
    assert schemas["busqueda"]["type"] == "string"
    assert schemas["fuente"]["type"] == "string"
    for field in ["fecha_desde", "fecha_hasta"]:
        assert schemas[field]["type"] == "string"
        assert schemas[field]["format"] == "date"
    assert schemas["puntuacion"]["type"] == "integer"
    assert schemas["puntuacion"]["minimum"] == 1
    assert schemas["puntuacion"]["maximum"] == 5
    assert schemas["estado"]["enum"] == ["nueva", "en_revision", "atendida"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ReviewList"
    }
