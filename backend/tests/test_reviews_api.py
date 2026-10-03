from datetime import datetime

import pytest

from app.models.review import Review
from app.models.tenant import Tenant


@pytest.fixture()
def seed_reviews(client, seed_users):
    _, session_factory = client
    with session_factory() as db:
        db.add(Tenant(id=20, nombre="Otro negocio", estado="activo"))
        db.add_all(
            [
                Review(
                    id=101,
                    tenant_id=10,
                    autor="Ana",
                    contenido="Review anterior",
                    fecha=datetime(2026, 9, 18),
                    fuente="Google",
                    puntuacion=4,
                    estado="nueva",
                ),
                Review(
                    id=102,
                    tenant_id=10,
                    autor="Luis",
                    contenido="Review reciente",
                    fecha=datetime(2026, 9, 20),
                    fuente="Facebook",
                    puntuacion=5,
                    estado="atendida",
                ),
                Review(
                    id=201,
                    tenant_id=20,
                    autor="Persona externa",
                    contenido="Review de otro tenant",
                    fecha=datetime(2026, 9, 21),
                    fuente="Google",
                    puntuacion=1,
                    estado="nueva",
                ),
            ]
        )
        db.commit()


def login(client, correo: str = "usuario@example.com") -> dict[str, str]:
    response = client[0].post(
        "/api/v1/auth/login",
        json={"correo": correo, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def manual_review_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "autor": "Cliente manual",
        "contenido": "El servicio fue excelente.",
        "fecha": "2026-09-24T10:30:00",
        "puntuacion": 5,
    }
    payload.update(overrides)
    return payload


def test_registrar_review_manual_persiste_con_valores_de_servidor(client, seed_users) -> None:
    response = client[0].post(
        "/api/v1/reviews",
        json=manual_review_payload(),
        headers=login(client),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == 10
    assert body["autor"] == "Cliente manual"
    assert body["contenido"] == "El servicio fue excelente."
    assert body["puntuacion"] == 5
    assert body["fuente"] == "manual"
    assert body["estado"] == "nueva"
    assert body["categoria"] is None
    assert body["prioridad"] is None

    _, session_factory = client
    with session_factory() as db:
        persisted_review = db.get(Review, body["id"])

    assert persisted_review is not None
    assert persisted_review.tenant_id == 10


def test_registrar_review_manual_requiere_autenticacion(client) -> None:
    response = client[0].post("/api/v1/reviews", json=manual_review_payload())

    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        manual_review_payload(contenido="   "),
        manual_review_payload(puntuacion=6),
        manual_review_payload(tenant_id=20),
    ],
)
def test_registrar_review_manual_rechaza_payload_invalido(client, seed_users, payload) -> None:
    response = client[0].post(
        "/api/v1/reviews",
        json=payload,
        headers=login(client),
    )

    assert response.status_code == 422


def test_listar_reviews_requiere_autenticacion(client) -> None:
    response = client[0].get("/api/v1/reviews")

    assert response.status_code == 401


def test_listar_reviews_devuelve_solo_el_tenant_autenticado(
    client,
    seed_reviews,
) -> None:
    response = client[0].get("/api/v1/reviews", headers=login(client))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [102, 101]
    assert {item["tenant_id"] for item in body["items"]} == {10}


def test_consultar_detalle_del_mismo_tenant(client, seed_reviews) -> None:
    response = client[0].get("/api/v1/reviews/101", headers=login(client))

    assert response.status_code == 200
    assert response.json()["contenido"] == "Review anterior"


@pytest.mark.parametrize("review_id", [201, 999])
def test_review_ajena_o_inexistente_devuelve_404(
    client,
    seed_reviews,
    review_id: int,
) -> None:
    response = client[0].get(
        f"/api/v1/reviews/{review_id}",
        headers=login(client),
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Review con id {review_id} no encontrada"
    }


def test_admin_general_sin_tenant_no_puede_consultar_reviews(
    client,
    seed_reviews,
) -> None:
    response = client[0].get(
        "/api/v1/reviews",
        headers=login(client, "general@example.com"),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "El usuario no pertenece a un tenant"}
