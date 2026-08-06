"""spm: CLI for Semantic Scholar with persistent cache and offline fallback."""

from scholar_paper_mcp.config import Settings, get_settings, init_cache_dir
from scholar_paper_mcp.exceptions import (
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
from scholar_paper_mcp.models import (
    Author,
    AuthorBrief,
    AuthorSearchResult,
    CacheMetadata,
    CitationEdge,
    Paper,
    PaperBrief,
    PaperSearchResult,
    SearchResult,
    ToolResponse,
)

__version__ = "0.1.0"

__all__ = [
    "APIError",
    "APINotFoundError",
    "APIRateLimitError",
    "APIServerError",
    "APITimeoutError",
    "Author",
    "AuthorBrief",
    "AuthorSearchResult",
    "CacheError",
    "CacheMetadata",
    "CacheMissError",
    "CitationEdge",
    "ConfigError",
    "EmbeddingError",
    "EmbeddingInferenceError",
    "EmbeddingModelNotFoundError",
    "OfflineError",
    "Paper",
    "PaperBrief",
    "PaperSearchResult",
    "ScholarPaperError",
    "SearchResult",
    "Settings",
    "ToolResponse",
    "get_settings",
    "init_cache_dir",
]
