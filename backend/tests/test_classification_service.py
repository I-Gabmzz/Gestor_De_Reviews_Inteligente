from contextlib import nullcontext
from datetime import datetime
import json
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import create_engine, delete, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.ai_config import AISettings
from app.db.init_db import init_db
from app.models.review import Review
from app.models.tenant import Tenant
from app.repositories.review_repository import ReviewRepository
from app.schemas.ai import ClassificationResult
from app.schemas.classification import ClassificationDecision
from app.schemas.review import ReviewRead
from app.services.ai_provider import (
    AIBlockedResponseError, AIConfigurationError, AICredentialsError,
    AIInvalidResponseError, AIQuotaError, AITimeoutError, AIUnavailableError,
    create_ai_provider,
)
from app.services.classification_service import (
    ClassificationService, ClassificationContentError, ClassificationConflictError,
    ClassificationPersistenceError,
)
from app.services.review_service import ReviewNotFoundError


@pytest.fixture()
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'classification.db'}")
    init_db(engine)
    with Session(engine) as db:
        db.add_all([Tenant(id=10, nombre="Principal", estado="activo"),
                    Tenant(id=20, nombre="Ajeno", estado="activo")])
        db.flush()
        for review_id, tenant_id in ((101, 10), (102, 10), (201, 20)):
            db.add(Review(
                id=review_id, tenant_id=tenant_id, autor="Nombre privado de prueba",
                contenido="Excelente comida, pero tardaron una hora.",
                fecha=datetime(2026, 10, 17), fuente="manual", puntuacion=5,
                estado="en_revision", categoria="Consulta", prioridad="Alta",
                resumen="Resumen previo", tema="Tema previo",
            ))
        db.commit()
    yield engine
    engine.dispose()


def snapshot(engine, review_id=101):
    with Session(engine) as db:
        return ReviewRead.model_validate(db.get(Review, review_id)).model_dump()


def completion(text):
    return httpx.Response(200, json={"candidates": [{
        "finishReason": "STOP", "content": {"parts": [{"text": text}]}
    }]})


def factory(handler):
    config = AISettings(_env_file=None, gemini_api_key="private-test-key")
    return lambda: create_ai_provider(config, transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("category", ["Queja", "Sugerencia", "Felicitación", "Consulta"])
def test_service_validates_and_persists_only_category(database, category):
    before = snapshot(database)
    requests = []
    def handler(request):
        requests.append(json.loads(request.content))
        return completion(json.dumps({"categoria": category}))
    with Session(database) as db:
        saved = ClassificationService(ReviewRepository(db), factory(handler)).classify(101, 10)
        assert ReviewRead.model_validate(saved).model_dump() == before | {"categoria": category}
    assert snapshot(database) == before | {"categoria": category}
    assert snapshot(database, 102)["categoria"] == "Consulta"
    assert snapshot(database, 201)["categoria"] == "Consulta"
    assert len(requests) == 1
    body = requests[0]
    assert body["contents"] == [{"role": "user", "parts": [{"text": before["contenido"]}]}]
    assert before["autor"] not in json.dumps(body, ensure_ascii=False)
    assert body["generationConfig"]["responseJsonSchema"] == ClassificationDecision.model_json_schema()
    instructions = body["systemInstruction"]["parts"][0]["text"]
    assert "intención principal" in instructions and "Queja > Sugerencia > Consulta > Felicitación" in instructions


@pytest.mark.parametrize("review_id", [201, 999])
def test_foreign_or_missing_review_never_creates_provider(database, review_id):
    forbidden_factory = Mock(side_effect=AssertionError("No debe llamar a IA"))
    with Session(database) as db:
        with pytest.raises(ReviewNotFoundError):
            ClassificationService(ReviewRepository(db), forbidden_factory).classify(review_id, 10)
    forbidden_factory.assert_not_called()


@pytest.mark.parametrize("content", ["", " \n\t", "\u2003"])
def test_empty_content_never_creates_provider_or_replaces_category(database, content):
    with Session(database) as db:
        db.get(Review, 101).contenido = content
        db.commit()
        forbidden_factory = Mock(side_effect=AssertionError("No debe llamar a IA"))
        with pytest.raises(ClassificationContentError):
            ClassificationService(ReviewRepository(db), forbidden_factory).classify(101, 10)
        forbidden_factory.assert_not_called()
    assert snapshot(database)["categoria"] == "Consulta"


def test_non_analyzable_content_keeps_every_previous_result(database):
    before = snapshot(database)
    with Session(database) as db:
        service = ClassificationService(ReviewRepository(db), factory(lambda _: completion('{"categoria":null}')))
        with pytest.raises(ClassificationContentError):
            service.classify(101, 10)
    assert snapshot(database) == before


@pytest.mark.parametrize("output", [
    "no es JSON", '{}', '{"categoria":"Positiva"}', '{"categoria":"Felicitacion"}',
    '{"categoria":123}', '{"categoria":"Queja","tema":"Otro"}', '[]',
])
def test_invalid_provider_output_does_not_write(database, output):
    before = snapshot(database)
    with Session(database) as db:
        with pytest.raises(AIInvalidResponseError):
            ClassificationService(ReviewRepository(db), factory(lambda _: completion(output))).classify(101, 10)
    assert snapshot(database) == before


@pytest.mark.parametrize("status,error", [
    (401, AICredentialsError), (403, AICredentialsError), (404, AIConfigurationError),
    (429, AIQuotaError), (503, AIUnavailableError), (504, AITimeoutError),
])
def test_provider_failure_preserves_results_and_hides_provider_body(database, status, error):
    before = snapshot(database)
    with Session(database) as db:
        with pytest.raises(error) as caught:
            ClassificationService(ReviewRepository(db), factory(
                lambda _: httpx.Response(status, text="private-provider-body")
            )).classify(101, 10)
        assert "private-provider-body" not in str(caught.value)
    assert snapshot(database) == before


@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectError])
def test_network_failure_preserves_results(database, error):
    before = snapshot(database)
    def handler(request):
        raise error("private-network-detail", request=request)
    with Session(database) as db:
        with pytest.raises((AITimeoutError, AIUnavailableError)) as caught:
            ClassificationService(ReviewRepository(db), factory(handler)).classify(101, 10)
        assert "private-network-detail" not in str(caught.value)
    assert snapshot(database) == before


