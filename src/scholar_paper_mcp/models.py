"""Pydantic domain models for Semantic Scholar data.

All models use extra="ignore" and str_strip_whitespace=True unless noted.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


def _or_default(v: Any, default: Any) -> Any:
    """Return default if v is None, else v. Used by validators."""
    return default if v is None else v


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class AuthorBrief(_Base):
    """Brief author info embedded in Paper."""

    author_id: str
    name: str
    affiliations: list[str] = Field(default_factory=list)
    h_index: int | None = None
    paper_count: int | None = None


class PaperBrief(_Base):
    """Brief paper info embedded in Author."""

    paper_id: str
    title: str | None = None
    year: int | None = None
    citation_count: int = 0
    venue: str | None = None

    @field_validator("citation_count", mode="before")
    @classmethod
    def _coerce_citation_count(cls, v: Any) -> Any:
        return _or_default(v, 0)


class Paper(_Base):
    """Normalized paper matching Semantic Scholar schema."""

    paper_id: str
    fetched_at: datetime
    ttl_until: datetime
    title: str | None = None
    abstract: str | None = None
    year: int | None = None
    venue: str | None = None
    publication_types: list[str] = Field(default_factory=list)
    fields_of_study: list[str] = Field(default_factory=list)
    citation_count: int = 0
    reference_count: int = 0
    influential_citation_count: int = 0
    is_open_access: bool = False
    open_access_pdf_url: HttpUrl | None = None
    external_ids: dict[str, str] = Field(default_factory=dict)
    authors: list[AuthorBrief] = Field(default_factory=list)

    @field_validator("publication_types", "fields_of_study", "authors", mode="before")
    @classmethod
    def _coerce_lists(cls, v: Any) -> Any:
        return _or_default(v, [])

    @field_validator("citation_count", "reference_count", "influential_citation_count", mode="before")
    @classmethod
    def _coerce_ints(cls, v: Any) -> Any:
        return _or_default(v, 0)

    @field_validator("is_open_access", mode="before")
    @classmethod
    def _coerce_is_open_access(cls, v: Any) -> Any:
        return _or_default(v, False)

    @field_validator("external_ids", mode="before")
    @classmethod
    def _coerce_external_ids(cls, v: Any) -> Any:
        if v is None:
            return {}
        if not isinstance(v, dict):
            return v
        return {k: str(val) for k, val in v.items() if val is not None}

    embedding: list[float] | None = None
    raw: dict[str, Any] | None = None


class Author(_Base):
    """Full author with paper references."""

    author_id: str
    fetched_at: datetime
    ttl_until: datetime
    name: str | None = None
    affiliations: list[str] = Field(default_factory=list)
    h_index: int | None = None
    paper_count: int | None = None
    papers: list[PaperBrief] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)

    @field_validator("affiliations", "papers", "aliases", mode="before")
    @classmethod
    def _coerce_lists(cls, v: Any) -> Any:
        return _or_default(v, [])


class CitationEdge(_Base):
    """Directed citation link from one paper to another."""

    from_paper_id: str
    to_paper_id: str
    context_intent: list[str] | None = None
    is_influential: bool = False


class CacheMetadata(_Base):
    """Cache metadata envelope for every response."""

    cached: bool
    fetched_at: datetime
    source: Literal["cache", "api", "offline_cache", "embeddings"]
    offline: bool = False
    ttl_until: datetime | None = None
    cache_key: str | None = None


class SearchResult[T](_Base):
    """Paginated search result with metadata."""

    query: str
    total: int
    offset: int = 0
    next_offset: int | None = None
    data: list[T]


PaperSearchResult = SearchResult[Paper]
AuthorSearchResult = SearchResult[Author]


class ToolResponse[T](_Base):
    """Universal response envelope for all tools."""

    data: T
    meta: CacheMetadata
