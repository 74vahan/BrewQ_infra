"""Application settings read from environment variables (and a local .env file)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/backend/app/core/config.py -> parents[3] is the repository's `app/` directory
DEFAULT_MEDIA_DIR = Path(__file__).resolve().parents[3] / "media"


class Settings(BaseSettings):
    # env_ignore_empty: `KEY=` lines copied from .env.example mean "use the default".
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True
    )

    database_url: str
    barista_password: SecretStr = SecretStr("")
    barista_token_secret: SecretStr = SecretStr("")
    barista_token_ttl_hours: int = Field(default=12, ge=1, le=72)
    migrate_on_start: bool = False
    seed_on_start: bool = False
    serve_media: bool = False
    media_dir: Path = DEFAULT_MEDIA_DIR
    enable_docs: bool = False
    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        if level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("LOG_LEVEL must be one of CRITICAL, ERROR, WARNING, INFO, DEBUG")
        return level

    @model_validator(mode="after")
    def _check_barista_secrets(self) -> "Settings":
        # The barista endpoints arrive in a later task; the rule is enforced here
        # so a half-configured environment fails at startup, not at first login.
        if self.barista_password.get_secret_value() and (
            len(self.barista_token_secret.get_secret_value()) < 32
        ):
            raise ValueError("BARISTA_TOKEN_SECRET must be at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
