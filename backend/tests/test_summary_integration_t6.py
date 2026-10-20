"""T6: recorrido HTTP completo desde login hasta lectura y regeneración."""

from datetime import datetime
import json

import httpx

from app.core.ai_config import AISettings
from app.models.review import Review
from app.services.ai_provider import create_ai_provider


def test_login_generate_reload_and_regenerate_with_mock_provider(client, seed_users, monkeypatch):
    http_client, session_factory = client
    with session_factory() as db:
        db.add(Review(
            id=101, tenant_id=10, contenido="La entrega tardó, pero el producto llegó bien.",
            fecha=datetime(2026, 10, 19), fuente="manual", puntuacion=3, estado="nueva",
        ))
        db.commit()

    summaries = iter((
        "La entrega tardó y el producto llegó en buen estado.",
        "El producto llegó bien, aunque hubo demora en la entrega.",
    ))
    provider_requests = []

    def respond(request):
        provider_requests.append(request)
        return httpx.Response(200, json={"candidates": [{
            "finishReason": "STOP",
            "content": {"parts": [{"text": json.dumps({"resumen": next(summaries)})}]},
        }]})

    settings = AISettings(_env_file=None, gemini_api_key="test-key-not-for-production")
    monkeypatch.setattr(
        "app.services.summary_service.create_ai_provider",
        lambda: create_ai_provider(settings, transport=httpx.MockTransport(respond)),
    )

    login = http_client.post("/api/v1/auth/login", json={
        "correo": "usuario@example.com", "password": "secret123",
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    first = http_client.post("/api/v1/reviews/101/resumen", headers=headers, json={})
    assert first.status_code == 200
    assert first.json()["resumen"] == "La entrega tardó y el producto llegó en buen estado."
    detail = http_client.get("/api/v1/reviews/101", headers=headers)
    assert detail.status_code == 200
    assert detail.json() == first.json()

    second = http_client.post("/api/v1/reviews/101/resumen", headers=headers, json={})
    assert second.status_code == 200
    assert second.json()["resumen"] == "El producto llegó bien, aunque hubo demora en la entrega."
    assert http_client.get("/api/v1/reviews/101", headers=headers).json() == second.json()
    assert len(provider_requests) == 2
    assert all(
        json.loads(request.content)["contents"][0]["parts"][0]["text"]
        == "La entrega tardó, pero el producto llegó bien."
        for request in provider_requests
    )
