"""Adversarial H1-H4 regressions; reuse the isolated A-21B HTTP/DB fixtures."""

import pytest
from sqlalchemy import CheckConstraint, MetaData, select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable

from app.api.routers.external_reviews import get_external_import_service
from app.db.base import Base
from app.db.external_import_schema import CHECKS, TABLE, ExternalImportSchemaError, _check_signature, verify_external_import_schema
from app.db.init_db import init_db
from app.models import ExternalReviewImportAttempt
from app.schemas.external_review_import import (
    ExternalReviewImportAccessErrorResponse, ExternalReviewImportErrorResponse,
    ExternalReviewImportUnprocessableResponse,
)
from test_external_review_import_api import (
    BUSINESS, FOREIGN, PATH, PRIVATE, api, counts, env, page, post, record, synthetic_only,
)


@pytest.mark.parametrize("second_place,expected", [(BUSINESS, 200), (FOREIGN, 502), (None, 502), (123, 502)])
def test_h1_every_page_must_identify_the_authorized_establishment(env, api, second_place, expected):
    env.current_service = env.service(max_pages=2)
    env.handler = lambda _: (page(record("first"), token="synthetic-next") if len(env.calls) == 1
                             else page(record("second"), place=second_place))
    response = post(api)
    assert response.status_code == expected
    assert len(env.calls) == 2 and env.closed == 1
    if expected == 200:
        assert response.json()["inserted"] == 2 and counts(env) == (2, 2)
    else:
        assert response.json()["detail"]["code"] == "place_unverified"
        assert response.json()["detail"]["committed_count"] == 0 and counts(env) == (0, 0)
        with env.sessions() as db:
            assert db.scalar(select(ExternalReviewImportAttempt.state)) == "finished"


