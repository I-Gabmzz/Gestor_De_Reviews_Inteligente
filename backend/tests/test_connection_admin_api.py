"""Panel administrativo: autorización real, transacciones y datos sintéticos."""

from datetime import datetime
from types import SimpleNamespace
import httpx
import pytest
from sqlalchemy import func, select
from app.api.routers.connection_admin import get_maps_resolver
from app.core.security import verify_password
from app.models import ExternalReviewConnection, ExternalReviewIdentity, ExternalReviewImportAttempt, Tenant, User
from app.services.google_maps_link_service import GoogleMapsLinkResolver
from test_external_review_import_api import BUSINESS, FOREIGN, api, counts, env, headers, synthetic_only

PATH = "/api/v1/admin/google-connections"
ACCOUNTS = "/api/v1/admin/business-accounts"
URL = "https://maps.app.goo.gl/SyntheticBusiness"
FULL = f"https://www.google.com/maps/place/Negocio/data=!4m2!1s{BUSINESS}!1b1"
PASSWORD = "synthetic-admin-account-password"


@pytest.fixture()
def maps(api, env):
    state = SimpleNamespace(calls=[], handler=lambda _: httpx.Response(302, headers={"Location": FULL}))
    def handle(request):
        assert not env.checked_out, "DB connection retained during Google request"
        state.calls.append(str(request.url))
        return state.handler(request)
    api.app.dependency_overrides[get_maps_resolver] = lambda: GoogleMapsLinkResolver(transport=httpx.MockTransport(handle))
    yield state
    assert env.factory_calls == 0 and env.calls == []


def body(**changes):
    return {"business_name": "Nuevo negocio sintético", "nombre": "Persona de prueba",
            "correo": "new-admin@example.com", "password": PASSWORD,
            "google_maps_url": URL, "confirmed": True, **changes}


def total(env, model):
    with env.sessions() as db:
        return db.scalar(select(func.count()).select_from(model))


@pytest.mark.parametrize("who", [None, 1, 2, 4])
def test_only_general_admin_can_list_link_or_create_accounts(env, api, maps, who):
    auth = {} if who is None else headers(who, rol="admin_general", tenant_id=None)
    expected = 401 if who is None else 403
    assert api.get(PATH, params={"tenant_id": 10}, headers=auth).status_code == expected
    assert api.post(PATH, json={"tenant_id": 10, "google_maps_url": URL, "confirmed": True}, headers=auth).status_code == expected
    assert api.post(ACCOUNTS, json=body(), headers=auth).status_code == expected
    assert maps.calls == [] and total(env, User) == 4 and total(env, Tenant) == 2


def test_admin_lists_business_accounts_without_credentials_or_approval(env, api, maps):
    response = api.get(PATH, params={"tenant_id": 10}, headers=headers(3))
    assert response.status_code == 200
    data = response.json()
    assert data["tenant"]["id"] == 10
    assert {user["id"] for user in data["users"]} == {1, 4}
    assert data["connections"][0]["business_data_id"] == BUSINESS
    assert all(field not in response.text for field in ("password", "approval_reference", "api_key"))
    assert maps.calls == []


def test_short_link_can_be_saved_idempotently_without_importing(env, api, maps):
    payload = {"tenant_id": 10, "google_maps_url": URL, "confirmed": True}
    for _ in range(2):
        response = api.post(PATH, json=payload, headers=headers(3))
        assert response.status_code == 200 and response.json()["enabled"] is True
    assert len(maps.calls) == 2
    assert counts(env) == (0, 0) and total(env, ExternalReviewConnection) == 3
    assert total(env, ExternalReviewImportAttempt) == 0


def test_new_business_user_and_connection_are_created_together_and_can_login(env, api, maps):
    response = api.post(ACCOUNTS, json=body(), headers=headers(3))
    assert response.status_code == 201, response.json()
    result = response.json()
    assert result["tenant"]["nombre"] == "Nuevo negocio sintético"
    assert result["user"]["tenant_id"] == result["tenant"]["id"]
    assert result["user"]["rol"] == "admin_tenant"
    assert result["connection"]["enabled"] is True
    assert PASSWORD not in response.text and "password_hash" not in response.text
    with env.sessions() as db:
        saved = db.get(User, result["user"]["id"])
        assert verify_password(PASSWORD, saved.password_hash)
    login = api.post("/api/v1/auth/login", json={"correo": "new-admin@example.com", "password": PASSWORD})
    assert login.status_code == 200
    token = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert api.get("/api/v1/reviews", headers=token).json()["total"] == 0
    connections = api.get("/api/v1/integrations/google/reviews/connections", headers=token).json()["connections"]
    assert connections[0]["business_name"] == "Nuevo negocio sintético"
    assert api.get(PATH, params={"tenant_id": 10}, headers=token).status_code == 403


