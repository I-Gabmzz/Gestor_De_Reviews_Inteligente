"""N1 regressions: synthetic SQLite files and the production import HTTP path."""

import pytest
from sqlalchemy import MetaData, text
from sqlalchemy.dialects import sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable

from app.db.base import Base
from app.db.external_import_schema import TABLE, ExternalImportSchemaError, verify_external_import_schema
from app.db.init_db import init_db
from app.models import ExternalReviewImportAttempt
from test_external_review_import_api import BUSINESS, api, counts, env, post, synthetic_only


def _legacy_table(env):
    """Recreate only this fresh fixture's empty table with the pre-N1 CHECK."""
    metadata = MetaData()
    for original in Base.metadata.sorted_tables:
        original.to_metadata(metadata)
    table = metadata.tables[TABLE]
    next(item for item in table.constraints if item.name == "ck_external_import_active").sqltext = text(
        "active IS NULL OR active = true"
    )
    with env.engine.begin() as connection:
        ExternalReviewImportAttempt.__table__.drop(connection)
        connection.exec_driver_sql(str(CreateTable(table).compile(dialect=sqlite.dialect())))


def _insert(connection, operation, *, active=1, state="running", tenant=10, budget=1):
    connection.exec_driver_sql(
        "INSERT INTO external_review_import_attempts "
        "(operation_id,tenant_id,source,business_data_id,started_at,reserved_requests,active,state) "
        "VALUES (?,?,'Google',?,'2000-01-01',?,?,?)",
        (operation, tenant, BUSINESS, budget, active, state),
    )


def _snapshot(env):
    with env.engine.connect() as connection:
        ddl = connection.exec_driver_sql("SELECT sql FROM sqlite_master WHERE name=?", (TABLE,)).scalar_one()
        rows = connection.exec_driver_sql(f"SELECT * FROM {TABLE} ORDER BY operation_id").all()
    return ddl, rows


def _assert_blocked_without_mutation(env, api, before):
    with pytest.raises(ExternalImportSchemaError):
        init_db(env.engine)
    for _ in range(2):
        response = post(api)
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "admission_schema_invalid"
        assert response.json()["detail"]["committed_count"] == 0
    assert env.factory_calls == 0 and env.calls == [] and counts(env) == (0, 0)
    assert _snapshot(env) == before


def test_n1_original_true_shadow_unknown_active_two_cannot_acquire(env, api):
    _legacy_table(env)
    with env.engine.begin() as connection:
        connection.exec_driver_sql(
            'ALTER TABLE external_review_import_attempts ADD COLUMN "true" INTEGER NOT NULL DEFAULT 1'
        )
        # Exact original counterexample: no CHECK bypass is needed to insert 2.
        connection.exec_driver_sql(
            "INSERT INTO external_review_import_attempts "
            "(operation_id,tenant_id,source,business_data_id,started_at,reserved_requests,active,state,\"true\") "
            "VALUES ('synthetic-unresolved',10,'Google',?,'2000-01-01',1,2,'unknown',2)",
            (BUSINESS,),
        )
        assert connection.exec_driver_sql(
            "SELECT active,state FROM external_review_import_attempts"
        ).one() == (2, "unknown")
    _assert_blocked_without_mutation(env, api, _snapshot(env))


@pytest.mark.parametrize("name", ["true", "TRUE", "TrUe", "false", "FALSE", "null", "extra_flag"])
def test_n1_any_additional_column_is_incompatible_even_with_valid_rows(env, api, name):
    with env.engine.begin() as connection:
        _insert(connection, "synthetic-finished", active=None, state="finished")
        quoted = connection.dialect.identifier_preparer.quote_identifier(name)
        connection.exec_driver_sql(f"ALTER TABLE {TABLE} ADD COLUMN {quoted} INTEGER NOT NULL DEFAULT 1")
    _assert_blocked_without_mutation(env, api, _snapshot(env))


def test_n1_generated_true_column_is_also_rejected(env, api):
    with env.engine.begin() as connection:
        connection.exec_driver_sql(
            'ALTER TABLE external_review_import_attempts ADD COLUMN "true" INTEGER GENERATED ALWAYS AS (2) VIRTUAL'
        )
    _assert_blocked_without_mutation(env, api, _snapshot(env))


@pytest.mark.parametrize("active", [0, 2, -1, "true"])
def test_n1_new_sqlite_check_cannot_be_shadowed_even_without_verifier(env, active):
    with env.engine.begin() as connection:
        connection.exec_driver_sql(
            'ALTER TABLE external_review_import_attempts ADD COLUMN "true" INTEGER NOT NULL DEFAULT 2'
        )
        connection.exec_driver_sql(
            'ALTER TABLE external_review_import_attempts ADD COLUMN "false" INTEGER NOT NULL DEFAULT 1'
        )
        with pytest.raises(IntegrityError):
            _insert(connection, "synthetic-invalid", active=active, state="unknown")
        _insert(connection, "synthetic-valid", active=1, state="unknown")
        assert connection.exec_driver_sql(f"SELECT active FROM {TABLE}").scalar_one() == 1
        # A valid row cannot make an extended table admissible.
        with pytest.raises(ExternalImportSchemaError):
            verify_external_import_schema(connection)


@pytest.mark.parametrize("state,active,status", [("running", 1, 409), ("unknown", 1, 409), ("finished", None, 200)])
def test_n1_canonical_existing_states_keep_their_admission_behavior(env, api, state, active, status):
    with env.engine.begin() as connection:
        _insert(connection, "synthetic-existing", active=active, state=state, budget=5)
        verify_external_import_schema(connection)
    init_db(env.engine)
    response = post(api)
    assert response.status_code == status
    assert env.factory_calls == (1 if status == 200 else 0)
    assert counts(env) == ((1, 1) if status == 200 else (0, 0))
    if status == 409:
        assert response.json()["detail"]["code"] == "import_in_progress"
        assert env.calls == []


def test_n1_canonical_sql_uniqueness_tenants_and_finished_history(env, api):
    with env.engine.begin() as connection:
        for number in range(3):
            _insert(connection, f"synthetic-finished-{number}", active=None, state="finished")
        _insert(connection, "synthetic-tenant-10", state="unknown")
        with pytest.raises(IntegrityError):
            _insert(connection, "synthetic-duplicate", state="running")
        _insert(connection, "synthetic-tenant-20", tenant=20)
        verify_external_import_schema(connection)
        assert connection.exec_driver_sql(f"SELECT count(*) FROM {TABLE}").scalar_one() == 5
    init_db(env.engine)
    assert post(api).status_code == post(api, 2).status_code == 409
    assert env.factory_calls == 0 and env.calls == [] and counts(env) == (0, 0)


def test_n1_pre_n1_check_with_exact_columns_remains_compatible(env, api):
    _legacy_table(env)
    with env.engine.begin() as connection:
        _insert(connection, "synthetic-history", active=None, state="finished")
        _insert(connection, "synthetic-other-tenant", tenant=20, state="unknown")
        verify_external_import_schema(connection)
    before = _snapshot(env)
    init_db(env.engine)
    assert _snapshot(env) == before  # No migration or rewriting of a valid table.
    assert post(api).status_code == 200
    assert post(api, 2).status_code == 409
    assert len(env.calls) == env.factory_calls == 1 and counts(env) == (1, 1)
