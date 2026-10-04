from datetime import datetime

import pytest
from sqlalchemy import select

from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User


@pytest.fixture()
def editable_reviews(client, seed_users):
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
                    fecha=datetime(2026, 9, 20, 12),
                    fuente="Google",
                    puntuacion=4,
                    estado="en_revision",
                    categoria="Queja",
                    prioridad="Alta",
                ),
                Review(
                    id=102,
                    tenant_id=10,
                    autor="Luis",
                    contenido="Otra review del negocio",
                    fecha=datetime(2026, 9, 21, 12),
                    fuente="Facebook",
                    puntuacion=2,
                    estado="nueva",
                ),
                Review(
                    id=201,
                    tenant_id=20,
                    autor="Persona externa",
                    contenido="Contenido privado",
                    fecha=datetime(2026, 9, 22, 12),
                    fuente="Google",
                    puntuacion=1,
                    estado="nueva",
                ),
            ]
        )
        db.commit()


def login(client, correo="usuario@example.com") -> dict[str, str]:
    response = client[0].post(
        "/api/v1/auth/login",
        json={"correo": correo, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.parametrize("correo", ["usuario@example.com", "tenant@example.com"])
def test_editar_campos_permitidos_persiste_sin_modificar_campos_protegidos(
    client, editable_reviews, correo
) -> None:
    headers = login(client, correo)
    before = client[0].get("/api/v1/reviews/101", headers=headers).json()
    changes = {
        "autor": "Mariana",
        "contenido": "Contenido corregido",
        "fecha": "2026-09-27T09:30:00",
        "fuente": "Facebook",
        "puntuacion": 5,
    }

    response = client[0].patch(
        "/api/v1/reviews/101", headers=headers, json=changes
    )

    assert response.status_code == 200
    assert response.json() == before | changes
    # Cada petición GET usa una nueva sesión de base de datos.
    assert client[0].get("/api/v1/reviews/101", headers=headers).json() == before | changes
    with client[1]() as db:
        untouched = db.get(Review, 102)
        assert untouched.contenido == "Otra review del negocio"
        foreign = db.get(Review, 201)
        assert foreign.contenido == "Contenido privado"


def test_edicion_parcial_conserva_campos_omitidos(client, editable_reviews) -> None:
    headers = login(client)
    before = client[0].get("/api/v1/reviews/101", headers=headers).json()

    response = client[0].patch(
        "/api/v1/reviews/101",
        headers=headers,
        json={"contenido": "  Nuevo contenido  "},
    )

    assert response.status_code == 200
    assert response.json() == before | {"contenido": "Nuevo contenido"}


@pytest.mark.parametrize("autor", [None, "", "   "])
def test_autor_puede_eliminarse(client, editable_reviews, autor) -> None:
    headers = login(client)
    response = client[0].patch(
        "/api/v1/reviews/101", headers=headers, json={"autor": autor}
    )

    assert response.status_code == 200
    assert response.json()["autor"] is None
    assert client[0].get("/api/v1/reviews/101", headers=headers).json()["autor"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"contenido": ""},
        {"contenido": " \t\n "},
        {"contenido": None},
        {"contenido": 123},
        {"autor": "a" * 256},
        {"fuente": ""},
        {"fuente": "   "},
        {"fuente": "a" * 101},
        {"fuente": None},
        {"puntuacion": 0},
        {"puntuacion": 6},
        {"puntuacion": 1.5},
        {"puntuacion": True},
        {"puntuacion": "3"},
        {"puntuacion": None},
        {"fecha": "no-es-fecha"},
        {"fecha": "2026-02-30"},
        {"fecha": "42"},
        {"fecha": 42},
        {"fecha": None},
        {"contenido": "Cambio válido", "puntuacion": 6},
    ],
)
def test_datos_invalidos_no_guardan_cambios(client, editable_reviews, payload) -> None:
    headers = login(client)
    before = client[0].get("/api/v1/reviews/101", headers=headers).json()

    response = client[0].patch(
        "/api/v1/reviews/101", headers=headers, json=payload
    )

    assert response.status_code == 422
    assert client[0].get("/api/v1/reviews/101", headers=headers).json() == before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", 999),
        ("tenant_id", 20),
        ("estado", "atendida"),
        ("categoria", "Felicitacion"),
        ("prioridad", "Baja"),
        ("resumen", "Texto generado modificado"),
        ("solucion", "Solución modificada"),
    ],
)
def test_campos_protegidos_o_desconocidos_rechazan_toda_la_peticion(
    client, editable_reviews, field, value
) -> None:
    headers = login(client)
    before = client[0].get("/api/v1/reviews/101", headers=headers).json()

    response = client[0].patch(
        "/api/v1/reviews/101",
        headers=headers,
        json={"contenido": "Cambio válido", field: value},
    )

    assert response.status_code == 422
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    assert client[0].get("/api/v1/reviews/101", headers=headers).json() == before


