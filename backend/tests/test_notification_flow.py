"""Flujo HTTP de prioridad, aviso, lectura y exportación con datos sintéticos."""

import csv
import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError

from app.core.ai_config import AISettings
from app.core.security import get_password_hash
from app.models.notification import ReviewNotification
from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository
from app.services.ai_provider import create_ai_provider


FEED = "/api/v1/notificaciones"
PRIORITY = "/api/v1/reviews/101/prioridad"


@pytest.fixture()
def flow(client, seed_users, monkeypatch):
    with client[1]() as db:
        db.add(Tenant(id=20, nombre="Segundo negocio sintético", estado="activo"))
        db.flush()
        db.add(User(tenant_id=20, nombre="Cuenta de prueba", correo="otro@example.com",
                    password_hash=get_password_hash("secret123"), rol="usuario_negocio", estado="activo"))
        for review_id, tenant_id in ((101, 10), (201, 20)):
            db.add(Review(id=review_id, tenant_id=tenant_id, autor="Cliente sintético",
                          contenido="Me cobraron dos veces y nadie me responde.", fecha=datetime(2026, 11, 2),
                          fuente="manual", puntuacion=5, estado="en_revision", prioridad="Media",
                          categoria="Queja", resumen="Resumen conservado", tema="Cobro"))
        db.commit()
    settings = AISettings(_env_file=None, gemini_api_key="synthetic-test-key")
    behavior = {"text": '{"prioridad":"Alta"}', "status": 200, "handler": None, "calls": 0}

    def respond(request):
        behavior["calls"] += 1
        if behavior["handler"]:
            return behavior["handler"](request)
        if behavior["status"] != 200:
            return httpx.Response(behavior["status"], text="private-provider-detail")
        return httpx.Response(200, json={"candidates": [{
            "finishReason": "STOP", "content": {"parts": [{"text": behavior["text"]}]},
        }]})

    monkeypatch.setattr("app.services.priority_service.create_ai_provider",
                        lambda: create_ai_provider(settings, transport=httpx.MockTransport(respond)))
    return behavior


