from datetime import datetime, timedelta

from app.core.security import get_password_hash
from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User


def login_headers(client, correo: str) -> dict[str, str]:
    response = client[0].post(
        "/api/v1/auth/login",
        json={"correo": correo, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_dashboard_reviews(client) -> None:
    _, session_factory = client
    base_date = datetime(2026, 1, 1, 12, 0, 0)

    with session_factory() as db:
        db.add(Tenant(id=20, nombre="Tenant B", estado="activo"))
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
        db.add_all(
            [
                Review(
                    tenant_id=10,
                    autor=f"Cliente {index}",
                    contenido=f"Review Tenant A {index}",
                    fecha=base_date + timedelta(days=index),
                    fuente="manual",
                    puntuacion=score,
                    estado=estado,
                )
                for index, (score, estado) in enumerate(
                    [
                        (5, "Nueva"),
                        (4, "Nueva"),
                        (3, "En revisión"),
                        (2, "Atendida"),
                        (1, "Nueva"),
                        (5, "nueva"),
                    ],
                    start=1,
                )
            ]
        )
        db.add_all(
            [
                Review(
                    tenant_id=20,
                    autor="Cliente B",
                    contenido="Review de otro tenant",
                    fecha=base_date + timedelta(days=30),
                    fuente="manual",
                    puntuacion=1,
                    estado="Nueva",
                ),
                Review(
                    tenant_id=20,
                    autor="Cliente B2",
                    contenido="Otra review de otro tenant",
                    fecha=base_date + timedelta(days=31),
                    fuente="manual",
                    puntuacion=1,
                    estado="Nueva",
                ),
            ]
        )
        db.commit()


def test_usuario_autenticado_obtiene_metricas_del_dashboard(client, seed_users) -> None:
    seed_dashboard_reviews(client)

    response = client[0].get(
        "/api/v1/dashboard",
        headers=login_headers(client, "usuario@example.com"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_reviews"] == 6
    assert body["promedio_puntuacion"] == 20 / 6
    assert body["reviews_nuevas"] == 3
    assert len(body["reviews_recientes"]) == 5
    assert "tenant_id" not in body["reviews_recientes"][0]


def test_reviews_recientes_respetan_limite_y_orden_descendente(client, seed_users) -> None:
    seed_dashboard_reviews(client)

    response = client[0].get(
        "/api/v1/dashboard",
        headers=login_headers(client, "usuario@example.com"),
    )

    assert response.status_code == 200
    reviews = response.json()["reviews_recientes"]
    fechas = [review["fecha"] for review in reviews]
    assert len(reviews) == 5
    assert fechas == sorted(fechas, reverse=True)
    assert [review["contenido"] for review in reviews] == [
        "Review Tenant A 6",
        "Review Tenant A 5",
        "Review Tenant A 4",
        "Review Tenant A 3",
        "Review Tenant A 2",
    ]


def test_dashboard_aisla_reviews_de_otros_tenants(client, seed_users) -> None:
    seed_dashboard_reviews(client)

    response = client[0].get(
        "/api/v1/dashboard",
        headers=login_headers(client, "usuario-b@example.com"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_reviews"] == 2
    assert body["promedio_puntuacion"] == 1
    assert body["reviews_nuevas"] == 2
    assert [review["contenido"] for review in body["reviews_recientes"]] == [
        "Otra review de otro tenant",
        "Review de otro tenant",
    ]


def test_admin_general_sin_tenant_no_puede_consultar_dashboard(client, seed_users) -> None:
    response = client[0].get(
        "/api/v1/dashboard",
        headers=login_headers(client, "general@example.com"),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "El usuario no pertenece a un tenant"}


def test_dashboard_rechaza_solicitud_sin_autenticacion(client) -> None:
    response = client[0].get("/api/v1/dashboard")

    assert response.status_code == 401
    assert response.json() == {"detail": "Token inválido o ausente"}


def test_tenant_sin_reviews_obtiene_dashboard_vacio(client, seed_users) -> None:
    response = client[0].get(
        "/api/v1/dashboard",
        headers=login_headers(client, "usuario@example.com"),
    )

    assert response.status_code == 200
    assert response.json() == {
        "total_reviews": 0,
        "promedio_puntuacion": None,
        "reviews_nuevas": 0,
        "reviews_recientes": [],
    }
