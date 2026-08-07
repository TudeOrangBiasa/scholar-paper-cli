"""Tests for exceptions module."""

from scholar_paper_cli.exceptions import (
    APIError,
    APINotFoundError,
    APIRateLimitError,
    APIServerError,
    APITimeoutError,
    CacheError,
    CacheMissError,
    ConfigError,
    EmbeddingError,
    EmbeddingInferenceError,
    EmbeddingModelNotFoundError,
    OfflineError,
    ScholarPaperError,
)


def test_offline_error_catchable_as_root() -> None:
    """OfflineError is catchable as ScholarPaperError."""
    err = OfflineError("offline")
    assert isinstance(err, ScholarPaperError)


def test_rate_limit_catchable_as_api_and_root() -> None:
    """APIRateLimitError is catchable as APIError and ScholarPaperError."""
    err = APIRateLimitError("rate limited")
    assert isinstance(err, APIError)
    assert isinstance(err, ScholarPaperError)


def test_str_with_context() -> None:
    """__str__ includes context info when present."""
    err = APIError("bad request", context={"status": 400})
    text = str(err)
    assert "bad request" in text
    assert "400" in text


def test_str_without_context() -> None:
    """__str__ is just message without context."""
    err = APIError("bad request")
    assert str(err) == "bad request"


def test_cache_miss_is_cache_error() -> None:
    """CacheMissError is subclass of CacheError."""
    err = CacheMissError("not found")
    assert isinstance(err, CacheError)
    assert isinstance(err, ScholarPaperError)


def test_all_api_subtypes() -> None:
    """All API error subclasses are APIError + ScholarPaperError."""
    for exc in [
        APIRateLimitError(""),
        APINotFoundError(""),
        APIServerError(""),
        APITimeoutError(""),
    ]:
        assert isinstance(exc, APIError)
        assert isinstance(exc, ScholarPaperError)


def test_offline_hierarchy() -> None:
    """OfflineError is direct ScholarPaperError child (not APIError)."""
    err = OfflineError("offline")
    assert isinstance(err, ScholarPaperError)
    assert not isinstance(err, APIError)


def test_embedding_hierarchy() -> None:
    """EmbeddingModelNotFoundError is EmbeddingError + ScholarPaperError."""
    err = EmbeddingModelNotFoundError("model not found")
    assert isinstance(err, EmbeddingError)
    assert isinstance(err, ScholarPaperError)

    err2 = EmbeddingInferenceError("inference failed")
    assert isinstance(err2, EmbeddingError)
    assert isinstance(err2, ScholarPaperError)


def test_config_error_hierarchy() -> None:
    """ConfigError is a ScholarPaperError (not a subclass of other branches)."""
    err = ConfigError("invalid config")
    assert isinstance(err, ScholarPaperError)
    assert not isinstance(err, APIError)
    assert not isinstance(err, CacheError)
