from src.config.settings import Settings


def test_settings_load_with_defaults_when_no_env_present() -> None:
    """CI has no .env and none of our SUPABASE_*/REDIS_URL vars set — every
    field must have a safe default so Settings() doesn't crash at import
    time (Coding Standards §8: fail fast on a *missing required* var, not
    on the absence of optional ones)."""
    s = Settings(_env_file=None)  # type: ignore[call-arg]  # pydantic-settings' dynamic kwarg, not in the static __init__ signature
    assert s.environment == "development"
    assert s.redis_url == "redis://redis:6379"
