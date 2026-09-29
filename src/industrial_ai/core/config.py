"""Framework configuration loaded from environment variables (``IAI_*``) and an optional ``.env``.

Settings are passed explicitly to the components that need them; there is no global settings
object. See ``.env.example`` for the documented variables.
"""

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from industrial_ai.core.errors import ConfigurationError


class Environment(StrEnum):
    DEV = "dev"
    TEST = "test"
    DEMO = "demo"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Settings(BaseSettings):
    """Validated framework settings."""

    model_config = SettingsConfigDict(
        env_prefix="IAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    env: Environment = Environment.DEV
    log_level: LogLevel = LogLevel.INFO
    data_dir: Path = Path("./data")
    database_url: str = "sqlite:///./data/processed/industrial_ai.sqlite"
    reference_dirs: dict[str, Path] = Field(
        default_factory=lambda: {"m5_subset": Path("./data/reference/m5_subset")}
    )
    """Reference data the API may use, by id (``IAI_REFERENCE_DIRS`` as JSON). Clients send the id,
    never a path."""
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)


def load_settings(**overrides: Any) -> Settings:
    """Load settings from the environment / ``.env``; keyword overrides take precedence.

    Raises:
        ConfigurationError: if any value is invalid.
    """
    try:
        return Settings(**overrides)
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid configuration: {exc}") from exc
