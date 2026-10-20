from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock
import json

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.ai_config import AISettings
from app.repositories.review_repository import ReviewRepository
from app.schemas.ai import TopicResult
from app.schemas.topic import TopicDecision
from app.services.ai_provider import (
    AIInvalidResponseError, AIQuotaError, AITimeoutError, create_ai_provider,
)
from app.services.review_service import ReviewNotFoundError
from app.services.topic_service import (
    TOPIC_INSTRUCTIONS, TopicContentError, TopicPersistenceError, TopicService,
)


@pytest.fixture()
def repository():
    repo = Mock(spec=ReviewRepository)
    repo.get_by_id_for_tenant.return_value = SimpleNamespace(
        contenido="El personal fue amable.", tema=None,
    )
    return repo


def provider_factory(handler):
    config = AISettings(_env_file=None, gemini_api_key="synthetic-test-key")
    return lambda: create_ai_provider(config, transport=httpx.MockTransport(handler))


def completion(output):
    return httpx.Response(200, json={"candidates": [{
        "finishReason": "STOP", "content": {"parts": [{"text": output}]},
    }]})


@pytest.mark.parametrize("topic", ["Atención", "Servicio", "Precio", "Producto", "Otro"])
def test_analyze_returns_validated_result_without_writing(repository, topic):
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return completion(json.dumps({"tema": topic}))

    result = TopicService(repository, provider_factory(handler)).analyze(101, 10)
    assert type(result.result) is TopicResult
    assert result.result.tema == topic
    assert result.content == "El personal fue amable."
    repository.get_by_id_for_tenant.assert_called_once_with(101, 10)
    repository.save_ai_result.assert_not_called()
    assert len(requests) == 1
    assert requests[0]["contents"] == [{"role": "user", "parts": [{"text": result.content}]}]
    assert requests[0]["generationConfig"]["responseJsonSchema"] == TopicDecision.model_json_schema()
    assert TOPIC_INSTRUCTIONS in requests[0]["systemInstruction"]["parts"][0]["text"]


@pytest.mark.parametrize("review_id", [201, 999])
def test_unavailable_review_never_calls_provider(repository, review_id):
    repository.get_by_id_for_tenant.return_value = None
    factory = Mock(side_effect=AssertionError("No debe llamar IA"))
    with pytest.raises(ReviewNotFoundError):
        TopicService(repository, factory).analyze(review_id, 10)
    factory.assert_not_called()
    repository.save_ai_result.assert_not_called()


@pytest.mark.parametrize("content", ["", " \n\t", "\u2003", None])
def test_empty_content_never_calls_provider(repository, content):
    repository.get_by_id_for_tenant.return_value.contenido = content
    factory = Mock()
    with pytest.raises(TopicContentError):
        TopicService(repository, factory).analyze(101, 10)
    factory.assert_not_called()


def test_ambiguous_decision_is_not_persistible(repository):
    with pytest.raises(TopicContentError):
        TopicService(repository, provider_factory(lambda _: completion('{"tema":null}'))).analyze(101, 10)
    repository.save_ai_result.assert_not_called()


@pytest.mark.parametrize("output", [
    "no es JSON", '{}', '[]', '{"tema":"Calidad"}', '{"tema":"Atención y Precio"}',
    '{"tema":["Atención","Servicio"]}', '{"tema":123}', '{"tema":""}',
    '{"tema":"   "}', '{"tema":" atención "}', '{"tema":"Otro","tenant_id":20}',
])
def test_invalid_provider_output_is_rejected(repository, output):
    with pytest.raises(AIInvalidResponseError):
        TopicService(repository, provider_factory(lambda _: completion(output))).analyze(101, 10)
    repository.save_ai_result.assert_not_called()


@pytest.mark.parametrize("decision", [
    {"tema": "Atención"}, TopicResult(tema="Atención"),
    TopicDecision.model_construct(tema="Inventado"),
])
def test_service_revalidates_even_when_provider_is_substituted(repository, decision):
    provider = Mock()
    provider.generate_structured.return_value = decision
    with pytest.raises(AIInvalidResponseError):
        TopicService(repository, lambda: nullcontext(provider)).analyze(101, 10)


@pytest.mark.parametrize("status,error", [(429, AIQuotaError), (504, AITimeoutError)])
def test_provider_errors_propagate_without_writing(repository, status, error):
    with pytest.raises(error) as caught:
        TopicService(repository, provider_factory(
            lambda _: httpx.Response(status, text="private-provider-detail")
        )).analyze(101, 10)
    assert "private-provider-detail" not in str(caught.value)
    repository.save_ai_result.assert_not_called()


def test_database_read_error_is_controlled_before_provider(repository):
    repository.get_by_id_for_tenant.side_effect = SQLAlchemyError("private-db-detail")
    factory = Mock()
    with pytest.raises(TopicPersistenceError) as caught:
        TopicService(repository, factory).analyze(101, 10)
    assert "private-db-detail" not in str(caught.value)
    factory.assert_not_called()
