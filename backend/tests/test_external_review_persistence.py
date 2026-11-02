"""Persistencia #3834 con SQLite efímero y datos exclusivamente sintéticos."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
import subprocess
import sys
from threading import Barrier
import traceback

import pytest
from sqlalchemy import create_engine, event, func, literal, select
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.init_db import init_db
from app.models import ExternalReviewConnection, ExternalReviewIdentity, Review, Tenant, User
from app.repositories.review_repository import ReviewRepository
from app.schemas.auth import AuthenticatedUser
from app.schemas.ai import SummaryResult
from app.schemas.external_review import NormalizationIssue, RecordPosition
from app.schemas.serpapi import SerpApiPage, SerpApiResult, SerpApiReview
from app.schemas.review import ReviewStatus
from app.services.external_review_persistence_service import ExternalReviewPersistenceError, ExternalReviewPersistenceService
from app.services.serpapi_normalizer import normalize_serpapi_result


BUSINESS = "0x123:0x456"
OTHER_BUSINESS = "0x123:0x789"
PRIVATE = "synthetic-private-marker"


def row(identity="synthetic-review", **changes):
    return {"review_id": identity, "source": "Google", "user": {"name": "synthetic-author"},
            "snippet": "synthetic-content", "iso_date": "2026-11-02T06:01:32-07:00", "rating": 4, **changes}


def batch(*pages, business=BUSINESS, reason="no_next_token"):
    native = SerpApiResult(
        pages=tuple(SerpApiPage(index, 200, "Success", tuple(SerpApiReview(item) for item in page)) for index, page in enumerate(pages, 1)),
        place_info=None, first_page_metadata=None, request_count=len(pages), record_count=sum(map(len, pages)),
        stop_reason=reason, incomplete=reason != "no_next_token", limited=reason == "max_pages",
    )
    return normalize_serpapi_result(native, business_data_id=business)


def actor(identifier=1, **changes):
    tenant = 20 if identifier == 2 else None if identifier == 4 else 10
    role = "admin_tenant" if identifier == 3 else "admin_general" if identifier == 4 else "usuario_negocio"
    return AuthenticatedUser(**{"id": identifier, "tenant_id": tenant, "rol": role, "correo": f"synthetic-{identifier}@example.com", **changes})


@pytest.fixture()
def engine(tmp_path):
    database = create_engine(
        f"sqlite:///{tmp_path / 'synthetic-external.db'}", hide_parameters=True,
        connect_args={"check_same_thread": False, "timeout": 5},
    )

    @event.listens_for(database, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    init_db(database)
    with Session(database) as db:
        db.add_all([Tenant(id=10, nombre="synthetic-tenant-a", estado="activo"), Tenant(id=20, nombre="synthetic-tenant-b", estado="activo")])
        db.flush()
        for identifier in (1, 2, 3, 4):
            context = actor(identifier)
            db.add(User(id=identifier, tenant_id=context.tenant_id, nombre="synthetic-user", correo=context.correo,
                        password_hash="synthetic-unused-hash", rol=context.rol, estado="activo"))
        # Habilitación explícita exclusivamente dentro de esta base de prueba.
        for tenant, business in ((10, BUSINESS), (20, BUSINESS), (10, OTHER_BUSINESS)):
            db.add(ExternalReviewConnection(tenant_id=tenant, source="Google", business_data_id=business,
                                           persistence_enabled=True, approval_reference="synthetic-test-only"))
        db.commit()
    yield database
    database.dispose()


def persist(engine, data=None, *, current_user=None, business=BUSINESS, allow_incomplete=False):
    with Session(engine, autoflush=False) as db:
        return ExternalReviewPersistenceService(ReviewRepository(db), allow_incomplete=allow_incomplete).persist(
            batch([row()]) if data is None else data, current_user=current_user or actor(), business_data_id=business,
        )


def counts(engine):
    with Session(engine) as db:
        return tuple(db.scalar(select(func.count()).select_from(model)) for model in (Review, ExternalReviewIdentity))


def assert_reconciled(result):
    assert result.input_count == result.inserted + result.repeated + result.changed + result.omitted + result.rejected


def test_first_insert_uses_one_commit_flush_and_no_refresh(engine, monkeypatch):
    with Session(engine, autoflush=False) as db:
        assert not db.in_transaction()
        calls = []
        original = db.commit

        def commit():
            calls.append("commit")
            original()

        monkeypatch.setattr(db, "commit", commit)
        monkeypatch.setattr(db, "refresh", lambda *_: pytest.fail("Unexpected post-commit refresh"))
        result = ExternalReviewPersistenceService(ReviewRepository(db)).persist(batch([row()]), current_user=actor(), business_data_id=BUSINESS)
        assert calls == ["commit"]
    assert result.inserted == 1 and counts(engine) == (1, 1)
    assert_reconciled(result)
    with Session(engine) as db:
        saved = db.scalar(select(Review))
        identity = db.scalar(select(ExternalReviewIdentity))
        assert identity.review_id == saved.id and identity.tenant_id == saved.tenant_id == 10
        assert (identity.source, identity.business_data_id, identity.external_review_id) == ("Google", BUSINESS, "synthetic-review")
        assert len(identity.import_fingerprint) == 67 and identity.import_fingerprint.startswith("v1:")
        assert saved.fecha == datetime(2026, 11, 2, 13, 1, 32) and saved.fecha.tzinfo is None
        assert saved.estado == "nueva" and saved.puntuacion == 4
        assert saved.categoria is saved.resumen is saved.tema is saved.prioridad is None


def test_reimport_does_not_duplicate_and_fingerprint_uses_normalized_values(engine):
    persist(engine)
    result = persist(engine, batch([row(rating=4.0, iso_date="2026-11-02T13:01:32Z", extra=PRIVATE)]))
    assert (result.inserted, result.repeated, result.changed) == (0, 1, 0)
    assert counts(engine) == (1, 1)
    assert_reconciled(result)


def test_changed_provider_record_never_overwrites_manual_or_ai_values(engine):
    persist(engine)
    with Session(engine) as db:
        saved = db.scalar(select(Review))
        edits = dict(autor="synthetic-edited-author", contenido="synthetic-edited-content", fecha=datetime(2020, 1, 1),
                     fuente="synthetic-edited-source", puntuacion=2, estado="atendida", categoria="Queja",
                     resumen="synthetic-summary", tema="synthetic-topic", prioridad="Alta")
        for key, value in edits.items():
            setattr(saved, key, value)
        db.commit()
    unchanged = persist(engine)
    changed = persist(engine, batch([row(snippet="synthetic-provider-change")]))
    assert unchanged.repeated == 1 and changed.changed == 1 and changed.inserted == 0
    assert changed.changed_positions == (RecordPosition(1, 1, 1),)
    with Session(engine) as db:
        saved = db.scalar(select(Review))
        assert {key: getattr(saved, key) for key in edits} == edits
        assert db.scalar(select(ExternalReviewIdentity.source)) == "Google"
    assert counts(engine) == (1, 1)
    assert_reconciled(changed)


def test_same_external_identity_is_independent_between_tenants_and_businesses(engine):
    assert persist(engine).inserted == 1
    assert persist(engine, current_user=actor(2)).inserted == 1
    assert persist(engine, batch([row()], business=OTHER_BUSINESS), business=OTHER_BUSINESS).inserted == 1
    assert counts(engine) == (3, 3)
    with Session(engine) as db:
        assert sorted(db.scalars(select(Review.tenant_id))) == [10, 10, 20]


def test_opaque_ids_are_case_sensitive_and_preserve_spaces(engine):
    result = persist(engine, batch([row("A"), row("a"), row(" A ")]))
    assert result.inserted == 3
    with Session(engine) as db:
        assert set(db.scalars(select(ExternalReviewIdentity.external_review_id))) == {"A", "a", " A "}


def test_batch_duplicates_conflicts_rejections_and_textless_are_reconciled(engine):
    data = batch([row("a"), row("a"), row("empty", snippet=None, user=None)],
                 [row("conflict"), row("conflict", rating=5), row("invalid", rating=True)])
    result = persist(engine, data)
    assert (result.inserted, result.repeated, result.changed, result.omitted, result.rejected, result.batch_duplicates) == (1, 1, 0, 1, 3, 1)
    assert {issue.code for issue in result.warnings} == {"missing_author", "missing_content"}
    assert counts(engine) == (1, 1)
    assert_reconciled(result)


def test_textless_never_creates_identity_or_replaces_existing_text(engine):
    result = persist(engine, batch([row(snippet=None)]))
    assert result.omitted == 1 and counts(engine) == (0, 0)
    persist(engine)
    assert persist(engine, batch([row(snippet=None)])).omitted == 1
    with Session(engine) as db:
        assert db.scalar(select(Review.contenido)) == "synthetic-content"


@pytest.mark.parametrize("reason", ["error", "max_pages", "repeated_token", "empty_with_token"])
def test_incomplete_acquisition_is_disabled_unless_internal_option_is_explicit(engine, reason):
    data = batch([row()], reason=reason)
    with pytest.raises(ExternalReviewPersistenceError) as caught:
        persist(engine, data)
    assert caught.value.code == "incomplete_disabled" and caught.value.incomplete is True
    assert counts(engine) == (0, 0)
    result = persist(engine, data, allow_incomplete=True)
    assert result.inserted == 1 and result.incomplete and result.stop_reason == reason
    assert result.limited == (reason == "max_pages")


@pytest.mark.parametrize("identifier", [1, 3])
def test_existing_operational_roles_are_allowed(engine, identifier):
    assert persist(engine, current_user=actor(identifier)).inserted == 1


@pytest.mark.parametrize("context", [actor(4), actor(1, tenant_id=20), actor(1, rol="admin_tenant"), actor(99)])
def test_context_cannot_impersonate_other_tenant_role_or_general_administrator(engine, context):
    with pytest.raises(ExternalReviewPersistenceError) as caught:
        persist(engine, current_user=context)
    assert caught.value.code == "unauthorized_context" and counts(engine) == (0, 0)


@pytest.mark.parametrize("model,identifier", [(User, 1), (Tenant, 10)])
def test_current_database_state_blocks_inactive_actor_or_tenant(engine, model, identifier):
    with Session(engine) as db:
        db.get(model, identifier).estado = "inactivo"
        db.commit()
    with pytest.raises(ExternalReviewPersistenceError) as caught:
        persist(engine)
    assert caught.value.code == "unauthorized_context" and counts(engine) == (0, 0)


def test_foreign_and_missing_connection_are_indistinguishable(engine):
    with Session(engine) as db:
        db.delete(db.get(ExternalReviewConnection, (10, "Google", BUSINESS)))
        db.commit()
    errors = []
    for business in (BUSINESS, "0x111:0x222"):
        with pytest.raises(ExternalReviewPersistenceError) as caught:
            persist(engine, batch([row()], business=business), business=business)
        errors.append((caught.value.code, str(caught.value)))
    assert errors[0] == errors[1] and errors[0][0] == "connection_unavailable"
    assert counts(engine) == (0, 0)


def test_disabled_connection_and_server_default_do_not_allow_persistence(engine):
    with Session(engine) as db:
        configured = db.get(ExternalReviewConnection, (10, "Google", BUSINESS))
        configured.persistence_enabled = False
        db.add(ExternalReviewConnection(tenant_id=10, source="Google", business_data_id="0x1:0x2"))
        db.commit()
        assert db.get(ExternalReviewConnection, (10, "Google", "0x1:0x2")).persistence_enabled is False
    with pytest.raises(ExternalReviewPersistenceError) as caught:
        persist(engine)
    assert caught.value.code == "persistence_disabled" and counts(engine) == (0, 0)


def test_database_rejects_activation_without_approval_reference(engine):
    with Session(engine) as db:
        db.add(ExternalReviewConnection(tenant_id=10, source="Google", business_data_id="0x1:0x2", persistence_enabled=True))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


@pytest.mark.parametrize("tenant,business", [(20, BUSINESS), (10, "0x111:0x222")])
def test_composite_foreign_keys_prevent_cross_tenant_and_unregistered_connection(engine, tenant, business):
    persist(engine)
    with Session(engine) as db:
        identity = db.scalar(select(ExternalReviewIdentity))
        identity.tenant_id, identity.business_data_id = tenant, business
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    assert counts(engine) == (1, 1)


def test_database_unique_constraint_prevents_duplicate_without_prequery(engine):
    persist(engine)
    with Session(engine) as db:
        duplicate = Review(tenant_id=10, contenido="synthetic", fecha=datetime(2026, 1, 1), fuente="Google", puntuacion=4, estado="nueva")
        db.add(duplicate)
        db.flush()
        db.add(ExternalReviewIdentity(review_id=duplicate.id, tenant_id=10, source="Google", business_data_id=BUSINESS,
                                     external_review_id="synthetic-review", import_fingerprint="v1:" + "a" * 64))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    assert counts(engine) == (1, 1)


def test_foreign_keys_prevent_orphan_review_and_tenant_reassignment(engine):
    persist(engine)
    for operation in ("delete", "reassign"):
        with Session(engine) as db:
            saved = db.scalar(select(Review))
            if operation == "delete":
                db.delete(saved)
            else:
                saved.tenant_id = 20
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
    assert counts(engine) == (1, 1)


@pytest.mark.parametrize("fail_on", [1, 2])
def test_error_after_review_flush_rolls_back_entire_batch_and_allows_rerun(engine, monkeypatch, fail_on):
    original = ReviewRepository.add_external_review
    calls = []

    def fail(self, review, **kwargs):
        calls.append(1)
        if len(calls) == fail_on:
            self.db.add(review)
            self.db.flush()
            raise SQLAlchemyError(PRIVATE)
        return original(self, review, **kwargs)

    data = batch([row("a"), row("b")])
    with monkeypatch.context() as patch:
        patch.setattr(ReviewRepository, "add_external_review", fail)
        with pytest.raises(ExternalReviewPersistenceError) as caught:
            persist(engine, data)
    assert caught.value.outcome == "rolled_back" and caught.value.committed_count == 0
    assert PRIVATE not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__context__ is None and counts(engine) == (0, 0)
    assert persist(engine, data).inserted == 2 and counts(engine) == (2, 2)


@pytest.mark.parametrize("after_commit", [False, True])
def test_uncertain_commit_is_reported_without_claiming_zero_and_rerun_is_safe(engine, monkeypatch, after_commit):
    with Session(engine) as db:
        original = db.commit

        def fail():
            if after_commit:
                original()
            raise SQLAlchemyError(PRIVATE)

        with monkeypatch.context() as patch:
            patch.setattr(db, "commit", fail)
            with pytest.raises(ExternalReviewPersistenceError) as caught:
                ExternalReviewPersistenceService(ReviewRepository(db)).persist(batch([row()]), current_user=actor(), business_data_id=BUSINESS)
        assert caught.value.code == "commit_unknown" and caught.value.outcome == "unknown"
        assert caught.value.committed_count is None and caught.value.retryable
        assert PRIVATE not in repr(caught.value) and PRIVATE not in "".join(traceback.format_exception(caught.value))
    assert counts(engine) == ((1, 1) if after_commit else (0, 0))
    result = persist(engine)
    assert (result.inserted, result.repeated) == ((0, 1) if after_commit else (1, 0))
    assert counts(engine) == (1, 1)


def test_confirmed_commit_integrity_failure_rolls_back(engine, monkeypatch):
    with Session(engine) as db:
        def fail():
            raise IntegrityError("synthetic-statement", {"synthetic": PRIVATE}, Exception(PRIVATE))
        monkeypatch.setattr(db, "commit", fail)
        with pytest.raises(ExternalReviewPersistenceError) as caught:
            ExternalReviewPersistenceService(ReviewRepository(db)).persist(batch([row()]), current_user=actor(), business_data_id=BUSINESS)
    assert caught.value.code == "integrity" and caught.value.outcome == "rolled_back"
    assert counts(engine) == (0, 0)


def test_unique_collision_rolls_back_candidate_review_without_orphan(engine, monkeypatch):
    persist(engine)
    with monkeypatch.context() as patch:
        patch.setattr(ReviewRepository, "get_external_fingerprint", lambda *_: None)
        with pytest.raises(ExternalReviewPersistenceError) as caught:
            persist(engine)
    assert caught.value.code == "concurrent_conflict" and caught.value.retryable
    assert counts(engine) == (1, 1) and persist(engine).repeated == 1


def test_two_concurrent_imports_use_independent_sessions_without_duplicates(engine):
    barrier = Barrier(2)
    def run(_):
        barrier.wait(timeout=10)
        return persist(engine)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run, range(2)))
    assert sorted((item.inserted, item.repeated) for item in results) == [(0, 1), (1, 0)]
    assert counts(engine) == (1, 1)


def test_session_with_pending_work_is_rejected_without_rolling_back_that_work(engine):
    with Session(engine, autoflush=False) as db:
        pending = Tenant(nombre="synthetic-pending", estado="activo")
        db.add(pending)
        with pytest.raises(ExternalReviewPersistenceError) as caught:
            ExternalReviewPersistenceService(ReviewRepository(db)).persist(batch([row()]), current_user=actor(), business_data_id=BUSINESS)
        assert caught.value.code == "session_in_use" and pending in db.new
        db.rollback()
    assert counts(engine) == (0, 0)


def test_sqlite_service_refuses_foreign_keys_disabled(engine):
    with Session(engine) as db:
        db.connection().exec_driver_sql("PRAGMA foreign_keys=OFF")
        db.commit()
        with pytest.raises(ExternalReviewPersistenceError) as caught:
            ExternalReviewPersistenceService(ReviewRepository(db)).persist(batch([row()]), current_user=actor(), business_data_id=BUSINESS)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    assert caught.value.code == "foreign_keys_disabled" and counts(engine) == (0, 0)


@pytest.mark.parametrize("prior_work", ["auth-read", "flushed-write", "explicit-begin", "savepoint"])
def test_existing_transactions_are_neither_nested_committed_nor_rolled_back(engine, prior_work):
    with Session(engine) as db:
        if prior_work == "auth-read":
            db.get(User, 1)
        elif prior_work == "flushed-write":
            db.add(Tenant(nombre="synthetic-flushed-unrelated", estado="activo"))
            db.flush()
            assert not db.new
        elif prior_work == "explicit-begin":
            db.begin()
        else:
            db.begin_nested()
        transaction = db.get_transaction()
        with pytest.raises(ExternalReviewPersistenceError) as caught:
            ExternalReviewPersistenceService(ReviewRepository(db)).persist(batch([row()]), current_user=actor(), business_data_id=BUSINESS)
        assert caught.value.code == "session_in_use"
        assert db.get_transaction() is transaction and transaction.is_active
        db.rollback()
    assert counts(engine) == (0, 0)


def test_session_bound_to_external_connection_cannot_report_a_false_commit(engine):
    with engine.begin() as connection:
        with Session(bind=connection) as db:
            with pytest.raises(ExternalReviewPersistenceError) as caught:
                ExternalReviewPersistenceService(ReviewRepository(db)).persist(batch([row()]), current_user=actor(), business_data_id=BUSINESS)
            assert caught.value.code == "session_in_use" and connection.in_transaction()
    assert counts(engine) == (0, 0)


def test_sqlite_busy_is_confirmed_retryable_failure_without_automatic_retry(engine):
    with engine.connect() as locked:
        locked.exec_driver_sql("BEGIN IMMEDIATE")
        with Session(engine) as db:
            db.connection().exec_driver_sql("PRAGMA busy_timeout=0")
            db.commit()
            with pytest.raises(ExternalReviewPersistenceError) as caught:
                ExternalReviewPersistenceService(ReviewRepository(db)).persist(batch([row()]), current_user=actor(), business_data_id=BUSINESS)
            assert caught.value.code == "database_busy" and caught.value.outcome == "rolled_back"
            assert caught.value.retryable and caught.value.committed_count == 0
        locked.rollback()
    assert counts(engine) == (0, 0)
    assert persist(engine).inserted == 1


@pytest.mark.parametrize("state", ["40001", "40P01"])
def test_postgresql_retryable_error_classification_without_claiming_server_test(engine, monkeypatch, state):
    class SyntheticDriverError(Exception):
        sqlstate = state
    def fail(*_, **__):
        raise OperationalError("synthetic", {"value": PRIVATE}, SyntheticDriverError(PRIVATE))
    monkeypatch.setattr(ReviewRepository, "add_external_review", fail)
    with pytest.raises(ExternalReviewPersistenceError) as caught:
        persist(engine)
    assert caught.value.code == "concurrent_conflict" and caught.value.outcome == "rolled_back"
    assert PRIVATE not in "".join(traceback.format_exception(caught.value))
    assert counts(engine) == (0, 0)


def altered_batch(**changes):
    original = batch([row()])
    return replace(original, with_text=(replace(original.with_text[0], **changes),))


@pytest.mark.parametrize("changes", [
    {"external_review_id": None}, {"external_review_id": ""}, {"external_review_id": []},
    {"external_review_id": "x" * 513}, {"external_review_id": "\U0001f600" * 257},
    {"external_review_id": "\ud800"}, {"external_review_id": "x\x00y"},
    {"author": "x" * 256}, {"author": {}}, {"author": "x\x00y"}, {"author": "\ud800"},
    {"content": "x" * 65537}, {"content": "\u00e9" * 32769}, {"content": []},
    {"content": "x\x00y"}, {"content": "\ud800"}, {"content": None}, {"content": " "},
    {"review_date": datetime(2026, 1, 1)}, {"review_date": "2026-01-01T00:00:00Z"},
    {"review_date": datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=2)))},
    {"rating": True}, {"rating": 0}, {"rating": 6}, {"rating": 4.0}, {"rating": float("nan")},
    {"source": "SerpApi"}, {"business_data_id": OTHER_BUSINESS}, {"content_field": PRIVATE},
    {"position": RecordPosition(1, 1, 1000)},
])
def test_normalized_dto_is_revalidated_before_any_database_write(engine, changes):
    with pytest.raises(ExternalReviewPersistenceError) as caught:
        persist(engine, altered_batch(**changes))
    assert caught.value.code in ("invalid_record", "invalid_batch")
    assert PRIVATE not in str(caught.value) and counts(engine) == (0, 0)


@pytest.mark.parametrize("identity,content", [("x" * 512, "x" * 65536), ("\u00e9" * 512, "\u00e9" * 32768), ("\U0001f600" * 256, "synthetic")], ids=["ascii-boundary", "two-byte-boundary", "four-byte-boundary"])
def test_exact_character_and_utf8_byte_boundaries_are_accepted(engine, identity, content):
    result = persist(engine, batch([row(identity, snippet=content)]))
    assert result.inserted == 1 and counts(engine) == (1, 1)


def test_batch_occurrence_and_aggregate_text_limits(engine):
    with pytest.raises(ExternalReviewPersistenceError) as caught:
        persist(engine, batch([row(str(i)) for i in range(101)]))
    assert caught.value.code == "batch_limit"
    with pytest.raises(ExternalReviewPersistenceError) as caught:
        persist(engine, batch([row(str(i), snippet="x" * 60000) for i in range(20)]))
    assert caught.value.code == "text_budget" and counts(engine) == (0, 0)
    result = persist(engine, batch([row(str(i)) for i in range(100)]))
    assert result.inserted == 100 and counts(engine) == (100, 100)


@pytest.mark.parametrize("business", [None, "", [], "invalid", "0x" + "a" * 125 + ":0x1", "0x1:0x2\x00"], ids=["missing", "empty", "list", "format", "too-long", "nul"])
def test_invalid_business_is_rejected_before_access(engine, business):
    with pytest.raises(ExternalReviewPersistenceError) as caught:
        persist(engine, business=business)
    assert caught.value.code == "invalid_business" and counts(engine) == (0, 0)


def test_forged_diagnostics_counters_and_duplicate_positions_are_rejected(engine):
    original = batch([row()])
    forged = [replace(original, input_count=2), replace(original, with_text=(original.with_text[0], original.with_text[0]), input_count=2),
              replace(original, warnings=(NormalizationIssue(original.with_text[0].position, PRIVATE, "missing_author"),)),
              replace(original, incomplete=False, stop_reason="error")]
    for data in forged:
        with pytest.raises(ExternalReviewPersistenceError) as caught:
            persist(engine, data)
        assert PRIVATE not in repr(caught.value)
    assert counts(engine) == (0, 0)


def test_diagnostics_and_debug_sql_logs_do_not_expose_values(engine, caplog):
    caplog.set_level(logging.DEBUG, logger="sqlalchemy.engine")
    result = persist(engine, batch([row(PRIVATE, snippet=PRIVATE, user={"name": PRIVATE}), row("empty", snippet=None)]))
    assert PRIVATE not in repr(result) and PRIVATE not in caplog.text
    assert result.warnings[0].code == "missing_content"
    assert engine.hide_parameters


def logging_configuration():
    names = (None, "sqlalchemy.engine", "sqlalchemy.engine.Engine", "synthetic.other_component")
    return tuple((logger.level, logger.disabled, logger.propagate, tuple(logger.handlers), tuple(logger.filters))
                 for logger in (logging.getLogger(name) for name in names))


@pytest.mark.parametrize("hide_parameters", [True, False], ids=["default-engine", "injected-engine"])
def test_debug_logging_redacts_connection_rows_review_rows_and_sql_parameters(engine, caplog, hide_parameters):
    markers = {name: "synthetic-sensitive-" + name for name in ("id", "author", "content", "approval", "edited", "summary", "foreign")}
    persist(engine, batch([row(markers["id"], snippet=markers["content"], user={"name": markers["author"]})]))
    persist(engine, batch([row(markers["foreign"], snippet=markers["foreign"])]), current_user=actor(2))
    with Session(engine) as db:
        db.get(ExternalReviewConnection, (10, "Google", BUSINESS)).approval_reference = markers["approval"]
        identifier = db.scalar(select(Review.id).where(Review.tenant_id == 10))
        db.commit()
    engine.hide_parameters = hide_parameters  # La corrección no depende de esta opción del llamador.
    caplog.set_level(logging.DEBUG, logger="sqlalchemy.engine")
    config = logging_configuration()
    with Session(engine) as db:
        repo = ReviewRepository(db)
        connection = repo.get_external_connection(10, BUSINESS)
        assert connection.approval_reference == markers["approval"]
        fingerprint = repo.get_external_fingerprint(10, BUSINESS, markers["id"])
        assert fingerprint.startswith("v1:")
        assert repo.external_actor_is_active(1, 10, "usuario_negocio")
        assert repo.get_by_id_for_tenant(identifier, 20) is None
        assert len(repo.list_by_tenant(10, markers["content"])) == 1
        assert repo.count_by_tenant(10) == repo.count_new_by_tenant(10) == 1
        assert repo.average_score_by_tenant(10) == 4
        saved = repo.list_recent_by_tenant(10)[0]
        assert saved.contenido == markers["content"] and saved.autor == markers["author"]
        assert all(marker not in repr(saved) + repr(connection) for marker in markers.values())
        saved = repo.update(saved, {"contenido": markers["edited"]})
        assert saved.contenido == markers["edited"]
        saved = repo.update_status(saved, ReviewStatus.ATENDIDA)
        assert saved.estado == "atendida"
        saved = repo.save_ai_result(identifier, 10, SummaryResult(resumen=markers["summary"]))
        assert saved.resumen == markers["summary"]
        def manual():
            return Review(tenant_id=10, autor=markers["author"], contenido=markers["content"],
                          fecha=datetime(2026, 1, 1), fuente="manual", puntuacion=3, estado="nueva")
        assert repo.create(manual()).id is not None
        assert len(repo.create_many([manual()])) == 1
        assert repo.count_by_tenant(10) == 3
    assert persist(engine, batch([row(markers["id"] + "-new", snippet=markers["content"],
                                    user={"name": markers["author"]})])).inserted == 1
    assert logging_configuration() == config and engine.hide_parameters is hide_parameters
    assert not any(marker in caplog.text for marker in (*markers.values(), BUSINESS, fingerprint))
    assert "ReviewRepository get_external_connection" in caplog.text
    assert "ReviewRepository update: SQL" in caplog.text
    assert "[details redacted]" in caplog.text


@pytest.mark.parametrize("fail", [False, True], ids=["success", "exception"])
def test_repository_logging_guard_is_scoped_and_restored(engine, caplog, monkeypatch, fail):
    caplog.set_level(logging.DEBUG, logger="sqlalchemy.engine")
    caplog.set_level(logging.DEBUG, logger="synthetic.other_component")
    config = logging_configuration()
    with Session(engine) as db:
        connection = db.connection()
        original_listeners = tuple(db.dispatch.after_begin)
        original_attributes = {name: (name in connection.__dict__, connection.__dict__.get(name))
                               for name in ("_log_info", "_log_debug")}
        original_scalar = db.scalar
        def query(*args, **kwargs):
            logging.getLogger("synthetic.other_component").debug("synthetic-public-technical-record")
            # Otra conexión del mismo Engine mantiene su instrumentación normal.
            with engine.connect() as other:
                assert other.scalar(select(literal("synthetic-public-other-connection"))) == "synthetic-public-other-connection"
            if fail:
                raise SQLAlchemyError("synthetic-forced-query-failure")
            return original_scalar(*args, **kwargs)
        with monkeypatch.context() as patch:
            patch.setattr(db, "scalar", query)
            if fail:
                with pytest.raises(SQLAlchemyError):
                    ReviewRepository(db).get_external_connection(10, BUSINESS)
            else:
                assert ReviewRepository(db).get_external_connection(10, BUSINESS) is not None
        assert "_review_private_sql" not in db.info
        assert tuple(db.dispatch.after_begin) == original_listeners
        assert {name: (name in connection.__dict__, connection.__dict__.get(name))
                for name in original_attributes} == original_attributes
        assert connection.scalar(select(literal("synthetic-public-after-operation"))) == "synthetic-public-after-operation"
    assert logging_configuration() == config
    assert "synthetic-public-technical-record" in caplog.text
    assert "synthetic-public-other-connection" in caplog.text
    assert "synthetic-public-after-operation" in caplog.text
    assert BUSINESS not in caplog.text


def test_service_import_is_independent_of_http_gemini_and_default_database():
    script = r'''
import importlib.abc,sys
sys.path.insert(0,sys.argv[1])
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self,name,path=None,target=None):
        forbidden=('httpx','httpcore','google','app.services.ai_provider','app.services.serpapi_client','app.db.connection')
        if any(name==p or name.startswith(p+'.') for p in forbidden):
            raise AssertionError('Forbidden service import')
sys.meta_path.insert(0,Guard())
from app.services.external_review_persistence_service import ExternalReviewPersistenceService
print('isolated-service-import-ok')
'''
    completed = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(Path(__file__).resolve().parents[1])], capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "isolated-service-import-ok"
