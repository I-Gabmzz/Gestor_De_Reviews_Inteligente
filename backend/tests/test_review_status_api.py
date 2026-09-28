from datetime import datetime

import pytest

from app.models.review import Review
from app.models.tenant import Tenant


@pytest.fixture()
def reviews_for_status(client, seed_users):
    _, session_factory = client
    with session_factory() as db:
        db.add(Tenant(id=20, nombre="Otro negocio", estado="activo"))
        db.add_all(
            [
                Review(
                    id=101,
                    tenant_id=10,
                    autor="Ana",
                    contenido="Contenido original",
                    fecha=datetime(2026, 9, 20),
                    fuente="Google",
                    puntuacion=4,
                    estado="nueva",
                    categoria="servicio",
                    prioridad="alta",
                ),
                Review(
                    id=201,
                    tenant_id=20,
                    autor="Cliente externo",
                    contenido="Review ajena",
                    fecha=datetime(2026, 9, 21),
                    fuente="Facebook",
                    puntuacion=2,
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


@pytest.mark.parametrize("new_status", ["nueva", "en_revision", "atendida"])
def test_actualizar_estado_persiste_solo_estado(client, reviews_for_status, new_status):
    response = client[0].patch(
        "/api/v1/reviews/101/status",
        json={"estado": new_status},
        headers=login(client),
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": 101,
        "tenant_id": 10,
        "autor": "Ana",
        "contenido": "Contenido original",
        "fecha": "2026-09-20T00:00:00",
        "fuente": "Google",
        "puntuacion": 4,
        "estado": new_status,
        "categoria": "servicio",
        "prioridad": "alta",
    }

    with client[1]() as db:
        review = db.get(Review, 101)
        assert review.estado == new_status
        assert review.tenant_id == 10
        assert review.autor == "Ana"
        assert review.contenido == "Contenido original"
        assert review.fecha == datetime(2026, 9, 20)
        assert review.fuente == "Google"
        assert review.puntuacion == 4
        assert review.categoria == "servicio"
        assert review.prioridad == "alta"


@pytest.mark.parametrize("review_id", [201, 999])
def test_review_ajena_o_inexistente_no_se_actualiza(client, reviews_for_status, review_id):
    response = client[0].patch(
        f"/api/v1/reviews/{review_id}/status",
        json={"estado": "atendida"},
        headers=login(client),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": f"Review con id {review_id} no encontrada"}
    with client[1]() as db:
        assert db.get(Review, 201).estado == "nueva"


@pytest.mark.parametrize("payload", [{"estado": "pendiente"}, {"estado": "en revision"}, {}])
def test_rechaza_estado_invalido_o_ausente(client, reviews_for_status, payload):
    response = client[0].patch(
        "/api/v1/reviews/101/status",
        json=payload,
        headers=login(client),
    )

    assert response.status_code == 422
    with client[1]() as db:
        assert db.get(Review, 101).estado == "nueva"


def test_rechaza_cambios_a_otros_campos(client, reviews_for_status):
    response = client[0].patch(
        "/api/v1/reviews/101/status",
        json={"estado": "atendida", "contenido": "Contenido alterado"},
        headers=login(client),
    )

    assert response.status_code == 422
    with client[1]() as db:
        review = db.get(Review, 101)
        assert review.estado == "nueva"
        assert review.contenido == "Contenido original"


def test_actualizar_estado_requiere_autenticacion(client, reviews_for_status):
    response = client[0].patch(
        "/api/v1/reviews/101/status",
        json={"estado": "atendida"},
    )

    assert response.status_code == 401


def test_admin_general_sin_tenant_no_puede_actualizar(client, reviews_for_status):
    response = client[0].patch(
        "/api/v1/reviews/101/status",
        json={"estado": "atendida"},
        headers=login(client, "general@example.com"),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "El usuario no pertenece a un tenant"}
