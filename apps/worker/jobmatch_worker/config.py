from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    supabase_url: str
    supabase_service_role_key: str
    cv_bucket: str = "cvs"
    worker_poll_seconds: float = 1.0
    worker_id: str = "worker-1"
    max_attempts: int = 3
    ai_provider_order: str = "nvidia,openrouter,ollama"
    ai_timeout_seconds: float = 30.0
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = ""
    ollama_api_key: str = ""
    ollama_base_url: str = "https://ollama.com/api"
    ollama_model: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _require_ollama_credentials(self) -> Self:
        providers = [p.strip() for p in self.ai_provider_order.split(",") if p.strip()]
        if "ollama" in providers:
            if not self.ollama_api_key:
                raise ValueError("OLLAMA_API_KEY is required when ollama is in AI_PROVIDER_ORDER")
            if not self.ollama_model:
                raise ValueError("OLLAMA_MODEL is required when ollama is in AI_PROVIDER_ORDER")
        return self