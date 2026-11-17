"""Solo se ejecuta con TEST_POSTGRES_URL y un esquema de prueba aislado."""
import csv
import io
from datetime import datetime

from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_db
from app.core.security import get_password_hash
from app.db.init_db import init_db
from app.main import app
from app.models import Review, Tenant, User
from app.repositories.review_repository import ReviewRepository


def test_hu24_legacy_nullability_and_idempotence(postgres_engine):
    init_db(postgres_engine)
    with postgres_engine.begin() as c:
        c.exec_driver_sql("ALTER TABLE reviews ALTER COLUMN fecha SET NOT NULL")
        c.exec_driver_sql("ALTER TABLE reviews ALTER COLUMN puntuacion SET NOT NULL")
        c.exec_driver_sql("INSERT INTO tenants(id,nombre,estado) VALUES (10,'A','activo'),(20,'B','activo')")
        c.exec_driver_sql("INSERT INTO reviews(id,tenant_id,contenido,fecha,fuente,puntuacion,estado,resumen) VALUES (1,10,'A','2026-01-01','Google',5,'nueva','resumen'),(2,20,'B','2026-02-01','CSV',1,'atendida',NULL)")
        c.exec_driver_sql("INSERT INTO external_review_connections(tenant_id,source,business_data_id) VALUES (10,'Google','negocio')")
        c.exec_driver_sql("INSERT INTO external_review_identities(review_id,tenant_id,source,business_data_id,external_review_id,import_fingerprint) VALUES (1,10,'Google','negocio','externo', %s)", ('v1:' + 'a' * 64,))
        c.exec_driver_sql("INSERT INTO review_notifications(id,tenant_id,review_id,creada_en) VALUES (1,10,1,'2026-01-01')")
    with pytest.raises(RuntimeError, match='autorización'):
        init_db(postgres_engine, allow_review_nullable_migration=False)
    assert not {c['name']: c for c in inspect(postgres_engine).get_columns('reviews')}['fecha']['nullable']
    init_db(postgres_engine, allow_review_nullable_migration=True)
    init_db(postgres_engine, allow_review_nullable_migration=False)
    cols = {c['name']: c for c in inspect(postgres_engine).get_columns('reviews')}
    assert cols['fecha']['nullable'] and cols['puntuacion']['nullable']
    with postgres_engine.begin() as c:
        assert c.exec_driver_sql("SELECT count(*) FROM reviews WHERE id=1 AND tenant_id=10 AND fuente='Google' AND puntuacion=5 AND resumen='resumen'").scalar_one() == 1
        assert c.exec_driver_sql("SELECT count(*) FROM reviews WHERE id=2 AND tenant_id=20 AND fuente='CSV' AND estado='atendida'").scalar_one() == 1
        assert c.exec_driver_sql("SELECT count(*) FROM external_review_identities WHERE review_id=1 AND tenant_id=10 AND external_review_id='externo'").scalar_one() == 1
        assert c.exec_driver_sql("SELECT count(*) FROM review_notifications WHERE review_id=1 AND tenant_id=10").scalar_one() == 1
        c.exec_driver_sql("INSERT INTO reviews(id,tenant_id,contenido,fecha,fuente,puntuacion,estado) VALUES (3,10,'sin datos',NULL,'manual',NULL,'nueva')")


