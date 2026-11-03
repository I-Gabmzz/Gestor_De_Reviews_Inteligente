"""HU-18/T3: API protegida con generación simulada y SQLite temporal."""

from datetime import datetime
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import delete, event, select, update
from sqlalchemy.exc import SQLAlchemyError

from app.api.routers.suggested_responses import get_suggested_response_service
from app.core.ai_config import AISettings
from app.core.security import create_access_token
from app.main import app
from app.models.review import Review
from app.models.external_review_connection import ExternalReviewConnection
from app.models.external_review_identity import ExternalReviewIdentity
from app.models.notification import ReviewNotification
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.review_repository import ReviewRepository
from app.schemas.review import ReviewRead
from app.schemas.ai import PriorityResult
from app.schemas.auth import AuthenticatedUser
from app.schemas.serpapi import SerpApiPage, SerpApiResult, SerpApiReview
from app.services.external_review_persistence_service import ExternalReviewPersistenceService
from app.services.serpapi_normalizer import normalize_serpapi_result
from app.services.ai_provider import (
    AIError, AIBlockedResponseError, AIConfigurationError, AICredentialsError,
    AIInputError, AIInvalidResponseError, AIQuotaError, AIRequestError,
    AITimeoutError, AIUnavailableError, create_ai_provider,
)
from app.services.suggested_response_analysis_service import (
    SuggestedResponseConflictError, SuggestedResponsePersistenceError,
)
from app.services.suggested_response_service import (
    SuggestedResponseContentError, SuggestedResponsePrivacyError,
)


URL = "/api/v1/reviews/101/respuesta-sugerida"
SUGGESTION = "Lamentamos la demora que describes. Gracias por compartir tu experiencia."


def completion(text=SUGGESTION):
    import json
    return httpx.Response(200, json={"candidates": [{
        "finishReason": "STOP",
        "content": {"parts": [{"text": json.dumps({"respuesta_sugerida": text})}]},
    }]})


@pytest.fixture()
def reviews(client, seed_users):
    with client[1]() as db:
        db.add(Tenant(id=20, nombre="Otro negocio ficticio", estado="activo"))
        db.flush()
        db.add(User(
            id=20, tenant_id=20, nombre="Usuario B", correo="b@example.com",
            password_hash="hash-sintetico-no-usado-para-login", rol="usuario_negocio", estado="activo",
        ))
        for review_id, tenant_id in ((101, 10), (201, 20)):
            db.add(Review(
                id=review_id, tenant_id=tenant_id, autor="Cliente ficticio",
                contenido="Mi pedido llegó tarde.", fecha=datetime(2026, 10, 19),
                fuente="manual", puntuacion=2, estado="en_revision", categoria="Queja",
                resumen="Resumen previo", tema="Servicio", prioridad="Alta",
                respuesta_sugerida="Sugerencia anterior vigente.",
            ))
        db.commit()


@pytest.fixture()
def provider(monkeypatch):
    requests = []
    behavior = {"handler": lambda _: completion()}

    def handler(request):
        requests.append(request)
        return behavior["handler"](request)

    config = AISettings(_env_file=None, gemini_api_key="synthetic-test-key")
    factory = Mock(side_effect=lambda: create_ai_provider(config, transport=httpx.MockTransport(handler)))
    monkeypatch.setattr("app.services.suggested_response_service.create_ai_provider", factory)
    return factory, requests, behavior


def headers(subject="1", tenant_id=10):
    return {"Authorization": "Bearer " + create_access_token(
        subject=subject, rol="usuario_negocio", tenant_id=tenant_id,
    )}


def stored(client, review_id=101):
    with client[1]() as db:
        return ReviewRead.model_validate(db.get(Review, review_id)).model_dump(mode="json")


@pytest.mark.parametrize("subject", ["1", "2"])
def test_allowed_roles_persist_only_suggestion_and_get_reads_it(client, reviews, provider, subject):
    before = stored(client)
    other = stored(client, 201)
    response = client[0].post(URL, headers=headers(subject))
    assert response.status_code == 200
    assert response.json() == before | {"respuesta_sugerida": SUGGESTION}
    assert stored(client) == response.json()
    assert stored(client, 201) == other
    assert client[0].get("/api/v1/reviews/101", headers=headers(subject)).json() == response.json()
    assert client[0].get("/api/v1/reviews", headers=headers(subject)).json()["items"] == [response.json()]
    assert "respuesta_sugerida_version" not in response.json()
    assert len(provider[1]) == 1


