"""Contrato común, actualización de bases existentes y aislamiento de resultados."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.init_db import init_db
from app.models.review import Review
from app.models.tenant import Tenant
from app.repositories.review_repository import ReviewRepository
from app.schemas.ai import AIResponse, ClassificationResult, SummaryResult, TopicResult
from app.schemas.review import ReviewRead


@pytest.fixture()
def legacy_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql(
            "CREATE TABLE tenants (id INTEGER PRIMARY KEY, nombre VARCHAR(255) NOT NULL, "
            "estado VARCHAR(50) NOT NULL)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE reviews (id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL "
            "REFERENCES tenants(id), autor VARCHAR(255), contenido TEXT NOT NULL, "
            "fecha DATETIME NOT NULL, fuente VARCHAR(100) NOT NULL, "
            "puntuacion INTEGER NOT NULL, estado VARCHAR(50) NOT NULL, "
            "categoria VARCHAR(50), prioridad VARCHAR(50))"
        )
        connection.exec_driver_sql("CREATE INDEX ix_legacy_reviews_tenant ON reviews(tenant_id)")
        connection.exec_driver_sql("INSERT INTO tenants VALUES (10, 'Negocio previo', 'activo')")
        connection.exec_driver_sql(
            "INSERT INTO reviews VALUES (101, 10, 'Ana', 'Contenido previo', "
            "'2026-10-12 10:00:00', 'Google', 2, 'en_revision', 'Categoria anterior', 'Alta')"
        )
    yield engine
    engine.dispose()


def test_migration_preserves_legacy_rows_columns_indexes_and_foreign_keys(legacy_engine):
    with legacy_engine.connect() as connection:
        before = dict(connection.exec_driver_sql("SELECT * FROM reviews").mappings().one())
    init_db(legacy_engine)
    init_db(legacy_engine)
    with legacy_engine.connect() as connection:
        after = dict(connection.exec_driver_sql("SELECT * FROM reviews").mappings().one())
        assert after == before | {"resumen": None, "tema": None, "solucion": None}
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert connection.exec_driver_sql("SELECT count(*) FROM tenants").scalar_one() == 1
    inspector = inspect(legacy_engine)
    assert any(index["name"] == "ix_legacy_reviews_tenant" for index in inspector.get_indexes("reviews"))
    assert inspector.get_foreign_keys("reviews")[0]["referred_table"] == "tenants"
    with Session(legacy_engine) as db:
        read = ReviewRead.model_validate(db.get(Review, 101))
        assert read.categoria == "Categoria anterior"  # No se reescriben categorías antiguas.
        assert read.resumen is read.tema is None


def test_migration_completes_partial_upgrade_without_replacing_results(legacy_engine):
    with legacy_engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE reviews ADD COLUMN resumen TEXT")
        connection.exec_driver_sql("UPDATE reviews SET resumen='Resumen previo'")
    init_db(legacy_engine)
    with legacy_engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT resumen, tema FROM reviews").one() == (
            "Resumen previo", None
        )


def test_simultaneous_startups_serialize_sqlite_migration(legacy_engine):
    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(lambda _: init_db(legacy_engine), range(2)))
    assert {column["name"] for column in inspect(legacy_engine).get_columns("reviews")} >= {
        "resumen", "tema"
    }


@pytest.fixture()
def result_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'results.db'}")
    init_db(engine)
    with Session(engine) as db:
        db.add_all([
            Tenant(id=10, nombre="Principal", estado="activo"),
            Tenant(id=20, nombre="Otro negocio", estado="activo"),
        ])
        db.flush()
        for review_id, tenant_id in ((101, 10), (102, 10), (201, 20)):
            db.add(Review(
                id=review_id, tenant_id=tenant_id, autor="Ana", contenido="Servicio lento",
                fecha=datetime(2026, 10, 17), fuente="Google", puntuacion=2,
                estado="en_revision", prioridad="Alta",
            ))
        db.commit()
    yield engine
    engine.dispose()


def test_fresh_database_and_independent_results_survive_new_session(result_engine):
    with Session(result_engine) as db:
        repository = ReviewRepository(db)
        before = ReviewRead.model_validate(repository.get_by_id_for_tenant(101, 10)).model_dump()
        assert before["categoria"] is before["resumen"] is before["tema"] is None
        expected = before
        for result in (
            SummaryResult(resumen="El cliente señala lentitud."),
            TopicResult(tema="Atención al cliente"),
            ClassificationResult(categoria="Queja"),
            SummaryResult(resumen="Resumen regenerado."),
        ):
            saved = repository.save_ai_result(101, 10, result)
            expected = expected | result.model_dump()
            assert ReviewRead.model_validate(saved).model_dump() == expected
    init_db(result_engine)
    with Session(result_engine) as db:
        assert ReviewRead.model_validate(db.get(Review, 101)).model_dump() == expected
        for review_id in (102, 201):
            untouched = db.get(Review, review_id)
            assert untouched.categoria is untouched.resumen is untouched.tema is None


def test_two_sessions_updating_different_results_do_not_lose_values(result_engine):
    with Session(result_engine, expire_on_commit=False) as first, Session(result_engine) as second:
        stale = first.get(Review, 101)
        ReviewRepository(second).save_ai_result(101, 10, SummaryResult(resumen="Resumen nuevo"))
        saved = ReviewRepository(first).save_ai_result(101, 10, TopicResult(tema="Servicio"))
        assert saved is stale
        assert saved.resumen == "Resumen nuevo"
        assert saved.tema == "Servicio"


@pytest.mark.parametrize("review_id", [201, 999])
def test_result_write_for_foreign_or_missing_review_returns_none(result_engine, review_id):
    with Session(result_engine) as db:
        assert ReviewRepository(db).save_ai_result(
            review_id, 10, ClassificationResult(categoria="Queja")
        ) is None
    with Session(result_engine) as db:
        assert db.get(Review, 201).categoria is None


def test_failed_commit_rolls_back_result_and_keeps_session_usable(result_engine, monkeypatch):
    with Session(result_engine) as db:
        repository = ReviewRepository(db)
        repository.save_ai_result(101, 10, SummaryResult(resumen="Resumen conservado"))
        with monkeypatch.context() as patch:
            def fail_commit():
                raise SQLAlchemyError("Fallo simulado de escritura")
            patch.setattr(db, "commit", fail_commit)
            with pytest.raises(SQLAlchemyError):
                repository.save_ai_result(101, 10, ClassificationResult(categoria="Queja"))
        read = repository.get_by_id_for_tenant(101, 10)
        assert read.categoria is None
        assert read.resumen == "Resumen conservado"
        repository.save_ai_result(101, 10, TopicResult(tema="Servicio"))
    with Session(result_engine) as db:
        assert db.get(Review, 101).categoria is None
        assert db.get(Review, 101).tema == "Servicio"


@pytest.mark.parametrize("category", ["Queja", "Sugerencia", "Felicitación", "Consulta"])
def test_common_classification_contract_accepts_only_official_categories(category):
    assert ClassificationResult(categoria=category).categoria == category


@pytest.mark.parametrize("schema,payload", [
    (ClassificationResult, {"categoria": "Felicitacion"}),
    (ClassificationResult, {"categoria": None}),
    (ClassificationResult, {"categoria": "Queja", "resumen": "Extra"}),
    (SummaryResult, {"resumen": " \n\t"}),
    (SummaryResult, {"resumen": ""}),
    (SummaryResult, {"resumen": None}),
    (SummaryResult, {"resumen": 123}),
    (TopicResult, {"tema": "  "}),
    (TopicResult, {"tema": None}),
    (TopicResult, {"tema": 123}),
    (TopicResult, {"tema": "Servicio", "tenant_id": 20}),
])
def test_invalid_results_rejected_before_persistence(schema, payload):
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


def test_repository_revalidates_bypassed_models_and_rejects_arbitrary_fields(result_engine):
    with Session(result_engine) as db:
        repository = ReviewRepository(db)
        with pytest.raises(ValidationError):
            repository.save_ai_result(
                101, 10, ClassificationResult.model_construct(categoria="Inventada")
            )
        with pytest.raises(TypeError):
            repository.save_ai_result(101, 10, AIResponse())
        assert db.get(Review, 101).categoria is None


@pytest.fixture()
def api_results(client, seed_users):
    with client[1]() as db:
        db.add(Review(
            id=101, tenant_id=10, contenido="Servicio lento", fecha=datetime(2026, 10, 17),
            fuente="manual", puntuacion=2, estado="nueva", categoria="Queja",
            resumen="El cliente reporta lentitud.", tema="Servicio",
        ))
        db.commit()
    response = client[0].post("/api/v1/auth/login", json={
        "correo": "usuario@example.com", "password": "secret123"
    })
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_existing_get_routes_return_persisted_results_and_manual_edit_preserves_them(client, api_results):
    detail = client[0].get("/api/v1/reviews/101", headers=api_results)
    assert detail.status_code == 200
    assert {field: detail.json()[field] for field in ("categoria", "resumen", "tema")} == {
        "categoria": "Queja", "resumen": "El cliente reporta lentitud.", "tema": "Servicio"
    }
    listing = client[0].get("/api/v1/reviews", headers=api_results)
    assert listing.json()["items"] == [detail.json()]
    edited = client[0].patch("/api/v1/reviews/101", headers=api_results, json={"autor": "Luis"})
    assert edited.status_code == 200
    assert edited.json() == detail.json() | {"autor": "Luis"}


@pytest.mark.parametrize("field,value", [
    ("categoria", "Sugerencia"), ("resumen", "Resumen falso"), ("tema", "Tema falso")
])
def test_manual_create_and_patch_cannot_supply_ai_results(client, api_results, field, value):
    before = client[0].get("/api/v1/reviews/101", headers=api_results).json()
    rejected = client[0].patch("/api/v1/reviews/101", headers=api_results, json={
        "contenido": "Intento", field: value
    })
    assert rejected.status_code == 422
    assert client[0].get("/api/v1/reviews/101", headers=api_results).json() == before
    created = client[0].post("/api/v1/reviews", headers=api_results, json={
        "contenido": "Texto", "fecha": "2026-10-17", "puntuacion": 3, field: value
    })
    assert created.status_code == 422
    assert client[0].get("/api/v1/reviews", headers=api_results).json()["total"] == 1


def test_manual_creation_starts_with_null_ai_results(client, api_results):
    created = client[0].post("/api/v1/reviews", headers=api_results, json={
        "contenido": "Nueva review", "fecha": "2026-10-17", "puntuacion": 3
    })
    assert created.status_code == 201
    assert created.json()["categoria"] is created.json()["resumen"] is created.json()["tema"] is None
