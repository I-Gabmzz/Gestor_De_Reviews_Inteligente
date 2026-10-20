"""Contratos deterministas y ejemplos con decisiones simuladas, no calidad de Gemini."""

from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import re

from pydantic import ValidationError
import pytest

from app.repositories.review_repository import ReviewRepository
from app.schemas.ai import TopicResult
from app.schemas.topic import TopicDecision, TopicRequest
from app.services.topic_service import TopicContentError, TopicService


DOCUMENT = Path(__file__).resolve().parents[2] / "docs/hu-15/criterios-deteccion-temas.md"
EXAMPLES = [
    tuple(part.strip() for part in row.strip().strip("|").split("|"))[:3]
    for row in DOCUMENT.read_text(encoding="utf-8").splitlines()
    if re.match(r"^\| E\d{2} \|", row)
]


def test_document_keeps_all_nineteen_examples():
    assert [row[0] for row in EXAMPLES] == [f"E{i:02}" for i in range(1, 20)]


@pytest.mark.parametrize("example_id,content,expected", EXAMPLES, ids=[row[0] for row in EXAMPLES])
def test_documented_example_with_simulated_decision(example_id, content, expected):
    """Se simula la decisión esperada; no se atribuye comprensión semántica al mock."""
    if example_id == "E16":
        content = " \n\t"
    repository = Mock(spec=ReviewRepository)
    repository.get_by_id_for_tenant.return_value = SimpleNamespace(contenido=content)
    provider = Mock()
    analyzable = expected in {"Atención", "Servicio", "Precio", "Producto", "Otro"}
    provider.generate_structured.return_value = TopicDecision(tema=expected if analyzable else None)
    factory = Mock(side_effect=lambda: nullcontext(provider))
    service = TopicService(repository, factory)
    if analyzable:
        assert service.analyze(101, 10).result == TopicResult(tema=expected)
    else:
        with pytest.raises(TopicContentError):
            service.analyze(101, 10)
    if example_id == "E16":
        factory.assert_not_called()
    else:
        provider.generate_structured.assert_called_once()
        assert provider.generate_structured.call_args.args == (content,)
    repository.save_ai_result.assert_not_called()


@pytest.mark.parametrize("topic", ["Atención", "Servicio", "Precio", "Producto", "Otro"])
def test_specific_catalog_converts_to_unchanged_shared_contract(topic):
    assert TopicResult(tema=TopicDecision(tema=topic).tema).tema == topic


@pytest.mark.parametrize("payload", [
    {}, {"tema": ""}, {"tema": " "}, {"tema": 5}, {"tema": ["Servicio", "Precio"]},
    {"tema": "Servicio y Precio"}, {"tema": "Calidad"}, {"tema": "atención"},
    {"tema": "Atención", "categoria": "Queja"}, {"tema": "Atención", "tenant_id": 20},
])
def test_specific_contract_rejects_invalid_decisions(payload):
    with pytest.raises(ValidationError):
        TopicDecision.model_validate(payload)


def test_null_is_only_internal_rejection_not_persistible():
    assert TopicDecision(tema=None).tema is None
    with pytest.raises(ValidationError):
        TopicResult(tema=None)


def test_shared_contract_remains_open_for_other_consumers():
    # HU-15 no impone su catálogo a los consumidores existentes de HU-13.
    assert TopicResult(tema="Servicio de entrega").tema == "Servicio de entrega"


@pytest.mark.parametrize("payload", [{"tenant_id": 20}, {"tema": "Otro"}, {"review_id": 201}])
def test_request_never_accepts_authority_or_generated_fields(payload):
    with pytest.raises(ValidationError):
        TopicRequest.model_validate(payload)
