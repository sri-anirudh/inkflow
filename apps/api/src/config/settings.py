from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_REPO_ROOT_ENV_FILE, extra="ignore")

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_db_url: str = ""

    redis_url: str = "redis://redis:6379"

    sendgrid_api_key: str = ""
    sendgrid_from_email: str = ""

    jwt_jwks_url: str = ""
    environment: str = "development"


settings = Settings()
