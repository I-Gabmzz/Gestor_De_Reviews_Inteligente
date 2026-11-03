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


def _expected_csv_row_from_item(item: dict[str, object]) -> list[str]:
    """Convierte un elemento de ReviewList al vector de 8 celdas según el contrato CSV."""
    return [
        str(item["id"]),
        str(item["contenido"]),
        "" if item["autor"] is None else str(item["autor"]),
        str(item["fecha"]),
        str(item["fuente"]),
        str(item["puntuacion"]),
        "" if item["categoria"] is None else str(item["categoria"]),
        str(item["estado"]),
    ]


@pytest.fixture()
def seed_t4_comparison_reviews(client, seed_users):
    """Conjunto sintético exhaustivo para comparar listado y exportación en T4."""
    _, session_factory = client
    with session_factory() as db:
        db.add(Tenant(id=20, nombre="Segundo negocio T4", estado="activo"))
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
                # Límite previo a 2026-09-27
                Review(
                    id=301,
                    tenant_id=10,
                    autor="Lucía Gómez",
                    contenido="Servicio anterior en cafetería",
                    fecha=datetime(2026, 9, 26, 23, 59, 59, 999999),
                    fuente="Google",
                    puntuacion=5,
                    categoria="Atención",
                    estado="nueva",
                    prioridad="alta",
                    resumen="Resumen privado 301",
                    tema="Atención",
                ),
                # Límite inferior exacto 00:00:00 con campos opcionales nulos
                Review(
                    id=302,
                    tenant_id=10,
                    autor=None,
                    contenido="Servicio matutino excelente",
                    fecha=datetime(2026, 9, 27, 0, 0, 0),
                    fuente="Google",
                    puntuacion=5,
                    categoria=None,
                    estado="nueva",
                ),
                # Hora intermedia con autor presente y categoría nula
                Review(
                    id=303,
                    tenant_id=10,
                    autor="Carlos Ruiz",
                    contenido="Servicio lento en revisión, pero amable",
                    fecha=datetime(2026, 9, 27, 12, 30, 0),
                    fuente="Facebook",
                    puntuacion=4,
                    categoria=None,
                    estado="en_revision",
                ),
                # Empate de fecha exacta (23:59:59.999999) con id menor
                Review(
                    id=304,
                    tenant_id=10,
                    autor=None,
                    contenido='Servicio nocturno con "comillas" y coma, ok',
                    fecha=datetime(2026, 9, 27, 23, 59, 59, 999999),
                    fuente="Google",
                    puntuacion=5,
                    categoria="Servicio",
                    estado="nueva",
                ),
                # Empate de fecha exacta (23:59:59.999999) con id mayor
                Review(
                    id=305,
                    tenant_id=10,
                    autor="Elena",
                    contenido="Servicio nocturno empate\nSegunda línea",
                    fecha=datetime(2026, 9, 27, 23, 59, 59, 999999),
                    fuente="Google",
                    puntuacion=5,
                    categoria="Calidad",
                    estado="nueva",
                ),
                # Día siguiente exacto 00:00:00 y caracteres especiales de búsqueda (% y _)
                Review(
                    id=306,
                    tenant_id=10,
                    autor="Pedro",
                    contenido="Descuento 100% en servicio_especial",
                    fecha=datetime(2026, 9, 28, 0, 0, 0),
                    fuente="CSV",
                    puntuacion=3,
                    categoria="Precio",
                    estado="atendida",
                ),
                # Fuente con minúsculas para verificar igualdad exacta y sensibilidad en fuente
                Review(
                    id=307,
                    tenant_id=10,
                    autor=None,
                    contenido="SERVICIO EN MAYÚSCULAS",
                    fecha=datetime(2026, 9, 28, 15, 0, 0),
                    fuente="google",
                    puntuacion=2,
                    categoria="Otro",
                    estado="atendida",
                ),
                # Registros del tenant 20 con los mismos criterios de filtro para probar aislamiento
                Review(
                    id=401,
                    tenant_id=20,
                    autor="Cliente Tenant B",
                    contenido="Servicio matutino del tenant 20",
                    fecha=datetime(2026, 9, 27, 10, 0, 0),
                    fuente="Google",
                    puntuacion=5,
                    categoria="Atención",
                    estado="nueva",
                ),
                Review(
                    id=402,
                    tenant_id=20,
                    autor=None,
                    contenido="Otro comentario en revisión tenant 20",
                    fecha=datetime(2026, 9, 27, 18, 0, 0),
                    fuente="Facebook",
                    puntuacion=4,
                    categoria=None,
                    estado="en_revision",
                ),
            ]
        )
        db.commit()


