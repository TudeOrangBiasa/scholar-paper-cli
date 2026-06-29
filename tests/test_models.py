"""Tests for models module."""

from datetime import datetime, timedelta, timezone
from typing import Literal, cast

import pytest
from pydantic import HttpUrl, ValidationError

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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def test_paper_minimal() -> None:
    """Paper validates with only paper_id and required timestamps."""
    now = _utcnow()
    p = Paper(paper_id="abc", fetched_at=now, ttl_until=now)
    assert p.paper_id == "abc"
    assert p.title is None
    assert p.abstract is None
    assert p.year is None


def test_paper_all_optional_defaults() -> None:
    """All optional Paper fields have sensible defaults."""
    now = _utcnow()
    p = Paper(paper_id="abc", fetched_at=now, ttl_until=now)
    assert p.citation_count == 0
    assert p.reference_count == 0
    assert p.influential_citation_count == 0
    assert p.is_open_access is False
    assert p.publication_types == []
    assert p.fields_of_study == []
    assert p.external_ids == {}
    assert p.authors == []
    assert p.embedding is None


def test_paper_embedding_default_none() -> None:
    """Paper.embedding defaults to None."""
    now = _utcnow()
    p = Paper(paper_id="abc", fetched_at=now, ttl_until=now)
    assert p.embedding is None


def test_paper_with_embedding() -> None:
    """Paper.embedding accepts list[float]."""
    now = _utcnow()
    p = Paper(paper_id="abc", embedding=[0.1, 0.2, 0.3], fetched_at=now, ttl_until=now)
    assert p.embedding == [0.1, 0.2, 0.3]


def test_paper_coerces_int_external_id_values() -> None:
    """CorpusId from S2 API is int; model must accept and coerce to str."""
    now = _utcnow()
    p = Paper(
        paper_id="abc",
        fetched_at=now,
        ttl_until=now + timedelta(days=30),
        external_ids={"DOI": "10.1234/abc", "CorpusId": 272999614},  # int!
    )
    assert p.external_ids["DOI"] == "10.1234/abc"
    assert p.external_ids["CorpusId"] == "272999614"  # coerced
    assert isinstance(p.external_ids["CorpusId"], str)


def test_paper_coerces_null_lists_and_bool() -> None:
    """S2 returns null for these fields; model must accept and use default."""
    now = _utcnow()
    p = Paper(
        paper_id="abc",
        fetched_at=now,
        ttl_until=now + timedelta(days=30),
        publication_types=None,
        fields_of_study=None,
        authors=None,
        is_open_access=None,
        external_ids=None,
    )
    assert p.publication_types == []
    assert p.fields_of_study == []
    assert p.authors == []
    assert p.is_open_access is False
    assert p.external_ids == {}


def test_author_coerces_null_fields() -> None:
    """S2 returns null for author list fields; model must accept."""
    now = _utcnow()
    a = Author(
        author_id="123",
        fetched_at=now,
        ttl_until=now + timedelta(days=30),
        name="X",
        affiliations=None,
        papers=None,
        aliases=None,
    )
    assert a.affiliations == []
    assert a.papers == []
    assert a.aliases == []


def test_paper_brief_coerces_null_citation_count() -> None:
    pb = PaperBrief(paper_id="abc", citation_count=None)
    assert pb.citation_count == 0


def test_author_name_accepts_none() -> None:
    """Some S2 disambiguation stubs have null name."""
    now = _utcnow()
    a = Author(
        author_id="123",
        fetched_at=now,
        ttl_until=now + timedelta(days=30),
        name=None,
    )
    assert a.name is None


def test_paper_coerces_null_int_fields() -> None:
    """S2 returns null for citation_count, reference_count, influential_citation_count."""
    now = _utcnow()
    p = Paper(
        paper_id="abc",
        fetched_at=now,
        ttl_until=now + timedelta(days=30),
        citation_count=None,
        reference_count=None,
        influential_citation_count=None,
    )
    assert p.citation_count == 0
    assert p.reference_count == 0
    assert p.influential_citation_count == 0


def test_external_ids_filters_none_values() -> None:
    """None values in external_ids should be filtered, not persisted."""
    now = _utcnow()
    p = Paper(
        paper_id="abc",
        fetched_at=now,
        ttl_until=now + timedelta(days=30),
        external_ids={"DOI": "10.1234/abc", "CorpusId": None, "ArXiv": None},
    )
    assert p.external_ids == {"DOI": "10.1234/abc"}
    assert "CorpusId" not in p.external_ids
    assert "ArXiv" not in p.external_ids


def test_author_brief_minimal() -> None:
    """AuthorBrief validates with required fields only."""
    a = AuthorBrief(author_id="123", name="Dr. Smith")
    assert a.author_id == "123"
    assert a.name == "Dr. Smith"
    assert a.affiliations == []


def test_author_with_papers() -> None:
    """Author validates with nested PaperBrief list."""
    now = _utcnow()
    a = Author(
        author_id="123",
        name="Dr. Smith",
        papers=[PaperBrief(paper_id="abc")],
        fetched_at=now,
        ttl_until=now,
    )
    assert len(a.papers) == 1
    assert a.papers[0].paper_id == "abc"