def test_manual_regeneration_replaces_previous_value_only_after_success(client, reviews, provider):
    before = stored(client)

    def handler(_):
        assert stored(client) == before
        return completion()

    provider[2]["handler"] = handler
    assert client[0].post(URL, headers=headers()).status_code == 200
    provider[2]["handler"] = lambda _: completion("Gracias por compartir la experiencia que describes.")
    response = client[0].post(URL, headers=headers(), json={})
    assert response.status_code == 200
    assert response.json() == before | {"respuesta_sugerida": "Gracias por compartir la experiencia que describes."}
    with client[1]() as db:
        assert db.get(Review, 101).respuesta_sugerida_version == 2


@pytest.mark.parametrize("credentials", [{}, {"Authorization": "Bearer invalid"}])
def test_authentication_required_before_ai(client, reviews, provider, credentials):
    assert client[0].post(URL, headers=credentials).status_code == 401
    provider[0].assert_not_called()


@pytest.mark.parametrize("subject", ["3", "4"])
def test_wrong_role_or_inactive_user_denied_before_ai(client, reviews, provider, subject):
    assert client[0].post(URL + "?tenant_id=10", headers=headers(subject)).status_code == 403
    provider[0].assert_not_called()


@pytest.mark.parametrize("target", ["tenant", "role"])
def test_authorization_uses_current_database_state(client, reviews, provider, target):
    token = headers()
    with client[1]() as db:
        if target == "tenant":
            db.get(Tenant, 10).estado = "inactivo"
        else:
            actor = db.get(User, 1)
            actor.rol = "admin_general"
            actor.tenant_id = None
        db.commit()
    assert client[0].post(URL, headers=token).status_code == 403
    provider[0].assert_not_called()


@pytest.mark.parametrize("review_id", [201, 999])
def test_foreign_or_missing_review_is_404_without_ai(client, reviews, provider, review_id):
    before = stored(client, 201)
    response = client[0].post(f"/api/v1/reviews/{review_id}/respuesta-sugerida", headers=headers())
    assert response.status_code == 404
    provider[0].assert_not_called()
    assert stored(client, 201) == before


def test_bidirectional_tenant_isolation_and_manual_tenant_is_ignored(client, reviews, provider):
    a = headers()
    b = headers("20", 20)
    assert client[0].post(URL, headers=a).status_code == 200
    calls = len(provider[1])
    assert client[0].get("/api/v1/reviews/101?tenant_id=10", headers=b).status_code == 404
    assert client[0].post(URL + "?tenant_id=10", headers=b).status_code == 404
    assert client[0].post("/api/v1/reviews/201/respuesta-sugerida?tenant_id=20", headers=a).status_code == 404
    assert len(provider[1]) == calls
    assert client[0].post("/api/v1/reviews/201/respuesta-sugerida", headers=b).status_code == 200
    assert client[0].get("/api/v1/reviews/201", headers=a).status_code == 404
    assert client[0].post(URL + "?tenant_id=20", headers=a).status_code == 200


@pytest.mark.parametrize("payload", [
    {"tenant_id": 20}, {"contenido": "Texto arbitrario"}, {"respuesta_sugerida": "Falsa"},
    {"estado": "atendida"}, {"publicar": True}, {"respuesta_sugerida_version": 99},
])
def test_client_cannot_supply_content_results_or_authority(client, reviews, provider, payload):
    before = stored(client)
    assert client[0].post(URL, headers=headers(), json=payload).status_code == 422
    provider[0].assert_not_called()
    assert stored(client) == before


@pytest.mark.parametrize("review_id", ["0", "-1", "abc"])
def test_invalid_identifier_never_calls_ai(client, reviews, provider, review_id):
    assert client[0].post(f"/api/v1/reviews/{review_id}/respuesta-sugerida", headers=headers()).status_code == 422
    provider[0].assert_not_called()


@pytest.mark.parametrize("text,status", [(None, 422), ("", 502), ("   ", 502), (42, 502)])
def test_invalid_or_unanalyzable_result_preserves_previous_suggestion(client, reviews, provider, text, status):
    before = stored(client)
    provider[2]["handler"] = lambda _: completion(text)
    assert client[0].post(URL, headers=headers()).status_code == status
    assert stored(client) == before


