from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    worker_poll_seconds: float = 1.0
    worker_id: str = "worker-1"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")