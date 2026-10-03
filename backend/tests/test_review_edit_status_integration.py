from datetime import datetime

from app.models.review import Review
from app.models.tenant import Tenant


def test_edit_and_status_endpoints_preserve_each_others_fields(client, seed_users) -> None:
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
                ),
                Review(
                    id=201,
                    tenant_id=20,
                    autor="Cliente externo",
                    contenido="Contenido privado",
                    fecha=datetime(2026, 9, 21),
                    fuente="Google",
                    puntuacion=2,
                    estado="nueva",
                ),
            ]
        )
        db.commit()

    login = client[0].post(
        "/api/v1/auth/login",
        json={"correo": "usuario@example.com", "password": "secret123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    status_response = client[0].patch(
        "/api/v1/reviews/101/status",
        headers=headers,
        json={"estado": "en_revision"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["contenido"] == "Contenido original"

    edit_response = client[0].patch(
        "/api/v1/reviews/101",
        headers=headers,
        json={"contenido": "Contenido corregido", "puntuacion": 5},
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["estado"] == "en_revision"

    assert client[0].patch(
        "/api/v1/reviews/101",
        headers=headers,
        json={"estado": "atendida"},
    ).status_code == 422
    assert client[0].patch(
        "/api/v1/reviews/101/status",
        headers=headers,
        json={"estado": "atendida", "contenido": "Cambio no permitido"},
    ).status_code == 422

    for path in ("/api/v1/reviews/201", "/api/v1/reviews/201/status"):
        assert client[0].patch(
            path,
            headers=headers,
            json={"contenido": "Cambio"} if path.endswith("/201") else {"estado": "atendida"},
        ).status_code == 404

    with session_factory() as db:
        own = db.get(Review, 101)
        foreign = db.get(Review, 201)
        assert (own.contenido, own.puntuacion, own.estado) == (
            "Contenido corregido",
            5,
            "en_revision",
        )
        assert (foreign.contenido, foreign.estado) == ("Contenido privado", "nueva")
