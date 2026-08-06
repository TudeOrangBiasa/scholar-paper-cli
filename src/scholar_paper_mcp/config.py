"""Typed settings from env vars. Singleton via lru_cache."""

import functools
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from env vars with SPM_ prefix.

    All fields have sensible defaults. Set SPM_ env vars in .env or
    environment to override.
    """

    model_config = SettingsConfigDict(
        env_prefix="SPM_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    api_key: str | None = Field(default=None, description="Semantic Scholar API key")
    cache_path: Path = Field(
        default=Path("~/.local/share/scholar-paper-cli/cache.db"),
        description="Path to SQLite cache database",
    )
    cache_ttl_days: int = Field(default=30, ge=1, description="Cache TTL in days")
    offline_mode: bool = Field(default=False, description="Force offline mode, never call API")
    embedding_model: Literal["intfloat/multilingual-e5-small", "none"] = Field(
        default="intfloat/multilingual-e5-small",
        description="Embedding model to use",
    )
    default_search_limit: int = Field(
        default=10, ge=1, le=100, description="Default search result limit"
    )
    default_papers_limit: int = Field(
        default=20, ge=1, le=100, description="Default papers result limit"
    )
    default_citations_limit: int = Field(
        default=100, ge=1, le=1000, description="Default citations result limit"
    )
    ss_api_base: HttpUrl = Field(
        default=HttpUrl("https://api.semanticscholar.org/graph/v1"),
        description="Semantic Scholar API base URL",
    )
    offline_probe_timeout_seconds: float = Field(
        default=2.0,
        ge=0.5,
        le=10.0,
        description="Timeout for offline probe",
    )
    offline_probe_grace_seconds: int = Field(
        default=60,
        ge=1,
        le=600,
        description="Grace period before retrying after offline",
    )

    @field_validator("cache_path", mode="before")
    @classmethod
    def _expand_cache_path(cls, v: str | Path) -> Path:
        return Path(v).expanduser()


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings singleton.

    Call ``get_settings.cache_clear()`` in tests to force fresh load.
    """
    return Settings()


def init_cache_dir() -> Path:
    """Create cache parent directory if missing. Returns resolved cache path.

    Call once at server startup; settings import should not have side effects.
    """
    p = get_settings().cache_path
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
