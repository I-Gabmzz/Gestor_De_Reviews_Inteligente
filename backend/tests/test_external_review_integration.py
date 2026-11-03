"""HU-21 #3835, fase A: componentes reales, HTTP y datos sintéticos exclusivamente."""

from contextlib import ExitStack, nullcontext
from datetime import datetime, timezone
import logging
import socket
import traceback

import httpx
import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.serpapi_config import SerpApiSettings
from app.db.init_db import init_db
from app.models import ExternalReviewConnection, ExternalReviewIdentity, Review, Tenant, User
from app.repositories.review_repository import ReviewRepository
from app.schemas.auth import AuthenticatedUser
from app.services.ai_provider import GeminiAdapter
from app.services.external_review_persistence_service import (
    ExternalReviewPersistenceError, ExternalReviewPersistenceService,
)
from app.services.serpapi_client import SERPAPI_ENDPOINT, SerpApiClient, SerpApiError
from app.services.serpapi_normalizer import normalize_serpapi_result


BUSINESS = "0xabc:0x123"
FOREIGN_BUSINESS = "0xabc:0x456"
KEY = "synthetic-integration-not-a-credential"
TEXT = "synthetic-integration-private-content"
AUTHOR = "synthetic-integration-private-author"
REVIEW_ID = "synthetic-integration-private-review"
TOKEN = "synthetic-integration-private-token"


def record(identity=REVIEW_ID, **changes):
    return {
        "review_id": identity, "source": "Google", "user": {"name": AUTHOR},
        "snippet": TEXT, "iso_date": "2026-10-12T23:30:00-07:00", "rating": 4,
        **changes,
    }


def page(*rows, token=None, place=True, **changes):
    body = {"search_metadata": {"status": "Success"}, "reviews": list(rows)}
    if place:
        body["place_info"] = {"title": "Negocio exclusivamente sintético", "data_id": BUSINESS}
    if token is not None:
        body["serpapi_pagination"] = {"next_page_token": token, "next": "https://untrusted.invalid/"}
    return httpx.Response(200, json={**body, **changes})


def actor(identifier=1):
    return AuthenticatedUser(id=identifier, tenant_id=10 if identifier == 1 else 20,
                             rol="usuario_negocio", correo=f"synthetic-{identifier}@example.com")