@pytest.mark.parametrize("review_id", [201, 999])
def test_editar_review_ajena_o_inexistente_no_revela_datos(
    client, editable_reviews, review_id
) -> None:
    response = client[0].patch(
        f"/api/v1/reviews/{review_id}",
        headers=login(client),
        json={"contenido": "Intento de modificación"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": f"Review con id {review_id} no encontrada"}
    with client[1]() as db:
        assert db.get(Review, 201).contenido == "Contenido privado"


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer token-invalido"}])
def test_editar_requiere_autenticacion(client, editable_reviews, headers) -> None:
    response = client[0].patch(
        "/api/v1/reviews/101", headers=headers, json={"contenido": "Cambio"}
    )

    assert response.status_code == 401
    with client[1]() as db:
        assert db.get(Review, 101).contenido == "Contenido original"


def test_admin_general_sin_tenant_no_puede_editar(client, editable_reviews) -> None:
    response = client[0].patch(
        "/api/v1/reviews/101",
        headers=login(client, "general@example.com"),
        json={"contenido": "Cambio"},
    )

    assert response.status_code == 403
    with client[1]() as db:
        assert db.get(Review, 101).contenido == "Contenido original"


def test_usuario_desactivado_no_puede_editar_con_token_anterior(
    client, editable_reviews
) -> None:
    headers = login(client)
    with client[1]() as db:
        user = db.scalar(select(User).where(User.correo == "usuario@example.com"))
        user.estado = "inactivo"
        db.commit()

    response = client[0].patch(
        "/api/v1/reviews/101", headers=headers, json={"contenido": "Cambio"}
    )

    assert response.status_code == 403
    with client[1]() as db:
        assert db.get(Review, 101).contenido == "Contenido original"


@pytest.mark.parametrize(
    ("fecha", "expected"),
    [
        ("2026-09-27", "2026-09-27T00:00:00"),
        ("2026-09-27T12:30:00-07:00", "2026-09-27T19:30:00"),
    ],
)
def test_fecha_iso_se_guarda_correctamente(client, editable_reviews, fecha, expected) -> None:
    headers = login(client)
    response = client[0].patch(
        "/api/v1/reviews/101", headers=headers, json={"fecha": fecha}
    )

    assert response.status_code == 200
    assert response.json()["fecha"] == expected
    assert client[0].get("/api/v1/reviews/101", headers=headers).json()["fecha"] == expected


def test_editar_puntuacion_actualiza_dashboard_sin_incluir_otro_tenant(
    client, editable_reviews
) -> None:
    headers = login(client)
    before = client[0].get("/api/v1/dashboard", headers=headers).json()
    assert before["promedio_puntuacion"] == 3

    response = client[0].patch(
        "/api/v1/reviews/101", headers=headers, json={"puntuacion": 5}
    )
    dashboard = client[0].get("/api/v1/dashboard", headers=headers)

    assert response.status_code == 200
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["promedio_puntuacion"] == 3.5
    assert body["total_reviews"] == before["total_reviews"] == 2
    assert body["reviews_nuevas"] == before["reviews_nuevas"] == 1