def test_author_aliases() -> None:
    """Author aliases default to empty list."""
    now = _utcnow()
    a = Author(author_id="123", name="Dr. Smith", fetched_at=now, ttl_until=now)
    assert a.aliases == []


def test_search_result_generic_paper() -> None:
    """SearchResult[Paper] validates."""
    sr = SearchResult[Paper](query="machine learning", total=0, data=[])
    assert sr.query == "machine learning"
    assert sr.total == 0
    assert sr.offset == 0
    assert sr.next_offset is None


def test_search_result_with_data() -> None:
    """SearchResult[Paper] holds Paper instances."""
    now = _utcnow()
    sr = SearchResult[Paper](
        query="test",
        total=2,
        data=[
            Paper(paper_id="a", fetched_at=now, ttl_until=now),
            Paper(paper_id="b", fetched_at=now, ttl_until=now),
        ],
    )
    assert len(sr.data) == 2
    assert sr.data[0].paper_id == "a"


def test_paper_search_result_alias() -> None:
    """PaperSearchResult is an alias for SearchResult[Paper]."""
    pr = PaperSearchResult(query="q", total=0, data=[])
    assert isinstance(pr, SearchResult)


def test_author_search_result_alias() -> None:
    """AuthorSearchResult is an alias for SearchResult[Author]."""
    ar = AuthorSearchResult(query="q", total=0, data=[])
    assert isinstance(ar, SearchResult)


def test_cache_metadata_minimal() -> None:
    """CacheMetadata validates with required fields."""
    cm = CacheMetadata(
        cached=True,
        fetched_at=datetime.now(timezone.utc),
        source="cache",
    )
    assert cm.cached is True
    assert cm.offline is False
    assert cm.ttl_until is None


def test_cache_metadata_valid_sources() -> None:
    """CacheMetadata accepts all valid sources."""
    now = datetime.now(timezone.utc)
    for source in ("cache", "api", "offline_cache", "embeddings"):
        cm = CacheMetadata(cached=True, fetched_at=now, source=source)  # type: ignore[arg-type]
        assert cm.source == source


def test_cache_metadata_invalid_source() -> None:
    """CacheMetadata rejects invalid source literal."""
    with pytest.raises(ValidationError):
        CacheMetadata(
            cached=True,
            fetched_at=datetime.now(timezone.utc),
            source=cast(Literal["cache", "api", "offline_cache", "embeddings"], "invalid"),
        )


def test_tool_response_generic() -> None:
    """ToolResponse[PaperSearchResult] validates with nested types."""
    now = _utcnow()
    sr = SearchResult[Paper](
        query="test",
        total=1,
        data=[Paper(paper_id="abc", fetched_at=now, ttl_until=now)],
    )
    cm = CacheMetadata(
        cached=False,
        fetched_at=datetime.now(timezone.utc),
        source="api",
    )
    tr = ToolResponse[PaperSearchResult](data=sr, meta=cm)
    assert tr.data.total == 1
    assert tr.meta.source == "api"
    assert tr.data.data[0].paper_id == "abc"


def test_tool_response_generic_author() -> None:
    """ToolResponse[Author] validates."""
    now = _utcnow()
    a = Author(author_id="1", name="Researcher", fetched_at=now, ttl_until=now)
    cm = CacheMetadata(
        cached=True,
        fetched_at=datetime.now(timezone.utc),
        source="cache",
    )
    tr = ToolResponse[Author](data=a, meta=cm)
    assert tr.data.name == "Researcher"


def test_extra_fields_ignored() -> None:
    """Extra fields are silently ignored."""
    now = _utcnow()
    p = Paper.model_validate(
        {
            "paper_id": "abc",
            "title": "X",
            "unknown_field": "ignored",
            "fetched_at": now,
            "ttl_until": now,
        }
    )
    assert p.title == "X"


def test_http_url_valid() -> None:
    """HttpUrl accepts valid URL string."""
    now = _utcnow()
    url = HttpUrl("https://example.com/p.pdf")
    p = Paper(paper_id="abc", open_access_pdf_url=url, fetched_at=now, ttl_until=now)
    assert p.open_access_pdf_url is not None
    assert str(p.open_access_pdf_url) == "https://example.com/p.pdf"


def test_http_url_invalid() -> None:
    """HttpUrl rejects invalid URL string."""
    now = _utcnow()
    with pytest.raises(ValidationError):
        Paper.model_validate(
            {
                "paper_id": "abc",
                "open_access_pdf_url": "not a url",
                "fetched_at": now,
                "ttl_until": now,
            }
        )


def test_citation_edge_minimal() -> None:
    """CitationEdge validates with required fields."""
    ce = CitationEdge(from_paper_id="a", to_paper_id="b")
    assert ce.from_paper_id == "a"
    assert ce.to_paper_id == "b"
    assert ce.is_influential is False
    assert ce.context_intent is None


def test_citation_edge_with_intent() -> None:
    """CitationEdge with context_intent."""
    ce = CitationEdge(
        from_paper_id="a",
        to_paper_id="b",
        context_intent=["background"],
        is_influential=True,
    )
    assert ce.context_intent == ["background"]
    assert ce.is_influential is True


def test_paper_brief_minimal() -> None:
    """PaperBrief validates with only paper_id."""
    pb = PaperBrief(paper_id="abc")
    assert pb.citation_count == 0
    assert pb.venue is None
