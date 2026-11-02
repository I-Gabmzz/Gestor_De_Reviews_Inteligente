import json
import sys

import httpx
import pytest

from app.core.ai_config import AISettings
from app.main import app
from app.services.ai_provider import create_ai_provider
from scripts import verify_priority_t5


@pytest.mark.parametrize("actual,expected_exit", [("Alta", 0), ("Media", 1)])
def test_verification_records_mismatches_without_hiding_them_or_exposing_credentials(monkeypatch, tmp_path, actual, expected_exit):
    output = tmp_path / "results.json"
    settings = AISettings(_env_file=None, gemini_api_key="synthetic-private-key")
    monkeypatch.setattr(verify_priority_t5, "AISettings", lambda **_: settings)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"candidates": [{
            "finishReason": "STOP", "content": {"parts": [{"text": json.dumps({"prioridad": actual})}]},
        }]})

    monkeypatch.setattr(verify_priority_t5, "create_ai_provider", lambda config: create_ai_provider(config, transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(sys, "argv", ["verify_priority_t5", "--case", "cobro_pendiente", "--output", str(output)])
    before_overrides = app.dependency_overrides.copy()
    assert verify_priority_t5.main() == expected_exit
    report_text = output.read_text()
    report = json.loads(report_text)
    assert report["all_passed"] is (expected_exit == 0)
    assert report["completed_semantic_cases"] == report["planned_semantic_cases"] == 1
    assert report["semantic_cases"][0]["expected"] == "Alta"
    assert report["semantic_cases"][0]["actual"] == actual
    assert len(requests) == report["provider_calls"] == 1
    assert all(case["provider_calls"] == 0 and case["passed"] for case in report["access_cases"])
    assert report["semantic_cases"][0]["other_fields_preserved"]
    assert "synthetic-private-key" not in report_text
    assert "access_token" not in report_text
    assert "password" not in report_text
    assert app.dependency_overrides == before_overrides


def test_verification_rejects_empty_content_without_provider_and_never_overwrites_report(monkeypatch, tmp_path):
    output = tmp_path / "results.json"
    monkeypatch.setattr(verify_priority_t5, "AISettings", lambda **_: AISettings(_env_file=None, gemini_api_key="synthetic-private-key"))

    def unexpected_provider(_):
        pytest.fail("El contenido vacío no debe llegar al proveedor")

    monkeypatch.setattr(verify_priority_t5, "create_ai_provider", unexpected_provider)
    monkeypatch.setattr(sys, "argv", ["verify_priority_t5", "--case", "vacio", "--output", str(output)])
    assert verify_priority_t5.main() == 0
    original = output.read_bytes()
    report = json.loads(original)
    assert report["all_passed"] and report["provider_calls"] == 0
    assert report["semantic_cases"][0]["http_status"] == 422
    assert report["semantic_cases"][0]["previous_priority_preserved_on_error"]
    assert verify_priority_t5.main() == 2
    assert output.read_bytes() == original
