"""A-21B: production router/services, synthetic databases and MockTransport only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Event
from types import SimpleNamespace
import os

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, inspect, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateTable

from app.api.dependencies import get_db
from app.api.routers import api_router
from app.api.routers.external_reviews import get_external_import_service, get_external_import_sessions
from app.core.external_import_config import ExternalImportSettings
from app.core.security import create_access_token
from app.core.serpapi_config import SerpApiSettings
from app.db.init_db import init_db
from app.models import ExternalReviewConnection, ExternalReviewIdentity, ExternalReviewImportAttempt, Review, Tenant, User
from app.schemas.auth import AuthenticatedUser
from app.services.external_review_import_service import ExternalReviewImportError, ExternalReviewImportService
from app.services.serpapi_client import SerpApiClient


PATH = "/api/v1/integrations/google/reviews/import"
BUSINESS = "0xabc:0x123"
FOREIGN = "0xabc:0x456"
PRIVATE = "synthetic-private-import-marker"


def record(identity="synthetic-review", **changes):
    return {"review_id": identity, "source": "Google", "user": {"name": PRIVATE},
            "snippet": PRIVATE, "iso_date": "2026-11-02T12:00:00Z", "rating": 4, **changes}


def page(*rows, token=None, place=BUSINESS):
    body = {"search_metadata": {"status": "Success"}, "reviews": list(rows)}
    if place is not None:
        body["place_info"] = {"data_id": place, "title": PRIVATE}
    if token is not None:
        body["serpapi_pagination"] = {"next_page_token": token}
    return httpx.Response(200, json=body)


def actor(identifier=1):
    return AuthenticatedUser(id=identifier, correo=f"synthetic-{identifier}@example.com",
                             rol="usuario_negocio", tenant_id=10 if identifier == 1 else 20)


def headers(identifier=1, **claims):
    token = create_access_token(**{
        "subject": str(identifier), "rol": "usuario_negocio", "tenant_id": 10, **claims,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def synthetic_only(monkeypatch):
    for key in tuple(os.environ):
        if key.startswith(("SERPAPI_", "EXTERNAL_IMPORT_")):
            monkeypatch.delenv(key)
    monkeypatch.setitem(SerpApiSettings.model_config, "env_file", None)

    def forbidden(*args, **kwargs):
        raise AssertionError("Real HTTP forbidden in A-21B tests")

    async def async_forbidden(*args, **kwargs):
        forbidden()

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", async_forbidden)


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'synthetic-import-api.db'}", hide_parameters=True,
                           connect_args={"check_same_thread": False, "timeout": 5})
    checked_out = set()

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "checkout")
    def checkout(connection, *_):
        checked_out.add(id(connection))

    @event.listens_for(engine, "checkin")
    def checkin(connection, *_):
        checked_out.discard(id(connection))

    sessions = sessionmaker(bind=engine, autoflush=False)
    init_db(engine)
    with sessions() as db:
        db.add_all(Tenant(id=i, nombre="synthetic-tenant", estado="activo") for i in (10, 20))
        db.flush()
        for identifier, tenant, role in ((1, 10, "usuario_negocio"), (2, 20, "usuario_negocio"),
                                          (3, None, "admin_general"), (4, 10, "admin_tenant")):
            db.add(User(id=identifier, tenant_id=tenant, nombre="synthetic-user",
                        correo=f"synthetic-{identifier}@example.com", rol=role,
                        estado="activo", password_hash="synthetic-unused-hash"))
        for tenant, business in ((10, BUSINESS), (20, BUSINESS), (20, FOREIGN)):
            db.add(ExternalReviewConnection(tenant_id=tenant, source="Google", business_data_id=business,
                                           persistence_enabled=True, approval_reference="synthetic-test-only"))
        db.commit()

    state = SimpleNamespace(engine=engine, sessions=sessions, calls=[], factory_calls=0,
                            checked_out=checked_out, handler=lambda _: page(record()), closed=0)

    class Transport(httpx.MockTransport):
        def close(self):
            state.closed += 1
            super().close()

    def factory():
        state.factory_calls += 1
        assert not checked_out, "Authentication/admission connections leaked into HTTP"

        def handle(request):
            assert not checked_out, "A transaction/connection was retained during HTTP"
            state.calls.append((request.url.params["data_id"], request.url.params.get("next_page_token"),
                                int(request.url.params["num"])))
            return state.handler(request)

        config = SerpApiSettings(_env_file=None, serpapi_api_key="synthetic-not-a-key",
                                serpapi_page_size=20, serpapi_max_pages=5)
        return SerpApiClient(config, transport=Transport(handle))

    def service(**policy):
        settings = ExternalImportSettings(**{
            "enabled": True, "tenant_request_budget": 50, "account_request_budget": 100, **policy,
        })
        return ExternalReviewImportService(sessions, settings, client_factory=factory)

    state.service = service
    yield state
    assert not checked_out
    engine.dispose()


@pytest.fixture()
def api(env):
    app = FastAPI()  # No production lifespan/database; production router registration.
    app.include_router(api_router)
    env.current_service = env.service()
    app.dependency_overrides[get_external_import_sessions] = lambda: env.sessions
    app.dependency_overrides[get_external_import_service] = lambda: env.current_service

    def read_session():
        with env.sessions() as db:
            yield db

    app.dependency_overrides[get_db] = read_session
    with TestClient(app) as client:
        yield client


def post(api, identifier=1, **body):
    return api.post(PATH, json={"business_data_id": BUSINESS, **body}, headers=headers(identifier))


def counts(env):
    with env.sessions() as db:
        return tuple(db.scalar(select(func.count()).select_from(model)) for model in (Review, ExternalReviewIdentity))


def assert_no_acquisition(env):
    assert env.calls == [] and env.factory_calls == 0
    assert counts(env) == (0, 0)


def test_default_gate_and_production_dependency_cannot_acquire(env, api):
    assert ExternalImportSettings().enabled is False
    api.app.dependency_overrides.pop(get_external_import_service)
    response = post(api)
    assert response.status_code == 403 and response.json()["detail"]["code"] == "import_disabled"
    assert_no_acquisition(env)


@pytest.mark.parametrize("case,expected", [("missing", 401), ("invalid", 401), ("unknown", 401),
                                            ("general", 403), ("inactive-user", 403), ("inactive-tenant", 403)])
def test_authentication_and_current_database_roles_precede_http(env, api, case, expected):
    auth = headers()
    if case == "missing":
        auth = {}
    elif case == "invalid":
        auth = {"Authorization": "Bearer synthetic-invalid"}
    elif case in ("unknown", "general"):
        auth = headers(999 if case == "unknown" else 3)
    else:
        with env.sessions() as db:
            db.get(User if case == "inactive-user" else Tenant, 1 if case == "inactive-user" else 10).estado = "inactivo"
            db.commit()
    response = api.post(PATH, json={"business_data_id": BUSINESS}, headers=auth)
    assert response.status_code == expected
    assert_no_acquisition(env)


@pytest.mark.parametrize("body", [
    {"tenant_id": 20}, {"persistence_enabled": True}, {"approval_reference": PRIVATE},
    {"max_pages": 5}, {"source": "Other"}, {"allow_incomplete": True},
    {"business_data_id": "arbitrary"}, {"business_data_id": "0x" + "a" * 130 + ":0x1"},
    {"business_data_id": 123},
])
def test_request_forbids_scope_approval_and_limit_overrides(env, api, body):
    assert post(api, **body).status_code == 422
    assert_no_acquisition(env)


@pytest.mark.parametrize("business", [FOREIGN, "0x99:0x88"])
def test_missing_and_foreign_connections_are_indistinguishable(env, api, business):
    response = post(api, business_data_id=business)
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "connection_unavailable"
    assert_no_acquisition(env)


@pytest.mark.parametrize("approval", [None, "synthetic-test-only"])
def test_disabled_connection_never_constructs_client(env, api, approval):
    with env.sessions() as db:
        connection = db.get(ExternalReviewConnection, (10, "Google", BUSINESS))
        connection.persistence_enabled = False
        connection.approval_reference = approval
        db.commit()
    assert post(api).status_code == 403
    assert_no_acquisition(env)


def test_missing_approval_in_incompatible_legacy_data_is_also_blocked(env, api):
    # Deliberately corrupt ONLY the ephemeral fixture to exercise defense in depth.
    with env.engine.begin() as db:
        db.exec_driver_sql("PRAGMA ignore_check_constraints=ON")
        db.exec_driver_sql("UPDATE external_review_connections SET approval_reference=NULL WHERE tenant_id=10")
        db.exec_driver_sql("PRAGMA ignore_check_constraints=OFF")
    assert post(api).status_code == 403
    assert_no_acquisition(env)


@pytest.mark.parametrize("identifier", [1, 4])
def test_operational_roles_can_import_and_read_their_review(env, api, identifier):
    response = post(api, identifier)
    assert response.status_code == 200
    result = response.json()
    assert result["inserted"] == result["input_count"] == result["request_count"] == 1
    assert result["outcome"] == "committed" and result["control_status"] == "released"
    assert PRIVATE not in response.text
    listed = api.get("/api/v1/reviews", headers=headers(identifier)).json()
    assert listed["total"] == 1 and listed["items"][0]["fuente"] == "Google"
    assert counts(env) == (1, 1) and env.closed == 1


@pytest.mark.parametrize("place", [FOREIGN, None, ""])
def test_unverified_or_contradictory_place_never_persists(env, api, place):
    env.handler = lambda _: page(record(), place=place)
    response = post(api)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "place_unverified"
    assert counts(env) == (0, 0) and len(env.calls) == 1 and env.closed == 1


@pytest.mark.parametrize("kind,expected_attempts", [("max_pages", 1), ("empty_with_token", 1), ("repeated_token", 2)])
def test_incomplete_acquisitions_keep_reason_and_zero_writes(env, api, kind, expected_attempts):
    env.current_service = env.service(max_pages=2 if kind == "repeated_token" else 1)
    env.handler = lambda _: page(*([] if kind == "empty_with_token" else [record()]), token="synthetic-next")
    response = post(api)
    detail = response.json()["detail"]
    assert response.status_code == 409 and detail["code"] == "incomplete_acquisition"
    assert detail["stop_reason"] == kind and detail["incomplete"] is True
    assert detail["request_count"] == expected_attempts and counts(env) == (0, 0)


def test_server_pagination_and_counts_are_composed_without_raw_dtos(env, api):
    env.current_service = env.service(max_pages=2, page_size=5)
    env.handler = lambda _: (
        page(record(), token="synthetic-next") if len(env.calls) == 1 else
        page(record(), record("no-text", snippet=None), record("bad", rating=False))
    )
    response = post(api)
    result = response.json()
    assert response.status_code == 200
    assert (result["input_count"], result["inserted"], result["repeated"], result["omitted"], result["rejected"]) == (4, 1, 1, 1, 1)
    assert result["batch_duplicates"] == 1 and result["request_count"] == 2
    assert env.calls == [(BUSINESS, None, 5), (BUSINESS, "synthetic-next", 5)]
    assert PRIVATE not in response.text


@pytest.mark.parametrize("status,expected", [(401, 503), (403, 503), (429, 503), (503, 503), (302, 502)])
def test_provider_failures_are_sanitized_without_retry(env, api, status, expected):
    env.handler = lambda _: httpx.Response(status, text=PRIVATE)
    response = post(api)
    assert response.status_code == expected and PRIVATE not in response.text
    assert response.json()["detail"]["request_count"] == 1
    assert len(env.calls) == 1 and counts(env) == (0, 0)


@pytest.mark.parametrize("after_page", [False, True])
def test_timeout_preserves_partial_diagnostics_without_writes(env, api, after_page):
    env.current_service = env.service(max_pages=2)

    def handler(_):
        if after_page and len(env.calls) == 1:
            return page(record(), token="synthetic-next")
        raise httpx.ReadTimeout(PRIVATE)

    env.handler = handler
    response = post(api)
    detail = response.json()["detail"]
    assert response.status_code == 504 and detail["code"] == "provider_timeout"
    assert detail["request_count"] == (2 if after_page else 1)
    assert detail["obtained"] == (1 if after_page else 0)
    assert PRIVATE not in response.text and counts(env) == (0, 0)


@pytest.mark.parametrize("body", [{"error": PRIVATE}, {"search_metadata": {"status": "Processing"}}, []])
def test_provider_error_pending_and_invalid_json_are_not_success(env, api, body):
    env.handler = lambda _: httpx.Response(200, json=body)
    response = post(api)
    assert response.status_code == 502 and PRIVATE not in response.text
    assert len(env.calls) == 1 and counts(env) == (0, 0)


def test_reimport_is_idempotent_and_changed_content_preserves_manual_edits(env, api):
    assert post(api).json()["inserted"] == 1
    assert post(api).json()["repeated"] == 1
    with env.sessions() as db:
        review = db.scalar(select(Review))
        review.contenido, review.estado, review.resumen = "synthetic-manual-edit", "atendida", "synthetic-summary"
        db.commit()
    env.handler = lambda _: page(record(snippet="synthetic-external-change"))
    result = post(api).json()
    assert result["changed"] == 1 and result["inserted"] == 0 and counts(env) == (1, 1)
    with env.sessions() as db:
        review = db.scalar(select(Review))
        assert (review.contenido, review.estado, review.resumen) == ("synthetic-manual-edit", "atendida", "synthetic-summary")


def test_database_context_overrides_token_claims_and_tenants_remain_isolated(env, api):
    response = api.post(PATH, json={"business_data_id": BUSINESS}, headers=headers(1, tenant_id=20, rol="admin_general"))
    assert response.status_code == 200
    assert api.get("/api/v1/reviews", headers=headers(2)).json()["total"] == 0
    assert post(api, 2).json()["inserted"] == 1 and counts(env) == (2, 2)
    with env.sessions() as db:
        assert set(db.scalars(select(Review.tenant_id))) == {10, 20}


@pytest.mark.parametrize("kind", ["user", "tenant", "role", "connection", "approval"])
def test_revocation_during_acquisition_is_revalidated_before_persistence(env, api, kind):
    def handler(_):
        with env.sessions() as db:
            if kind == "user":
                db.get(User, 1).estado = "inactivo"
            elif kind == "tenant":
                db.get(Tenant, 10).estado = "inactivo"
            elif kind == "role":
                db.get(User, 1).rol = "admin_tenant"
            else:
                connection = db.get(ExternalReviewConnection, (10, "Google", BUSINESS))
                connection.persistence_enabled = False
                if kind == "approval":
                    connection.approval_reference = None
            db.commit()
        return page(record())

    env.handler = handler
    assert post(api).status_code == 403 and counts(env) == (0, 0)
    assert len(env.calls) == 1


def test_rollback_uses_existing_service_and_releases_admission(env, api, monkeypatch):
    from app.repositories.review_repository import ReviewRepository
    original = ReviewRepository.add_external_review
    calls = []

    def fail_second(self, *args, **kwargs):
        original(self, *args, **kwargs)
        calls.append(1)
        if len(calls) == 2:
            raise SQLAlchemyError(PRIVATE)

    monkeypatch.setattr(ReviewRepository, "add_external_review", fail_second)
    env.handler = lambda _: page(record("first"), record("second"))
    response = post(api)
    assert response.status_code == 503 and response.json()["detail"]["outcome"] == "rolled_back"
    assert PRIVATE not in response.text and counts(env) == (0, 0)
    monkeypatch.setattr(ReviewRepository, "add_external_review", original)
    assert post(api).json()["inserted"] == 2


@pytest.mark.parametrize("after_commit", [False, True])
def test_uncertain_review_commit_keeps_connection_blocked_for_reconciliation(env, api, monkeypatch, after_commit):
    original = Session.commit
    commits = []

    def uncertain(self):
        commits.append(1)
        if len(commits) == 2:  # admission first, review transaction second
            if after_commit:
                original(self)
            raise SQLAlchemyError(PRIVATE)
        return original(self)

    monkeypatch.setattr(Session, "commit", uncertain)
    response = post(api)
    detail = response.json()["detail"]
    assert response.status_code == 503 and detail["outcome"] == "unknown"
    assert detail["committed_count"] is None and detail["control_status"] == "reconciliation_required"
    assert counts(env) == ((1, 1) if after_commit else (0, 0))
    assert post(api).status_code == 409 and len(env.calls) == 1


def test_journal_failure_never_changes_a_confirmed_review_commit_to_failure(env, api, monkeypatch):
    original = Session.commit
    commits = []

    def fail_finish(self):
        commits.append(1)
        if len(commits) == 3:
            raise SQLAlchemyError(PRIVATE)
        return original(self)

    monkeypatch.setattr(Session, "commit", fail_finish)
    response = post(api)
    assert response.status_code == 200 and response.json()["inserted"] == 1
    assert response.json()["control_status"] == "reconciliation_required" and counts(env) == (1, 1)
    assert post(api).status_code == 409 and len(env.calls) == 1


def test_two_services_cannot_acquire_the_same_connection_simultaneously(env):
    started, release = Event(), Event()

    def handler(_):
        started.set()
        assert release.wait(5)
        return page(record())

    env.handler = handler
    first, second = env.service(), env.service()
    with ThreadPoolExecutor(max_workers=2) as executor:
        future = executor.submit(first.import_reviews, actor(), BUSINESS)
        assert started.wait(5)
        try:
            with pytest.raises(ExternalReviewImportError) as caught:
                second.import_reviews(actor(), BUSINESS)
            assert caught.value.detail.code == "import_in_progress"
        finally:
            release.set()
        assert future.result(timeout=5).inserted == 1
    assert len(env.calls) == 1


def test_budget_is_reserved_before_http_and_not_refunded_for_provider_failure(env, api):
    env.current_service = env.service(tenant_request_budget=1)
    env.handler = lambda _: httpx.Response(503, text=PRIVATE)
    assert post(api).status_code == 503
    response = post(api)
    assert response.status_code == 429 and response.json()["detail"]["code"] == "budget_exhausted"
    assert len(env.calls) == 1


def test_shared_account_budget_rejects_a_different_tenant_while_first_http_runs(env):
    started, release = Event(), Event()

    def handler(_):
        started.set()
        assert release.wait(5)
        return page(record())

    env.handler = handler
    first, second = env.service(account_request_budget=1), env.service(account_request_budget=1)
    with ThreadPoolExecutor(max_workers=2) as executor:
        future = executor.submit(first.import_reviews, actor(), BUSINESS)
        assert started.wait(5)
        try:
            with pytest.raises(ExternalReviewImportError) as caught:
                second.import_reviews(actor(2), BUSINESS)
            assert caught.value.detail.code == "budget_exhausted"
        finally:
            release.set()
        assert future.result(timeout=5).inserted == 1
    assert len(env.calls) == 1


@pytest.mark.parametrize("after_commit", [False, True])
def test_uncertain_admission_commit_never_starts_acquisition(env, api, monkeypatch, after_commit):
    original = Session.commit

    def uncertain(self):
        if after_commit:
            original(self)
        raise SQLAlchemyError(PRIVATE)

    monkeypatch.setattr(Session, "commit", uncertain)
    response = post(api)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "admission_unavailable"
    assert response.json()["detail"]["control_status"] == "reconciliation_required"
    assert PRIVATE not in response.text
    assert_no_acquisition(env)


def test_diagnostics_and_debug_logs_do_not_publish_review_values(env, api, caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    env.engine.echo = "debug"
    response = post(api)
    assert response.status_code == 200 and PRIVATE not in response.text
    assert PRIVATE not in caplog.text


def test_account_budget_is_shared_across_tenants_and_rolls_with_time(env, api):
    service = env.service(account_request_budget=1)
    now = datetime(2026, 11, 3, 12)
    service.clock = lambda: now
    env.current_service = service
    assert post(api).status_code == 200
    assert post(api, 2).status_code == 429 and len(env.calls) == 1
    service.clock = lambda: now + timedelta(seconds=3601)
    assert post(api, 2).status_code == 200 and len(env.calls) == 2


def test_stale_running_admission_does_not_expire_or_trigger_http(env, api):
    with env.sessions() as db:
        db.add(ExternalReviewImportAttempt(operation_id="synthetic-unresolved", tenant_id=10, source="Google",
                                          business_data_id=BUSINESS, started_at=datetime(2000, 1, 1),
                                          reserved_requests=1, active=True, state="running"))
        db.commit()
    assert post(api).status_code == 409
    assert_no_acquisition(env)


@pytest.mark.parametrize("dialect", [sqlite.dialect(), postgresql.dialect()], ids=["sqlite", "postgresql-ddl-only"])
def test_admission_schema_compiles_for_both_targets_without_server(dialect):
    ddl = str(CreateTable(ExternalReviewImportAttempt.__table__).compile(dialect=dialect))
    assert "uq_external_import_active" in ddl and "fk_external_import_connection" in ddl


def test_initialization_adds_admission_table_without_enabling_connections(env):
    with env.sessions() as db:
        connection = db.get(ExternalReviewConnection, (10, "Google", BUSINESS))
        connection.persistence_enabled, connection.approval_reference = False, None
        db.commit()
    with env.engine.begin() as connection:
        ExternalReviewImportAttempt.__table__.drop(connection)
    init_db(env.engine)
    init_db(env.engine)
    assert "external_review_import_attempts" in inspect(env.engine).get_table_names()
    with env.sessions() as db:
        assert db.get(ExternalReviewConnection, (10, "Google", BUSINESS)).persistence_enabled is False
