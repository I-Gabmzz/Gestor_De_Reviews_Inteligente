"""Migraciones #3834 sólo sobre archivos nuevos de pytest, nunca la BD local."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.base import Base
from app.db.init_db import init_db
from app.db.migrations import _is_complete_parent_key
from app.models import ExternalReviewConnection, ExternalReviewIdentity, Review
from app.repositories.review_repository import ReviewRepository


@pytest.fixture()
def legacy(tmp_path, request):
    engine = create_engine(f"sqlite:///{tmp_path / 'synthetic-legacy.db'}", hide_parameters=True, connect_args={"check_same_thread": False, "timeout": 5})

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE tenants (id INTEGER PRIMARY KEY, nombre VARCHAR(255) NOT NULL, estado VARCHAR(50) NOT NULL)")
        unique = ", CONSTRAINT uq_synthetic_parent UNIQUE(id,tenant_id)" if getattr(request, "param", None) == "constraint" else ""
        connection.exec_driver_sql(
            "CREATE TABLE reviews (id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id), "
            "autor VARCHAR(255), contenido TEXT NOT NULL, fecha DATETIME NOT NULL, fuente VARCHAR(100) NOT NULL, "
            "puntuacion INTEGER NOT NULL, estado VARCHAR(50) NOT NULL, categoria VARCHAR(50), prioridad VARCHAR(50)"
            + unique + ")"
        )
        connection.exec_driver_sql("CREATE INDEX ix_synthetic_legacy_tenant ON reviews(tenant_id)")
        connection.exec_driver_sql("INSERT INTO tenants VALUES (10, 'synthetic-tenant', 'activo')")
        connection.exec_driver_sql(
            "INSERT INTO reviews VALUES (101,10,'synthetic-author','synthetic-content','2026-01-01 00:00:00',"
            "'Google',4,'en_revision','synthetic-category','Alta')"
        )
    yield engine
    engine.dispose()


def legacy_row(engine):
    with engine.connect() as connection:
        return dict(connection.exec_driver_sql("SELECT * FROM reviews WHERE id=101").mappings().one())


def test_legacy_rows_indexes_foreign_keys_and_ai_migration_are_preserved(legacy):
    before = legacy_row(legacy)
    init_db(legacy)
    init_db(legacy)
    assert legacy_row(legacy) == before | {
        "resumen": None, "tema": None,
        "respuesta_sugerida": None, "respuesta_sugerida_version": 0,
    }
    inspector = inspect(legacy)
    assert set(inspector.get_table_names()) == {"reviews", "tenants", "users", "external_review_connections", "external_review_identities", "review_notifications"}
    indexes = {item["name"]: item for item in inspector.get_indexes("reviews")}
    assert indexes["uq_reviews_id_tenant"]["unique"] and indexes["uq_reviews_id_tenant"]["column_names"] == ["id", "tenant_id"]
    assert "ix_synthetic_legacy_tenant" in indexes
    assert inspector.get_foreign_keys("reviews")[0]["referred_table"] == "tenants"
    with legacy.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM external_review_connections").scalar_one() == 0
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM external_review_identities").scalar_one() == 0


@pytest.mark.parametrize("stage", ["parent_index", "connection_table", "partial_ai"])
def test_supported_partial_migrations_complete_idempotently(legacy, stage):
    with legacy.begin() as connection:
        if stage == "parent_index":
            connection.exec_driver_sql("CREATE UNIQUE INDEX uq_reviews_id_tenant ON reviews(id,tenant_id)")
        elif stage == "connection_table":
            ExternalReviewConnection.__table__.create(connection)
        else:
            connection.exec_driver_sql("ALTER TABLE reviews ADD COLUMN resumen TEXT")
            connection.exec_driver_sql("UPDATE reviews SET resumen='synthetic-previous-summary'")
    before = legacy_row(legacy)
    init_db(legacy)
    init_db(legacy)
    after = legacy_row(legacy)
    assert after == before | {
        "tema": None, **({"resumen": None} if stage != "partial_ai" else {}),
        "respuesta_sugerida": None, "respuesta_sugerida_version": 0,
    }


def test_simultaneous_startups_are_serialized_without_data_loss(legacy):
    before = legacy_row(legacy)
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda _: init_db(legacy), range(2)))
    assert legacy_row(legacy) == before | {
        "resumen": None, "tema": None,
        "respuesta_sugerida": None, "respuesta_sugerida_version": 0,
    }
    assert len(inspect(legacy).get_indexes("reviews")) == 2


def test_incompatible_existing_index_is_rejected_and_ddl_is_rolled_back(legacy):
    with legacy.begin() as connection:
        connection.exec_driver_sql("CREATE INDEX uq_reviews_id_tenant ON reviews(tenant_id)")
    before = legacy_row(legacy)
    with pytest.raises(RuntimeError, match="índice"):
        init_db(legacy)
    assert legacy_row(legacy) == before
    assert set(inspect(legacy).get_table_names()) == {"reviews", "tenants"}


def test_incompatible_partial_external_table_is_rejected_without_rewriting_rows(legacy):
    with legacy.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE external_review_connections (tenant_id INTEGER)")
    before = legacy_row(legacy)
    with pytest.raises(Exception):
        init_db(legacy)
    assert legacy_row(legacy) == before
    assert "external_review_identities" not in inspect(legacy).get_table_names()


def test_existing_external_connections_are_never_enabled_by_migration(legacy):
    init_db(legacy)
    with legacy.begin() as connection:
        connection.execute(ExternalReviewConnection.__table__.insert().values(tenant_id=10, source="Google", business_data_id="0x1:0x2"))
    init_db(legacy)
    with legacy.connect() as connection:
        assert connection.execute(select(ExternalReviewConnection.persistence_enabled)).scalar_one() is False


def test_new_database_has_complete_foreign_keys_and_unique_constraints(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'synthetic-new.db'}")
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    try:
        init_db(engine)
        inspector = inspect(engine)
        assert inspector.get_pk_constraint("external_review_connections")["constrained_columns"] == ["tenant_id", "source", "business_data_id"]
        assert inspector.get_pk_constraint("external_review_identities")["constrained_columns"] == ["review_id"]
        assert any(item["column_names"] == ["tenant_id", "source", "business_data_id", "external_review_id"] for item in inspector.get_unique_constraints("external_review_identities"))
        foreign = inspector.get_foreign_keys("external_review_identities")
        assert any(item["constrained_columns"] == ["review_id", "tenant_id"] and item["referred_columns"] == ["id", "tenant_id"] for item in foreign)
        assert any(item["referred_table"] == "external_review_connections" for item in foreign)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    finally:
        engine.dispose()


@pytest.mark.parametrize("dialect", [sqlite.dialect(), postgresql.dialect()], ids=["sqlite-ddl", "postgresql-ddl-only"])
def test_external_schema_compiles_for_both_dialects_without_driver_or_server(dialect):
    ddl = "\n".join(str(CreateTable(table).compile(dialect=dialect)) for table in Base.metadata.sorted_tables)
    index = next(item for item in Review.__table__.indexes if item.name == "uq_reviews_id_tenant")
    ddl += str(CreateIndex(index).compile(dialect=dialect))
    assert "uq_external_review_identity" in ddl
    assert "FOREIGN KEY(review_id, tenant_id) REFERENCES reviews (id, tenant_id)" in ddl
    assert "uq_reviews_id_tenant" in ddl and "ck_external_connection_approval" in ddl
    assert ('COLLATE "C"' if dialect.name == "postgresql" else 'COLLATE "BINARY"') in ddl
    assert "persistence_enabled" in ddl and "DEFAULT" in ddl


def test_postgresql_connection_lookup_is_scoped_and_locked():
    class CaptureSession:
        def scalar(self, statement):
            self.statement = statement
            return None
    session = CaptureSession()
    assert ReviewRepository(session).get_external_connection(10, "0x1:0x2") is None
    statement = session.statement
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql and "tenant_id =" in sql and "business_data_id =" in sql and "source =" in sql
    assert statement.get_execution_options()["populate_existing"] is True


@pytest.mark.parametrize("definition", [
    "UNIQUE INDEX uq_reviews_id_tenant ON reviews(id,tenant_id) WHERE tenant_id=999",
    "INDEX uq_reviews_id_tenant ON reviews(id,tenant_id)",
    "UNIQUE INDEX uq_reviews_id_tenant ON reviews(id,fuente)",
    "UNIQUE INDEX uq_reviews_id_tenant ON reviews(id,tenant_id,fuente)",
    "UNIQUE INDEX uq_reviews_id_tenant ON reviews(id,lower(tenant_id))",
    "UNIQUE INDEX uq_reviews_id_tenant ON reviews(id COLLATE NOCASE,tenant_id)",
], ids=["partial", "non-unique", "wrong-columns", "extra-column", "expression", "wrong-collation"])
def test_incompatible_parent_indexes_fail_safely_without_changing_legacy_schema(legacy, definition):
    with legacy.begin() as connection:
        connection.exec_driver_sql("CREATE " + definition)
        schema = connection.exec_driver_sql("SELECT type,name,sql FROM sqlite_schema ORDER BY type,name").all()
    before = legacy_row(legacy)
    for _ in range(2):
        with pytest.raises(RuntimeError) as caught:
            init_db(legacy)
        assert "synthetic-content" not in str(caught.value)
        assert "999" not in str(caught.value)
        assert legacy_row(legacy) == before
        with legacy.connect() as connection:
            assert connection.exec_driver_sql("SELECT type,name,sql FROM sqlite_schema ORDER BY type,name").all() == schema


def assert_parent_fk_operates(engine):
    with engine.begin() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        connection.exec_driver_sql("INSERT INTO external_review_connections(tenant_id,source,business_data_id) VALUES(10,'Google','0x1:0x2')")
        connection.exec_driver_sql(
            "INSERT INTO external_review_identities VALUES(101,10,'Google','0x1:0x2','synthetic-identity',?)", ("v1:" + "a" * 64,)
        )
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        with pytest.raises(IntegrityError) as caught:
            connection.exec_driver_sql("UPDATE external_review_identities SET tenant_id=999")
        assert getattr(caught.value.orig, "sqlite_errorcode", None) == 787
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM external_review_identities").scalar_one() == 1


@pytest.mark.parametrize("legacy", ["constraint"], indirect=True)
def test_existing_unique_table_constraint_is_accepted_and_reused(legacy):
    before = legacy_row(legacy)
    init_db(legacy)
    init_db(legacy)
    assert legacy_row(legacy) == before | {
        "resumen": None, "tema": None,
        "respuesta_sugerida": None, "respuesta_sugerida_version": 0,
    }
    with legacy.connect() as connection:
        indexes = connection.exec_driver_sql("PRAGMA index_list('reviews')").mappings().all()
        assert any(index["origin"] == "u" and index["unique"] and not index["partial"] for index in indexes)
        assert not any(index["name"] == "uq_reviews_id_tenant" for index in indexes)
    assert_parent_fk_operates(legacy)


@pytest.mark.parametrize("kind", ["canonical", "other-name", "coexisting", "reverse"], ids=["complete-index", "existing-other-name", "coexisting-indexes", "reversed-valid-key"])
def test_complete_unique_keys_are_reused_without_removing_coexisting_indexes(legacy, kind):
    name = "uq_synthetic_other_parent" if kind == "other-name" else "uq_reviews_id_tenant"
    columns = "tenant_id,id" if kind == "reverse" else "id,tenant_id"
    with legacy.begin() as connection:
        connection.exec_driver_sql(f"CREATE UNIQUE INDEX {name} ON reviews({columns})")
        if kind == "coexisting":
            connection.exec_driver_sql("CREATE UNIQUE INDEX uq_synthetic_duplicate ON reviews(id,tenant_id)")
            connection.exec_driver_sql("CREATE UNIQUE INDEX uq_synthetic_partial ON reviews(id,tenant_id) WHERE tenant_id=10")
        before_indexes = connection.exec_driver_sql("SELECT name,sql FROM sqlite_schema WHERE type='index' ORDER BY name").all()
        keys = connection.exec_driver_sql(f'PRAGMA index_xinfo("{name}")').mappings().all()
        assert [key["name"] for key in keys if key["key"]] == columns.split(",")
    init_db(legacy)
    init_db(legacy)
    with legacy.connect() as connection:
        assert connection.exec_driver_sql("SELECT name,sql FROM sqlite_schema WHERE type='index' AND tbl_name='reviews' ORDER BY name").all() == before_indexes
    assert_parent_fk_operates(legacy)


def test_incompatible_reserved_index_is_rejected_even_with_another_valid_key(legacy):
    with legacy.begin() as connection:
        connection.exec_driver_sql("CREATE UNIQUE INDEX uq_synthetic_valid ON reviews(id,tenant_id)")
        connection.exec_driver_sql("CREATE UNIQUE INDEX uq_reviews_id_tenant ON reviews(id,tenant_id) WHERE tenant_id=10")
    before = legacy_row(legacy)
    with pytest.raises(RuntimeError, match="incompatible"):
        init_db(legacy)
    assert legacy_row(legacy) == before


def test_unrelated_partial_index_is_preserved_but_not_used_as_parent_key(legacy):
    with legacy.begin() as connection:
        connection.exec_driver_sql("CREATE UNIQUE INDEX uq_synthetic_partial ON reviews(id,tenant_id) WHERE tenant_id=10")
    init_db(legacy)
    init_db(legacy)
    with legacy.connect() as connection:
        indexes = {item["name"]: item for item in connection.exec_driver_sql("PRAGMA index_list('reviews')").mappings()}
        assert indexes["uq_synthetic_partial"]["partial"] == 1
        assert indexes["uq_reviews_id_tenant"]["unique"] == 1
        assert indexes["uq_reviews_id_tenant"]["partial"] == 0
    assert_parent_fk_operates(legacy)


@pytest.mark.parametrize("changes", [
    {"unique": False}, {"column_names": ["id", "other"]},
    {"column_names": ["id", "tenant_id", "extra"]}, {"column_names": ["id", None]},
    {"expressions": ["id", "lower(tenant_id)"]},
    {"dialect_options": {"postgresql_where": text("tenant_id > 0")}},
    {"include_columns": ["extra"]}, {"dialect_options": {"postgresql_ops": {"id": "custom_ops"}}},
], ids=["non-unique", "wrong-column", "extra-key", "expression-key", "expression-metadata", "partial-pg", "include", "operator-class"])
def test_postgresql_reflected_key_metadata_rejects_incompatible_candidates(changes):
    metadata = {"name": "synthetic", "unique": True, "column_names": ["id", "tenant_id"]}
    assert _is_complete_parent_key(metadata)
    assert _is_complete_parent_key(metadata | {"column_names": ["tenant_id", "id"]})
    assert not _is_complete_parent_key(metadata | changes)


def test_postgresql_partial_index_compiles_but_is_not_a_valid_parent_key():
    from sqlalchemy import Index, MetaData, Table, Column, Integer
    parent = Table("synthetic_parent", MetaData(), Column("id", Integer), Column("tenant_id", Integer))
    full = Index("synthetic_full", parent.c.id, parent.c.tenant_id, unique=True)
    partial = Index("synthetic_partial", parent.c.id, parent.c.tenant_id, unique=True, postgresql_where=parent.c.tenant_id > 0)
    dialect = postgresql.dialect()
    assert "WHERE" not in str(CreateIndex(full).compile(dialect=dialect))
    assert "WHERE" in str(CreateIndex(partial).compile(dialect=dialect))