@pytest.fixture()
def pg_api(postgres_engine, monkeypatch):
    init_db(postgres_engine)
    sessions = sessionmaker(bind=postgres_engine, expire_on_commit=False)
    with sessions() as db:
        db.add_all(
            [
                Tenant(id=10, nombre="Negocio A", estado="activo"),
                Tenant(id=20, nombre="Negocio B", estado="activo"),
            ]
        )
        db.flush()
        hashed = get_password_hash("PruebaLocal!2026")
        db.add_all(
            [
                User(
                    tenant_id=10,
                    nombre="Usuario A",
                    correo="hu24_pg_a@example.com",
                    password_hash=hashed,
                    rol="usuario_negocio",
                    estado="activo",
                ),
                User(
                    tenant_id=20,
                    nombre="Usuario B",
                    correo="hu24_pg_b@example.com",
                    password_hash=hashed,
                    rol="usuario_negocio",
                    estado="activo",
                ),
            ]
        )
        db.commit()

    def override_get_db():
        with sessions() as db:
            yield db

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("app.main.init_db", lambda: init_db(postgres_engine))
    try:
        with TestClient(app) as client:
            yield client, sessions
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def _login_headers(client: TestClient, correo: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"correo": correo, "password": "PruebaLocal!2026"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_import_file(extension: str, rows: list[dict], headers: list[str] | None = None) -> bytes:
    columns = headers or ["contenido", "autor", "fecha", "puntuacion", "fuente", "tenant_id"]
    if extension == "csv":
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)
        return stream.getvalue().encode("utf-8-sig")
    workbook = Workbook()
    workbook.active.append(columns)
    for row in rows:
        workbook.active.append([row.get(col) for col in columns])
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def test_hu24_postgres_create_read_and_edit_optional_reviews(pg_api):
    client, sessions = pg_api
    headers_a = _login_headers(client, "hu24_pg_a@example.com")

    explicit_nulls = client.post(
        "/api/v1/reviews",
        headers=headers_a,
        json={"contenido": "Alta con nulos explícitos", "autor": None, "fecha": None, "puntuacion": None},
    )
    assert explicit_nulls.status_code == 201
    nulls_body = explicit_nulls.json()
    assert (
        nulls_body["autor"],
        nulls_body["fecha"],
        nulls_body["puntuacion"],
        nulls_body["fuente"],
        nulls_body["estado"],
        nulls_body["tenant_id"],
    ) == (None, None, None, "manual", "nueva", 10)

    omitted = client.post(
        "/api/v1/reviews",
        headers=headers_a,
        json={"contenido": "Alta omitiendo opcionales"},
    )
    assert omitted.status_code == 201
    omitted_body = omitted.json()
    assert (omitted_body["autor"], omitted_body["fecha"], omitted_body["puntuacion"]) == (None, None, None)

    fetched = client.get(f"/api/v1/reviews/{nulls_body['id']}", headers=headers_a)
    assert fetched.status_code == 200
    assert (fetched.json()["autor"], fetched.json()["fecha"], fetched.json()["puntuacion"]) == (None, None, None)

    listed = client.get("/api/v1/reviews", headers=headers_a)
    assert listed.status_code == 200 and listed.json()["total"] == 2
    assert all(item["autor"] is None and item["fecha"] is None and item["puntuacion"] is None for item in listed.json()["items"])

    populated = client.patch(
        f"/api/v1/reviews/{nulls_body['id']}",
        headers=headers_a,
        json={"autor": "Ana", "fecha": "2026-09-24T10:30:00", "puntuacion": 5},
    )
    assert populated.status_code == 200
    assert (populated.json()["autor"], populated.json()["puntuacion"]) == ("Ana", 5)
    assert populated.json()["fecha"].startswith("2026-09-24T10:30:00")

    cleared = client.patch(
        f"/api/v1/reviews/{nulls_body['id']}",
        headers=headers_a,
        json={"autor": None, "fecha": None, "puntuacion": None},
    )
    assert cleared.status_code == 200
    assert (cleared.json()["autor"], cleared.json()["fecha"], cleared.json()["puntuacion"]) == (None, None, None)

    with sessions() as db:
        saved = db.get(Review, nulls_body["id"])
        assert (saved.autor, saved.fecha, saved.puntuacion, saved.tenant_id) == (None, None, None, 10)

    re_populated = client.patch(
        f"/api/v1/reviews/{nulls_body['id']}",
        headers=headers_a,
        json={"autor": "Carlos", "fecha": "2026-09-25T08:15:00", "puntuacion": 4},
    )
    assert re_populated.status_code == 200
    assert (re_populated.json()["autor"], re_populated.json()["puntuacion"]) == ("Carlos", 4)
    assert re_populated.json()["fecha"].startswith("2026-09-25T08:15:00")

    with sessions() as db:
        saved = db.get(Review, nulls_body["id"])
        assert (saved.autor, saved.puntuacion, saved.tenant_id) == ("Carlos", 4, 10)
        assert saved.fecha == datetime(2026, 9, 25, 8, 15, 0)


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_hu24_postgres_csv_and_xlsx_import_optional_and_validation(pg_api, extension):
    client, sessions = pg_api
    headers_a = _login_headers(client, "hu24_pg_a@example.com")

    valid_file = _make_import_file(
        extension,
        [
            {"contenido": f"Importada {extension} vacia", "autor": "", "fecha": "", "puntuacion": "", "fuente": "", "tenant_id": 20},
            {"contenido": f"Importada {extension} completa", "autor": "Luis", "fecha": "2026-09-26", "puntuacion": 5, "fuente": "Google", "tenant_id": 20},
        ],
    )
    imported = client.post(
        "/api/v1/reviews/import",
        headers=headers_a,
        files={"file": (f"opcionales.{extension}", valid_file)},
    )
    assert imported.status_code == 200
    body = imported.json()
    assert body["es_valido"] is True and body["filas_guardadas"] == 2

    with sessions() as db:
        rows = list(db.scalars(select(Review).where(Review.tenant_id == 10).order_by(Review.id.asc())))
        assert len(rows) == 2
        empty_row, full_row = rows
        assert (empty_row.autor, empty_row.fecha, empty_row.puntuacion, empty_row.tenant_id) == (None, None, None, 10)
        assert (full_row.autor, full_row.puntuacion, full_row.fuente, full_row.tenant_id) == ("Luis", 5, "Google", 10)
        assert db.scalar(select(func.count()).select_from(Review).where(Review.tenant_id == 20)) == 0

    missing_headers_file = _make_import_file(
        extension,
        [{"contenido": "Sin columna fecha", "puntuacion": 4}],
        headers=["contenido", "puntuacion"],
    )
    missing_resp = client.post(
        "/api/v1/reviews/import",
        headers=headers_a,
        files={"file": (f"sin_headers.{extension}", missing_headers_file)},
    )
    assert missing_resp.status_code == 200
    assert missing_resp.json()["es_valido"] is False and missing_resp.json()["filas_guardadas"] == 0

    invalid_batch_file = _make_import_file(
        extension,
        [
            {"contenido": f"No persistir {extension}", "autor": "", "fecha": "", "puntuacion": "", "fuente": "", "tenant_id": 10},
            {"contenido": "   ", "autor": "", "fecha": "", "puntuacion": 4, "fuente": "", "tenant_id": 10},
            {"contenido": "Puntuacion invalida", "autor": "", "fecha": "", "puntuacion": 6, "fuente": "", "tenant_id": 10},
        ],
    )
    invalid_resp = client.post(
        "/api/v1/reviews/import",
        headers=headers_a,
        files={"file": (f"invalido.{extension}", invalid_batch_file)},
    )
    assert invalid_resp.status_code == 200
    assert invalid_resp.json()["es_valido"] is False and invalid_resp.json()["filas_guardadas"] == 0

    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(Review)) == 2