@pytest.mark.parametrize(
    ("params", "expected_ids"),
    [
        ({}, [307, 306, 305, 304, 303, 302, 301]),
        ({"busqueda": "servicio"}, [307, 306, 305, 304, 303, 302, 301]),
        ({"busqueda": "  SERVICIO NOCTURNO  "}, [305, 304]),
        ({"busqueda": "100%"}, [306]),
        ({"busqueda": "servicio_especial"}, [306]),
        ({"busqueda": ""}, [307, 306, 305, 304, 303, 302, 301]),
        ({"busqueda": "   "}, [307, 306, 305, 304, 303, 302, 301]),
        ({"busqueda": "no-existe-coincidencia"}, []),
        ({"fecha_desde": "2026-09-27"}, [307, 306, 305, 304, 303, 302]),
        ({"fecha_hasta": "2026-09-27"}, [305, 304, 303, 302, 301]),
        ({"fecha_desde": "2026-09-27", "fecha_hasta": "2026-09-27"}, [305, 304, 303, 302]),
        ({"fecha_desde": "2026-09-27", "fecha_hasta": "2026-09-28"}, [307, 306, 305, 304, 303, 302]),
        ({"puntuacion": 5}, [305, 304, 302, 301]),
        ({"puntuacion": 3}, [306]),
        ({"estado": "nueva"}, [305, 304, 302, 301]),
        ({"estado": "en_revision"}, [303]),
        ({"estado": "atendida"}, [307, 306]),
        ({"fuente": "Google"}, [305, 304, 302, 301]),
        ({"fuente": "  Google  "}, [305, 304, 302, 301]),
        ({"fuente": "google"}, [307]),
        ({"fuente": "GOOGLE"}, []),
        ({"fuente": ""}, [307, 306, 305, 304, 303, 302, 301]),
        (
            {
                "busqueda": "servicio",
                "fecha_desde": "2026-09-27",
                "fecha_hasta": "2026-09-27",
                "puntuacion": 5,
                "estado": "nueva",
                "fuente": "Google",
            },
            [305, 304, 302],
        ),
        ({"estado": "atendida", "fuente": "Facebook"}, []),
    ],
)
def test_comparacion_exhaustiva_listado_y_csv_ocho_columnas_orden_y_nulos(
    client, seed_t4_comparison_reviews, params, expected_ids
) -> None:
    headers = login(client)
    listed_res = client[0].get("/api/v1/reviews", params=params, headers=headers)
    exported_res = client[0].get(EXPORT_URL, params=params, headers=headers)

    assert listed_res.status_code == exported_res.status_code == 200
    items = listed_res.json()["items"]
    assert listed_res.json()["total"] == len(items) == len(expected_ids)
    assert [item["id"] for item in items] == expected_ids

    rows = csv_rows(exported_res)
    assert rows[0] == HEADERS
    data_rows = rows[1:]
    assert len(data_rows) == len(items)

    for item, csv_row in zip(items, data_rows, strict=True):
        assert len(csv_row) == 8
        assert csv_row == _expected_csv_row_from_item(item)
        if item["autor"] is None:
            assert csv_row[2] == ""
        if item["categoria"] is None:
            assert csv_row[6] == ""


