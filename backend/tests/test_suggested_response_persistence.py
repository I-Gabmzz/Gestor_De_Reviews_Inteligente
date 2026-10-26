"""HU-18/T3: evolución, invalidación y concurrencia con bases aisladas."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateColumn
from sqlalchemy.sql.dml import Update

from app.db.init_db import init_db
from app.models.review import Review
from app.models.tenant import Tenant
from app.repositories.review_repository import ReviewRepository
from app.schemas.ai import ClassificationResult, SummaryResult, TopicResult
from app.schemas.suggested_response import SuggestedResponseResult
from app.services.suggested_response_analysis_service import (
    SuggestedResponseAnalysisService, SuggestedResponseConflictError,
    SuggestedResponsePersistenceError,
)
from app.services.suggested_response_service import SuggestedResponseService


@pytest.fixture()
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'suggestions.db'}")
    init_db(engine)
    with Session(engine) as db:
        db.add_all([
            Tenant(id=10, nombre="Principal ficticio", estado="activo"),
            Tenant(id=20, nombre="Ajeno ficticio", estado="activo"),
        ])
        db.flush()
        for review_id, tenant_id in ((101, 10), (201, 20)):
            db.add(Review(
                id=review_id, tenant_id=tenant_id, contenido="El pedido tardó.",
                fecha=datetime(2026, 10, 19), fuente="manual", puntuacion=2,
                estado="en_revision", categoria="Queja", resumen="Resumen previo",
                tema="Servicio", prioridad="Alta", respuesta_sugerida="Sugerencia previa.",
            ))
        db.commit()
    yield engine
    engine.dispose()


def result(text="Lamentamos la demora que describes."):
    return SuggestedResponseResult(respuesta_sugerida=text)


@pytest.fixture()
def legacy_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-suggestions.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE tenants (id INTEGER PRIMARY KEY, nombre VARCHAR(255) NOT NULL, estado VARCHAR(50) NOT NULL)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE reviews (id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id), "
            "autor VARCHAR(255), contenido TEXT NOT NULL, fecha DATETIME NOT NULL, "
            "fuente VARCHAR(100) NOT NULL, puntuacion INTEGER NOT NULL, estado VARCHAR(50) NOT NULL, "
            "categoria VARCHAR(50), prioridad VARCHAR(50), resumen TEXT, tema TEXT)"
        )
        connection.exec_driver_sql("CREATE INDEX ix_legacy_tenant ON reviews(tenant_id)")
        connection.exec_driver_sql("INSERT INTO tenants VALUES (10, 'Anterior ficticio', 'activo')")
        connection.exec_driver_sql(
            "INSERT INTO reviews VALUES (101, 10, 'Cliente ficticio', 'Comentario previo', "
            "'2026-10-19 12:00:00', 'manual', 2, 'en_revision', 'Queja', 'Alta', 'Resumen previo', 'Servicio')"
        )
    yield engine
    engine.dispose()


def test_migration_is_additive_idempotent_and_preserves_existing_values(legacy_database):
    with legacy_database.connect() as connection:
        before = dict(connection.exec_driver_sql("SELECT * FROM reviews").mappings().one())
    init_db(legacy_database)
    init_db(legacy_database)
    with legacy_database.connect() as connection:
        after = dict(connection.exec_driver_sql("SELECT * FROM reviews").mappings().one())
        assert after == before | {"respuesta_sugerida": None, "respuesta_sugerida_version": 0}
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    assert any(index["name"] == "ix_legacy_tenant" for index in inspect(legacy_database).get_indexes("reviews"))


@pytest.mark.parametrize("existing", ["respuesta_sugerida", "respuesta_sugerida_version"])
def test_partial_migration_preserves_existing_column(legacy_database, existing):
    with legacy_database.begin() as connection:
        if existing == "respuesta_sugerida":
            connection.exec_driver_sql("ALTER TABLE reviews ADD COLUMN respuesta_sugerida TEXT")
            connection.exec_driver_sql("UPDATE reviews SET respuesta_sugerida='Borrador previo'")
        else:
            connection.exec_driver_sql("ALTER TABLE reviews ADD COLUMN respuesta_sugerida_version INTEGER NOT NULL DEFAULT 7")
    init_db(legacy_database)
    with Session(legacy_database) as db:
        review = db.get(Review, 101)
        assert review.respuesta_sugerida == ("Borrador previo" if existing == "respuesta_sugerida" else None)
        assert review.respuesta_sugerida_version == (7 if existing == "respuesta_sugerida_version" else 0)


def test_concurrent_initialization_adds_columns_once(legacy_database):
    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(lambda _: init_db(legacy_database), range(2)))
    assert {column["name"] for column in inspect(legacy_database).get_columns("reviews")} >= {
        "respuesta_sugerida", "respuesta_sugerida_version",
    }


def test_result_survives_new_session_and_keeps_other_fields(database):
    with Session(database) as db:
        saved = ReviewRepository(db).save_suggested_response(
            101, 10, result(), expected_content="El pedido tardó.", expected_version=0,
        )
        assert saved.respuesta_sugerida == result().respuesta_sugerida
        assert saved.respuesta_sugerida_version == 1
        assert (saved.estado, saved.categoria, saved.resumen, saved.tema, saved.prioridad) == (
            "en_revision", "Queja", "Resumen previo", "Servicio", "Alta",
        )
    with Session(database) as db:
        assert db.get(Review, 101).respuesta_sugerida == result().respuesta_sugerida
        assert db.get(Review, 201).respuesta_sugerida == "Sugerencia previa."


@pytest.mark.parametrize("review_id,tenant_id", [(201, 10), (101, 20), (999, 10)])
def test_repository_cannot_write_foreign_or_missing_review(database, review_id, tenant_id):
    with Session(database) as db:
        assert ReviewRepository(db).save_suggested_response(
            review_id, tenant_id, result(), expected_content="El pedido tardó.", expected_version=0,
        ) is None
    with Session(database) as db:
        assert db.get(Review, 101).respuesta_sugerida == "Sugerencia previa."
        assert db.get(Review, 201).respuesta_sugerida == "Sugerencia previa."


def test_repository_revalidates_and_does_not_accept_other_results(database):
    with Session(database) as db:
        repository = ReviewRepository(db)
        with pytest.raises(ValidationError):
            repository.save_suggested_response(
                101, 10, SuggestedResponseResult.model_construct(respuesta_sugerida=""),
                expected_content="El pedido tardó.", expected_version=0,
            )
        with pytest.raises(TypeError):
            repository.save_suggested_response(
                101, 10, SummaryResult(resumen="Otro resultado"),
                expected_content="El pedido tardó.", expected_version=0,
            )


def test_same_version_cannot_replace_a_concurrently_saved_result(database):
    with Session(database, expire_on_commit=False) as first, Session(database) as second:
        stale = first.get(Review, 101)
        version = stale.respuesta_sugerida_version
        content = stale.contenido
        ReviewRepository(second).save_suggested_response(
            101, 10, result("Ganó la otra solicitud."), expected_content=content, expected_version=version,
        )
        assert ReviewRepository(first).save_suggested_response(
            101, 10, result("Resultado tardío."), expected_content=content, expected_version=version,
        ) is None
    with Session(database) as db:
        assert db.get(Review, 101).respuesta_sugerida == "Ganó la otra solicitud."


def test_concurrent_identical_results_also_advance_version(database):
    with Session(database) as db:
        repository = ReviewRepository(db)
        assert repository.save_suggested_response(
            101, 10, result("Sugerencia previa."), expected_content="El pedido tardó.", expected_version=0,
        ) is not None
        assert repository.save_suggested_response(
            101, 10, result("Resultado anterior en vuelo."), expected_content="El pedido tardó.", expected_version=0,
        ) is None


def test_two_simultaneous_generations_have_one_winner_and_one_conflict(database):
    barrier = Barrier(2)

    def generate(text):
        generator = Mock(spec=SuggestedResponseService)

        def wait_for_other(content):
            assert content == "El pedido tardó."
            barrier.wait(timeout=10)
            return result(text)

        generator.generate.side_effect = wait_for_other
        with Session(database) as db:
            try:
                saved = SuggestedResponseAnalysisService(ReviewRepository(db), generator).generate_for_review(101, 10)
                return ("saved", saved.respuesta_sugerida)
            except SuggestedResponseConflictError:
                return ("conflict", None)

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(generate, ["Sugerencia A.", "Sugerencia B."]))
    assert sorted(state for state, _ in outcomes) == ["conflict", "saved"]
    winner = next(text for state, text in outcomes if state == "saved")
    with Session(database) as db:
        assert db.get(Review, 101).respuesta_sugerida == winner
        assert db.get(Review, 101).respuesta_sugerida_version == 1


def test_stale_edit_of_same_local_content_checks_current_database_value(database):
    with Session(database, expire_on_commit=False) as first, Session(database) as second:
        stale = first.get(Review, 101)
        ReviewRepository(second).update(second.get(Review, 101), {"contenido": "Contenido cambiado."})
        ReviewRepository(second).save_suggested_response(
            101, 10, result(), expected_content="Contenido cambiado.", expected_version=1,
        )
        saved = ReviewRepository(first).update(stale, {"contenido": "El pedido tardó."})
        assert saved.respuesta_sugerida is None
        assert saved.respuesta_sugerida_version == 3


def test_stale_edit_to_current_content_does_not_invalidate_a_new_suggestion(database):
    with Session(database, expire_on_commit=False) as first, Session(database) as second:
        stale = first.get(Review, 101)
        ReviewRepository(second).update(second.get(Review, 101), {"contenido": "Contenido cambiado."})
        ReviewRepository(second).save_suggested_response(
            101, 10, result(), expected_content="Contenido cambiado.", expected_version=1,
        )
        saved = ReviewRepository(first).update(stale, {"contenido": "Contenido cambiado."})
        assert saved.respuesta_sugerida == result().respuesta_sugerida
        assert saved.respuesta_sugerida_version == 2


def test_other_ai_operations_preserve_suggestion_and_counter(database):
    with Session(database) as db:
        repository = ReviewRepository(db)
        for value in (
            ClassificationResult(categoria="Consulta"), SummaryResult(resumen="Otro resumen"),
            TopicResult(tema="Producto"),
        ):
            saved = repository.save_ai_result(101, 10, value)
            assert saved.respuesta_sugerida == "Sugerencia previa."
            assert saved.respuesta_sugerida_version == 0


@pytest.mark.parametrize("operation", ["read", "write"])
def test_orchestration_controls_database_errors_without_exposing_details(operation):
    repository = Mock(spec=ReviewRepository)
    generator = Mock(spec=SuggestedResponseService)
    generator.generate.return_value = result()
    error = SQLAlchemyError("synthetic-private-database-detail")
    if operation == "read":
        repository.get_by_id_for_tenant.side_effect = error
    else:
        review = Mock(contenido="El pedido tardó.", respuesta_sugerida_version=0)
        repository.get_by_id_for_tenant.return_value = review
        repository.save_suggested_response.side_effect = error
    with pytest.raises(SuggestedResponsePersistenceError) as caught:
        SuggestedResponseAnalysisService(repository, generator).generate_for_review(101, 10)
    assert "synthetic-private-database-detail" not in str(caught.value)
    if operation == "read":
        generator.generate.assert_not_called()


def test_postgresql_ddl_and_conditional_updates_compile_without_a_server(database, monkeypatch):
    dialect = postgresql.dialect()
    for name in ("respuesta_sugerida", "respuesta_sugerida_version"):
        assert name in str(CreateColumn(Review.__table__.c[name]).compile(dialect=dialect))
    statements = []
    with Session(database) as db:
        execute = db.execute

        def capture(statement, *args, **kwargs):
            if isinstance(statement, Update):
                statements.append(statement)
            return execute(statement, *args, **kwargs)

        monkeypatch.setattr(db, "execute", capture)
        repository = ReviewRepository(db)
        repository.save_suggested_response(
            101, 10, result(), expected_content="El pedido tardó.", expected_version=0,
        )
        repository.update(db.get(Review, 101), {"contenido": "Texto corregido."})
    compiled = [str(statement.compile(dialect=dialect)) for statement in statements]
    assert len(compiled) == 2
    assert all("tenant_id" in sql and "respuesta_sugerida_version" in sql for sql in compiled)
    assert "CASE WHEN" in compiled[1]