def test_blocked_response_does_not_replace_category(database):
    before = snapshot(database)
    with Session(database) as db:
        with pytest.raises(AIBlockedResponseError):
            ClassificationService(ReviewRepository(db), factory(lambda _: httpx.Response(
                200, json={"promptFeedback": {"blockReason": "SAFETY"}}
            ))).classify(101, 10)
    assert snapshot(database) == before


def test_missing_configuration_is_lazy_and_preserves_results(database, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    before = snapshot(database)
    with Session(database) as db:
        service = ClassificationService(ReviewRepository(db))
        with pytest.raises(AIConfigurationError):
            service.classify(101, 10)
    assert snapshot(database) == before


@pytest.mark.parametrize("decision", [
    {"categoria": "Queja"}, ClassificationResult(categoria="Queja"),
    ClassificationDecision.model_construct(categoria="Inventada"),
])
def test_service_revalidates_provider_contract(database, decision):
    provider = Mock()
    provider.generate_structured.return_value = decision
    before = snapshot(database)
    with Session(database) as db:
        with pytest.raises(AIInvalidResponseError):
            ClassificationService(ReviewRepository(db), lambda: nullcontext(provider)).classify(101, 10)
    assert snapshot(database) == before


@pytest.mark.parametrize("change", ["contenido", "tenant", "delete"])
def test_changed_or_removed_review_during_generation_rejects_stale_result(database, change):
    def handler(_):
        with Session(database) as other:
            if change == "delete":
                other.execute(delete(Review).where(Review.id == 101))
            else:
                values = {"contenido": "Contenido corregido"} if change == "contenido" else {"tenant_id": 20}
                other.execute(update(Review).where(Review.id == 101).values(**values))
            other.commit()
        return completion('{"categoria":"Queja"}')
    with Session(database) as db:
        with pytest.raises(ClassificationConflictError):
            ClassificationService(ReviewRepository(db), factory(handler)).classify(101, 10)
    if change != "delete":
        assert snapshot(database)["categoria"] == "Consulta"
        assert snapshot(database)["resumen"] == "Resumen previo"


def test_other_analysis_saved_during_generation_is_preserved(database):
    def handler(_):
        with Session(database) as other:
            other.execute(update(Review).where(Review.id == 101).values(resumen="Resumen nuevo"))
            other.commit()
        return completion('{"categoria":"Queja"}')
    with Session(database) as db:
        saved = ClassificationService(ReviewRepository(db), factory(handler)).classify(101, 10)
        assert saved.resumen == "Resumen nuevo"
        assert saved.categoria == "Queja"


def test_database_commit_failure_is_controlled_and_rolls_back(database, monkeypatch):
    before = snapshot(database)
    with Session(database) as db:
        def fail_commit():
            raise SQLAlchemyError("private-database-detail")
        monkeypatch.setattr(db, "commit", fail_commit)
        with pytest.raises(ClassificationPersistenceError) as caught:
            ClassificationService(ReviewRepository(db), factory(lambda _: completion('{"categoria":"Queja"}'))).classify(101, 10)
        assert "private-database-detail" not in str(caught.value)
        assert db.get(Review, 101).categoria == "Consulta"
    assert snapshot(database) == before


def test_database_read_failure_never_calls_provider():
    repository = Mock(spec=ReviewRepository)
    repository.get_by_id_for_tenant.side_effect = SQLAlchemyError("private-query-detail")
    provider_factory = Mock()
    with pytest.raises(ClassificationPersistenceError) as caught:
        ClassificationService(repository, provider_factory).classify(101, 10)
    assert "private-query-detail" not in str(caught.value)
    provider_factory.assert_not_called()