def test_hu24_postgres_export_formula_protection_and_multitenancy(pg_api):
    client, sessions = pg_api
    headers_a = _login_headers(client, "hu24_pg_a@example.com")
    headers_b = _login_headers(client, "hu24_pg_b@example.com")

    review_a_null = client.post(
        "/api/v1/reviews",
        headers=headers_a,
        json={"contenido": "=SUM(A1) contenido A", "autor": "@autorA"},
    )
    review_a_full = client.post(
        "/api/v1/reviews",
        headers=headers_a,
        json={"contenido": "Reseña normal A", "autor": "Ana", "fecha": "2026-09-27T09:00:00", "puntuacion": 5},
    )
    review_b = client.post(
        "/api/v1/reviews",
        headers=headers_b,
        json={"contenido": "+CMD secreto B"},
    )
    assert review_a_null.status_code == review_a_full.status_code == review_b.status_code == 201
    id_a_null = review_a_null.json()["id"]
    id_b = review_b.json()["id"]

    # Aislamiento en lectura y edición cruzada.
    cross_get = client.get(f"/api/v1/reviews/{id_a_null}", headers=headers_b)
    cross_patch = client.patch(f"/api/v1/reviews/{id_a_null}", headers=headers_b, json={"contenido": "Intento B"})
    assert cross_get.status_code == cross_patch.status_code == 404
    assert "=SUM(A1)" not in cross_get.text and "=SUM(A1)" not in cross_patch.text

    list_a = client.get("/api/v1/reviews", headers=headers_a).json()["items"]
    list_b = client.get("/api/v1/reviews", headers=headers_b).json()["items"]
    assert {item["id"] for item in list_a} == {id_a_null, review_a_full.json()["id"]}
    assert [item["id"] for item in list_b] == [id_b]

    export_a = client.get("/api/v1/reviews/export", headers=headers_a)
    assert export_a.status_code == 200
    assert export_a.content.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in export_a.content
    rows_a = list(csv.reader(io.StringIO(export_a.content.decode("utf-8-sig"), newline="")))
    assert rows_a[0] == ["id", "contenido", "autor", "fecha", "fuente", "puntuacion", "categoria", "estado"]
    assert [int(r[0]) for r in rows_a[1:]] == [item["id"] for item in list_a]
    by_id_a = {int(r[0]): r for r in rows_a[1:]}
    assert by_id_a[id_a_null][1] == "'=SUM(A1) contenido A"
    assert by_id_a[id_a_null][2] == "'@autorA"
    assert by_id_a[id_a_null][3] == "" and by_id_a[id_a_null][5] == ""
    assert by_id_a[review_a_full.json()["id"]][5] == "5"
    assert "+CMD secreto B" not in export_a.text

    export_b = client.get("/api/v1/reviews/export", headers=headers_b)
    assert export_b.status_code == 200
    rows_b = list(csv.reader(io.StringIO(export_b.content.decode("utf-8-sig"), newline="")))
    assert [int(r[0]) for r in rows_b[1:]] == [id_b]
    assert rows_b[1][1] == "'+CMD secreto B"
    assert rows_b[1][2] == "" and rows_b[1][3] == "" and rows_b[1][5] == ""
    assert "=SUM(A1)" not in export_b.text

    with sessions() as db:
        assert db.get(Review, id_a_null).contenido == "=SUM(A1) contenido A"


