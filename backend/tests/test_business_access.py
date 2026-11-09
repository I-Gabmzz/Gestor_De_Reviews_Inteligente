from datetime import datetime

import jwt
import pytest
from sqlalchemy import create_engine

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.init_db import init_db
from app.models.external_review_connection import ExternalReviewConnection
from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User


def login(api, email):
    return api.post("/api/v1/auth/login", json={"correo": email, "password": "secret123"})


def bearer(response):
    assert response.status_code == 200, response.json()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def businesses(client, seed_users):
    api, sessions = client
    with sessions() as db:
        db.add(Tenant(id=20, nombre="Negocio B", estado="activo"))
        db.flush()
        db.add(User(
            tenant_id=20, nombre="Usuario B", correo="user-b@example.com",
            password_hash=get_password_hash("secret123"), rol="usuario_negocio", estado="activo",
        ))
        db.add_all([
            Review(
                id=101, tenant_id=10, contenido="Reseña A", fecha=datetime(2026, 11, 9),
                fuente="manual", puntuacion=4, estado="nueva",
            ),
            Review(
                id=202, tenant_id=20, contenido="Reseña B", fecha=datetime(2026, 11, 9),
                fuente="manual", puntuacion=5, estado="nueva",
            ),
            ExternalReviewConnection(
                tenant_id=10, source="Google", business_data_id="0xabc:0x123",
                persistence_enabled=True, approval_reference="Conexión sintética",
            ),
        ])
        db.commit()
    return api, sessions


def test_business_lifecycle_preserves_data_and_revokes_previous_sessions(businesses):
    api, sessions = businesses
    general = bearer(login(api, "general@example.com"))
    admin_a = bearer(login(api, "tenant@example.com"))
    user_a = bearer(login(api, "usuario@example.com"))
    user_b = bearer(login(api, "user-b@example.com"))
    business = "/api/v1/tenants/10"
    review_a = "/api/v1/reviews/101"
    review_b = "/api/v1/reviews/202"

    for headers in (admin_a, user_a, user_b):
        assert api.patch(business, headers=headers, json={"estado": "inactivo"}).status_code == 403
    assert api.get(review_a, headers=user_b).status_code == 404
    assert api.get(review_b, headers=user_a).status_code == 404

    renamed = api.patch(business, headers=general, json={"nombre": "Negocio A renovado"})
    assert renamed.status_code == 200
    assert api.get(business, headers=general).json() == {
        "id": 10, "nombre": "Negocio A renovado", "estado": "activo",
    }
    assert api.get(review_a, headers=admin_a).status_code == 200
    assert api.get(review_a, headers=user_a).status_code == 200

    assert api.patch(business, headers=general, json={"estado": "inactivo"}).status_code == 200
    assert api.get(business, headers=general).json()["estado"] == "inactivo"
    for email, headers in (("tenant@example.com", admin_a), ("usuario@example.com", user_a)):
        assert api.get(review_a, headers=headers).status_code == 403
        assert login(api, email).status_code == 403
    assert api.get(review_b, headers=user_b).status_code == 200
    with sessions() as db:
        assert db.get(Review, 101).contenido == "Reseña A"
        assert db.get(ExternalReviewConnection, (10, "Google", "0xabc:0x123")).persistence_enabled
        assert db.get(Tenant, 20).estado == "activo"

    assert api.patch(business, headers=general, json={"estado": "activo"}).status_code == 200
    assert api.get(business, headers=general).json()["estado"] == "activo"
    for email, previous in (("tenant@example.com", admin_a), ("usuario@example.com", user_a)):
        assert api.get(review_a, headers=previous).status_code == 401
        current = bearer(login(api, email))
        assert api.get(review_a, headers=current).status_code == 200
        assert api.get(review_b, headers=current).status_code == 404
    assert login(api, "inactive@example.com").status_code == 403
    assert api.get(review_b, headers=user_b).status_code == 200


def test_session_issued_before_upgrade_stays_valid_until_deactivation(businesses):
    api, _ = businesses
    general = bearer(login(api, "general@example.com"))
    token = login(api, "usuario@example.com").json()["access_token"]
    claims = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    del claims["session_version"]
    legacy = jwt.encode(claims, settings.secret_key, algorithm=settings.jwt_algorithm)
    headers = {"Authorization": f"Bearer {legacy}"}
    assert api.get("/api/v1/reviews/101", headers=headers).status_code == 200
    for state in ("inactivo", "activo"):
        assert api.patch("/api/v1/tenants/10", headers=general, json={"estado": state}).status_code == 200
    assert api.get("/api/v1/reviews/101", headers=headers).status_code == 401


def test_startup_adds_session_version_to_existing_businesses(tmp_path):
    database = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    try:
        with database.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE tenants (id INTEGER PRIMARY KEY, nombre VARCHAR(255) NOT NULL, estado VARCHAR(50) NOT NULL)"
            )
            connection.exec_driver_sql("INSERT INTO tenants VALUES (10, 'Negocio anterior', 'activo')")
        init_db(database)
        init_db(database)
        with database.connect() as connection:
            assert tuple(connection.exec_driver_sql("SELECT * FROM tenants").one()) == (
                10, "Negocio anterior", "activo", 0,
            )
    finally:
        database.dispose()