def login(client, email="usuario@example.com"):
    response = client[0].post("/api/v1/auth/login", json={"correo": email, "password": "secret123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def feed(client, headers):
    response = client[0].get(FEED, headers=headers)
    assert response.status_code == 200
    return response.json()


def detail(client, headers):
    response = client[0].get("/api/v1/reviews/101", headers=headers)
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize("email", ["usuario@example.com", "tenant@example.com"])
def test_high_result_reaches_feed_detail_and_csv_without_changing_followup(client, flow, email):
    headers = login(client, email)
    before = detail(client, headers)
    previous_csv = client[0].get("/api/v1/reviews/export", headers=headers).content
    assert feed(client, headers) == {"items": [], "total": 0}
    result = client[0].post(PRIORITY, headers=headers)
    assert result.status_code == 200
    assert result.json() == before | {"prioridad": "Alta"}
    notice = feed(client, headers)
    assert notice["total"] == 1 and notice["items"][0]["review_id"] == 101
    assert notice["items"][0]["extracto"] == before["contenido"]
    assert detail(client, headers) == result.json()
    exported = client[0].get("/api/v1/reviews/export", headers=headers)
    assert exported.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert len(rows) == 1 and rows[0]["id"] == "101"
    assert rows[0]["estado"] == before["estado"]
    assert exported.content == previous_csv


def test_http_retries_and_priority_cycle_reuse_the_same_notice(client, flow):
    headers = login(client)
    assert client[0].post(PRIORITY, headers=headers).status_code == 200
    original = feed(client, headers)
    for priority in ("Alta", "Alta", "Media", "Alta"):
        flow["text"] = json.dumps({"prioridad": priority})
        assert client[0].post(PRIORITY, headers=headers).status_code == 200
        assert feed(client, headers) == ({"items": [], "total": 0} if priority == "Media" else original)
        assert detail(client, headers)["estado"] == "en_revision"
    with client[1]() as db:
        assert db.query(ReviewNotification).count() == 1


@pytest.mark.parametrize("priority", ["Baja", "Media"])
def test_non_high_result_never_creates_a_notice(client, flow, priority):
    headers = login(client)
    before = detail(client, headers)
    flow["text"] = json.dumps({"prioridad": priority})
    result = client[0].post(PRIORITY, headers=headers)
    assert result.status_code == 200
    assert detail(client, headers) == before | {"prioridad": priority}
    assert feed(client, headers) == {"items": [], "total": 0}


@pytest.mark.parametrize("text,status,expected", [
    ('{"prioridad":null}', 200, 422), ('{"prioridad":"Urgente"}', 200, 502),
    ("no JSON", 200, 502), ("", 429, 503), ("", 504, 504),
])
def test_provider_failures_preserve_saved_priority_and_notice(client, flow, text, status, expected):
    headers = login(client)
    assert client[0].post(PRIORITY, headers=headers).status_code == 200
    before, notices = detail(client, headers), feed(client, headers)
    flow.update(text=text, status=status)
    response = client[0].post(PRIORITY, headers=headers)
    assert response.status_code == expected
    assert "private-provider-detail" not in response.text
    assert detail(client, headers) == before and feed(client, headers) == notices


@pytest.mark.parametrize("failure", ["insert", "commit"])
def test_http_write_failure_rolls_back_priority_and_notice(client, flow, monkeypatch, failure):
    headers = login(client)
    before = detail(client, headers)

    def fail(*args, **kwargs):
        raise SQLAlchemyError("private-database-detail")

    with monkeypatch.context() as patch:
        if failure == "insert":
            patch.setattr(NotificationRepository, "add_for_high_review", fail)
        else:
            patch.setattr(client[1].class_, "commit", fail)
        response = client[0].post(PRIORITY, headers=headers)
    assert response.status_code == 500
    assert "private-database-detail" not in response.text
    assert detail(client, headers) == before
    assert feed(client, headers) == {"items": [], "total": 0}


def test_content_changed_during_generation_creates_no_notice(client, flow):
    headers = login(client)

    def change_content(request):
        with client[1]() as db:
            db.execute(update(Review).where(Review.id == 101).values(contenido="Contenido corregido"))
            db.commit()
        return httpx.Response(200, json={"candidates": [{
            "finishReason": "STOP", "content": {"parts": [{"text": '{"prioridad":"Alta"}'}]},
        }]})

    flow["handler"] = change_content
    assert client[0].post(PRIORITY, headers=headers).status_code == 409
    assert detail(client, headers)["prioridad"] == "Media"
    assert feed(client, headers) == {"items": [], "total": 0}


def test_notifications_and_their_review_links_are_isolated_both_ways(client, flow):
    accounts = [(login(client), 101, 201), (login(client, "otro@example.com"), 201, 101)]
    for headers, own, _ in accounts:
        assert client[0].post(f"/api/v1/reviews/{own}/prioridad", headers=headers).status_code == 200
    calls = flow["calls"]
    for headers, own, foreign in accounts:
        notice = client[0].get(FEED + "?tenant_id=999", headers=headers).json()
        assert notice["total"] == 1 and notice["items"][0]["review_id"] == own
        assert client[0].get(f"/api/v1/reviews/{foreign}", headers=headers).status_code == 404
        assert client[0].post(f"/api/v1/reviews/{foreign}/prioridad", headers=headers).status_code == 404
    assert flow["calls"] == calls


def test_concurrent_http_retries_create_only_one_notice(client, flow):
    headers = login(client)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: client[0].post(PRIORITY, headers=headers), range(4)))
    assert all(response.status_code == 200 for response in responses)
    assert feed(client, headers)["total"] == 1
    assert detail(client, headers)["estado"] == "en_revision"
    with client[1]() as db:
        assert db.query(ReviewNotification).count() == 1