def test_existing_business_can_receive_user_without_relinking(env, api, maps):
    payload = body(tenant_id=10, business_name=None, google_maps_url=None, rol="usuario_negocio")
    response = api.post(ACCOUNTS, json=payload, headers=headers(3))
    assert response.status_code == 201
    assert response.json()["user"]["tenant_id"] == 10 and response.json()["connection"] is None
    assert maps.calls == [] and total(env, Tenant) == 2


@pytest.mark.parametrize("changes", [
    {"correo": "synthetic-1@example.com"}, {"business_name": "synthetic-tenant"},
    {"tenant_id": 10}, {"rol": "admin_general"}, {"password": "short"},
    {"google_maps_url": "https://127.0.0.1/maps"}, {"confirmed": False},
    {"tenant_id": 999, "business_name": None},
])
def test_invalid_or_conflicting_account_never_leaves_partial_records(env, api, maps, changes):
    response = api.post(ACCOUNTS, json=body(**changes), headers=headers(3))
    assert response.status_code in (404, 409, 422)
    assert total(env, Tenant) == 2 and total(env, User) == 4
    assert total(env, ExternalReviewConnection) == 3
    assert PASSWORD not in response.text


@pytest.mark.parametrize("changes", [{"correo": "invalid"}, {"nombre": None}, {"extra": PASSWORD}, {"nombre": ""}])
def test_validation_diagnostics_never_echo_password_or_input_body(env, api, maps, changes):
    response = api.post(ACCOUNTS, json=body(**changes), headers=headers(3))
    assert response.status_code == 422 and PASSWORD not in response.text
    assert '"input"' not in response.text


def test_missing_field_does_not_echo_other_secret_fields(env, api, maps):
    payload = body()
    payload.pop("nombre")
    response = api.post(ACCOUNTS, json=payload, headers=headers(3))
    assert response.status_code == 422 and PASSWORD not in response.text


def test_confirmation_and_active_business_precede_google_request(env, api, maps):
    for payload in ({"tenant_id": 10, "google_maps_url": URL, "confirmed": False},
                    {"tenant_id": 999, "google_maps_url": URL, "confirmed": True}):
        assert api.post(PATH, json=payload, headers=headers(3)).status_code in (404, 422)
    with env.sessions() as db, db.begin():
        db.get(Tenant, 10).estado = "inactivo"
    assert api.post(PATH, json={"tenant_id": 10, "google_maps_url": URL, "confirmed": True}, headers=headers(3)).status_code == 409
    assert maps.calls == []


def test_admin_revoked_while_google_responds_cannot_save(env, api, maps):
    def revoke(_):
        with env.sessions() as db, db.begin():
            actor = db.get(User, 3)
            actor.rol, actor.tenant_id = "usuario_negocio", 10
        return httpx.Response(302, headers={"Location": FULL})
    maps.handler = revoke
    response = api.post(PATH, json={"tenant_id": 10, "google_maps_url": URL, "confirmed": True}, headers=headers(3))
    assert response.status_code == 403 and total(env, ExternalReviewConnection) == 3


def test_pending_import_prevents_connection_changes(env, api, maps):
    with env.sessions() as db, db.begin():
        db.add(ExternalReviewImportAttempt(operation_id="synthetic-pending", tenant_id=10, source="Google",
            business_data_id=BUSINESS, started_at=datetime.now(), reserved_requests=1, active=True, state="unknown"))
    response = api.patch(PATH, json={"tenant_id": 10, "business_data_id": BUSINESS, "enabled": False}, headers=headers(3))
    assert response.status_code == 409
    with env.sessions() as db:
        assert db.get(ExternalReviewImportAttempt, "synthetic-pending").active is True
        assert db.get(ExternalReviewConnection, (10, "Google", BUSINESS)).persistence_enabled is True


def test_pause_then_link_another_profile_preserves_existing_connection(env, api, maps):
    assert api.patch(PATH, json={"tenant_id": 10, "business_data_id": BUSINESS, "enabled": False}, headers=headers(3)).status_code == 200
    foreign_url = FULL.replace(BUSINESS, FOREIGN)
    response = api.post(PATH, json={"tenant_id": 10, "google_maps_url": foreign_url, "confirmed": True}, headers=headers(3))
    assert response.status_code == 200
    with env.sessions() as db:
        assert db.get(ExternalReviewConnection, (10, "Google", BUSINESS)).persistence_enabled is False
        assert db.get(ExternalReviewConnection, (10, "Google", FOREIGN)).persistence_enabled is True
    assert api.patch(PATH, json={"tenant_id": 10, "business_data_id": BUSINESS, "enabled": True}, headers=headers(3)).status_code == 409
    assert maps.calls == []