@pytest.mark.parametrize(
    ("correo", "expected_ids"),
    [
        ("usuario@example.com", [305, 304, 302]),
        ("tenant@example.com", [305, 304, 302]),
        ("usuario-b@example.com", [401]),
    ],
)
def test_aislamiento_multitenant_comparado_con_mismos_filtros(
    client, seed_t4_comparison_reviews, correo, expected_ids
) -> None:
    params = {
        "busqueda": "servicio",
        "fecha_desde": "2026-09-27",
        "fecha_hasta": "2026-09-27",
        "puntuacion": 5,
        "estado": "nueva",
        "fuente": "Google",
    }
    headers = login(client, correo)
    listed_res = client[0].get("/api/v1/reviews", params=params, headers=headers)
    exported_res = client[0].get(EXPORT_URL, params=params, headers=headers)

    assert listed_res.status_code == exported_res.status_code == 200
    items = listed_res.json()["items"]
    rows = csv_rows(exported_res)

    assert [item["id"] for item in items] == expected_ids
    assert rows[0] == HEADERS
    assert [row for row in rows[1:]] == [_expected_csv_row_from_item(item) for item in items]


def test_t5_codificacion_utf8_bom_unico_y_unicode_multilingue(client, seed_users) -> None:
    _, session_factory = client
    with session_factory() as db:
        db.add_all(
            [
                Review(
                    id=501,
                    tenant_id=10,
                    autor="Mónica Núñez-Gómez (Ü/ü)",
                    contenido=(
                        "Café pingüino: $150.00 MXN, €120,50, £99.99, ¥2000 — "
                        "¡Excelente atención! ☕⭐🔥👍 "
                        "日本語のレビュー / 中文评价 / 한국어 리뷰"
                    ),
                    fecha=datetime(2026, 10, 1, 9, 30, 0),
                    fuente="Google Maps™",
                    puntuacion=5,
                    categoria="Atención & Café",
                    estado="nueva",
                ),
            ]
        )
        db.commit()

    response = client[0].get(EXPORT_URL, headers=login(client))
    assert response.status_code == 200
    raw = response.content

    # 1. Comienza exactamente con el BOM UTF-8 (EF BB BF) y no duplica el BOM.
    assert raw.startswith(b"\xef\xbb\xbf")
    assert not raw[3:].startswith(b"\xef\xbb\xbf")
    assert raw.count(b"\xef\xbb\xbf") == 1

    # 2. Se decodifica limpiamente como UTF-8 y utf-8-sig elimina el BOM del primer encabezado.
    decoded_utf8 = raw.decode("utf-8")
    assert decoded_utf8.startswith("\ufeffid,contenido,autor,fecha,fuente,puntuacion,categoria,estado\r\n")
    decoded_sig = raw.decode("utf-8-sig")
    assert decoded_sig.startswith("id,contenido,autor,fecha,fuente,puntuacion,categoria,estado\r\n")

    rows = list(csv.reader(io.StringIO(decoded_sig, newline="")))
    assert rows[0] == HEADERS
    assert rows[0][0] == "id"
    assert "\ufeff" not in rows[0][0]
    assert rows[1] == [
        "501",
        (
            "Café pingüino: $150.00 MXN, €120,50, £99.99, ¥2000 — "
            "¡Excelente atención! ☕⭐🔥👍 "
            "日本語のレビュー / 中文评价 / 한국어 리뷰"
        ),
        "Mónica Núñez-Gómez (Ü/ü)",
        "2026-10-01T09:30:00",
        "Google Maps™",
        "5",
        "Atención & Café",
        "nueva",
    ]


