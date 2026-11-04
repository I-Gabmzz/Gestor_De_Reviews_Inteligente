"""A-21F discovery: real authentication and synthetic, read-only fixtures."""

import logging

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import ExternalReviewConnection, ExternalReviewImportAttempt, Tenant, User
from app.repositories.review_repository import ReviewRepository
from test_external_review_import_api import BUSINESS, FOREIGN, api, counts, env, headers, synthetic_only


PATH = "/api/v1/integrations/google/reviews/connections"
APPROVAL = "synthetic-a21f-private-approval"


def get(api, who=1, suffix="", **claims):
    return api.get(PATH + suffix, headers=headers(who, **claims))


def assert_no_consumption(env):
    assert env.factory_calls == 0 and env.calls == [] and counts(env) == (0, 0)
    with env.sessions() as db:
        assert list(db.scalars(select(ExternalReviewImportAttempt))) == []


def test_default_policy_is_visible_without_activating_or_consuming(env, api):
    response = get(api)
    assert response.status_code == 200
    assert response.json() == {
        "source": "Google", "import_enabled": False,
        "connections": [{"business_data_id": BUSINESS, "business_name": "synthetic-tenant", "status": "available"}],
    }
    assert_no_consumption(env)


def test_business_label_comes_from_current_tenant_not_query_or_token(env, api):
    with env.sessions() as db, db.begin():
        db.get(Tenant, 10).nombre = "Negocio A"
        db.get(Tenant, 20).nombre = "Negocio B"
    assert get(api, suffix="?tenant_id=20", tenant_id=20).json()["connections"][0]["business_name"] == "Negocio A"
    assert all(row["business_name"] == "Negocio B" for row in get(api, 2).json()["connections"])
    assert_no_consumption(env)


@pytest.mark.parametrize("who", [1, 4])
def test_operational_roles_can_discover_only_their_tenant(env, api, who):
    response = get(api, who, suffix="?tenant_id=20", tenant_id=20, rol="admin_general")
    assert response.status_code == 200
    assert response.json()["connections"] == [{"business_data_id": BUSINESS, "business_name": "synthetic-tenant", "status": "available"}]
    assert FOREIGN not in response.text
    other = get(api, 2).json()
    assert {row["business_data_id"] for row in other["connections"]} == {BUSINESS, FOREIGN}
    assert_no_consumption(env)


@pytest.mark.parametrize("case,status", [
    ("missing", 401), ("invalid", 401), ("unknown", 401), ("general", 403),
    ("inactive-user", 403), ("inactive-tenant", 403),
])
def test_current_authentication_and_permissions_precede_discovery(env, api, case, status):
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
    response = api.get(PATH, headers=auth)
    assert response.status_code == status
    assert "connections" not in response.json()
    assert_no_consumption(env)


def test_empty_and_disabled_connections_expose_no_approval_reason(env, api):
    with env.sessions() as db:
        configured = db.get(ExternalReviewConnection, (10, "Google", BUSINESS))
        configured.persistence_enabled = False
        configured.approval_reference = APPROVAL
        db.commit()
    response = get(api)
    assert response.json()["connections"] == [{"business_data_id": BUSINESS, "business_name": "synthetic-tenant", "status": "disabled"}]
    assert APPROVAL not in response.text
    for field in ("tenant_id", "approval_reference", "persistence_enabled", "api_key", "operation_id"):
        assert field not in response.text
    with env.sessions() as db:
        db.delete(db.get(ExternalReviewConnection, (10, "Google", BUSINESS)))
        db.commit()
    assert get(api).json()["connections"] == []
    assert_no_consumption(env)


@pytest.mark.parametrize("approval", [None, "", "   ", "\t\n"])
def test_missing_or_blank_legacy_approval_stays_disabled(env, api, approval):
    with env.engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA ignore_check_constraints=ON")
        connection.exec_driver_sql(
            "UPDATE external_review_connections SET approval_reference=? WHERE tenant_id=10", (approval,),
        )
        connection.exec_driver_sql("PRAGMA ignore_check_constraints=OFF")
    assert get(api).json()["connections"] == [{"business_data_id": BUSINESS, "business_name": "synthetic-tenant", "status": "disabled"}]
    assert_no_consumption(env)


def test_invalid_configured_identifier_is_not_offered_as_available(env, api):
    with env.sessions() as db:
        db.add(ExternalReviewConnection(tenant_id=10, source="Google", business_data_id="synthetic-legacy",
                                       persistence_enabled=True, approval_reference=APPROVAL))
        db.commit()
    options = get(api).json()["connections"]
    assert {row["business_data_id"]: row["status"] for row in options}["synthetic-legacy"] == "disabled"
    assert_no_consumption(env)


def test_global_enable_is_read_only_and_never_constructs_provider(env, api, monkeypatch):
    monkeypatch.setenv("EXTERNAL_IMPORT_ENABLED", "true")
    assert get(api).json()["import_enabled"] is True
    assert_no_consumption(env)


def test_get_does_not_commit_or_flush_and_rechecks_actor(env, api, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Discovery must not write")
    monkeypatch.setattr(Session, "commit", forbidden)
    monkeypatch.setattr(Session, "flush", forbidden)
    assert get(api).status_code == 200
    monkeypatch.setattr(ReviewRepository, "external_actor_is_active", lambda *_: False)
    response = get(api)
    assert response.status_code == 403 and response.json()["detail"]["code"] == "unauthorized_context"
    assert_no_consumption(env)


def test_database_failure_and_invalid_policy_are_sanitized(env, api, monkeypatch):
    def broken(*args):
        raise SQLAlchemyError(APPROVAL)
    monkeypatch.setattr(ReviewRepository, "list_external_connections", broken)
    response = get(api)
    assert response.status_code == 503 and response.json()["detail"]["code"] == "connections_unavailable"
    assert APPROVAL not in response.text
    monkeypatch.setenv("EXTERNAL_IMPORT_MAX_PAGES", APPROVAL)
    response = get(api)
    assert response.status_code == 503 and response.json()["detail"]["code"] == "policy_unavailable"
    assert APPROVAL not in response.text
    assert_no_consumption(env)


def test_approval_is_absent_from_http_and_debug_sql_logs(env, api, caplog):
    with env.sessions() as db:
        db.get(ExternalReviewConnection, (10, "Google", BUSINESS)).approval_reference = APPROVAL
        db.commit()
    caplog.set_level(logging.DEBUG)
    env.engine.echo = "debug"
    response = get(api)
    assert response.status_code == 200 and APPROVAL not in response.text and APPROVAL not in caplog.text
    assert_no_consumption(env)


def test_discovery_openapi_exposes_only_get_and_public_fields(api):
    spec = api.get("/openapi.json").json()
    assert set(spec["paths"][PATH]) == {"get"}
    assert "requestBody" not in spec["paths"][PATH]["get"]
    fields = spec["components"]["schemas"]["ExternalReviewConnectionOption"]["properties"]
    assert set(fields) == {"business_data_id", "business_name", "status"}
