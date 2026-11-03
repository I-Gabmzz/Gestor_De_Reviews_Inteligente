from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, update
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import create_access_token, get_password_hash
from app.models.notification import ReviewNotification
from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository


URL = "/api/v1/notificaciones"


@pytest.fixture()
def notifications(client, seed_users):
    with client[1]() as db:
        db.add(Tenant(id=20, nombre="Otro negocio", estado="activo"))
        db.flush()
        db.add(User(id=20, tenant_id=20, nombre="Otra cuenta", correo="otro@example.com",
                    password_hash=get_password_hash("secret123"), rol="usuario_negocio", estado="activo"))
        for review_id, tenant_id, priority in [(101, 10, "Alta"), (102, 10, "Alta"), (103, 10, "Media"), (201, 20, "Alta")]:
            db.add(Review(id=review_id, tenant_id=tenant_id, autor=f"Autor {review_id}", contenido="Comentario sintético " * 20,
                          fecha=datetime(2026, 11, 1), fuente="manual", puntuacion=3, estado="en_revision", prioridad=priority))
        db.flush()
        for notification_id, review_id, tenant_id in [(1, 101, 10), (2, 102, 10), (3, 103, 10), (4, 201, 20)]:
            db.add(ReviewNotification(id=notification_id, tenant_id=tenant_id, review_id=review_id, creada_en=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)))
        db.commit()


def login(client, correo="usuario@example.com"):
    response = client[0].post("/api/v1/auth/login", json={"correo": correo, "password": "secret123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.parametrize("correo", ["usuario@example.com", "tenant@example.com"])
def test_business_roles_read_only_active_high_notifications_with_utc_preview(client, notifications, correo):
    response = client[0].get(URL, headers=login(client, correo))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["review_id"] for item in body["items"]] == [102, 101]
    for item in body["items"]:
        assert set(item) == {"id", "review_id", "creada_en", "autor", "extracto", "prioridad"}
        assert item["creada_en"].endswith("Z")
        assert len(item["extracto"]) == 180
        assert item["prioridad"] == "Alta"


def test_tenant_injection_never_expands_access_and_isolation_is_bidirectional(client, notifications):
    for correo, expected in [("usuario@example.com", [102, 101]), ("otro@example.com", [201])]:
        response = client[0].get(URL + "?tenant_id=999", headers=login(client, correo))
        assert [item["review_id"] for item in response.json()["items"]] == expected


@pytest.mark.parametrize("correo,status", [(None, 401), ("general@example.com", 403), ("inactive@example.com", 403)])
def test_unauthorized_accounts_cannot_read_notifications(client, notifications, correo, status):
    if correo == "inactive@example.com":
        headers = {"Authorization": "Bearer " + create_access_token(subject="4", rol="usuario_negocio", tenant_id=10)}
    else:
        headers = login(client, correo) if correo else {}
    assert client[0].get(URL, headers=headers).status_code == status


def test_expired_or_invalid_token_is_rejected(client, notifications):
    assert client[0].get(URL, headers={"Authorization": "Bearer invalid"}).status_code == 401


@pytest.mark.parametrize("target", ["user", "tenant", "role"])
def test_current_account_state_is_checked_with_existing_token(client, notifications, target):
    headers = login(client)
    with client[1]() as db:
        if target == "tenant":
            db.get(Tenant, 10).estado = "inactivo"
        elif target == "user":
            db.get(User, 1).estado = "inactivo"
        else:
            db.get(User, 1).rol = "admin_general"
            db.get(User, 1).tenant_id = None
        db.commit()
    assert client[0].get(URL, headers=headers).status_code == 403


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "limit=no"])
def test_pagination_is_bounded(client, notifications, query):
    assert client[0].get(URL + "?" + query, headers=login(client)).status_code == 422


def test_pagination_keeps_total_and_deterministic_order(client, notifications):
    body = client[0].get(URL + "?limit=1&offset=1", headers=login(client)).json()
    assert body["total"] == 2 and [item["review_id"] for item in body["items"]] == [101]


@pytest.mark.parametrize("change", ["priority", "tenant", "delete"])
def test_hidden_or_unavailable_reviews_do_not_expose_old_notifications(client, notifications, change):
    with client[1]() as db:
        if change == "delete":
            db.execute(delete(Review).where(Review.id == 101))
        else:
            db.execute(update(Review).where(Review.id == 101).values(**({"prioridad": "Baja"} if change == "priority" else {"tenant_id": 20})))
        db.commit()
    body = client[0].get(URL, headers=login(client)).json()
    assert body["total"] == 1 and [item["review_id"] for item in body["items"]] == [102]
    assert [item["review_id"] for item in client[0].get(URL, headers=login(client, "otro@example.com")).json()["items"]] == [201]


def test_read_does_not_create_events_or_change_review_status(client, notifications):
    headers = login(client)
    for _ in range(2):
        assert client[0].get(URL, headers=headers).status_code == 200
    with client[1]() as db:
        assert db.query(ReviewNotification).count() == 4
        assert all(review.estado == "en_revision" for review in db.query(Review).all())
    assert client[0].post(URL, headers=headers, json={"review_id": 103, "tenant_id": 10}).status_code == 405


@pytest.mark.parametrize("review_id,tenant_id", [(103, 10), (201, 10), (999, 10)])
def test_internal_creation_requires_current_high_review_in_tenant(client, notifications, review_id, tenant_id):
    with client[1]() as db:
        assert NotificationRepository(db).add_for_high_review(review_id, tenant_id) is None


def test_internal_creation_does_not_commit_callers_transaction(client, notifications):
    with client[1]() as db:
        db.execute(delete(ReviewNotification).where(ReviewNotification.review_id == 101))
        db.commit()
        created = NotificationRepository(db).add_for_high_review(101, 10)
        assert created is not None
        db.rollback()
    with client[1]() as db:
        assert db.query(ReviewNotification).filter_by(review_id=101, tenant_id=10).count() == 0


def test_database_failure_is_controlled_without_exposing_details(client, notifications, monkeypatch):
    def fail_query(*args, **kwargs):
        raise SQLAlchemyError("private-database-detail")

    monkeypatch.setattr(NotificationRepository, "list_for_tenant", fail_query)
    response = client[0].get(URL, headers=login(client))
    assert response.status_code == 500
    assert response.json() == {"detail": "No fue posible consultar los avisos de prioridad"}


def test_empty_feed_and_legacy_high_priority_are_not_backfilled(client, notifications):
    with client[1]() as db:
        db.execute(delete(ReviewNotification).where(ReviewNotification.tenant_id == 10))
        db.commit()
    headers = login(client)
    assert client[0].get(URL, headers=headers).json() == {"items": [], "total": 0}
    assert client[0].get(URL, headers=headers).json() == {"items": [], "total": 0}
