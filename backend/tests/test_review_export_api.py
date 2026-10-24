"""Contrato HTTP y CSV de HU-19 T2 con bases temporales y datos sintéticos."""

import csv
import io
import re
from datetime import datetime

import pytest

from app.core.security import get_password_hash
from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User


HEADERS = ["id", "contenido", "autor", "fecha", "fuente", "puntuacion", "categoria", "estado"]
EXPORT_URL = "/api/v1/reviews/export"


def login(client, correo: str = "usuario@example.com") -> dict[str, str]:
    response = client[0].post(
        "/api/v1/auth/login", json={"correo": correo, "password": "secret123"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def csv_rows(response) -> list[list[str]]:
    assert response.content.startswith(b"\xef\xbb\xbf")
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"), newline="")))


@pytest.fixture()
def seed_export_reviews(client, seed_users):
    _, session_factory = client
    with session_factory() as db:
        db.add(Tenant(id=20, nombre="Otro negocio de prueba", estado="activo"))
        db.add(
            User(
                tenant_id=20,
                nombre="Usuario negocio B",
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
                    autor="María Peña",
                    contenido="Servicio, fantástico\nVolveré.",
                    fecha=datetime(2026, 9, 27, 23, 59, 59, 999999),
                    fuente="Google",
                    puntuacion=5,
                    categoria="Atención",
                    estado="nueva",
                    prioridad="alta",
                    resumen="No exportar resumen",
                    tema="No exportar tema",
                ),
                Review(
                    id=102,
                    tenant_id=10,
                    autor=None,
                    contenido='Dijo "excelente".',
                    fecha=datetime(2026, 9, 27, 23, 59, 59, 999999),
                    fuente="Facebook",
                    puntuacion=4,
                    categoria=None,
                    estado="atendida",
                ),
                Review(
                    id=103,
                    tenant_id=10,
                    autor=" @Persona",
                    contenido="\t =SUMA(1,1)",
                    fecha=datetime(2026, 9, 28, 8),
                    fuente="Google",
                    puntuacion=5,
                    categoria="-Categoría",
                    estado="nueva",
                ),
                Review(
                    id=201,
                    tenant_id=20,
                    autor="Usuario externo",
                    contenido="Servicio secreto del segundo negocio",
                    fecha=datetime(2026, 9, 29, 8),
                    fuente="Google",
                    puntuacion=5,
                    categoria=None,
                    estado="nueva",
                ),
            ]
        )
        db.commit()


def test_exportacion_sin_filtros_cumple_contrato_y_orden(client, seed_export_reviews) -> None:
    response = client[0].get(EXPORT_URL, headers=login(client))

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert re.fullmatch(
        r'attachment; filename="reviews_\d{8}\.csv"',
        response.headers["content-disposition"],
    )
    rows = csv_rows(response)
    assert rows[0] == HEADERS
    assert [row[0] for row in rows[1:]] == ["103", "102", "101"]
    assert all(len(row) == len(HEADERS) for row in rows)
    assert response.content.count(b"\r\n") == 4
    assert rows[3] == [
        "101", "Servicio, fantástico\nVolveré.", "María Peña",
        "2026-09-27T23:59:59.999999", "Google", "5", "Atención", "nueva",
    ]
    assert rows[2][1] == 'Dijo "excelente".'
    assert rows[2][2] == rows[2][6] == ""
    assert b"No exportar resumen" not in response.content
    assert b"No exportar tema" not in response.content


@pytest.mark.parametrize(
    ("params", "expected_ids"),
    [
        ({"busqueda": "  SERVICIO  "}, ["101"]),
        ({"fecha_desde": "2026-09-28"}, ["103"]),
        ({"fecha_hasta": "2026-09-27"}, ["102", "101"]),
        ({"puntuacion": 5}, ["103", "101"]),
        ({"estado": "atendida"}, ["102"]),
        ({"fuente": "Facebook"}, ["102"]),
        (
            {
                "busqueda": "servicio",
                "fecha_desde": "2026-09-27",
                "fecha_hasta": "2026-09-27",
                "puntuacion": 5,
                "estado": "nueva",
                "fuente": "Google",
            },
            ["101"],
        ),
    ],
)
def test_exportacion_reutiliza_filtros_del_listado(client, seed_export_reviews, params, expected_ids) -> None:
    headers = login(client)
    response = client[0].get(EXPORT_URL, params=params, headers=headers)
    listed = client[0].get("/api/v1/reviews", params=params, headers=headers)

    assert response.status_code == listed.status_code == 200
    assert [row[0] for row in csv_rows(response)[1:]] == expected_ids
    assert [item["id"] for item in listed.json()["items"]] == [int(i) for i in expected_ids]


def test_exportacion_vacia_contiene_solo_bom_y_encabezados(client, seed_export_reviews) -> None:
    response = client[0].get(
        EXPORT_URL, params={"busqueda": "sin coincidencias"}, headers=login(client)
    )

    assert response.status_code == 200
    assert csv_rows(response) == [HEADERS]
    assert response.content.count(b"\r\n") == 1


@pytest.mark.parametrize("correo", ["usuario@example.com", "tenant@example.com"])
def test_roles_de_negocio_pueden_exportar(client, seed_export_reviews, correo) -> None:
    response = client[0].get(EXPORT_URL, headers=login(client, correo))
    assert response.status_code == 200
    assert [row[0] for row in csv_rows(response)[1:]] == ["103", "102", "101"]


def test_exportacion_requiere_sesion_y_rechaza_admin_general(client, seed_users) -> None:
    assert client[0].get(EXPORT_URL).status_code == 401
    assert client[0].get(
        EXPORT_URL, headers={"Authorization": "Bearer invalido"}
    ).status_code == 401
    assert client[0].get(
        EXPORT_URL, headers=login(client, "general@example.com")
    ).status_code == 403


def test_usuario_y_tenant_inactivos_no_exportan_con_token_previo(client, seed_users) -> None:
    headers = login(client)
    _, session_factory = client
    with session_factory() as db:
        db.get(User, 1).estado = "inactivo"
        db.commit()
    assert client[0].get(EXPORT_URL, headers=headers).status_code == 403

    with session_factory() as db:
        db.get(User, 1).estado = "activo"
        db.get(Tenant, 10).estado = "inactivo"
        db.commit()
    assert client[0].get(EXPORT_URL, headers=headers).status_code == 403


def test_exportacion_aisla_tenants_y_ignora_tenant_id_del_cliente(client, seed_export_reviews) -> None:
    first = client[0].get(
        EXPORT_URL, params={"tenant_id": 20}, headers=login(client)
    )
    second = client[0].get(
        EXPORT_URL, params={"tenant_id": 10}, headers=login(client, "usuario-b@example.com")
    )

    assert [row[0] for row in csv_rows(first)[1:]] == ["103", "102", "101"]
    assert [row[0] for row in csv_rows(second)[1:]] == ["201"]
    assert b"Servicio secreto del segundo negocio" not in first.content


@pytest.mark.parametrize(
    "params",
    [
        {"fecha_desde": "27-09-2026"},
        {"fecha_hasta": "2026-02-30"},
        {"fecha_desde": "2026-09-28", "fecha_hasta": "2026-09-27"},
        {"puntuacion": 0},
        {"estado": "desconocido"},
    ],
)
def test_filtros_invalidos_tienen_el_mismo_error_que_el_listado(client, seed_users, params) -> None:
    headers = login(client)
    exported = client[0].get(EXPORT_URL, params=params, headers=headers)
    listed = client[0].get("/api/v1/reviews", params=params, headers=headers)

    assert exported.status_code == listed.status_code == 422
    assert exported.json() == listed.json()


def test_formulas_se_marcan_solo_en_csv_y_no_se_escriben_datos(client, seed_export_reviews) -> None:
    response = client[0].get(EXPORT_URL, headers=login(client))
    row = csv_rows(response)[1]
    assert row == [
        "103", "'\t =SUMA(1,1)", "' @Persona", "2026-09-28T08:00:00",
        "Google", "5", "'-Categoría", "nueva",
    ]

    _, session_factory = client
    with session_factory() as db:
        stored = db.get(Review, 103)
        assert stored.contenido == "\t =SUMA(1,1)"
        assert stored.autor == " @Persona"
        assert stored.categoria == "-Categoría"
        assert db.query(Review).count() == 4


def test_openapi_publica_export_antes_de_la_ruta_de_detalle(client) -> None:
    paths = client[0].get("/openapi.json").json()["paths"]
    operation = paths[EXPORT_URL]["get"]
    assert {parameter["name"] for parameter in operation["parameters"]} == {
        "busqueda", "fecha_desde", "fecha_hasta", "puntuacion", "estado", "fuente"
    }
    assert "/api/v1/reviews/{review_id}" in paths
