from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    supabase_url: str
    supabase_service_role_key: str
    cv_bucket: str = "cvs"
    worker_poll_seconds: float = 1.0
    worker_id: str = "worker-1"
    max_attempts: int = 3
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")