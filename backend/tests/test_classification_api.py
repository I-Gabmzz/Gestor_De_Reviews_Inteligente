from datetime import datetime
import json
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import update

from app.api.routers.reviews import get_classification_service
from app.core.ai_config import AISettings
from app.core.security import create_access_token
from app.main import app
from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.review import ReviewRead
from app.services.ai_provider import (
    AIError, AIBlockedResponseError, AIConfigurationError, AICredentialsError,
    AIInputError, AIInvalidResponseError, AIQuotaError, AIRequestError,
    AITimeoutError, AIUnavailableError, create_ai_provider,
)
from app.services.classification_service import (
    ClassificationContentError, ClassificationConflictError, ClassificationPersistenceError,
)


URL = "/api/v1/reviews/101/clasificacion"


def completion(text):
    return httpx.Response(200, json={"candidates": [{
        "finishReason": "STOP", "content": {"parts": [{"text": text}]}
    }]})


@pytest.fixture()
def reviews(client, seed_users):
    with client[1]() as db:
        db.add(Tenant(id=20, nombre="Otro negocio", estado="activo"))
        db.flush()
        for review_id, tenant_id in ((101, 10), (201, 20)):
            db.add(Review(
                id=review_id, tenant_id=tenant_id, autor="Ana", contenido="Mi pedido llegó tarde.",
                fecha=datetime(2026, 10, 17), fuente="manual", puntuacion=2,
                estado="en_revision", categoria="Consulta", prioridad="Alta",
                resumen="Resumen previo", tema="Entrega",
            ))
        db.commit()


@pytest.fixture()
def provider(monkeypatch):
    requests = []
    behavior = {"handler": lambda _: completion('{"categoria":"Queja"}')}
    def handler(request):
        requests.append(request)
        return behavior["handler"](request)
    config = AISettings(_env_file=None, gemini_api_key="private-test-key")
    factory = Mock(side_effect=lambda: create_ai_provider(config, transport=httpx.MockTransport(handler)))
    monkeypatch.setattr("app.services.classification_service.create_ai_provider", factory)
    return factory, requests, behavior


