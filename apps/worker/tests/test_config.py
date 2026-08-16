import pytest
from pydantic import ValidationError

from jobmatch_worker.config import Settings


def _set_base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")


def test_default_ai_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-key")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
    settings = Settings(_env_file=None)
    assert settings.ai_provider_order == "nvidia,ollama,openrouter"
    assert settings.ai_timeout_seconds == 30.0
    assert settings.nvidia_base_url == "https://integrate.api.nvidia.com/v1"
    assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert settings.ollama_base_url == "https://ollama.com/api"
    assert settings.ollama_model == "llama3.2"


def test_ollama_in_provider_order_requires_api_key_and_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER_ORDER", "nvidia,ollama")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_ollama_in_provider_order_passes_with_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER_ORDER", "nvidia,ollama")
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-key")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
    settings = Settings(_env_file=None)
    assert settings.ollama_api_key == "ollama-key"
    assert settings.ollama_model == "llama3.2"


def test_ollama_not_required_when_out_of_provider_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER_ORDER", "nvidia")
    settings = Settings(_env_file=None)
    assert settings.ai_provider_order == "nvidia"


def test_default_connector_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-key")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
    settings = Settings(_env_file=None)
    assert settings.brave_search_api_key == ""
    assert settings.greenhouse_board_token == ""
    assert settings.lever_site_name == ""
    assert settings.requirement_extraction_enabled is False