def _replace_admission_table(env, variant):
    metadata = MetaData()
    for original in Base.metadata.sorted_tables:
        original.to_metadata(metadata)
    table = metadata.tables[TABLE]
    names = {
        "no_fk": "fk_external_import_connection", "no_unique": "uq_external_import_active",
        "no_budget": "ck_external_import_budget", "no_active": "ck_external_import_active",
        "no_state": "ck_external_import_state",
    }
    if variant in names:
        table.constraints.remove(next(item for item in table.constraints if item.name == names[variant]))
    elif variant == "invalid_check":
        constraint = next(item for item in table.constraints if item.name == "ck_external_import_budget")
        constraint.sqltext = text("reserved_requests >= -100")
    elif variant == "same_name_tautology":
        next(item for item in table.constraints if item.name == "ck_external_import_budget").sqltext = text("1 = 1")
    elif variant == "grouping_changed":
        next(item for item in table.constraints if item.name == "ck_external_import_state").sqltext = text(
            "state = 'running' AND (active IS NOT NULL OR state = 'unknown') AND "
            "(active IS NOT NULL OR state = 'finished') AND active IS NULL"
        )
    elif variant == "nullable_budget":
        table.c.reserved_requests.nullable = True
    elif variant == "wrong_type":
        from sqlalchemy import String
        table.c.reserved_requests.type = String(10)
    elif variant == "nocase_state":
        from sqlalchemy import String
        table.c.state.type = String(16, collation="NOCASE")
    elif variant == "wrong_fk":
        table.constraints.remove(next(item for item in table.constraints if item.name == "fk_external_import_connection"))
        from sqlalchemy import ForeignKeyConstraint
        table.append_constraint(ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_external_import_connection"))
    elif variant == "no_checks":
        for constraint in list(table.constraints):
            if isinstance(constraint, CheckConstraint):
                table.constraints.remove(constraint)
    with env.engine.begin() as connection:
        ExternalReviewImportAttempt.__table__.drop(connection)
        connection.exec_driver_sql(str(CreateTable(table).compile(dialect=sqlite.dialect())))


@pytest.mark.parametrize("variant", [
    "no_fk", "wrong_fk", "no_unique", "no_checks", "no_budget", "no_active", "no_state",
    "invalid_check", "same_name_tautology", "grouping_changed", "nullable_budget", "wrong_type", "nocase_state",
])
def test_h2_incompatible_schema_is_rejected_at_startup_and_before_http(env, api, variant):
    _replace_admission_table(env, variant)
    with env.engine.connect() as connection:
        before = connection.exec_driver_sql("SELECT sql FROM sqlite_master WHERE name=?", (TABLE,)).scalar_one()
    with pytest.raises(ExternalImportSchemaError, match="revisión administrativa"):
        init_db(env.engine)
    with env.engine.connect() as connection:
        after = connection.exec_driver_sql("SELECT sql FROM sqlite_master WHERE name=?", (TABLE,)).scalar_one()
    assert before == after  # No repair, DROP, reconstruction or DDL mutation.
    response = post(api)
    assert response.status_code == 503 and response.json()["detail"]["code"] == "admission_schema_invalid"
    assert env.factory_calls == 0 and env.calls == [] and counts(env) == (0, 0)


def _insert(connection, operation, *, active=1, state="running", budget=1, tenant=10):
    connection.exec_driver_sql(
        "INSERT INTO external_review_import_attempts "
        "(operation_id,tenant_id,source,business_data_id,started_at,reserved_requests,active,state) "
        "VALUES (?,?,'Google',?,'2026-11-03 12:00:00',?,?,?)",
        (operation, tenant, BUSINESS, budget, active, state),
    )


def test_h2_new_and_preexisting_valid_table_preserve_rows_and_connections(env):
    with env.engine.begin() as connection:
        _insert(connection, "synthetic-finished", active=None, state="finished")
    for _ in range(2):
        init_db(env.engine)
    with env.engine.connect() as connection:
        verify_external_import_schema(connection)
        assert connection.exec_driver_sql("SELECT count(*) FROM external_review_import_attempts").scalar_one() == 1
        assert connection.exec_driver_sql("SELECT count(*) FROM external_review_connections WHERE persistence_enabled=1").scalar_one() == 3
    assert env.factory_calls == 0


@pytest.mark.parametrize("field,value", [("budget", -99), ("budget", 0), ("active", 2), ("state", "invalid")])
def test_h2_preexisting_invalid_data_is_not_silently_rewritten(env, api, field, value):
    options = {"active": None, "state": "finished", "budget": 1, field: value}
    if field == "active":
        options["state"] = "running"
    with env.engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA ignore_check_constraints=ON")
        _insert(connection, "synthetic-corrupt", **options)
        connection.exec_driver_sql("PRAGMA ignore_check_constraints=OFF")
    with pytest.raises(ExternalImportSchemaError):
        init_db(env.engine)
    assert post(api).json()["detail"]["code"] == "admission_schema_invalid"
    assert env.factory_calls == 0
    with env.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM external_review_import_attempts").scalar_one() == 1


@pytest.mark.parametrize("active,state,budget", [
    (2, "running", 1), (-1, "running", 1), (0, "running", 1), ("bad", "unknown", 1),
    (None, "running", 1), (1, "finished", 1), (1, "invalid", 1),
    (1, "running", -1), (1, "running", 0), (1, "running", 6),
])
def test_h3_raw_sql_rejects_noncanonical_activity_states_and_budgets(env, active, state, budget):
    with env.engine.begin() as connection:
        with pytest.raises(IntegrityError):
            _insert(connection, "synthetic-invalid", active=active, state=state, budget=budget)


def test_h3_raw_sql_unique_active_and_multiple_finished_rows(env):
    with env.engine.begin() as connection:
        _insert(connection, "synthetic-active")
        with pytest.raises(IntegrityError):
            _insert(connection, "synthetic-duplicate")
        _insert(connection, "synthetic-other-tenant", tenant=20)
        _insert(connection, "synthetic-finished-one", active=None, state="finished")
        _insert(connection, "synthetic-finished-two", active=None, state="finished")
        assert connection.exec_driver_sql("SELECT count(*) FROM external_review_import_attempts WHERE active=1").scalar_one() == 2


@pytest.mark.parametrize("dialect", [sqlite.dialect(), postgresql.dialect()], ids=["sqlite", "postgresql-ddl-only"])
def test_h3_strict_domain_is_present_in_both_ddl_targets(dialect):
    ddl = str(CreateTable(ExternalReviewImportAttempt.__table__).compile(dialect=dialect))
    active_literal = "1" if dialect.name == "sqlite" else "true"
    assert f"CHECK (active IS NULL OR active = {active_literal})" in ddl
    assert "UNIQUE (tenant_id, source, business_data_id, active)" in ddl


@pytest.mark.parametrize("reflected,expected", [
    ("((reserved_requests >= 1) AND (reserved_requests <= 5))", CHECKS[0]),
    ("((active IS NULL) OR (active = true))", CHECKS[1]),
    ("((active IS NULL) OR (active = 1))", CHECKS[1]),
    ("((state)::text = 'running'::text AND active IS NOT NULL) OR "
     "((state)::text = 'unknown'::text AND active IS NOT NULL) OR "
     "((state)::text = 'finished'::text AND active IS NULL)", CHECKS[2]),
])
def test_h2_recognizes_pg_reflection_without_erasing_boolean_grouping(reflected, expected):
    assert _check_signature(reflected) == _check_signature(expected)


@pytest.mark.parametrize("bad", [
    "reserved_requests >= -100", "reserved_requests BETWEEN 1 AND 5 OR reserved_requests = 9999",
    "active IS NULL OR active", "active IS NULL OR active = 2", "1=1",
    "state='running' AND (active IS NOT NULL OR state='unknown') AND "
    "(active IS NOT NULL OR state='finished') AND active IS NULL",
])
def test_h2_invalid_checks_cannot_masquerade_as_required_constraints(bad):
    assert _check_signature(bad) not in {_check_signature(sql) for sql in CHECKS}


@pytest.mark.parametrize("sql", ['"ACTIVE" IS NULL OR "ACTIVE" = true', "length(state) > 0", "state::varchar(1) = 'r'"])
def test_h2_unsupported_or_case_sensitive_sql_is_not_guessed(sql):
    with pytest.raises(ValueError):
        _check_signature(sql)


def test_h2_disabled_sqlite_checks_are_rejected_before_acquisition(env, api):
    with env.engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA ignore_check_constraints=ON")
    try:
        response = post(api)
        assert response.status_code == 503 and response.json()["detail"]["code"] == "admission_schema_invalid"
        assert env.factory_calls == 0
    finally:
        with env.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA ignore_check_constraints=OFF")


def test_h2_existing_orphan_is_rejected_without_deleting_it(env, api):
    with env.engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        _insert(connection, "synthetic-orphan", active=None, state="finished", tenant=999)
        connection.commit()
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    with pytest.raises(ExternalImportSchemaError):
        init_db(env.engine)
    assert post(api).status_code == 503 and env.factory_calls == 0
    with env.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM external_review_import_attempts").scalar_one() == 1


@pytest.mark.parametrize("variant", ["valid", "not_validated", "not_enforced", "invalid_index", "deferred", "nocase", "nulls_not_distinct", "extra_column"])
def test_h2_postgresql_catalog_flags_fail_closed_without_claiming_real_server(monkeypatch, variant):
    from types import SimpleNamespace
    from sqlalchemy import Boolean, DateTime, Integer, String
    import app.db.external_import_schema as verifier

    columns = [{"name": name, "type": kind, "nullable": name == "active"} for name, kind in (
        ("operation_id", String(36)), ("tenant_id", Integer()), ("source", String(100)),
        ("business_data_id", String(128)), ("started_at", DateTime()),
        ("reserved_requests", Integer()), ("active", Boolean()), ("state", String(16)),
    )]
    if variant == "extra_column":
        columns.append({"name": "true", "type": Integer(), "nullable": False})
    scope = ["tenant_id", "source", "business_data_id"]
    inspector = SimpleNamespace(
        default_schema_name="public", get_columns=lambda _: columns,
        get_pk_constraint=lambda _: {"constrained_columns": ["operation_id"]},
        get_foreign_keys=lambda _: [{"constrained_columns": scope, "referred_columns": scope,
                                    "referred_table": "external_review_connections", "options": {}}],
        get_unique_constraints=lambda _: [{"column_names": [*scope, "active"],
                                          "dialect_options": {"postgresql_nulls_not_distinct": variant == "nulls_not_distinct"}}],
        get_check_constraints=lambda _: [{"sqltext": sql} for sql in CHECKS],
    )
    monkeypatch.setattr(verifier, "inspect", lambda _: inspector)

    def execute(statement, parameters):
        assert parameters == {"table": TABLE}
        if "pg_attribute" in str(statement):
            rows = [SimpleNamespace(collname="NOCASE" if variant == "nocase" else "C") for _ in range(3)]
            return SimpleNamespace(all=lambda: rows)
        rows = [{"convalidated": variant != "not_validated", "condeferrable": variant == "deferred",
                 "index_valid": variant != "invalid_index", "enforced": variant != "not_enforced"}]
        return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: rows))

    connection = SimpleNamespace(dialect=postgresql.dialect(), execute=execute,
                                 exec_driver_sql=lambda _: SimpleNamespace(scalar_one=lambda: False))
    if variant == "valid":
        verify_external_import_schema(connection)
    else:
        with pytest.raises(ExternalImportSchemaError):
            verify_external_import_schema(connection)


