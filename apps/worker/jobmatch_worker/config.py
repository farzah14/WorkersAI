from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    supabase_url: str
    supabase_service_role_key: str
    cv_bucket: str = "cvs"
    exports_bucket: str = "exports"
    worker_poll_seconds: float = 1.0
    worker_id: str = "worker-1"
    max_attempts: int = 3
    daily_discovery_hour_jakarta: int = 7
    scheduler_interval_minutes: int = 15
    requirement_extraction_enabled: bool = True
    ai_provider_order: str = "9router"
    ai_timeout_seconds: float = 30.0
    ninerouter_api_key: str = ""
    ninerouter_base_url: str = "http://localhost:20128/v1"
    ninerouter_model: str = ""
    ninerouter_embed_model: str = ""
    tavily_api_key: str = ""
    greenhouse_board_token: str = ""
    lever_site_name: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _require_ninerouter_credentials(self) -> Self:
        providers = [p.strip() for p in self.ai_provider_order.split(",") if p.strip()]
        if "9router" in providers and not self.ninerouter_model:
            raise ValueError("NINEROUTER_MODEL is required when 9router is in AI_PROVIDER_ORDER")
        return self
