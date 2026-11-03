import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pydantic_settings import SettingsError

from app.core.config import LOCAL_FRONTEND_ORIGIN, Settings, settings
from app.main import app, create_app


PRODUCTION_ORIGIN = "https://gestorreviews-web.onrender.com"


def test_default_keeps_local_frontend(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert Settings(_env_file=None).cors_origins == [LOCAL_FRONTEND_ORIGIN]


def test_environment_replaces_default_and_normalizes_origins(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", json.dumps([
        PRODUCTION_ORIGIN + "/", "https://GESTORREVIEWS-WEB.onrender.com:443",
        " http://localhost:5173/ ",
    ]))
    assert Settings(_env_file=None).cors_origins == [
        PRODUCTION_ORIGIN, LOCAL_FRONTEND_ORIGIN,
    ]


@pytest.mark.parametrize("origin", [
    "*", "https://*.onrender.com", "gestorreviews-web.onrender.com",
    "https://gestorreviews-web.onrender.com/api/v1",
    "https://user:password@example.com", "https://example.com?query=1",
    "https://example.com#fragment", "file:///tmp/index.html", "",
])
def test_invalid_origins_fail_configuration(monkeypatch, origin):
    monkeypatch.setenv("CORS_ORIGINS", json.dumps([origin]))
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_environment_requires_json_list(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", PRODUCTION_ORIGIN)
    with pytest.raises(SettingsError):
        Settings(_env_file=None)


@pytest.mark.parametrize("origins", [
    [PRODUCTION_ORIGIN], [PRODUCTION_ORIGIN, LOCAL_FRONTEND_ORIGIN], [],
])
def test_real_app_uses_configured_origins(monkeypatch, origins):
    monkeypatch.setenv("CORS_ORIGINS", json.dumps(origins))
    config = Settings(_env_file=None)
    monkeypatch.setattr(settings, "cors_origins", config.cors_origins)
    # These requests do not require a database or start the lifespan.
    client = TestClient(create_app())
    try:
        for origin in [PRODUCTION_ORIGIN, LOCAL_FRONTEND_ORIGIN,
                       "https://other.example", PRODUCTION_ORIGIN + ".other.example"]:
            response = client.options("/api/v1/auth/login", headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            })
            assert response.status_code == (200 if origin in origins else 400)
            assert response.headers.get("access-control-allow-origin") == (
                origin if origin in origins else None
            )

            response = client.get("/api/v1/health", headers={"Origin": origin})
            assert response.status_code == 200
            assert response.headers.get("access-control-allow-origin") == (
                origin if origin in origins else None
            )
            if origin in origins:
                assert response.headers["access-control-allow-credentials"] == "true"
                assert "content-disposition" in response.headers[
                    "access-control-expose-headers"
                ].lower()

        response = client.get("/api/v1/reviews/export",
                              headers={"Origin": PRODUCTION_ORIGIN})
        assert response.status_code == 401
    finally:
        client.close()


def test_production_login_and_export_keep_authentication_and_filename(
    client, seed_users, monkeypatch,
):
    monkeypatch.setenv("CORS_ORIGINS", json.dumps([PRODUCTION_ORIGIN]))
    config = Settings(_env_file=None)
    monkeypatch.setattr(settings, "cors_origins", config.cors_origins)
    production_app = create_app()
    production_app.dependency_overrides.update(app.dependency_overrides)
    with TestClient(production_app) as browser:
        login = browser.post("/api/v1/auth/login", headers={"Origin": PRODUCTION_ORIGIN},
                             json={"correo": "usuario@example.com", "password": "secret123"})
        assert login.status_code == 200
        assert login.headers["access-control-allow-origin"] == PRODUCTION_ORIGIN
        response = browser.get("/api/v1/reviews/export", headers={
            "Origin": PRODUCTION_ORIGIN,
            "Authorization": f"Bearer {login.json()['access_token']}",
        })
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == PRODUCTION_ORIGIN
        assert "content-disposition" in response.headers[
            "access-control-expose-headers"
        ].lower()
        assert response.headers["content-disposition"].startswith(
            'attachment; filename="reviews_'
        )