def test_t5_serializacion_csv_comas_comillas_saltos_espacios_nulos_y_contenido_largo(
    client, seed_users
) -> None:
    long_paragraph = (" Reseña extensa con acentos, comillas \"internas\" y detalles; " * 40) + "fin  "
    _, session_factory = client
    with session_factory() as db:
        db.add_all(
            [
                Review(
                    id=510,
                    tenant_id=10,
                    autor='  Juan "El Crítico", Jr.  ',
                    contenido='Línea 1 con "comillas", comas, y LF\nLínea 2 con CRLF\r\nLínea 3 final.',
                    fecha=datetime(2026, 10, 2, 10, 0, 0),
                    fuente='Portal, "Verificado"',
                    puntuacion=4,
                    categoria=' Producto, "Premium" ',
                    estado="en_revision",
                    prioridad="alta",
                    resumen="Resumen IA oculto",
                    tema="Producto",
                ),
                Review(
                    id=511,
                    tenant_id=10,
                    autor="",
                    contenido=long_paragraph,
                    fecha=datetime(2026, 10, 2, 11, 0, 0),
                    fuente="Web",
                    puntuacion=1,
                    categoria="",
                    estado="atendida",
                ),
                Review(
                    id=512,
                    tenant_id=10,
                    autor=None,
                    contenido="   Espacios al inicio y al final conservados   ",
                    fecha=datetime(2026, 10, 2, 12, 0, 0),
                    fuente="Manual",
                    puntuacion=3,
                    categoria=None,
                    estado="nueva",
                ),
            ]
        )
        db.commit()

    response = client[0].get(EXPORT_URL, headers=login(client))
    assert response.status_code == 200
    rows = csv_rows(response)
    assert rows[0] == HEADERS
    assert all(len(row) == 8 for row in rows)

    # Orden fecha DESC, id DESC -> 512, 511, 510
    assert rows[1] == [
        "512",
        "   Espacios al inicio y al final conservados   ",
        "",
        "2026-10-02T12:00:00",
        "Manual",
        "3",
        "",
        "nueva",
    ]
    assert rows[2] == [
        "511",
        long_paragraph,
        "",
        "2026-10-02T11:00:00",
        "Web",
        "1",
        "",
        "atendida",
    ]
    assert rows[3] == [
        "510",
        'Línea 1 con "comillas", comas, y LF\nLínea 2 con CRLF\r\nLínea 3 final.',
        '  Juan "El Crítico", Jr.  ',
        "2026-10-02T10:00:00",
        'Portal, "Verificado"',
        "4",
        ' Producto, "Premium" ',
        "en_revision",
    ]
    assert b"Resumen IA oculto" not in response.content


def test_t5_neutralizacion_formulas_cinco_columnas_texto_y_preservacion_legitimos(
    client, seed_users
) -> None:
    _, session_factory = client
    with session_factory() as db:
        db.add_all(
            [
                # Prefijos directos =, +, -, @ y con espacios/controles iniciales en las 5 columnas de texto
                Review(
                    id=520,
                    tenant_id=10,
                    autor="+52 55 1234 5678",
                    contenido='=HIPERVINCULO("https://malicioso.example","clic")',
                    fecha=datetime(2026, 10, 3, 8, 0, 0),
                    fuente="-FuenteExterna",
                    puntuacion=2,
                    categoria="@categoria_riesgo",
                    estado="=estado_forzado",
                ),
                Review(
                    id=521,
                    tenant_id=10,
                    autor="\t\r\n @usuario_control",
                    contenido="   \u200b=1+1",
                    fecha=datetime(2026, 10, 3, 9, 0, 0),
                    fuente=" \x00+FuenteConNuloControl",
                    puntuacion=4,
                    categoria="\n-CategoriaConSalto",
                    estado="  @estado_con_espacio",
                ),
                # Valores legítimos con signos =, +, -, @ en el interior que NO deben alterarse
                Review(
                    id=522,
                    tenant_id=10,
                    autor="cliente@dominio.example (Juan-Pablo)",
                    contenido="Calidad A+ y relación costo-beneficio = excelente @sucursal centro",
                    fecha=datetime(2026, 10, 3, 10, 0, 0),
                    fuente="App-Móvil v2+1",
                    puntuacion=5,
                    categoria="Relación calidad-precio = 10",
                    estado="en_revision",
                ),
            ]
        )
        db.commit()

    # Exportación sin filtro de estado valida las 3 filas y las 5 columnas de texto
    response = client[0].get(EXPORT_URL, headers=login(client))
    assert response.status_code == 200
    rows = csv_rows(response)
    assert rows[0] == HEADERS

    # Row 1 -> id 522 (legítimo, sin apóstrofo añadido en ninguna columna)
    assert rows[1] == [
        "522",
        "Calidad A+ y relación costo-beneficio = excelente @sucursal centro",
        "cliente@dominio.example (Juan-Pablo)",
        "2026-10-03T10:00:00",
        "App-Móvil v2+1",
        "5",
        "Relación calidad-precio = 10",
        "en_revision",
    ]
    # Row 2 -> id 521 (prefijos tras espacios y caracteres de control Cc/Cf neutralizados en las 5 columnas)
    assert rows[2] == [
        "521",
        "'   \u200b=1+1",
        "'\t\r\n @usuario_control",
        "2026-10-03T09:00:00",
        "' \x00+FuenteConNuloControl",
        "4",
        "'\n-CategoriaConSalto",
        "'  @estado_con_espacio",
    ]
    # Row 3 -> id 520 (prefijos directos neutralizados en las 5 columnas; id y puntuacion numéricos intactos)
    assert rows[3] == [
        "520",
        '\'=HIPERVINCULO("https://malicioso.example","clic")',
        "'+52 55 1234 5678",
        "2026-10-03T08:00:00",
        "'-FuenteExterna",
        "2",
        "'@categoria_riesgo",
        "'=estado_forzado",
    ]

    # Verificar que la base de datos no sufrió ninguna modificación
    with session_factory() as db:
        r520 = db.get(Review, 520)
        assert r520.contenido == '=HIPERVINCULO("https://malicioso.example","clic")'
        assert r520.autor == "+52 55 1234 5678"
        assert r520.fuente == "-FuenteExterna"
        assert r520.categoria == "@categoria_riesgo"
        assert r520.estado == "=estado_forzado"


