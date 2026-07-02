from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> Path | None:
    """Walk up from this file looking for a repo-root `.env`.

    Only relevant for local (non-Docker) runs, where cwd can be anywhere
    under the repo. Inside containers there's no `.env` file at all —
    docker-compose's `env_file: .env` injects real environment variables
    directly, so returning None here is correct and expected: pydantic-
    settings then reads from os.environ alone.
    """
    for candidate in Path(__file__).resolve().parents:
        env_path = candidate / ".env"
        if env_path.is_file():
            return env_path
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_find_env_file(), extra="ignore")

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
