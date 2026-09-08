import pytest
from pydantic import ValidationError

from jobmatch_worker.config import Settings


def _set_base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)


def test_default_ai_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("NINEROUTER_MODEL", "gpt-4o-mini")
    settings = Settings(_env_file=None)
    assert settings.ai_provider_order == "9router"
    assert settings.ai_timeout_seconds == 30.0
    assert settings.ninerouter_base_url == "http://localhost:20128/v1"
    assert settings.ninerouter_model == "gpt-4o-mini"
    assert settings.ninerouter_api_key == ""
    assert settings.ninerouter_embed_model == ""


def test_ninerouter_in_provider_order_requires_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER_ORDER", "9router")
    monkeypatch.delenv("NINEROUTER_MODEL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_ninerouter_in_provider_order_passes_with_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER_ORDER", "9router")
    monkeypatch.setenv("NINEROUTER_MODEL", "deepseek-chat")
    monkeypatch.setenv("NINEROUTER_API_KEY", "custom-token")
    settings = Settings(_env_file=None)
    assert settings.ninerouter_model == "deepseek-chat"
    assert settings.ninerouter_api_key == "custom-token"


def test_ninerouter_not_required_when_out_of_provider_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER_ORDER", "")
    settings = Settings(_env_file=None)
    assert settings.ai_provider_order == ""


def test_default_connector_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("NINEROUTER_MODEL", "gpt-4o-mini")
    settings = Settings(_env_file=None)
    assert settings.tavily_api_key == ""
    assert settings.greenhouse_board_token == ""
    assert settings.lever_site_name == ""
    assert settings.requirement_extraction_enabled is True


def test_requirement_extraction_can_be_disabled_explicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("NINEROUTER_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("REQUIREMENT_EXTRACTION_ENABLED", "false")
    settings = Settings(_env_file=None)
    assert settings.requirement_extraction_enabled is False


def test_legacy_worker_environment_aliases_are_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("NINEROUTER_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("EXPORT_BUCKET", "custom-exports")
    monkeypatch.setenv("DAILY_DISCOVERY_HOUR_ASIA_JAKARTA", "12")
    settings = Settings(_env_file=None)
    assert settings.exports_bucket == "custom-exports"
    assert settings.daily_discovery_hour_jakarta == 12


def test_canonical_worker_environment_names_take_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("NINEROUTER_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("EXPORT_BUCKET", "legacy-exports")
    monkeypatch.setenv("EXPORTS_BUCKET", "canonical-exports")
    monkeypatch.setenv("DAILY_DISCOVERY_HOUR_ASIA_JAKARTA", "12")
    monkeypatch.setenv("DAILY_DISCOVERY_HOUR_JAKARTA", "9")
    settings = Settings(_env_file=None)
    assert settings.exports_bucket == "canonical-exports"
    assert settings.daily_discovery_hour_jakarta == 9


def test_daily_discovery_hour_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("NINEROUTER_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("DAILY_DISCOVERY_HOUR_ASIA_JAKARTA", "24")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_tavily_api_key_is_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-key")
    monkeypatch.setenv("NINEROUTER_MODEL", "gpt-4o-mini")
    settings = Settings(_env_file=None)

    assert settings.tavily_api_key == "tavily-key"
