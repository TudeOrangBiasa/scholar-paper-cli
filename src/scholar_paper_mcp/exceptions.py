"""Exception hierarchy: ScholarPaperError -> OfflineError, CacheError, APIError, EmbeddingError, ConfigError.

APIError splits into APIRateLimitError (429), APINotFoundError (404), APIServerError (5xx), APITimeoutError.
CacheError splits into CacheMissError.
EmbeddingError splits into EmbeddingModelNotFoundError, EmbeddingInferenceError.
"""

from typing import Any


class ScholarPaperError(Exception):
    """Root exception for the scholar-paper-mcp package."""

    def __init__(
        self,
        message: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            return f"{self.message} | context={self.context}"
        return self.message


class OfflineError(ScholarPaperError):
    """Raised when API is unreachable AND no cached data is available."""


class CacheError(ScholarPaperError):
    """Cache layer failure (read/write/serialize)."""


class CacheMissError(CacheError):
    """Explicit cache miss — key not present."""


class APIError(ScholarPaperError):
    """Semantic Scholar API failure."""


class APIRateLimitError(APIError):
    """HTTP 429 — rate limited."""


class APINotFoundError(APIError):
    """HTTP 404 — resource not found."""


class APIServerError(APIError):
    """HTTP 5xx — server error."""


class APITimeoutError(APIError):
    """Timeout or connection error."""


class EmbeddingError(ScholarPaperError):
    """ONNX model load or inference failure."""


class EmbeddingModelNotFoundError(EmbeddingError):
    """Embedding model file not found."""


class EmbeddingInferenceError(EmbeddingError):
    """Error during embedding inference."""


class ConfigError(ScholarPaperError):
    """Invalid configuration or missing required value."""
