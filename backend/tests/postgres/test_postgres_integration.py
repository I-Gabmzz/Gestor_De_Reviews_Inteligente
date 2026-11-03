"""Compatibilidad real del motor; todas las entradas y proveedores son sintéticos."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import csv
from datetime import datetime
from io import BytesIO, StringIO
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_db
from app.api.routers.external_reviews import get_external_import_service, get_external_import_sessions
from app.core.external_import_config import ExternalImportSettings
from app.core.security import create_access_token, get_password_hash
from app.core.serpapi_config import SerpApiSettings
from app.db.external_import_schema import ExternalImportSchemaError, verify_external_import_schema
from app.db.init_db import init_db
from app.main import app
from app.models import ExternalReviewConnection, ExternalReviewIdentity, ExternalReviewImportAttempt, Review, Tenant, User
from app.models.notification import ReviewNotification
from app.repositories.review_repository import ReviewRepository
from app.schemas.ai import PriorityResult
from app.schemas.auth import AuthenticatedUser
from app.schemas.serpapi import SerpApiPage, SerpApiResult, SerpApiReview
from app.schemas.suggested_response import SuggestedResponseResult
from app.services.external_review_persistence_service import ExternalReviewPersistenceService
from app.services.external_review_import_service import ExternalReviewImportError, ExternalReviewImportService
from app.services.serpapi_client import SerpApiClient
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
                connection.exec_driver_sql("ALTER TABLE reviews ADD COLUMN solucion TEXT")
                connection.exec_driver_sql("ALTER TABLE reviews ADD COLUMN respuesta_sugerida TEXT")
                connection.exec_driver_sql("ALTER TABLE reviews ADD COLUMN respuesta_sugerida_version INTEGER NOT NULL DEFAULT 0")
                connection.exec_driver_sql("UPDATE reviews SET resumen='Resumen conservado'")
                connection.exec_driver_sql("UPDATE reviews SET solucion='Solución conservada', respuesta_sugerida='Respuesta conservada', respuesta_sugerida_version=3")
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda _: init_db(database), range(2)))
    init_db(database)
    assert set(inspect(database).get_table_names()) == {
        "tenants", "users", "reviews", "review_notifications",
        "external_review_connections", "external_review_identities",
        "external_review_import_attempts",
    }
    with database.connect() as connection:
        verify_external_import_schema(connection)
    if stage != "new":
        with Session(database) as db:
            row = db.get(Review, 101)
            assert (row.contenido, row.estado, row.prioridad) == ("Comentario conservado", "nueva", "Media")
            assert row.resumen == ("Resumen conservado" if stage == "partial" else None)
            assert row.tema is None
            assert row.solucion == ("Solución conservada" if stage == "partial" else None)
            assert row.respuesta_sugerida == ("Respuesta conservada" if stage == "partial" else None)
            assert row.respuesta_sugerida_version == (3 if stage == "partial" else 0)
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
    def persisted_version():
        with Session(seeded) as db:
            return db.get(Review, 101).respuesta_sugerida_version

    class SyntheticProvider:
        def generate_structured(self, content, *, instructions, response_model):
            fields = {"categoria": "Queja", "resumen": "Demora en entrega", "tema": "Servicio",
                      "prioridad": "Alta", "solucion": "Revisar el proceso de entrega.",
                      "respuesta_sugerida": "Lamentamos la demora descrita."}
            return response_model.model_validate({name: fields[name] for name in response_model.model_fields})
    for module in ("classification", "summary", "topic", "priority", "solution", "suggested_response"):
        monkeypatch.setattr(f"app.services.{module}_service.create_ai_provider", lambda: nullcontext(SyntheticProvider()))
    url = "/api/v1/reviews/101"
    for operation in ("clasificacion", "resumen", "tema", "prioridad", "solucion", "respuesta-sugerida"):
        response = api.post(url + "/" + operation, headers=headers())
        assert response.status_code == 200, (operation, response.json())
        assert response.json()["estado"] == "nueva"
    assert api.post(url + "/prioridad", headers=headers()).status_code == 200
    seeded.dispose()
    saved = api.get(url, headers=headers()).json()
    assert (saved["categoria"], saved["resumen"], saved["tema"], saved["prioridad"], saved["solucion"], saved["respuesta_sugerida"]) == (
        "Queja", "Demora en entrega", "Servicio", "Alta", "Revisar el proceso de entrega.", "Lamentamos la demora descrita.",
    )
    assert "respuesta_sugerida_version" not in saved
    assert persisted_version() == 1
    assert api.get("/api/v1/notificaciones", headers=headers()).json()["total"] == 1
    assert api.get("/api/v1/notificaciones", headers=headers(2, 20)).json()["total"] == 0
    assert api.post(url + "/respuesta-sugerida", headers=headers(2, 20)).status_code == 404
    assert api.post(url + "/solucion", headers=headers(2, 20)).status_code == 404
    assert api.patch(url, headers=headers(), json={"contenido": saved["contenido"]}).status_code == 200
    unchanged = api.get(url, headers=headers()).json()
    assert (unchanged["solucion"], unchanged["respuesta_sugerida"]) == (
        saved["solucion"], saved["respuesta_sugerida"],
    )
    assert "respuesta_sugerida_version" not in unchanged
    assert persisted_version() == 1
    assert api.patch(url, headers=headers(), json={"contenido": "Comentario corregido"}).status_code == 200
    changed = api.get(url, headers=headers()).json()
    assert changed["solucion"] is changed["respuesta_sugerida"] is None
    assert "respuesta_sugerida_version" not in changed
    assert persisted_version() == 2


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


IMPORT_PATH = "/api/v1/integrations/google/reviews/import"
IMPORT_BUSINESS = "0xabc:0x123"


@pytest.fixture()
def external_control(seeded):
    """Real admission/persistence against the isolated schema; HTTP is simulated."""
    sessions = sessionmaker(bind=seeded, autoflush=False, expire_on_commit=False)
    with sessions() as db:
        db.add_all([
            ExternalReviewConnection(tenant_id=tenant, source="Google", business_data_id=business,
                                     persistence_enabled=True, approval_reference="Autorización sintética")
            for tenant, business in ((10, IMPORT_BUSINESS), (20, IMPORT_BUSINESS), (20, "0xabc:0x999"))
        ])
        db.commit()
    control = SimpleNamespace(sessions=sessions, factory_calls=0, requests=0, checked_out=0)

    def checkout(*_):
        control.checked_out += 1

    def checkin(*_):
        control.checked_out -= 1

    event.listen(seeded, "checkout", checkout)
    event.listen(seeded, "checkin", checkin)

    def factory():
        assert control.checked_out == 0
        control.factory_calls += 1

        def transport(_):
            assert control.checked_out == 0
            control.requests += 1
            return httpx.Response(200, json={
                "search_metadata": {"status": "Success", "google_maps_reviews_url":
                                    f"https://www.google.com/maps/place/data=!4m2!1s{IMPORT_BUSINESS}!1b1"},
                "search_parameters": {"engine": "google_maps_reviews", "data_id": IMPORT_BUSINESS},
                "place_info": {"data_id": IMPORT_BUSINESS},
                "reviews": [{"review_id": "synthetic-api-review", "source": "Google",
                             "snippet": "Comentario importado sintético", "rating": 4,
                             "iso_date": "2026-11-03T10:00:00Z"}],
            })

        return SerpApiClient(
            SerpApiSettings(_env_file=None, serpapi_api_key="synthetic-not-a-key"),
            transport=httpx.MockTransport(transport),
        )

    def service(**policy):
        return ExternalReviewImportService(sessions, ExternalImportSettings(**{
            "enabled": True, "tenant_request_budget": 10, "account_request_budget": 20, **policy,
        }), client_factory=factory)

    control.service = service
    control.actor = lambda tenant: AuthenticatedUser(
        id=1 if tenant == 10 else 2, tenant_id=tenant, rol="usuario_negocio",
        correo=f"prueba{1 if tenant == 10 else 2}@example.com",
    )
    try:
        yield control
    finally:
        event.remove(seeded, "checkout", checkout)
        event.remove(seeded, "checkin", checkin)
        assert control.checked_out == 0


@pytest.fixture()
def import_api(api, external_control):
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_external_import_sessions] = lambda: external_control.sessions
    app.dependency_overrides[get_external_import_service] = lambda: external_control.service()
    try:
        yield api
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_external_api_roundtrip_retains_ai_contracts_and_scopes_connections(import_api, external_control):
    catalog = import_api.get(IMPORT_PATH.replace("/import", "/connections"), headers=headers())
    assert catalog.status_code == 200
    assert catalog.json()["connections"] == [{"business_data_id": IMPORT_BUSINESS, "status": "available"}]
    assert catalog.json()["import_enabled"] is False  # The global production gate remains disabled.
    for expected in ((1, 0), (0, 1)):
        response = import_api.post(IMPORT_PATH, headers=headers(), json={"business_data_id": IMPORT_BUSINESS})
        assert response.status_code == 200, response.json()
        result = response.json()
        assert (result["inserted"], result["repeated"]) == expected
        assert (result["outcome"], result["control_status"]) == ("committed", "released")
    assert external_control.requests == external_control.factory_calls == 2
    with external_control.sessions() as db:
        imported = db.scalar(select(Review).where(Review.fuente == "Google"))
        assert imported.tenant_id == 10
        assert imported.solucion is imported.respuesta_sugerida is None
        assert imported.respuesta_sugerida_version == 0
        attempts = db.scalars(select(ExternalReviewImportAttempt)).all()
        assert len(attempts) == 2 and all(row.active is None and row.state == "finished" for row in attempts)
    denied = import_api.post(IMPORT_PATH, headers=headers(), json={"business_data_id": "0xabc:0x999"})
    assert denied.status_code == 404
    assert external_control.factory_calls == 2


@pytest.mark.parametrize("state", ["running", "unknown"])
def test_admission_excludes_pending_connection_but_not_another_tenant(import_api, external_control, state):
    service = external_control.service()
    operation = str(uuid4())
    service._reserve(external_control.actor(10), IMPORT_BUSINESS, operation)
    if state == "unknown":
        service._finish(operation, uncertain=True)
    response = import_api.post(IMPORT_PATH, headers=headers(), json={"business_data_id": IMPORT_BUSINESS})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "import_in_progress"
    assert external_control.requests == external_control.factory_calls == 0
    other = import_api.post(IMPORT_PATH, headers=headers(2, 20), json={"business_data_id": IMPORT_BUSINESS})
    assert other.status_code == 200, other.json()
    with external_control.sessions() as db:
        original = db.get(ExternalReviewImportAttempt, operation)
        assert original.active is True and original.state == state
        assert db.scalar(select(func.count()).select_from(ExternalReviewIdentity).where(
            ExternalReviewIdentity.tenant_id == 10,
        )) == 0


def test_finished_attempts_keep_cumulative_budget(import_api, external_control):
    service = external_control.service(tenant_request_budget=2)
    app.dependency_overrides[get_external_import_service] = lambda: service
    for _ in range(2):
        assert import_api.post(IMPORT_PATH, headers=headers(), json={"business_data_id": IMPORT_BUSINESS}).status_code == 200
    response = import_api.post(IMPORT_PATH, headers=headers(), json={"business_data_id": IMPORT_BUSINESS})
    assert response.status_code == 429 and response.json()["detail"]["code"] == "budget_exhausted"
    assert external_control.requests == external_control.factory_calls == 2
    with external_control.sessions() as db:
        assert db.scalar(select(func.sum(ExternalReviewImportAttempt.reserved_requests))) == 2


def test_concurrent_admission_reserves_once_and_retains_unknown(external_control):
    service = external_control.service()
    barrier = Barrier(2)

    def reserve(_):
        operation = str(uuid4())
        barrier.wait(timeout=10)
        try:
            service._reserve(external_control.actor(10), IMPORT_BUSINESS, operation)
            return operation
        except ExternalReviewImportError as error:
            assert error.detail.code == "import_in_progress"
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, range(2)))
    accepted = [result for result in results if result is not None]
    assert len(accepted) == 1
    service._finish(accepted[0], uncertain=True)
    with pytest.raises(ExternalReviewImportError) as rejected:
        service._reserve(external_control.actor(10), IMPORT_BUSINESS, str(uuid4()))
    assert rejected.value.detail.code == "import_in_progress"
    with external_control.sessions() as db:
        assert db.scalar(select(func.count()).select_from(ExternalReviewImportAttempt)) == 1
        assert db.scalar(select(ExternalReviewImportAttempt.state)) == "unknown"
    assert external_control.factory_calls == 0


@pytest.mark.parametrize("active,state,budget,tenant", [
    ("false", "running", 1, 10), ("2", "unknown", 1, 10), ("-1", "running", 1, 10),
    ("'invalid'", "unknown", 1, 10), ("NULL", "running", 1, 10),
    ("true", "finished", 1, 10), ("true", "invalid", 1, 10),
    ("true", "running", 0, 10), ("true", "running", 6, 10),
    ("true", "running", 1, 999),
])
def test_admission_raw_constraints_reject_invalid_rows(external_control, active, state, budget, tenant):
    with external_control.sessions.begin() as db:
        with pytest.raises(DBAPIError), db.begin_nested():
            # Only fixed literals above are interpolated; all row data are bound.
            db.execute(text(
                "INSERT INTO external_review_import_attempts "
                "(operation_id,tenant_id,source,business_data_id,started_at,reserved_requests,active,state) "
                f"VALUES (:operation,:tenant,'Google',:business,CURRENT_TIMESTAMP,:budget,{active},:state)"
            ), {"operation": str(uuid4()), "tenant": tenant, "business": IMPORT_BUSINESS,
                "budget": budget, "state": state})
        assert db.scalar(select(func.count()).select_from(ExternalReviewImportAttempt)) == 0


def test_admission_unique_active_and_multiple_finished_rows(external_control):
    service = external_control.service()
    service._reserve(external_control.actor(10), IMPORT_BUSINESS, str(uuid4()))
    with external_control.sessions.begin() as db:
        with pytest.raises(DBAPIError), db.begin_nested():
            db.add(ExternalReviewImportAttempt(
                operation_id=str(uuid4()), tenant_id=10, source="Google", business_data_id=IMPORT_BUSINESS,
                started_at=datetime.now(), reserved_requests=1, active=True, state="unknown",
            ))
            db.flush()
        for _ in range(2):
            db.add(ExternalReviewImportAttempt(
                operation_id=str(uuid4()), tenant_id=10, source="Google", business_data_id=IMPORT_BUSINESS,
                started_at=datetime.now(), reserved_requests=1, active=None, state="finished",
            ))
    with external_control.sessions() as db:
        assert db.scalar(select(func.count()).select_from(ExternalReviewImportAttempt)) == 3


def test_incompatible_admission_schema_is_rejected_without_acquisition(import_api, external_control, seeded):
    service = external_control.service()
    operation = str(uuid4())
    service._reserve(external_control.actor(10), IMPORT_BUSINESS, operation)
    service._finish(operation, uncertain=True)
    with seeded.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE external_review_import_attempts ADD COLUMN "true" INTEGER')
    with pytest.raises(ExternalImportSchemaError):
        init_db(seeded)
    response = import_api.post(IMPORT_PATH, headers=headers(), json={"business_data_id": IMPORT_BUSINESS})
    assert response.status_code == 503 and response.json()["detail"]["code"] == "admission_schema_invalid"
    assert external_control.factory_calls == external_control.requests == 0
    with external_control.sessions() as db:
        row = db.get(ExternalReviewImportAttempt, operation)
        assert row.active is True and row.state == "unknown"
        assert db.scalar(select(func.count()).select_from(ExternalReviewImportAttempt)) == 1
        assert db.scalar(select(func.count()).select_from(Review)) == 1
