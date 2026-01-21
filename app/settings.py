from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/store_db"
    max_batch_size: int = 1000
    api_key_prefix: str = "sk_"
    api_key_length: int = 48
    resend_api_key: str | None = None
    email_from: str | None = Field(default=None, validation_alias="EMAIL")
    email_provider: str = "console"
    reset_token_debug: bool = False
    rate_limit_requests: int = 300
    rate_limit_window_seconds: int = 60
    api_key_reset_cooldown_minutes: int = 30
    allowed_origin_regex: str = r"^https?://([a-zA-Z0-9-]+\.)*usepharmacyos\.com$"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