def login(client, correo="usuario@example.com"):
    response = client[0].post("/api/v1/auth/login", json={"correo": correo, "password": "secret123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def stored(client, review_id=101):
    with client[1]() as db:
        return ReviewRead.model_validate(db.get(Review, review_id)).model_dump(mode="json")


@pytest.mark.parametrize("correo", ["usuario@example.com", "tenant@example.com"])
def test_allowed_roles_classify_and_read_persisted_result(client, reviews, provider, correo):
    headers = login(client, correo)
    before = stored(client)
    response = client[0].post(URL, headers=headers)
    assert response.status_code == 200
    assert response.json() == before | {"categoria": "Queja"}
    assert stored(client) == response.json()
    assert client[0].get("/api/v1/reviews/101", headers=headers).json() == response.json()
    assert stored(client, 201)["categoria"] == "Consulta"
    provider[0].assert_called_once()
    body = json.loads(provider[1][0].content)
    assert body["contents"] == [{"role": "user", "parts": [{"text": before["contenido"]}]}]


def test_regeneration_changes_only_category(client, reviews, provider):
    headers = login(client)
    before = stored(client)
    assert client[0].post(URL, headers=headers).json()["categoria"] == "Queja"
    provider[2]["handler"] = lambda _: completion('{"categoria":"Sugerencia"}')
    response = client[0].post(URL, headers=headers, json={})
    assert response.status_code == 200
    assert stored(client) == before | {"categoria": "Sugerencia"}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid"}, {"Authorization": "Basic invalid"}])
def test_missing_or_invalid_auth_never_creates_provider(client, reviews, provider, headers):
    before = stored(client)
    response = client[0].post(URL, headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    provider[0].assert_not_called()
    assert stored(client) == before


def test_admin_general_cannot_classify_even_with_supplied_tenant(client, reviews, provider):
    before = stored(client)
    response = client[0].post(URL + "?tenant_id=10", headers=login(client, "general@example.com"))
    assert response.status_code == 403
    provider[0].assert_not_called()
    assert stored(client) == before


@pytest.mark.parametrize("resource_id", [201, 999])
def test_foreign_and_missing_reviews_return_same_not_found_before_ai(client, reviews, provider, resource_id):
    response = client[0].post(f"/api/v1/reviews/{resource_id}/clasificacion", headers=login(client))
    assert response.status_code == 404
    assert response.json() == {"detail": f"Review con id {resource_id} no encontrada"}
    provider[0].assert_not_called()
    assert stored(client, 201)["categoria"] == "Consulta"


@pytest.mark.parametrize("target", ["user", "tenant"])
def test_current_inactive_user_or_tenant_blocks_previous_token(client, reviews, provider, target):
    headers = login(client)
    with client[1]() as db:
        (db.get(User, 1) if target == "user" else db.get(Tenant, 10)).estado = "inactivo"
        db.commit()
    response = client[0].post(URL, headers=headers)
    assert response.status_code == 403
    provider[0].assert_not_called()
    assert stored(client)["categoria"] == "Consulta"


def test_signed_token_claims_cannot_override_current_tenant(client, reviews, provider):
    token = create_access_token(subject="1", rol="admin_tenant", tenant_id=20)
    response = client[0].post("/api/v1/reviews/201/clasificacion", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404
    provider[0].assert_not_called()


def test_query_tenant_does_not_override_authenticated_scope(client, reviews, provider):
    response = client[0].post(URL + "?tenant_id=20", headers=login(client))
    assert response.status_code == 200
    assert response.json()["tenant_id"] == 10
    assert stored(client, 201)["categoria"] == "Consulta"


@pytest.mark.parametrize("payload", [
    {"tenant_id": 20}, {"contenido": "Texto sustituido"}, {"categoria": "Felicitación"},
    {"review_id": 201}, {"resumen": "Resumen sustituido"}, {"tema": "Tema sustituido"},
])
def test_body_rejects_fields_instead_of_overriding_server_data(client, reviews, provider, payload):
    before = stored(client)
    response = client[0].post(URL, headers=login(client), json=payload)
    assert response.status_code == 422
    provider[0].assert_not_called()
    assert stored(client) == before


@pytest.mark.parametrize("review_id", ["0", "-1", "no-es-id"])
def test_invalid_path_rejected_before_ai(client, reviews, provider, review_id):
    response = client[0].post(f"/api/v1/reviews/{review_id}/clasificacion", headers=login(client))
    assert response.status_code == 422
    provider[0].assert_not_called()


@pytest.mark.parametrize("error,status", [
    (ClassificationContentError, 422), (AIInputError, 422), (AIBlockedResponseError, 422),
    (ClassificationConflictError, 409), (ClassificationPersistenceError, 500),
    (AIInvalidResponseError, 502), (AIRequestError, 502), (AIConfigurationError, 503),
    (AICredentialsError, 503), (AIQuotaError, 503), (AIUnavailableError, 503), (AITimeoutError, 504),
])
def test_domain_errors_have_controlled_http_status_and_detail(client, reviews, error, status):
    service = Mock()
    service.classify.side_effect = error()
    app.dependency_overrides[get_classification_service] = lambda: service
    before = stored(client)
    response = client[0].post(URL, headers=login(client))
    assert response.status_code == status
    assert response.json() == {"detail": error.message}
    assert stored(client) == before


def test_unknown_ai_error_does_not_expose_its_message(client, reviews):
    class UnexpectedAIError(AIError):
        message = "private-internal-message"
    service = Mock()
    service.classify.side_effect = UnexpectedAIError()
    app.dependency_overrides[get_classification_service] = lambda: service
    response = client[0].post(URL, headers=login(client))
    assert response.status_code == 502
    assert response.json() == {"detail": AIError.message}


@pytest.mark.parametrize("body", ['{"categoria":"Positiva"}', 'no JSON', '{"categoria":null}'])
def test_invalid_or_unanalyzable_real_adapter_response_keeps_data(client, reviews, provider, body):
    before = stored(client)
    provider[2]["handler"] = lambda _: completion(body)
    response = client[0].post(URL, headers=login(client))
    assert response.status_code == (422 if body == '{"categoria":null}' else 502)
    assert stored(client) == before


def test_real_adapter_quota_error_is_503_without_provider_details(client, reviews, provider):
    before = stored(client)
    provider[2]["handler"] = lambda _: httpx.Response(429, text="private-provider-detail")
    response = client[0].post(URL, headers=login(client))
    assert response.status_code == 503
    assert response.json() == {"detail": AIQuotaError.message}
    assert stored(client) == before


def test_missing_configuration_returns_503_and_keeps_non_ai_routes_usable(client, reviews, monkeypatch, tmp_path):
    headers = login(client)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    before = stored(client)
    response = client[0].post(URL, headers=headers)
    assert response.status_code == 503
    assert response.json() == {"detail": AIConfigurationError.message}
    assert stored(client) == before
    assert client[0].get("/api/v1/health").status_code == 200
    assert client[0].get("/api/v1/reviews/101", headers=headers).status_code == 200


def test_content_changed_during_ai_returns_conflict_and_keeps_category(client, reviews, provider):
    def handler(_):
        with client[1]() as db:
            db.execute(update(Review).where(Review.id == 101).values(contenido="Texto corregido"))
            db.commit()
        return completion('{"categoria":"Queja"}')
    provider[2]["handler"] = handler
    response = client[0].post(URL, headers=login(client))
    assert response.status_code == 409
    assert stored(client)["categoria"] == "Consulta"
    assert stored(client)["contenido"] == "Texto corregido"


def test_openapi_documents_auth_server_owned_input_and_persisted_response(client):
    schema = client[0].get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/reviews/{review_id}/clasificacion"]["post"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert [(item["name"], item["in"]) for item in operation["parameters"]] == [("review_id", "path")]
    assert operation["requestBody"].get("required", False) is False
    assert schema["components"]["schemas"]["ClassificationRequest"]["additionalProperties"] is False
    assert schema["components"]["schemas"]["ClassificationRequest"]["properties"] == {}
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/ReviewRead"}
    assert set(operation["responses"]) >= {"200", "401", "403", "404", "409", "422", "500", "502", "503", "504"}