def test_t5_volumen_1000_reviews_sinteticas_y_aislamiento_tenant(
    client, seed_users
) -> None:
    from datetime import timedelta

    _, session_factory = client
    base_time = datetime(2026, 1, 1, 0, 0, 0)
    with session_factory() as db:
        db.add(Tenant(id=20, nombre="Tenant Ajeno Volumen", estado="activo"))
        tenant_10_reviews = [
            Review(
                id=1000 + index,
                tenant_id=10,
                autor=f"Autor Sintético {index}" if index % 3 != 0 else None,
                contenido=(
                    f"Reseña sintética #{index}, atención 100% buena"
                    if index % 5 != 0
                    else f"=FORMULA_PRUEBA({index})"
                ),
                fecha=base_time + timedelta(minutes=index),
                fuente="Google" if index % 2 == 0 else "CSV",
                puntuacion=(index % 5) + 1,
                categoria="Servicio" if index % 2 == 0 else None,
                estado=("nueva", "en_revision", "atendida")[index % 3],
            )
            for index in range(1, 1001)
        ]
        tenant_20_reviews = [
            Review(
                id=3000 + index,
                tenant_id=20,
                autor=f"Externo {index}",
                contenido=f"Reseña ajena #{index}",
                fecha=base_time + timedelta(minutes=index),
                fuente="Google",
                puntuacion=5,
                categoria="Otro",
                estado="nueva",
            )
            for index in range(1, 51)
        ]
        db.add_all(tenant_10_reviews + tenant_20_reviews)
        db.commit()

    headers = login(client)
    listed_res = client[0].get("/api/v1/reviews", headers=headers)
    exported_res = client[0].get(EXPORT_URL, headers=headers)

    assert listed_res.status_code == exported_res.status_code == 200
    items = listed_res.json()["items"]
    assert listed_res.json()["total"] == len(items) == 1000

    rows = csv_rows(exported_res)
    assert rows[0] == HEADERS
    data_rows = rows[1:]
    assert len(data_rows) == 1000

    # Primer registro (más reciente: index=1000 -> id=2000) y último (index=1 -> id=1001)
    assert data_rows[0][0] == "2000"
    assert data_rows[0][1] == "'=FORMULA_PRUEBA(1000)"
    assert data_rows[-1][0] == "1001"
    assert data_rows[-1][1] == "Reseña sintética #1, atención 100% buena"
    assert all(len(row) == 8 for row in data_rows)
    assert b"Externo " not in exported_res.content
    assert b"ajena #" not in exported_res.content