class TrackingTransport(httpx.MockTransport):
    def __init__(self, responses, business):
        self.responses = responses
        self.business = business
        self.requests = []  # Deliberadamente excluye api_key y URL autenticada.
        self.closed = False
        super().__init__(self.handle)

    def handle(self, request):
        assert request.method == "GET"
        assert str(request.url.copy_with(query=None)) == SERPAPI_ENDPOINT
        params = dict(request.url.params)
        assert params.pop("api_key") == KEY
        assert params["data_id"] == self.business
        self.requests.append(params)
        # Inyectar en emisores reales: el contexto del cliente debe suprimirlo.
        for name in ("httpx", "httpcore.connection"):
            logging.getLogger(name).debug("%s %s %s %s", request.url, TEXT, REVIEW_ID, TOKEN)
        assert len(self.requests) <= len(self.responses), "Unexpected retry/pagination"
        response = self.responses[len(self.requests) - 1]
        if isinstance(response, Exception):
            raise response
        return response

    def close(self):
        self.closed = True
        super().close()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Bloquear resolutores socket enumerados, conexiones y HTTP/IA no previstos."""
    attempts = []

    def denied(*args, **kwargs):
        attempts.append("unexpected external operation")
        raise AssertionError("External operations disabled in synthetic integration")

    async def async_denied(*args, **kwargs):
        denied()

    for name in ("connect", "connect_ex", "sendto"):
        monkeypatch.setattr(socket.socket, name, denied)
    for name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr"):
        monkeypatch.setattr(socket, name, denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", denied)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", async_denied)
    monkeypatch.setattr(GeminiAdapter, "__init__", denied)
    original_send = httpx.Client.send

    def only_simulated_get(client, request, *args, **kwargs):
        if (not isinstance(client._transport, TrackingTransport)
                or request.method != "GET" or request.url.host != "serpapi.com"
                or request.url.path != "/search.json"
                or request.url.params.get("engine") != "google_maps_reviews"):
            denied()
        return original_send(client, request, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "send", only_simulated_get)
    for name in ("SERPAPI_API_KEY", "SERPAPI_PAGE_SIZE", "SERPAPI_MAX_PAGES", "SERPAPI_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setitem(SerpApiSettings.model_config, "env_file", None)
    yield attempts
    assert attempts == [], "An external/AI/publication operation was attempted"


@pytest.mark.parametrize("resolver", ["gethostbyname", "gethostbyname_ex", "gethostbyaddr"])
@pytest.mark.parametrize("raise_on_exit", [False, True], ids=["normal-exit", "exception-exit"])
def test_legacy_resolvers_are_blocked_and_restored_without_dns(monkeypatch, resolver, raise_on_exit):
    outer_guard = getattr(socket, resolver)
    original_calls = []

    def original_stub(*args, **kwargs):
        original_calls.append("resolver reached")
        raise AssertionError("The resolver beneath the guard must never run")

    # El resolver original se sustituye por un centinela antes del fixture anidado:
    # incluso una regresión del bloqueo no podría hacer una consulta DNS real.
    with monkeypatch.context() as baseline:
        baseline.setattr(socket, resolver, original_stub)
        expected = pytest.raises(RuntimeError, match="synthetic-scope-exit") if raise_on_exit else nullcontext()
        with expected:
            with pytest.MonkeyPatch.context() as scoped:
                guard = offline.__wrapped__(scoped)
                blocked = next(guard)
                try:
                    target = "192.0.2.1" if resolver == "gethostbyaddr" else "synthetic.invalid"
                    with pytest.raises(AssertionError, match="External operations disabled"):
                        getattr(socket, resolver)(target)
                    assert blocked == ["unexpected external operation"]
                    # Sólo se retira la sonda deliberada y comprobada; cualquier
                    # operación adicional haría fallar el cierre del fixture.
                    blocked.pop()
                    assert original_calls == []
                    if raise_on_exit:
                        raise RuntimeError("synthetic-scope-exit")
                finally:
                    with pytest.raises(StopIteration):
                        next(guard)
        assert getattr(socket, resolver) is original_stub
    assert getattr(socket, resolver) is outer_guard
    assert original_calls == []


@pytest.fixture()
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'synthetic-integration.db'}", hide_parameters=True)
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

    try:
        init_db(engine)
        with Session(engine) as db:
            db.add_all([Tenant(id=t, nombre=f"synthetic-tenant-{t}", estado="activo") for t in (10, 20)])
            db.flush()
            for identifier in (1, 2):
                user = actor(identifier)
                db.add(User(id=user.id, tenant_id=user.tenant_id, nombre="synthetic-user",
                            correo=user.correo, password_hash="synthetic-unused-hash",
                            rol=user.rol, estado="activo"))
            # Únicamente esta base efímera; nunca se activa una conexión real.
            for tenant, business in ((10, BUSINESS), (20, BUSINESS), (20, FOREIGN_BUSINESS)):
                db.add(ExternalReviewConnection(tenant_id=tenant, source="Google", business_data_id=business,
                                               persistence_enabled=True, approval_reference="synthetic-test-only"))
            db.commit()
        yield engine, checked_out
        assert checked_out == set(), "A persistence/query session leaked its connection"
    finally:
        engine.dispose()


@pytest.fixture()
def read(database):
    engine, checked_out = database
    transports = []

    def acquire(responses, *, business=BUSINESS, page_size=20, max_pages=5):
        assert checked_out == set(), "HTTP must run outside database transactions"
        settings = SerpApiSettings(_env_file=None, serpapi_api_key=KEY,
                                  serpapi_page_size=20, serpapi_max_pages=5)
        transport = TrackingTransport(responses, business)
        transports.append(transport)
        with SerpApiClient(settings, transport=transport) as client:
            result = client.fetch_reviews(business, page_size=page_size, max_pages=max_pages)
        assert transport.closed and all(r.is_closed for r in responses if isinstance(r, httpx.Response))
        # Composición sólo de pruebas: NO es una validación automática del cliente.
        place_id = (result.place_info or {}).get("data_id")
        if place_id is not None and place_id != business:
            raise ValueError("Synthetic establishment identity mismatch")
        normalized = normalize_serpapi_result(result, business_data_id=business)
        return result, normalized, transport

    acquire.transports = transports
    yield acquire
    assert all(t.closed for t in transports)


def persist(database, batch, *, current_user=None, business=BUSINESS):
    engine, checked_out = database
    assert checked_out == set()
    with Session(engine, autoflush=False) as db:
        assert not db.in_transaction()
        result = ExternalReviewPersistenceService(ReviewRepository(db)).persist(
            batch, current_user=current_user or actor(), business_data_id=business,
        )
        assert not db.in_transaction()
    assert checked_out == set()
    assert result.input_count == result.inserted + result.repeated + result.changed + result.omitted + result.rejected
    return result


def counts(database):
    with Session(database[0]) as db:
        return tuple(db.scalar(select(func.count()).select_from(model)) for model in (Review, ExternalReviewIdentity))


def test_complete_flow_and_second_http_import_are_idempotent(database, read):
    for expected_inserted in (1, 0):
        native, batch, transport = read([page(record())], page_size=5, max_pages=1)
        assert native.request_count == len(transport.requests) == 1
        assert native.record_count == 1 and native.stop_reason == "no_next_token"
        assert native.place_info["data_id"] == BUSINESS
        normalized = batch.with_text[0]
        assert (normalized.source, normalized.business_data_id, normalized.external_review_id) == ("Google", BUSINESS, REVIEW_ID)
        assert (normalized.author, normalized.content, normalized.rating) == (AUTHOR, TEXT, 4)
        assert normalized.review_date == datetime(2026, 10, 13, 6, 30, tzinfo=timezone.utc)
        result = persist(database, batch)
        assert (result.inserted, result.repeated) == (expected_inserted, 1 - expected_inserted)
    assert sum(len(t.requests) for t in read.transports) == 2
    assert counts(database) == (1, 1)
    with Session(database[0]) as db:
        review = db.scalar(select(Review))
        identity = db.scalar(select(ExternalReviewIdentity))
        assert identity.review_id == review.id and identity.tenant_id == review.tenant_id == 10
        assert (identity.source, identity.business_data_id, identity.external_review_id) == ("Google", BUSINESS, REVIEW_ID)
        assert identity.import_fingerprint.startswith("v1:") and len(identity.import_fingerprint) == 67
        assert (review.autor, review.contenido, review.fuente, review.puntuacion) == (AUTHOR, TEXT, "Google", 4)
        assert review.fecha == datetime(2026, 10, 13, 6, 30) and review.estado == "nueva"
        assert review.categoria is review.resumen is review.tema is review.prioridad is None


def test_multiple_pages_duplicate_conflicts_and_omissions(database, read):
    native, batch, transport = read([
        page(record("same"), record("empty", snippet=None), record("conflict"), token=TOKEN),
        page(record("same"), record("conflict", rating=5), record("no-author", user=None), place=False),
    ])
    assert len(transport.requests) == native.request_count == 2
    assert "next_page_token" not in transport.requests[0]
    assert transport.requests[1]["next_page_token"] == TOKEN
    assert transport.requests[0]["num"] == transport.requests[1]["num"] == "20"
    assert batch.input_count == 6 and not batch.incomplete
    assert batch.counts.conflicting == 2 and len(batch.conflicts) == 1
    assert {i.code for i in batch.warnings} == {"missing_author", "missing_content"}
    assert batch.with_text[1].author is None
    result = persist(database, batch)
    assert (result.inserted, result.repeated, result.omitted, result.rejected, result.batch_duplicates) == (2, 1, 1, 2, 1)
    assert counts(database) == (2, 2)


@pytest.mark.parametrize("reason,responses,max_pages,attempts", [
    ("max_pages", lambda: [page(record(), token=TOKEN)], 1, 1),
    ("empty_with_token", lambda: [page(token=TOKEN)], 5, 1),
    ("repeated_token", lambda: [page(record(), token=TOKEN), page(record("second"), token=TOKEN)], 5, 2),
])
def test_incomplete_acquisitions_never_persist_by_default(database, read, reason, responses, max_pages, attempts):
    native, batch, transport = read(responses(), max_pages=max_pages)
    assert native.request_count == len(transport.requests) == attempts
    assert batch.incomplete and batch.stop_reason == reason
    assert batch.limited == (reason == "max_pages")
    with pytest.raises(ExternalReviewPersistenceError) as caught:
        persist(database, batch)
    assert caught.value.code == "incomplete_disabled"
    assert counts(database) == (0, 0)


@pytest.mark.parametrize("response,code", [
    (lambda: httpx.Response(401, text=TEXT), "credentials"),
    (lambda: httpx.Response(429, text=TEXT), "quota"),
    (lambda: httpx.Response(503, text=TEXT), "unavailable"),
    (lambda: page(error=TEXT), "provider_error"),
    (lambda: page(search_metadata={"status": "Processing"}), "pending"),
    (lambda: httpx.ReadTimeout(TEXT), "timeout"),
])
@pytest.mark.parametrize("after_valid_page", [False, True])
def test_acquisition_errors_preserve_partial_but_never_retry_or_write(database, read, response, code, after_valid_page):
    responses = ([page(record(), token=TOKEN)] if after_valid_page else []) + [response()]
    with pytest.raises(SerpApiError) as caught:
        read(responses)
    error = caught.value
    native = error.partial_result
    assert error.code == code and native.stop_reason == "error"
    assert native.request_count == len(read.transports[-1].requests) == 1 + int(after_valid_page)
    assert native.record_count == int(after_valid_page)
    assert read.transports[-1].closed
    assert all(r.is_closed for r in responses if isinstance(r, httpx.Response))
    batch = normalize_serpapi_result(native, business_data_id=BUSINESS)
    with pytest.raises(ExternalReviewPersistenceError) as blocked:
        persist(database, batch)
    assert blocked.value.code == "incomplete_disabled"
    diagnostic = "".join(traceback.format_exception(error))
    assert all(marker not in diagnostic for marker in (KEY, TEXT, REVIEW_ID, TOKEN, "api_key="))
    assert counts(database) == (0, 0)


@pytest.mark.parametrize("rating,accepted", [(1, True), (5.0, True), (0, False), (6, False), (True, False), (3.5, False), ("4", False)])
def test_rating_validation_crosses_all_components(database, read, rating, accepted):
    _, batch, _ = read([page(record(rating=rating))])
    result = persist(database, batch)
    assert (result.inserted, result.rejected) == (int(accepted), int(not accepted))
    if not accepted:
        assert batch.rejected[0].issues[0].code == "invalid_rating"
    assert counts(database) == (int(accepted), int(accepted))


def test_source_and_text_origin_are_validated_without_inventing_fields(database, read):
    _, batch, _ = read([page(record("foreign", source="SerpApi"),
                              record("original", extracted_snippet={"original": " synthetic-original "}),
                              record("textless", snippet=" ", user=None))])
    assert batch.rejected[0].issues[0].code == "unsupported_source"
    assert batch.with_text[0].content == "synthetic-original"
    assert batch.with_text[0].content_field == "extracted_snippet.original"
    assert batch.without_text[0].author is batch.without_text[0].content is None
    result = persist(database, batch)
    assert (result.inserted, result.omitted, result.rejected) == (1, 1, 1)
    assert counts(database) == (1, 1)


def test_changed_external_record_preserves_manual_edits_and_synthetic_ai_results(database, read):
    _, batch, _ = read([page(record())])
    persist(database, batch)
    with Session(database[0]) as db:
        review = db.scalar(select(Review))
        review.contenido, review.autor, review.fuente, review.estado = "synthetic-manual", "synthetic-editor", "synthetic-manual-source", "revisada"
        review.categoria, review.resumen, review.tema, review.prioridad = "synthetic-category", "synthetic-summary", "synthetic-topic", "alta"
        fingerprint = db.scalar(select(ExternalReviewIdentity.import_fingerprint))
        db.commit()
    _, identical, _ = read([page(record())])
    assert persist(database, identical).repeated == 1
    _, changed, _ = read([page(record(snippet="synthetic-external-change", rating=5))])
    result = persist(database, changed)
    assert result.changed == 1 and result.inserted == result.repeated == 0
    assert result.changed_positions == (changed.with_text[0].position,)
    with Session(database[0]) as db:
        review = db.scalar(select(Review))
        assert (review.contenido, review.autor, review.fuente, review.estado) == ("synthetic-manual", "synthetic-editor", "synthetic-manual-source", "revisada")
        assert (review.categoria, review.resumen, review.tema, review.prioridad) == ("synthetic-category", "synthetic-summary", "synthetic-topic", "alta")
        assert db.scalar(select(ExternalReviewIdentity.import_fingerprint)) == fingerprint
    assert counts(database) == (1, 1)


def test_two_tenants_same_external_id_ignore_provider_tenant_claims(database, read):
    for identifier in (1, 2):
        _, batch, _ = read([page(record(tenant_id=999, current_user={"tenant_id": 999}), tenant_id=999)])
        assert persist(database, batch, current_user=actor(identifier)).inserted == 1
    with Session(database[0]) as db:
        identities = list(db.scalars(select(ExternalReviewIdentity)))
        assert {(r.tenant_id, r.external_review_id) for r in identities} == {(10, REVIEW_ID), (20, REVIEW_ID)}
        assert len({r.review_id for r in identities}) == 2
        assert set(db.scalars(select(Review.tenant_id))) == {10, 20}
    assert counts(database) == (2, 2)


def test_foreign_business_connection_cannot_be_used_by_other_tenant(database, read):
    response = page(record(), place_info={"data_id": FOREIGN_BUSINESS})
    _, batch, _ = read([response], business=FOREIGN_BUSINESS)
    with pytest.raises(ExternalReviewPersistenceError) as caught:
        persist(database, batch, business=FOREIGN_BUSINESS)
    assert caught.value.code == "connection_unavailable"
    assert counts(database) == (0, 0)
    assert persist(database, batch, business=FOREIGN_BUSINESS, current_user=actor(2)).inserted == 1


def test_normalizer_and_persistence_business_context_must_agree(database, read):
    native, _, _ = read([page(record())])
    different_context = normalize_serpapi_result(native, business_data_id=FOREIGN_BUSINESS)
    with pytest.raises(ExternalReviewPersistenceError) as caught:
        persist(database, different_context, business=BUSINESS)
    assert caught.value.code == "invalid_record"
    assert counts(database) == (0, 0)


def test_verifiable_place_mismatch_is_stopped_by_test_composition(database, read):
    # El cliente conserva place_info; la comprobación es responsabilidad del llamador.
    with pytest.raises(ValueError, match="identity mismatch"):
        read([page(record(), place_info={"title": "Negocio exclusivamente sintético", "data_id": FOREIGN_BUSINESS})])
    assert len(read.transports[-1].requests) == 1 and counts(database) == (0, 0)


def test_missing_place_identifier_is_not_inferred_from_commercial_name(database, read):
    native, batch, _ = read([page(record(), place_info={"title": "Negocio exclusivamente sintético"})])
    assert "data_id" not in native.place_info
    assert batch.with_text[0].business_data_id == BUSINESS  # Contexto confiable solicitado, no identidad demostrada por el nombre.
    assert persist(database, batch).inserted == 1


@pytest.mark.parametrize("enabled,approval", [(False, None), (False, "synthetic-approval")])
def test_real_storage_gate_remains_closed_without_enabling_fixture(database, read, enabled, approval):
    with Session(database[0]) as db:
        configured = db.get(ExternalReviewConnection, (10, "Google", BUSINESS))
        configured.persistence_enabled, configured.approval_reference = enabled, approval
        db.commit()
    _, batch, _ = read([page(record())])
    with pytest.raises(ExternalReviewPersistenceError) as caught:
        persist(database, batch)
    assert caught.value.code == "persistence_disabled"
    assert counts(database) == (0, 0)


def test_failure_after_first_insert_rolls_back_both_tables_and_rerun_succeeds(database, read, monkeypatch):
    _, batch, _ = read([page(record("first"), record("second"))])
    original = ReviewRepository.add_external_review
    calls = []

    def fail_second(repository, *args, **kwargs):
        calls.append("insert")
        original(repository, *args, **kwargs)
        if len(calls) == 2:
            raise SQLAlchemyError(TEXT)

    with monkeypatch.context() as patch:
        patch.setattr(ReviewRepository, "add_external_review", fail_second)
        with pytest.raises(ExternalReviewPersistenceError) as caught:
            persist(database, batch)
    assert calls == ["insert", "insert"]
    assert caught.value.outcome == "rolled_back" and caught.value.committed_count == 0
    assert TEXT not in "".join(traceback.format_exception(caught.value))
    assert counts(database) == (0, 0)
    assert persist(database, batch).inserted == 2
    assert counts(database) == (2, 2)


@pytest.mark.parametrize("field,value,accepted", [
    ("review_id", "i" * 512, True), ("review_id", "i" * 513, False),
    ("review_id", "\u754c" * 342, False),
    ("snippet", "c" * 65536, True), ("snippet", "c" * 65537, False),
    ("snippet", "\u754c" * 21846, False),
], ids=["id-at-limit", "id-over-limit", "id-over-utf8-budget", "content-at-limit", "content-over-limit", "content-over-utf8-budget"])
def test_normalization_to_persistence_character_and_byte_limits(database, read, field, value, accepted):
    _, batch, transport = read([page(record(**{field: value}))])
    assert len(batch.with_text) == len(transport.requests) == 1
    if accepted:
        assert persist(database, batch).inserted == 1
    else:
        with pytest.raises(ExternalReviewPersistenceError) as caught:
            persist(database, batch)
        assert caught.value.code == "invalid_record" and counts(database) == (0, 0)


@pytest.mark.parametrize("length,accepted", [(128, True), (129, False)])
def test_business_identifier_limit_across_transport_context_and_storage(database, read, length, accepted):
    business = "0x" + "a" * (length - 6) + ":0xb"
    assert len(business) == length
    if accepted:
        with Session(database[0]) as db:
            db.add(ExternalReviewConnection(tenant_id=10, source="Google", business_data_id=business,
                                           persistence_enabled=True, approval_reference="synthetic-test-only"))
            db.commit()
    _, batch, transport = read([page(record(), place_info={"data_id": business})], business=business)
    assert transport.requests[0]["data_id"] == batch.with_text[0].business_data_id == business
    if accepted:
        assert persist(database, batch, business=business).inserted == 1
    else:
        with pytest.raises(ExternalReviewPersistenceError) as caught:
            persist(database, batch, business=business)
        assert caught.value.code == "invalid_business" and counts(database) == (0, 0)


def test_aggregate_text_budget_applies_after_complete_http_acquisition(database, read):
    rows = [record(f"synthetic-{i}", snippet="c" * 65536) for i in range(16)]
    native, batch, _ = read([page(*rows)])
    assert native.request_count == 1 and len(batch.with_text) == 16
    with pytest.raises(ExternalReviewPersistenceError) as caught:
        persist(database, batch)
    assert caught.value.code == "text_budget" and counts(database) == (0, 0)


def test_absolute_page_record_and_attempt_limits_are_composable(database, read):
    responses = [page(*(record(f"synthetic-{p}-{i}") for i in range(20)),
                      token=f"synthetic-page-{p}" if p < 4 else None) for p in range(5)]
    native, batch, transport = read(responses)
    assert native.request_count == len(transport.requests) == 5
    assert native.record_count == batch.input_count == 100 and not batch.incomplete
    result = persist(database, batch)
    assert result.inserted == 100 and counts(database) == (100, 100)


def test_oversized_provider_page_is_rejected_before_normalization_or_writes(database, read):
    with pytest.raises(SerpApiError) as caught:
        read([page(*(record(str(i)) for i in range(21)))])
    assert caught.value.code == "invalid_response"
    assert caught.value.partial_result.request_count == 1
    assert caught.value.partial_result.record_count == 0
    assert len(read.transports[-1].requests) == 1 and counts(database) == (0, 0)


@pytest.mark.parametrize("limits", [{"page_size": 21}, {"max_pages": 6}])
def test_invalid_limits_make_zero_simulated_requests(database, read, limits):
    with pytest.raises(SerpApiError) as caught:
        read([], **limits)
    assert caught.value.code == "input" and read.transports[-1].requests == []
    assert counts(database) == (0, 0)


def test_sensitive_data_is_absent_from_debug_logs_repr_and_global_logging_changes(database, read, caplog, offline):
    names = ("", "httpx", "httpcore", "httpcore.connection", "sqlalchemy.engine", "sqlalchemy.engine.Engine")
    loggers = [logging.getLogger(name) for name in names]
    before = [(logger.level, tuple(logger.handlers), logger.propagate) for logger in loggers]
    with ExitStack() as stack:
        for name in names:
            stack.enter_context(caplog.at_level(logging.DEBUG, logger=name or None))
        native, batch, transport = read([page(record(), record("synthetic-textless", snippet=None))])
        result = persist(database, batch)
        diagnostic = repr((native, native.pages, native.reviews, batch, batch.with_text, result))
        assert result.inserted == result.omitted == 1
        assert transport.closed and offline == []
        assert caplog.records, "Privacy assertions require exercised logging"
        assert any("ReviewRepository" in entry.message for entry in caplog.records)
        for marker in (KEY, TEXT, AUTHOR, REVIEW_ID, TOKEN, "api_key=", "https://serpapi.com/search.json?"):
            assert marker not in caplog.text and marker not in diagnostic
    assert [(logger.level, tuple(logger.handlers), logger.propagate) for logger in loggers] == before
    assert counts(database) == (1, 1)