@pytest.mark.parametrize("error,status", [
    (SuggestedResponseContentError, 422), (SuggestedResponsePrivacyError, 422),
    (AIInputError, 422), (AIBlockedResponseError, 422),
    (SuggestedResponseConflictError, 409), (SuggestedResponsePersistenceError, 500),
    (AIInvalidResponseError, 502), (AIRequestError, 502), (AIConfigurationError, 503),
    (AICredentialsError, 503), (AIQuotaError, 503), (AIUnavailableError, 503), (AITimeoutError, 504),
])
def test_error_mapping_is_controlled_without_writes(client, reviews, error, status):
    service = Mock()
    service.generate_for_review.side_effect = error()
    app.dependency_overrides[get_suggested_response_service] = lambda: service
    before = stored(client)
    response = client[0].post(URL, headers=headers())
    assert response.status_code == status
    assert response.json() == {"detail": error.message}
    assert stored(client) == before


def test_unknown_ai_error_hides_internal_message(client, reviews):
    class UnknownError(AIError):
        message = "synthetic-internal-detail"

    service = Mock()
    service.generate_for_review.side_effect = UnknownError()
    app.dependency_overrides[get_suggested_response_service] = lambda: service
    response = client[0].post(URL, headers=headers())
    assert response.status_code == 502
    assert response.json() == {"detail": AIError.message}


@pytest.mark.parametrize("http_status,expected", [(401, 503), (429, 503), (503, 503), (504, 504)])
def test_actual_adapter_failure_preserves_previous_result(client, reviews, provider, http_status, expected):
    before = stored(client)
    provider[2]["handler"] = lambda _: httpx.Response(http_status, text="synthetic-private-provider-detail")
    response = client[0].post(URL, headers=headers())
    assert response.status_code == expected
    assert "synthetic-private-provider-detail" not in response.text
    assert stored(client) == before


def test_network_timeout_preserves_previous_result(client, reviews, provider):
    def handler(request):
        raise httpx.ReadTimeout("synthetic-private-network-detail", request=request)

    provider[2]["handler"] = handler
    before = stored(client)
    response = client[0].post(URL, headers=headers())
    assert response.status_code == 504
    assert stored(client) == before


@pytest.mark.parametrize("content", ["", "   ", "Mi contraseña es secreto-ficticio."])
def test_unsafe_or_empty_stored_content_is_rejected_before_ai(client, reviews, provider, content):
    with client[1]() as db:
        db.get(Review, 101).contenido = content
        db.commit()
    before = stored(client)
    assert client[0].post(URL, headers=headers()).status_code == 422
    provider[0].assert_not_called()
    assert stored(client) == before


@pytest.mark.parametrize("change", ["content", "revert", "tenant", "delete"])
def test_changes_during_generation_reject_obsolete_result(client, reviews, provider, change):
    before = stored(client)

    def handler(_):
        with client[1]() as db:
            repository = ReviewRepository(db)
            review = db.get(Review, 101)
            if change in {"content", "revert"}:
                repository.update(review, {"contenido": "La experiencia fue distinta."})
                if change == "revert":
                    repository.update(review, {"contenido": before["contenido"]})
            elif change == "tenant":
                db.execute(update(Review).where(Review.id == 101).values(tenant_id=20))
                db.commit()
            else:
                db.execute(delete(Review).where(Review.id == 101))
                db.commit()
        return completion()

    provider[2]["handler"] = handler
    assert client[0].post(URL, headers=headers()).status_code == 409
    if change in {"content", "revert"}:
        assert stored(client)["respuesta_sugerida"] is None
    elif change == "tenant":
        assert stored(client) == before | {"tenant_id": 20}
    else:
        with client[1]() as db:
            assert db.get(Review, 101) is None


def test_other_fields_can_change_during_generation_without_being_overwritten(client, reviews, provider):
    before = stored(client)

    def handler(_):
        with client[1]() as db:
            ReviewRepository(db).update(db.get(Review, 101), {"autor": "Autor actualizado"})
            db.get(Review, 101).estado = "atendida"
            db.commit()
        return completion()

    provider[2]["handler"] = handler
    assert client[0].post(URL, headers=headers()).status_code == 200
    assert stored(client) == before | {
        "respuesta_sugerida": SUGGESTION, "autor": "Autor actualizado", "estado": "atendida",
    }


