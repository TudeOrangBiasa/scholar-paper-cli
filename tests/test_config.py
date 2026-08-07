"""Tests for config module."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from scholar_paper_cli.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Clear singleton cache before each test for isolation."""
    get_settings.cache_clear()


def test_default_settings() -> None:
    """Default Settings() has expected default values."""
    s = Settings()
    assert s.cache_ttl_days == 30
    assert s.offline_mode is False
    assert s.default_search_limit == 10
    assert s.default_papers_limit == 20
    assert s.default_citations_limit == 100
    assert isinstance(s.cache_path, Path)
    assert s.cache_path.name == "cache.db"


def test_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env var overrides default."""
    monkeypatch.setenv("SPM_CACHE_TTL_DAYS", "7")
    s = Settings()
    assert s.cache_ttl_days == 7


def test_invalid_limit_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Out-of-range value raises ValidationError (no silent clamp)."""
    monkeypatch.setenv("SPM_DEFAULT_SEARCH_LIMIT", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_offline_mode_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """SPM_OFFLINE_MODE=true sets offline_mode=True."""
    monkeypatch.setenv("SPM_OFFLINE_MODE", "true")
    s = Settings()
    assert s.offline_mode is True


def test_get_settings_singleton() -> None:
    """get_settings() returns same cached instance."""
    a = get_settings()
    b = get_settings()
    assert a is b


def test_get_settings_cache_clear() -> None:
    """cache_clear() allows creating a fresh instance."""
    a = get_settings()
    get_settings.cache_clear()
    b = get_settings()
    assert a is not b


def test_cache_path_expands_tilde() -> None:
    """cache_path expands ~ to home directory."""
    s = Settings(cache_path=Path("~/custom/cache.db"))
    assert "~" not in str(s.cache_path)
    assert s.cache_path.parent.name == "custom"
