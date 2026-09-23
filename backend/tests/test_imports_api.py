from app.core.security import get_password_hash
from app.models.tenant import Tenant
from app.models.user import User


def login_headers(client, correo: str = "usuario@example.com") -> dict[str, str]:
    response = client[0].post(
        "/api/v1/auth/login",
        json={"correo": correo, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def csv_file(rows: str = "") -> dict:
    content = (
        "autor,contenido,fecha,fuente,puntuacion\n"
        "Ana,Excelente servicio,2026-09-21,Google,5\n"
        "Luis,Tiempo de espera alto,2026-09-22,Facebook,3\n"
        f"{rows}"
    )
    return {"file": ("reviews.csv", content.encode("utf-8"), "text/csv")}


def seed_tenant_b(client) -> None:
    _, session_factory = client
    with session_factory() as db:
        db.add(Tenant(id=20, nombre="Otro negocio", estado="activo"))
        db.add(
            User(
                tenant_id=20,
                nombre="Usuario Tenant B",
                correo="usuario-b@example.com",
                password_hash=get_password_hash("secret123"),
                rol="usuario_negocio",
                estado="activo",
            )
        )
        db.commit()


def test_importar_reviews_requiere_autenticacion(client) -> None:
    response = client[0].post("/api/v1/reviews/import", files=csv_file())

    assert response.status_code == 401


def test_importacion_persiste_y_actualiza_reviews_y_dashboard(client, seed_users) -> None:
    headers = login_headers(client)

    import_response = client[0].post(
        "/api/v1/reviews/import",
        files=csv_file(),
        headers=headers,
    )

    assert import_response.status_code == 200
    assert import_response.json()["filas_guardadas"] == 2

    reviews_response = client[0].get("/api/v1/reviews", headers=headers)
    assert reviews_response.status_code == 200
    reviews_body = reviews_response.json()
    assert reviews_body["total"] == 2
    assert {item["estado"] for item in reviews_body["items"]} == {"nueva"}

    dashboard_response = client[0].get("/api/v1/dashboard", headers=headers)
    assert dashboard_response.status_code == 200
    dashboard_body = dashboard_response.json()
    assert dashboard_body["total_reviews"] == 2
    assert dashboard_body["promedio_puntuacion"] == 4
    assert dashboard_body["reviews_nuevas"] == 2
    assert [review["contenido"] for review in dashboard_body["reviews_recientes"]] == [
        "Tiempo de espera alto",
        "Excelente servicio",
    ]


def test_importacion_ignora_tenant_id_manipulable_en_query(client, seed_users) -> None:
    seed_tenant_b(client)

    response = client[0].post(
        "/api/v1/imports/upload?tenant_id=20",
        files=csv_file(),
        headers=login_headers(client, "usuario@example.com"),
    )

    assert response.status_code == 200
    assert response.json()["filas_guardadas"] == 2

    tenant_a_reviews = client[0].get(
        "/api/v1/reviews",
        headers=login_headers(client, "usuario@example.com"),
    )
    assert tenant_a_reviews.json()["total"] == 2

    tenant_b_reviews = client[0].get(
        "/api/v1/reviews",
        headers=login_headers(client, "usuario-b@example.com"),
    )
    assert tenant_b_reviews.json()["total"] == 0


def test_importacion_devuelve_errores_de_validacion_sin_persistir(client, seed_users) -> None:
    invalid_content = (
        "autor,contenido,fecha,fuente,puntuacion\n"
        "Ana,,2026-09-21,Google,5\n"
    )

    response = client[0].post(
        "/api/v1/reviews/import",
        files={"file": ("reviews.csv", invalid_content.encode("utf-8"), "text/csv")},
        headers=login_headers(client),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["es_valido"] is False
    assert body["filas_guardadas"] == 0
    assert body["total_errores"] == 1

    reviews_response = client[0].get("/api/v1/reviews", headers=login_headers(client))
    assert reviews_response.json()["total"] == 0
