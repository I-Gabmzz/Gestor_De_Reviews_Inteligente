import importlib
from pathlib import Path
import traceback

from pydantic import SecretStr, ValidationError
import pytest

from app.core.serpapi_config import SerpApiSettings
from app.services.serpapi_client import SerpApiClient, SerpApiError


DEFAULT_ENV_FILE = SerpApiSettings.model_config["env_file"]
TEST_MARKER = "test-only-not-a-credential"


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch):
    for name in ("SERPAPI_API_KEY", "SERPAPI_PAGE_SIZE", "SERPAPI_MAX_PAGES", "SERPAPI_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setitem(SerpApiSettings.model_config, "env_file", None)


def test_defaults_and_secret_representations():
    settings = SerpApiSettings(_env_file=None, serpapi_api_key=TEST_MARKER)
    assert isinstance(settings.serpapi_api_key, SecretStr)
    assert settings.serpapi_page_size == 5
    assert settings.serpapi_max_pages == 3
    assert settings.serpapi_timeout_seconds == 30
    assert TEST_MARKER not in repr(settings)
    assert "serpapi_api_key" not in settings.model_dump()
    assert TEST_MARKER not in settings.model_dump_json()


def test_env_file_is_absolute_and_independent_of_cwd(monkeypatch, tmp_path):
    assert DEFAULT_ENV_FILE == Path(__file__).resolve().parents[2] / ".env"
    assert DEFAULT_ENV_FILE.is_absolute()
    synthetic_env = tmp_path / "synthetic.env"
    synthetic_env.write_text(f"SERPAPI_API_KEY={TEST_MARKER}\nSERPAPI_PAGE_SIZE=2\n", encoding="utf-8")
    monkeypatch.setitem(SerpApiSettings.model_config, "env_file", synthetic_env)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert SerpApiSettings().serpapi_page_size == 2
    # La desactivación explícita evita incluso el archivo sintético configurado.
    with pytest.raises(ValidationError):
        SerpApiSettings(_env_file=None)


@pytest.mark.parametrize("field,value", [
    ("serpapi_api_key", ""), ("serpapi_api_key", " \t"),
    ("serpapi_api_key", "test\nmarker"), ("serpapi_api_key", "no-ASCII-ñ"),
    ("serpapi_page_size", 0), ("serpapi_page_size", 21),
    ("serpapi_max_pages", 0), ("serpapi_max_pages", 6),
    ("serpapi_timeout_seconds", 0), ("serpapi_timeout_seconds", 121),
    ("serpapi_timeout_seconds", "nan"), ("serpapi_timeout_seconds", "inf"),
    ("serpapi_timeout_seconds", TEST_MARKER),
])
def test_invalid_configuration_hides_input(field, value):
    values = {"serpapi_api_key": TEST_MARKER, field: value}
    with pytest.raises(ValidationError) as error:
        SerpApiSettings(_env_file=None, **values)
    assert TEST_MARKER not in str(error.value)
    assert TEST_MARKER not in repr(error.value)


def test_missing_key_is_lazy_and_client_error_is_sanitized(monkeypatch):
    # Importar configuración/cliente no construye Settings ni un cliente HTTP.
    module = importlib.import_module("app.core.serpapi_config")
    assert not any(isinstance(value, SerpApiSettings) for value in vars(module).values())
    monkeypatch.setenv("SERPAPI_PAGE_SIZE", TEST_MARKER)
    with pytest.raises(SerpApiError) as error:
        SerpApiClient()
    assert error.value.code == "configuration"
    assert TEST_MARKER not in "".join(traceback.format_exception(error.value))


def test_settings_can_use_environment_without_dotenv(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", TEST_MARKER)
    monkeypatch.setenv("SERPAPI_MAX_PAGES", "5")
    assert SerpApiSettings(_env_file=None).serpapi_max_pages == 5
