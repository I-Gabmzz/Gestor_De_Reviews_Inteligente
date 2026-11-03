"""Compatibilidad real del motor; todas las entradas y proveedores son sintéticos."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import csv
from datetime import datetime
from io import BytesIO, StringIO
from threading import Barrier

from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.security import create_access_token, get_password_hash
from app.db.init_db import init_db
from app.main import app
from app.models import ExternalReviewConnection, ExternalReviewIdentity, Review, Tenant, User
from app.models.notification import ReviewNotification
from app.repositories.review_repository import ReviewRepository
from app.schemas.ai import PriorityResult
from app.schemas.auth import AuthenticatedUser
from app.schemas.serpapi import SerpApiPage, SerpApiResult, SerpApiReview
from app.schemas.suggested_response import SuggestedResponseResult
from app.services.external_review_persistence_service import ExternalReviewPersistenceService
from app.services.serpapi_normalizer import normalize_serpapi_result


@pytest.mark.parametrize("stage", ["new", "legacy", "partial"])
def test_concurrent_startup_preserves_existing_data_and_completes_migrations(postgres_engine, stage):
    database = postgres_engine
    if stage != "new":
        with database.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE tenants (id SERIAL PRIMARY KEY, nombre VARCHAR(255) NOT NULL, estado VARCHAR(50) NOT NULL)")
            connection.exec_driver_sql(
                "CREATE TABLE reviews (id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id), "
                "autor VARCHAR(255), contenido TEXT NOT NULL, fecha TIMESTAMP NOT NULL, fuente VARCHAR(100) NOT NULL, "
                "puntuacion INTEGER NOT NULL, estado VARCHAR(50) NOT NULL, categoria VARCHAR(50), prioridad VARCHAR(50))"
            )
            connection.exec_driver_sql("CREATE INDEX ix_legacy_tenant ON reviews(tenant_id)")
            connection.exec_driver_sql("INSERT INTO tenants VALUES (10, 'Negocio sintético', 'activo')")
            connection.exec_driver_sql("INSERT INTO reviews VALUES (101,10,'Cliente ficticio','Comentario conservado','2026-11-03','manual',4,'nueva','Consulta','Media')")
            if stage == "partial":
                connection.exec_driver_sql("ALTER TABLE reviews ADD COLUMN resumen TEXT")
                connection.exec_driver_sql("UPDATE reviews SET resumen='Resumen conservado'")
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda _: init_db(database), range(2)))
    init_db(database)
    assert set(inspect(database).get_table_names()) == {
        "tenants", "users", "reviews", "review_notifications",
        "external_review_connections", "external_review_identities",
    }
    if stage != "new":
        with Session(database) as db:
            row = db.get(Review, 101)
            assert (row.contenido, row.estado, row.prioridad) == ("Comentario conservado", "nueva", "Media")
            assert row.resumen == ("Resumen conservado" if stage == "partial" else None)
            assert row.tema is row.respuesta_sugerida is None
            assert row.respuesta_sugerida_version == 0
        assert "ix_legacy_tenant" in {index["name"] for index in inspect(database).get_indexes("reviews")}


@pytest.fixture()
def seeded(postgres_engine):
    init_db(postgres_engine)
    with Session(postgres_engine) as db:
        db.add_all([Tenant(id=10, nombre="Negocio A", estado="activo"), Tenant(id=20, nombre="Negocio B", estado="activo")])
        db.flush()
        hashed = get_password_hash("PruebaLocal!2026")
        for user, tenant in ((1, 10), (2, 20)):
            db.add(User(id=user, tenant_id=tenant, nombre="Cuenta sintética", correo=f"prueba{user}@example.com",
                        password_hash=hashed, rol="usuario_negocio", estado="activo"))
        db.add(Review(id=101, tenant_id=10, autor="Cliente ficticio", contenido="La entrega llegó tarde.",
                      fecha=datetime(2026, 11, 3), fuente="manual", puntuacion=3, estado="nueva"))
        db.commit()
    return postgres_engine


@pytest.fixture()
def api(seeded, monkeypatch):
    def database():
        with Session(seeded) as db:
            yield db
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = database
    monkeypatch.setattr("app.main.init_db", lambda: init_db(seeded))
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def headers(user=1, tenant=10):
    return {"Authorization": "Bearer " + create_access_token(subject=str(user), rol="usuario_negocio", tenant_id=tenant)}


def test_http_authentication_crud_and_tenant_isolation(api, seeded):
    login = api.post("/api/v1/auth/login", json={"correo": "prueba1@example.com", "password": "PruebaLocal!2026"})
    assert login.status_code == 200
    auth = {"Authorization": "Bearer " + login.json()["access_token"]}
    created = api.post("/api/v1/reviews", headers=auth, json={
        "autor": "Cliente nuevo", "contenido": "Excelente atención.", "fecha": "2026-11-03T10:00:00", "puntuacion": 5,
    })
    assert created.status_code == 201
    identifier = created.json()["id"]
    url = f"/api/v1/reviews/{identifier}"
    assert api.patch(url, headers=auth, json={"contenido": "Atención actualizada."}).status_code == 200
    assert api.patch(url + "/status", headers=auth, json={"estado": "en_revision"}).status_code == 200
    assert api.get(url, headers=headers(2, 20)).status_code == 404
    assert api.patch(url, headers=headers(2, 20), json={"contenido": "Ajeno"}).status_code == 404
    assert api.get("/api/v1/reviews", headers=headers(2, 20)).json()["total"] == 0
    seeded.dispose()
    saved = api.get(url, headers=auth).json()
    assert (saved["contenido"], saved["estado"], saved["tenant_id"]) == ("Atención actualizada.", "en_revision", 10)
    assert api.get("/api/v1/dashboard", headers=auth).status_code == 200


@pytest.mark.parametrize("format", ["csv", "xlsx"])
def test_file_import_and_csv_export_roundtrip(api, format):
    columns = ["autor", "contenido", "fecha", "fuente", "puntuacion"]
    values = ["Cliente ficticio", "Servicio importado", "2026-11-03", "Google", 4]
    if format == "csv":
        stream = StringIO()
        writer = csv.writer(stream)
        writer.writerows([columns, values])
        content = stream.getvalue().encode()
        mime = "text/csv"
    else:
        workbook = Workbook()
        workbook.active.append(columns)
        workbook.active.append(values)
        stream = BytesIO()
        workbook.save(stream)
        workbook.close()
        content = stream.getvalue()
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    imported = api.post("/api/v1/imports/upload", headers=headers(), files={"file": (f"reviews.{format}", content, mime)})
    assert imported.status_code == 200
    exported = api.get("/api/v1/reviews/export", headers=headers())
    assert exported.status_code == 200
    rows = list(csv.DictReader(StringIO(exported.content.decode("utf-8-sig"))))
    assert len(rows) == 2
    assert any(row["contenido"] == "Servicio importado" and row["fuente"] == "Google" for row in rows)
    assert api.get("/api/v1/reviews", headers=headers(2, 20)).json()["total"] == 0


def test_ai_results_notifications_and_content_invalidation(api, seeded, monkeypatch):
    class SyntheticProvider:
        def generate_structured(self, content, *, instructions, response_model):
            fields = {"categoria": "Queja", "resumen": "Demora en entrega", "tema": "Servicio",
                      "prioridad": "Alta", "respuesta_sugerida": "Lamentamos la demora descrita."}
            return response_model.model_validate({name: fields[name] for name in response_model.model_fields})
    for module in ("classification", "summary", "topic", "priority", "suggested_response"):
        monkeypatch.setattr(f"app.services.{module}_service.create_ai_provider", lambda: nullcontext(SyntheticProvider()))
    url = "/api/v1/reviews/101"
    for operation in ("clasificacion", "resumen", "tema", "prioridad", "respuesta-sugerida"):
        response = api.post(url + "/" + operation, headers=headers())
        assert response.status_code == 200, (operation, response.json())
        assert response.json()["estado"] == "nueva"
    assert api.post(url + "/prioridad", headers=headers()).status_code == 200
    seeded.dispose()
    saved = api.get(url, headers=headers()).json()
    assert (saved["categoria"], saved["resumen"], saved["tema"], saved["prioridad"], saved["respuesta_sugerida"]) == (
        "Queja", "Demora en entrega", "Servicio", "Alta", "Lamentamos la demora descrita.",
    )
    assert api.get("/api/v1/notificaciones", headers=headers()).json()["total"] == 1
    assert api.get("/api/v1/notificaciones", headers=headers(2, 20)).json()["total"] == 0
    assert api.post(url + "/respuesta-sugerida", headers=headers(2, 20)).status_code == 404
    assert api.patch(url, headers=headers(), json={"contenido": "Comentario corregido"}).status_code == 200
    assert api.get(url, headers=headers()).json()["respuesta_sugerida"] is None


@pytest.mark.parametrize("operation", ["notification", "suggestion"])
def test_concurrent_writes_preserve_idempotency_and_versions(seeded, operation):
    barrier = Barrier(2)
    def save(_):
        with Session(seeded) as db:
            repository = ReviewRepository(db)
            barrier.wait(timeout=10)
            if operation == "notification":
                return repository.save_ai_result(101, 10, PriorityResult(prioridad="Alta")) is not None
            return repository.save_suggested_response(101, 10, SuggestedResponseResult(respuesta_sugerida="Gracias por compartir su experiencia."),
                expected_content="La entrega llegó tarde.", expected_version=0) is not None
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save, range(2)))
    with Session(seeded) as db:
        if operation == "notification":
            assert results == [True, True]
            assert db.scalar(select(func.count()).select_from(ReviewNotification)) == 1
        else:
            assert sorted(results) == [False, True]
            assert db.get(Review, 101).respuesta_sugerida_version == 1
        assert db.get(Review, 101).estado == "nueva"


def test_external_import_is_idempotent_with_postgresql_locks_and_constraints(seeded):
    business = "0x123:0x456"
    with Session(seeded) as db:
        db.add(ExternalReviewConnection(tenant_id=10, source="Google", business_data_id=business,
                                       persistence_enabled=True, approval_reference="Prueba sintética aislada"))
        db.commit()
    native = SerpApiResult(pages=(SerpApiPage(1, 200, "Success", (SerpApiReview({
        "review_id": "synthetic-review", "source": "Google", "snippet": "Comentario sintético",
        "iso_date": "2026-11-03T10:00:00Z", "rating": 4,
    }),)),), place_info=None, first_page_metadata=None, request_count=1, record_count=1,
        stop_reason="no_next_token", incomplete=False, limited=False)
    normalized = normalize_serpapi_result(native, business_data_id=business)
    actor = AuthenticatedUser(id=1, tenant_id=10, rol="usuario_negocio", correo="prueba1@example.com")
    results = []
    for _ in range(2):
        with Session(seeded, autoflush=False) as db:
            results.append(ExternalReviewPersistenceService(ReviewRepository(db)).persist(normalized, current_user=actor, business_data_id=business))
    assert (results[0].inserted, results[1].repeated) == (1, 1)
    with Session(seeded) as db:
        assert db.scalar(select(func.count()).select_from(ExternalReviewIdentity)) == 1
        assert db.scalar(select(func.count()).select_from(Review)) == 2