@pytest.mark.parametrize("changes,invalidated", [
    ({"contenido": "Nuevo comentario."}, True),
    ({"contenido": "  Mi pedido llegó tarde.  "}, False),
    ({"autor": "Otro autor"}, False), ({"puntuacion": 4}, False),
    ({"fuente": "Google"}, False), ({"fecha": "2026-10-20T10:00:00"}, False),
])
def test_edit_invalidates_only_when_normalized_content_really_changes(client, reviews, provider, changes, invalidated):
    before = stored(client)
    response = client[0].patch("/api/v1/reviews/101", headers=headers(), json=changes)
    assert response.status_code == 200
    assert response.json()["respuesta_sugerida"] == (None if invalidated else before["respuesta_sugerida"])
    for field in ("estado", "categoria", "resumen", "tema", "prioridad"):
        assert response.json()[field] == before[field]
    assert client[0].get("/api/v1/reviews/101", headers=headers()).json() == response.json()
    provider[0].assert_not_called()


def test_status_change_does_not_invalidate_or_generate(client, reviews, provider):
    before = stored(client)
    response = client[0].patch("/api/v1/reviews/101/status", headers=headers(), json={"estado": "atendida"})
    assert response.status_code == 200
    assert response.json() == before | {"estado": "atendida"}
    provider[0].assert_not_called()


@pytest.mark.parametrize("field", ["respuesta_sugerida", "respuesta_sugerida_version"])
def test_regular_create_and_edit_reject_suggestion_fields(client, reviews, provider, field):
    before = stored(client)
    assert client[0].patch("/api/v1/reviews/101", headers=headers(), json={
        "contenido": "No debe guardarse", field: "No permitido",
    }).status_code == 422
    assert client[0].post("/api/v1/reviews", headers=headers(), json={
        "contenido": "Comentario nuevo", "fecha": "2026-10-19T12:00:00", "puntuacion": 3, field: "No permitido",
    }).status_code == 422
    assert stored(client) == before
    provider[0].assert_not_called()


def test_commit_failure_rolls_back_and_hides_database_details(client, reviews, provider, monkeypatch):
    before = stored(client)

    def fail_commit(_):
        raise SQLAlchemyError("synthetic-private-database-detail")

    monkeypatch.setattr(client[1].class_, "commit", fail_commit)
    response = client[0].post(URL, headers=headers())
    assert response.status_code == 500
    assert response.json() == {"detail": SuggestedResponsePersistenceError.message}
    assert stored(client) == before
    with client[1]() as db:
        assert db.get(Review, 101).respuesta_sugerida_version == 0


def test_openapi_has_no_client_tenant_and_returns_review_read(client):
    schema = client[0].get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/reviews/{review_id}/respuesta-sugerida"]["post"]
    assert [(p["name"], p["in"]) for p in operation["parameters"]] == [("review_id", "path")]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/ReviewRead")
    assert schema["components"]["schemas"]["SuggestedResponseRequest"]["additionalProperties"] is False
    assert "respuesta_sugerida" in schema["components"]["schemas"]["ReviewRead"]["properties"]
    assert "respuesta_sugerida_version" not in schema["components"]["schemas"]["ReviewRead"]["properties"]


def notification_snapshot(client):
    with client[1]() as db:
        return list(db.execute(select(
            ReviewNotification.id, ReviewNotification.review_id,
            ReviewNotification.tenant_id, ReviewNotification.creada_en,
        )).all())


def test_priority_and_suggestion_keep_their_results_and_notifications_independent(client, reviews, provider):
    with client[1]() as db:
        ReviewRepository(db).save_ai_result(101, 10, PriorityResult(prioridad="Media"))
    assert notification_snapshot(client) == []
    assert client[0].post(URL, headers=headers()).status_code == 200
    first = stored(client)
    assert first["prioridad"] == "Media"
    assert notification_snapshot(client) == []
    with client[1]() as db:
        saved = ReviewRepository(db).save_ai_result(101, 10, PriorityResult(prioridad="Alta"))
        assert saved.respuesta_sugerida == SUGGESTION
    notices = notification_snapshot(client)
    assert len(notices) == 1 and notices[0].review_id == 101
    response = client[0].post(URL, headers=headers())
    assert response.status_code == 200
    assert response.json() == first | {"prioridad": "Alta"}
    assert notification_snapshot(client) == notices


@pytest.mark.parametrize("failure", ["timeout", "invalid"])
def test_failed_suggestion_preserves_priority_and_existing_notice(client, reviews, provider, failure):
    with client[1]() as db:
        ReviewRepository(db).save_ai_result(101, 10, PriorityResult(prioridad="Alta"))
    before, notices = stored(client), notification_snapshot(client)

    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic-timeout", request=request)
        return completion(42)

    provider[2]["handler"] = handler
    assert client[0].post(URL, headers=headers()).status_code == (504 if failure == "timeout" else 502)
    assert stored(client) == before
    assert notification_snapshot(client) == notices


