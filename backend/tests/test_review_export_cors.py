"""Exposición CORS del nombre de archivo de HU-19 T3."""

from app.core.config import LOCAL_FRONTEND_ORIGIN


EXPORT_URL = "/api/v1/reviews/export"


def auth_headers(client, correo: str = "usuario@example.com") -> dict[str, str]:
    response = client[0].post(
        "/api/v1/auth/login", json={"correo": correo, "password": "secret123"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_origen_permitido_puede_leer_nombre_de_exportacion(client, seed_users) -> None:
    response = client[0].get(
        EXPORT_URL,
        headers={"Origin": LOCAL_FRONTEND_ORIGIN, **auth_headers(client)},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == LOCAL_FRONTEND_ORIGIN
    exposed = [item.strip().lower() for item in response.headers["access-control-expose-headers"].split(",")]
    assert "content-disposition" in exposed
    assert response.headers["content-disposition"].startswith('attachment; filename="reviews_')
    assert response.headers["content-type"] == "text/csv; charset=utf-8"


def test_origen_no_permitido_no_recibe_acceso_cors(client, seed_users) -> None:
    response = client[0].get(
        EXPORT_URL,
        headers={"Origin": "https://origen-no-autorizado.example", **auth_headers(client)},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_no_cambia_autenticacion_ni_roles(client, seed_users) -> None:
    headers = {"Origin": LOCAL_FRONTEND_ORIGIN}
    assert client[0].get(EXPORT_URL, headers=headers).status_code == 401
    assert client[0].get(
        EXPORT_URL, headers={**headers, **auth_headers(client, "general@example.com")}
    ).status_code == 403