def test_h4_policy_error_is_structured_and_sanitized(env, api, monkeypatch):
    api.app.dependency_overrides.pop(get_external_import_service)
    monkeypatch.setenv("EXTERNAL_IMPORT_MAX_PAGES", PRIVATE)
    response = post(api)
    assert response.status_code == 503 and PRIVATE not in response.text
    parsed = ExternalReviewImportErrorResponse.model_validate(response.json())
    assert parsed.detail.code == "policy_unavailable" and parsed.detail.committed_count == 0
    assert env.factory_calls == 0


def test_h4_both_422_bodies_match_the_declared_union(env, api):
    invalid = post(api, tenant_id=20)
    assert invalid.status_code == 422 and isinstance(invalid.json()["detail"], list)
    ExternalReviewImportUnprocessableResponse.model_validate(invalid.json())
    env.handler = lambda _: page(record(snippet="x" * 65537))
    functional = post(api)
    assert functional.status_code == 422 and functional.json()["detail"]["code"] == "persistence_rejected"
    ExternalReviewImportUnprocessableResponse.model_validate(functional.json())
    assert counts(env) == (0, 0)


def test_h4_shared_auth_and_role_contracts_remain_text(env, api):
    unauthorized = api.post(PATH, json={"business_data_id": BUSINESS})
    forbidden = post(api, 3)
    assert unauthorized.status_code == 401 and unauthorized.headers["www-authenticate"] == "Bearer"
    assert forbidden.status_code == 403
    for response in (unauthorized, forbidden):
        assert isinstance(response.json()["detail"], str)
        ExternalReviewImportAccessErrorResponse.model_validate(response.json())
    env.current_service = env.service(enabled=False)
    blocked = post(api)
    assert blocked.status_code == 403 and isinstance(blocked.json()["detail"], dict)
    ExternalReviewImportAccessErrorResponse.model_validate(blocked.json())
    assert env.factory_calls == 0


def test_h4_internal_error_is_sanitized_and_declared(env, api):
    def broken_factory():
        raise RuntimeError(PRIVATE)
    env.current_service.client_factory = broken_factory
    response = post(api)
    assert response.status_code == 500 and PRIVATE not in response.text
    ExternalReviewImportAccessErrorResponse.model_validate(response.json())
    assert response.json()["detail"]["code"] == "internal_error"


def test_h4_openapi_declares_all_statuses_and_both_422_variants(api):
    spec = api.get("/openapi.json").json()
    operation = spec["paths"][PATH]["post"]
    assert set(operation["responses"]) == {str(status) for status in (200, 401, 403, 404, 409, 422, 429, 500, 502, 503, 504)}
    schemas = spec["components"]["schemas"]
    assert "ExternalReviewImportFailure" in schemas
    assert "ExternalReviewImportErrorResponse" in schemas
    union = schemas["ExternalReviewImportUnprocessableResponse"]["anyOf"]
    assert {item["$ref"].split("/")[-1] for item in union} == {
        "ExternalReviewImportErrorResponse", "ExternalReviewImportValidationErrorResponse",
    }
    assert operation["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith("/ExternalReviewImportUnprocessableResponse")
    assert operation["security"] == [{"HTTPBearer": []}]
