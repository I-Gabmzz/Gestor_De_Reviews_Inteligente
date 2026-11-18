from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.review_repository import ReviewRepository
from app.schemas.dashboard import DashboardResponse


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
                    prioridad=priority,
                )
                for index, (score, estado, priority) in enumerate(
                    [
                        (5, "nueva", "Alta"),
                        (4, "nueva", "Media"),
                        (3, "en_revision", "Alta"),
                        (2, "atendida", "Alta"),
                        (1, "nueva", None),
                        (5, "atendida", "Baja"),
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
                    estado="nueva",
                    prioridad="Alta",
                ),
                Review(
                    tenant_id=20,
                    autor="Cliente B2",
                    contenido="Otra review de otro tenant",
                    fecha=base_date + timedelta(days=31),
                    fuente="manual",
                    puntuacion=1,
                    estado="nueva",
                    prioridad="Alta",
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
    assert body["nombre_negocio"] == "Negocio de prueba"
    assert body["total_reviews"] == 6
    assert body["promedio_puntuacion"] == 20 / 6
    assert body["reviews_nuevas"] == 3
    assert body["reviews_en_revision"] == 1
    assert body["reviews_atendidas"] == 2
    assert body["reviews_urgentes"] == 2
    assert body["distribucion_puntuaciones"] == [
        {"puntuacion": 1, "total": 1},
        {"puntuacion": 2, "total": 1},
        {"puntuacion": 3, "total": 1},
        {"puntuacion": 4, "total": 1},
        {"puntuacion": 5, "total": 2},
    ]
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
    assert body["nombre_negocio"] == "Tenant B"
    assert body["total_reviews"] == 2
    assert body["promedio_puntuacion"] == 1
    assert body["reviews_nuevas"] == 2
    assert body["reviews_en_revision"] == 0
    assert body["reviews_atendidas"] == 0
    assert body["reviews_urgentes"] == 2
    assert body["distribucion_puntuaciones"] == [
        {"puntuacion": 1, "total": 2},
        {"puntuacion": 2, "total": 0},
        {"puntuacion": 3, "total": 0},
        {"puntuacion": 4, "total": 0},
        {"puntuacion": 5, "total": 0},
    ]
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
        "nombre_negocio": "Negocio de prueba",
        "total_reviews": 0,
        "promedio_puntuacion": None,
        "reviews_nuevas": 0,
        "reviews_en_revision": 0,
        "reviews_atendidas": 0,
        "reviews_urgentes": 0,
        "distribucion_puntuaciones": [
            {"puntuacion": score, "total": 0} for score in range(1, 6)
        ],
        "reviews_recientes": [],
    }


def test_dashboard_ignora_selector_de_tenant_y_filtros_de_bandeja(client, seed_users) -> None:
    seed_dashboard_reviews(client)
    http = client[0]
    headers = login_headers(client, "tenant@example.com")
    baseline = http.get("/api/v1/dashboard", headers=headers)
    filtered = http.get(
        "/api/v1/dashboard",
        params={"tenant_id": 20, "estado": "atendida", "urgente": "true"},
        headers=headers,
    )

    assert baseline.status_code == filtered.status_code == 200
    assert filtered.json() == baseline.json()
    assert filtered.json()["total_reviews"] == 6


def test_dashboard_rechaza_tenant_inactivo_con_token_previo(client, seed_users) -> None:
    headers = login_headers(client, "usuario@example.com")
    with client[1]() as db:
        db.get(Tenant, 10).estado = "inactivo"
        db.commit()
    assert client[0].get("/api/v1/dashboard", headers=headers).status_code == 403


def test_dashboard_actualiza_urgencia_y_estados_al_guardar_como_atendida(client, seed_users) -> None:
    seed_dashboard_reviews(client)
    http = client[0]
    headers = login_headers(client, "usuario@example.com")
    before = http.get("/api/v1/dashboard", headers=headers)
    urgent_before = http.get("/api/v1/reviews", params={"urgente": "true"}, headers=headers)
    assert before.status_code == urgent_before.status_code == 200
    assert before.json()["reviews_urgentes"] == urgent_before.json()["total"] == 2
    assert {row["contenido"] for row in urgent_before.json()["items"]} == {
        "Review Tenant A 1", "Review Tenant A 3",
    }

    review_id = next(
        row["id"] for row in urgent_before.json()["items"] if row["estado"] == "nueva"
    )
    saved = http.patch(f"/api/v1/reviews/{review_id}/status", json={"estado": "atendida"}, headers=headers)
    assert saved.status_code == 200
    assert saved.json()["estado"] == "atendida"

    after = http.get("/api/v1/dashboard", headers=headers)
    urgent_after = http.get("/api/v1/reviews", params={"urgente": "true"}, headers=headers)
    assert after.status_code == urgent_after.status_code == 200
    assert [row["contenido"] for row in urgent_after.json()["items"]] == ["Review Tenant A 3"]
    assert after.json()["reviews_urgentes"] == urgent_after.json()["total"] == 1
    assert after.json()["reviews_nuevas"] == 2
    assert after.json()["reviews_en_revision"] == 1
    assert after.json()["reviews_atendidas"] == 3
    for metric in ("total_reviews", "promedio_puntuacion", "distribucion_puntuaciones"):
        assert after.json()[metric] == before.json()[metric]


@pytest.mark.parametrize(("scores", "average", "distribution"), [
    ((5, None, 2), 3.5, [0, 1, 0, 0, 1]),
    ((None, None, None), None, [0, 0, 0, 0, 0]),
])
def test_agregacion_del_dashboard_con_puntuacion_nula(scores, average, distribution) -> None:
    # Solo la copia del esquema en memoria admite NULL. Se consulta con el repositorio real.
    metadata = MetaData()
    Tenant.__table__.to_metadata(metadata)
    reviews = Review.__table__.to_metadata(metadata)
    reviews.c.puntuacion.nullable = True
    engine = create_engine("sqlite:///:memory:")
    try:
        metadata.create_all(engine)
        with Session(engine) as db:
            db.add(Tenant(id=10, nombre="Negocio de prueba", estado="activo"))
            db.flush()
            db.add_all(
                Review(
                    tenant_id=10, contenido=f"Reseña {state}", fecha=datetime(2026, 1, 1),
                    fuente="manual", puntuacion=score, estado=state, prioridad=priority,
                )
                for score, state, priority in zip(
                    scores, ("nueva", "en_revision", "atendida"), ("Media", "Alta", "Alta"),
                    strict=True,
                )
            )
            db.commit()
            metrics = ReviewRepository(db).dashboard_metrics_by_tenant(10)

        assert metrics == {
            "total_reviews": 3,
            "promedio_puntuacion": average,
            "reviews_nuevas": 1,
            "reviews_en_revision": 1,
            "reviews_atendidas": 1,
            "reviews_urgentes": 1,
            "distribucion_puntuaciones": [
                {"puntuacion": score, "total": total}
                for score, total in enumerate(distribution, start=1)
            ],
        }
    finally:
        engine.dispose()


@pytest.mark.parametrize(("fecha", "puntuacion"), [
    (None, 4),
    (datetime(2026, 1, 2, 12), None),
    (None, None),
    (datetime(2026, 1, 2, 12), 4),
], ids=["fecha-nula", "puntuacion-nula", "ambas-nulas", "ambas-presentes"])
def test_dashboard_serializa_fecha_y_puntuacion_de_recientes(fecha, puntuacion):
    recent = SimpleNamespace(
        id=1, contenido="Reseña sintética", fuente="manual", estado="nueva",
        fecha=fecha, puntuacion=puntuacion,
    )
    dashboard = DashboardResponse(
        total_reviews=1, promedio_puntuacion=puntuacion, reviews_nuevas=1,
        reviews_en_revision=0, reviews_atendidas=0, reviews_urgentes=0,
        distribucion_puntuaciones=[], reviews_recientes=[recent],
    )
    serialized = dashboard.model_dump(mode="json")["reviews_recientes"][0]
    assert serialized["fecha"] == (fecha.isoformat() if fecha is not None else None)
    assert serialized["puntuacion"] == puntuacion


@pytest.mark.parametrize("field", ["fecha", "puntuacion"])
def test_dashboard_exige_ambas_claves_en_recientes_aunque_admitan_nulos(field):
    recent = dict(id=1, contenido="Reseña sintética", fuente="manual", estado="nueva",
                  fecha=datetime(2026, 1, 2, 12), puntuacion=4)
    recent.pop(field)
    with pytest.raises(ValidationError) as error:
        DashboardResponse(
            total_reviews=1, promedio_puntuacion=4, reviews_nuevas=1,
            reviews_en_revision=0, reviews_atendidas=0, reviews_urgentes=0,
            distribucion_puntuaciones=[], reviews_recientes=[recent],
        )
    assert [(item["loc"], item["type"]) for item in error.value.errors()] == [
        (("reviews_recientes", 0, field), "missing"),
    ]
