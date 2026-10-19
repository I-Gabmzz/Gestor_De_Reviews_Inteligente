from datetime import datetime
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import update

from app.api.routers.topics import get_topic_service
from app.core.ai_config import AISettings
from app.main import app
from app.models.review import Review
from app.models.tenant import Tenant
from app.schemas.review import ReviewRead
from app.services.ai_provider import (
    AIError, AIBlockedResponseError, AIConfigurationError, AICredentialsError,
    AIInputError, AIInvalidResponseError, AIQuotaError, AIRequestError,
    AITimeoutError, AIUnavailableError, create_ai_provider,
)
from app.services.topic_service import TopicContentError, TopicConflictError, TopicPersistenceError


URL = "/api/v1/reviews/101/tema"


def completion(text):
    return httpx.Response(200, json={"candidates": [{
        "finishReason": "STOP", "content": {"parts": [{"text": text}]},
    }]})


@pytest.fixture()
def reviews(client, seed_users):
    with client[1]() as db:
        db.add(Tenant(id=20, nombre="Otro negocio", estado="activo"))
        db.flush()
        for review_id, tenant_id in ((101, 10), (201, 20)):
            db.add(Review(
                id=review_id, tenant_id=tenant_id, autor="Ana", contenido="Mi pedido llegó tarde.",
                fecha=datetime(2026, 10, 19), fuente="manual", puntuacion=2,
                estado="en_revision", categoria="Queja", prioridad="Alta",
                resumen="Resumen previo", tema="Producto",
            ))
        db.commit()


@pytest.fixture()
def provider(monkeypatch):
    requests = []
    behavior = {"handler": lambda _: completion('{"tema":"Servicio"}')}

    def handler(request):
        requests.append(request)
        return behavior["handler"](request)

    config = AISettings(_env_file=None, gemini_api_key="synthetic-test-key")
    factory = Mock(side_effect=lambda: create_ai_provider(config, transport=httpx.MockTransport(handler)))
    monkeypatch.setattr("app.services.topic_service.create_ai_provider", factory)
    return factory, requests, behavior


def login(client, correo="usuario@example.com"):
    response = client[0].post("/api/v1/auth/login", json={"correo": correo, "password": "secret123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def stored(client, review_id=101):
    with client[1]() as db:
        return ReviewRead.model_validate(db.get(Review, review_id)).model_dump(mode="json")


@pytest.mark.parametrize("correo", ["usuario@example.com", "tenant@example.com"])
def test_detect_persists_only_topic_and_get_reads_it(client, reviews, provider, correo):
    headers = login(client, correo)
    before = stored(client)
    response = client[0].post(URL, headers=headers)
    assert response.status_code == 200
    assert response.json() == before | {"tema": "Servicio"}
    assert stored(client) == response.json()
    assert client[0].get("/api/v1/reviews/101", headers=headers).json() == response.json()
    assert stored(client, 201)["tema"] == "Producto"
    provider[0].assert_called_once()


def test_explicit_redetection_replaces_only_topic(client, reviews, provider):
    headers = login(client)
    before = stored(client)
    assert client[0].post(URL, headers=headers).json()["tema"] == "Servicio"
    provider[2]["handler"] = lambda _: completion('{"tema":"Atención"}')
    response = client[0].post(URL, headers=headers, json={})
    assert response.status_code == 200
    assert stored(client) == before | {"tema": "Atención"}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid"}])
def test_missing_auth_never_calls_ai(client, reviews, provider, headers):
    before = stored(client)
    assert client[0].post(URL, headers=headers).status_code == 401
    provider[0].assert_not_called()
    assert stored(client) == before


def test_general_admin_cannot_select_tenant(client, reviews, provider):
    assert client[0].post(URL + "?tenant_id=10", headers=login(client, "general@example.com")).status_code == 403
    provider[0].assert_not_called()


@pytest.mark.parametrize("review_id", [201, 999])
def test_foreign_and_missing_review_rejected_before_ai(client, reviews, provider, review_id):
    response = client[0].post(f"/api/v1/reviews/{review_id}/tema", headers=login(client))
    assert response.status_code == 404
    provider[0].assert_not_called()
    assert stored(client, 201)["tema"] == "Producto"


@pytest.mark.parametrize("payload", [{"tenant_id": 20}, {"contenido": "Otro texto"}, {"tema": "Precio"}])
def test_client_cannot_supply_topic_input(client, reviews, provider, payload):
    before = stored(client)
    assert client[0].post(URL, headers=login(client), json=payload).status_code == 422
    provider[0].assert_not_called()
    assert stored(client) == before


@pytest.mark.parametrize("error,status", [
    (TopicContentError, 422), (AIInputError, 422), (AIBlockedResponseError, 422),
    (TopicConflictError, 409), (TopicPersistenceError, 500),
    (AIInvalidResponseError, 502), (AIRequestError, 502), (AIConfigurationError, 503),
    (AICredentialsError, 503), (AIQuotaError, 503), (AIUnavailableError, 503), (AITimeoutError, 504),
])
def test_errors_have_controlled_status_without_writes(client, reviews, error, status):
    service = Mock()
    service.detect.side_effect = error()
    app.dependency_overrides[get_topic_service] = lambda: service
    before = stored(client)
    response = client[0].post(URL, headers=login(client))
    assert response.status_code == status
    assert response.json() == {"detail": error.message}
    assert stored(client) == before


def test_unknown_error_is_sanitized(client, reviews):
    class UnexpectedError(AIError):
        message = "private-internal-detail"

    service = Mock()
    service.detect.side_effect = UnexpectedError()
    app.dependency_overrides[get_topic_service] = lambda: service
    response = client[0].post(URL, headers=login(client))
    assert response.status_code == 502
    assert response.json() == {"detail": AIError.message}


def test_concurrent_content_change_does_not_store_stale_topic(client, reviews, provider):
    def handler(_):
        with client[1]() as db:
            db.execute(update(Review).where(Review.id == 101).values(contenido="Texto corregido"))
            db.commit()
        return completion('{"tema":"Servicio"}')

    provider[2]["handler"] = handler
    response = client[0].post(URL, headers=login(client))
    assert response.status_code == 409
    assert stored(client)["tema"] == "Producto"
    assert stored(client)["contenido"] == "Texto corregido"


def test_manual_edit_rejects_topic_without_partial_changes(client, reviews):
    before = stored(client)
    response = client[0].patch("/api/v1/reviews/101", headers=login(client), json={
        "tema": "Precio", "contenido": "Contenido que no debe guardarse",
    })
    assert response.status_code == 422
    assert stored(client) == before


@pytest.mark.parametrize("output,expected_status", [
    ('{"tema":null}', 422), ('{"tema":"Calidad"}', 502), ('no JSON', 502),
])
def test_invalid_or_ambiguous_result_preserves_previous_topic(client, reviews, provider, output, expected_status):
    before = stored(client)
    provider[2]["handler"] = lambda _: completion(output)
    assert client[0].post(URL, headers=login(client)).status_code == expected_status
    assert stored(client) == before


def test_openapi_uses_server_owned_request_and_review_response(client):
    schema = client[0].get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/reviews/{review_id}/tema"]["post"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert [(item["name"], item["in"]) for item in operation["parameters"]] == [("review_id", "path")]
    assert schema["components"]["schemas"]["TopicRequest"]["properties"] == {}
    assert schema["components"]["schemas"]["TopicRequest"]["additionalProperties"] is False
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/ReviewRead"}