@pytest.fixture()
def external_reviews(client, reviews):
    engine = client[1].kw["bind"]

    def foreign_keys(connection, *_):
        connection.execute("PRAGMA foreign_keys=ON")

    event.listen(engine, "checkout", foreign_keys)
    business = "0x123:0x456"
    try:
        with client[1]() as db:
            for tenant in (10, 20):
                db.add(ExternalReviewConnection(
                    tenant_id=tenant, source="Google", business_data_id=business,
                    persistence_enabled=True, approval_reference="synthetic-test-only",
                ))
            db.commit()
        native = SerpApiResult(
            pages=(SerpApiPage(1, 200, "Success", (SerpApiReview({
                "review_id": "synthetic-shared-external-id", "source": "Google",
                "user": {"name": "Cliente ficticio externo"}, "snippet": "La entrega tardó.",
                "iso_date": "2026-11-02T12:00:00Z", "rating": 2,
            }),)),),
            place_info=None, first_page_metadata=None, request_count=1, record_count=1,
            stop_reason="no_next_token", incomplete=False, limited=False,
        )
        batch = normalize_serpapi_result(native, business_data_id=business)
        identifiers = {}
        for user_id, tenant in ((1, 10), (20, 20)):
            with client[1]() as db:
                outcome = ExternalReviewPersistenceService(ReviewRepository(db)).persist(
                    batch, current_user=AuthenticatedUser(
                        id=user_id, tenant_id=tenant, rol="usuario_negocio", correo="ficticio@example.com",
                    ), business_data_id=business,
                )
                assert outcome.inserted == 1
            with client[1]() as db:
                identifiers[tenant] = db.scalar(select(ExternalReviewIdentity.review_id).where(
                    ExternalReviewIdentity.tenant_id == tenant,
                ))
        yield identifiers, batch, business
    finally:
        event.remove(engine, "checkout", foreign_keys)


def test_external_reviews_can_generate_only_within_their_tenant_without_losing_identity(
    client, external_reviews, provider,
):
    identifiers, batch, business = external_reviews
    with client[1]() as db:
        before = [(row.review_id, row.tenant_id, row.source, row.business_data_id,
                   row.external_review_id, row.import_fingerprint)
                  for row in db.scalars(select(ExternalReviewIdentity).order_by(ExternalReviewIdentity.review_id))]
    for tenant, subject in ((10, "1"), (20, "20")):
        own, foreign = identifiers[tenant], identifiers[20 if tenant == 10 else 10]
        response = client[0].post(f"/api/v1/reviews/{own}/respuesta-sugerida", headers=headers(subject, tenant))
        assert response.status_code == 200
        assert response.json() == stored(client, own)
        assert response.json()["respuesta_sugerida"] == SUGGESTION
        calls = len(provider[1])
        assert client[0].get(f"/api/v1/reviews/{foreign}", headers=headers(subject, tenant)).status_code == 404
        assert client[0].post(
            f"/api/v1/reviews/{foreign}/respuesta-sugerida?tenant_id={20 if tenant == 10 else 10}",
            headers=headers(subject, tenant),
        ).status_code == 404
        assert len(provider[1]) == calls
    assert notification_snapshot(client) == []
    with client[1]() as db:
        repeated = ExternalReviewPersistenceService(ReviewRepository(db)).persist(
            batch, current_user=AuthenticatedUser(
                id=1, tenant_id=10, rol="usuario_negocio", correo="ficticio@example.com",
            ), business_data_id=business,
        )
        assert repeated.repeated == 1 and repeated.inserted == 0
    assert stored(client, identifiers[10])["respuesta_sugerida"] == SUGGESTION
    response = client[0].patch(
        f"/api/v1/reviews/{identifiers[10]}", headers=headers(), json={"contenido": "La entrega fue distinta."},
    )
    assert response.status_code == 200 and response.json()["respuesta_sugerida"] is None
    with client[1]() as db:
        after = [(row.review_id, row.tenant_id, row.source, row.business_data_id,
                  row.external_review_id, row.import_fingerprint)
                 for row in db.scalars(select(ExternalReviewIdentity).order_by(ExternalReviewIdentity.review_id))]
    assert after == before