def test_hu24_postgres_ordering_nulls_last_and_date_filters(pg_api):
    client, sessions = pg_api
    headers_a = _login_headers(client, "hu24_pg_a@example.com")

    with sessions() as db:
        reviews = [
            Review(tenant_id=10, contenido="Null menor id", fecha=None, fuente="manual", puntuacion=None, estado="nueva"),
            Review(tenant_id=10, contenido="Fecha 2026-09-25", fecha=datetime(2026, 9, 25, 10, 0), fuente="manual", puntuacion=4, estado="nueva"),
            Review(tenant_id=10, contenido="Empate menor id", fecha=datetime(2026, 9, 27, 12, 0), fuente="CSV", puntuacion=5, estado="en_revision"),
            Review(tenant_id=10, contenido="Null mayor id", fecha=None, fuente="manual", puntuacion=None, estado="nueva"),
            Review(tenant_id=10, contenido="Empate mayor id", fecha=datetime(2026, 9, 27, 12, 0), fuente="Google", puntuacion=3, estado="atendida"),
            Review(tenant_id=10, contenido="Fecha maxima", fecha=datetime(9999, 12, 31, 23, 59, 59), fuente="manual", puntuacion=5, estado="nueva"),
            Review(tenant_id=20, contenido="Tenant B null", fecha=None, fuente="manual", puntuacion=None, estado="nueva"),
            Review(tenant_id=20, contenido="Tenant B fecha", fecha=datetime(2026, 9, 28, 9, 0), fuente="manual", puntuacion=2, estado="nueva"),
        ]
        for review in reviews:
            db.add(review)
            db.flush()
        db.commit()
        r_null_low, r_25, r_tie_low, r_null_high, r_tie_high, r_max, r_b_null, r_b_dated = reviews
        assert r_null_low.id < r_null_high.id and r_tie_low.id < r_tie_high.id

    expected_unfiltered = [r_max.id, r_tie_high.id, r_tie_low.id, r_25.id, r_null_high.id, r_null_low.id]

    unfiltered = client.get("/api/v1/reviews", headers=headers_a)
    assert unfiltered.status_code == 200
    assert [item["id"] for item in unfiltered.json()["items"]] == expected_unfiltered

    with sessions() as db:
        repo = ReviewRepository(db)
        assert [r.id for r in repo.list_recent_by_tenant(10, limit=4)] == [r_max.id, r_tie_high.id, r_tie_low.id, r_25.id]
        assert [r.id for r in repo.list_recent_by_tenant(10, limit=10)] == expected_unfiltered
        assert [r.id for r in repo.list_recent_by_tenant(20, limit=5)] == [r_b_dated.id, r_b_null.id]

    from_27 = client.get("/api/v1/reviews", params={"fecha_desde": "2026-09-27"}, headers=headers_a)
    assert from_27.status_code == 200
    assert [item["id"] for item in from_27.json()["items"]] == [r_max.id, r_tie_high.id, r_tie_low.id]

    until_27 = client.get("/api/v1/reviews", params={"fecha_hasta": "2026-09-27"}, headers=headers_a)
    assert until_27.status_code == 200
    assert [item["id"] for item in until_27.json()["items"]] == [r_tie_high.id, r_tie_low.id, r_25.id]

    until_max = client.get("/api/v1/reviews", params={"fecha_hasta": "9999-12-31"}, headers=headers_a)
    assert until_max.status_code == 200
    assert [item["id"] for item in until_max.json()["items"]] == [r_max.id, r_tie_high.id, r_tie_low.id, r_25.id]

    export_max = client.get("/api/v1/reviews/export", params={"fecha_hasta": "9999-12-31"}, headers=headers_a)
    assert export_max.status_code == 200
    rows_max = list(csv.reader(io.StringIO(export_max.content.decode("utf-8-sig"), newline="")))
    assert [int(r[0]) for r in rows_max[1:]] == [r_max.id, r_tie_high.id, r_tie_low.id, r_25.id]
