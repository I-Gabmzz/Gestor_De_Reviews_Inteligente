import csv
from io import BytesIO, StringIO

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User


def login_headers(client, correo: str = "usuario@example.com") -> dict[str, str]:
    response = client[0].post(
        "/api/v1/auth/login",
        json={"correo": correo, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def csv_file(rows: str = "") -> dict:
    content = (
        "autor,contenido,fecha,fuente,puntuacion\n"
        "Ana,Excelente servicio,2026-09-21,Google,5\n"
        "Luis,Tiempo de espera alto,2026-09-22,Facebook,3\n"
        f"{rows}"
    )
    return {"file": ("reviews.csv", content.encode("utf-8"), "text/csv")}


def review_file(filename: str, rows: list[dict], *, include_source: bool = True) -> dict:
    headers = ["contenido", "fecha", "puntuacion"]
    if include_source:
        headers.append("fuente")

    if filename.endswith(".csv"):
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        content = output.getvalue().encode("utf-8")
        mime_type = "text/csv"
    else:
        output = BytesIO()
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers)
        for row in rows:
            sheet.append([row.get(header) for header in headers])
        workbook.save(output)
        workbook.close()
        content = output.getvalue()
        mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    return {"file": (filename, content, mime_type)}


def seed_tenant_b(client) -> None:
    _, session_factory = client
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
        db.commit()


def test_importar_reviews_requiere_autenticacion(client) -> None:
    response = client[0].post("/api/v1/reviews/import", files=csv_file())

    assert response.status_code == 401


def test_importacion_persiste_y_actualiza_reviews_y_dashboard(client, seed_users) -> None:
    headers = login_headers(client)

    import_response = client[0].post(
        "/api/v1/reviews/import",
        files=csv_file(),
        headers=headers,
    )

    assert import_response.status_code == 200
    assert import_response.json()["filas_guardadas"] == 2

    reviews_response = client[0].get("/api/v1/reviews", headers=headers)
    assert reviews_response.status_code == 200
    reviews_body = reviews_response.json()
    assert reviews_body["total"] == 2
    assert {item["estado"] for item in reviews_body["items"]} == {"nueva"}

    dashboard_response = client[0].get("/api/v1/dashboard", headers=headers)
    assert dashboard_response.status_code == 200
    dashboard_body = dashboard_response.json()
    assert dashboard_body["total_reviews"] == 2
    assert dashboard_body["promedio_puntuacion"] == 4
    assert dashboard_body["reviews_nuevas"] == 2
    assert [review["contenido"] for review in dashboard_body["reviews_recientes"]] == [
        "Tiempo de espera alto",
        "Excelente servicio",
    ]


def test_importacion_ignora_tenant_id_manipulable_en_query(client, seed_users) -> None:
    seed_tenant_b(client)

    response = client[0].post(
        "/api/v1/imports/upload?tenant_id=20",
        files=csv_file(),
        headers=login_headers(client, "usuario@example.com"),
    )

    assert response.status_code == 200
    assert response.json()["filas_guardadas"] == 2

    tenant_a_reviews = client[0].get(
        "/api/v1/reviews",
        headers=login_headers(client, "usuario@example.com"),
    )
    assert tenant_a_reviews.json()["total"] == 2
    assert {(review["fuente"], review["puntuacion"]) for review in tenant_a_reviews.json()["items"]} == {
        ("Google", 5), ("Facebook", 3)
    }

    tenant_b_reviews = client[0].get(
        "/api/v1/reviews",
        headers=login_headers(client, "usuario-b@example.com"),
    )
    assert tenant_b_reviews.json()["total"] == 0


def test_importacion_devuelve_errores_de_validacion_sin_persistir(client, seed_users) -> None:
    invalid_content = (
        "autor,contenido,fecha,fuente,puntuacion\n"
        "Ana,,2026-09-21,Google,5\n"
    )

    response = client[0].post(
        "/api/v1/reviews/import",
        files={"file": ("reviews.csv", invalid_content.encode("utf-8"), "text/csv")},
        headers=login_headers(client),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["es_valido"] is False
    assert body["filas_guardadas"] == 0
    assert body["total_errores"] == 1

    reviews_response = client[0].get("/api/v1/reviews", headers=login_headers(client))
    assert reviews_response.json()["total"] == 0


@pytest.mark.parametrize(
    ("filename", "source", "include_source", "expected_source", "endpoint"),
    [
        ("reviews.csv", None, False, "CSV", "/api/v1/reviews/import"),
        ("reviews.csv", None, True, "CSV", "/api/v1/reviews/import"),
        ("reviews.csv", "", True, "CSV", "/api/v1/reviews/import"),
        ("reviews.csv", "   ", True, "CSV", "/api/v1/imports/upload"),
        ("reviews.xlsx", None, False, "Excel", "/api/v1/reviews/import"),
        ("reviews.xlsx", None, True, "Excel", "/api/v1/reviews/import"),
        ("reviews.xlsx", "", True, "Excel", "/api/v1/imports/upload"),
        ("reviews.xlsx", "   ", True, "Excel", "/api/v1/reviews/import"),
    ],
)
def test_importacion_asigna_fuente_por_formato_si_falta_o_esta_vacia(
    client, seed_users, filename, source, include_source, expected_source, endpoint
) -> None:
    rows = [{
        "contenido": "Fuente automática",
        "fecha": "2026-10-10",
        "puntuacion": 5,
        "fuente": source,
    }]
    response = client[0].post(
        endpoint,
        files=review_file(filename, rows, include_source=include_source),
        headers=login_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["es_valido"] is True
    assert response.json()["filas_guardadas"] == 1
    assert response.json()["total_errores"] == 0
    with client[1]() as db:
        review = db.scalar(select(Review))
        assert review is not None
        assert (review.fuente, review.puntuacion, review.tenant_id) == (expected_source, 5, 10)


@pytest.mark.parametrize(
    ("endpoint", "filename"),
    [
        ("/api/v1/reviews/import", "reviews.csv"),
        ("/api/v1/imports/upload", "reviews.xlsx"),
    ],
)
def test_ambos_endpoints_conservan_fuente_proporcionada_y_puntuacion(
    client, seed_users, endpoint, filename
) -> None:
    rows = [{
        "contenido": "Fuente proporcionada",
        "fecha": "2026-10-10",
        "puntuacion": "3.0",
        "fuente": "  gOogle  ",
    }]
    response = client[0].post(endpoint, files=review_file(filename, rows), headers=login_headers(client))

    assert response.status_code == 200
    assert response.json()["es_valido"] is True
    assert response.json()["filas_guardadas"] == 1
    with client[1]() as db:
        review = db.scalar(select(Review))
        assert review is not None
        assert (review.fuente, review.puntuacion) == ("gOogle", 3)


@pytest.mark.parametrize("filename", ["reviews.csv", "reviews.xlsx"])
def test_importacion_acepta_fuente_de_cien_caracteres_tras_normalizar(
    client, seed_users, filename
) -> None:
    source = "X" * 100
    rows = [{
        "contenido": "Fuente límite",
        "fecha": "2026-10-10",
        "puntuacion": 4,
        "fuente": f"  {source}  ",
    }]
    response = client[0].post(
        "/api/v1/reviews/import", files=review_file(filename, rows), headers=login_headers(client)
    )

    assert response.status_code == 200
    assert response.json()["es_valido"] is True
    assert response.json()["filas_guardadas"] == 1
    with client[1]() as db:
        review = db.scalar(select(Review))
        assert review is not None
        assert review.fuente == source


@pytest.mark.parametrize("filename", ["reviews.csv", "reviews.xlsx"])
def test_fuente_demasiado_larga_invalida_todo_el_lote(client, seed_users, filename) -> None:
    rows = [
        {"contenido": "Fila válida", "fecha": "2026-10-10", "puntuacion": 5, "fuente": "Google"},
        {"contenido": "Fila inválida", "fecha": "2026-10-10", "puntuacion": 4, "fuente": " X" + "x" * 100 + " "},
    ]
    response = client[0].post(
        "/api/v1/reviews/import", files=review_file(filename, rows), headers=login_headers(client)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["es_valido"] is False
    assert (body["total_filas"], body["filas_validas"], body["filas_guardadas"]) == (2, 1, 0)
    assert body["total_errores"] == 1
    assert body["errores_por_fila"][0]["fila"] == 2
    assert body["errores_por_fila"][0]["campo"] == "fuente"
    assert "100 caracteres" in body["errores_por_fila"][0]["mensaje"]
    with client[1]() as db:
        assert list(db.scalars(select(Review))) == []
