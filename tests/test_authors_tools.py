"""Tests for author tools."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from unittest.mock import AsyncMock

import pytest

from scholar_paper_cli.exceptions import APINotFoundError
from scholar_paper_cli.models import Author, CacheMetadata
from scholar_paper_cli.storage.cache import CachedSemanticScholarClient
from scholar_paper_cli.storage.db import apply_migrations, connect
from scholar_paper_cli.tools.authors import (
    consolidate_authors,
    find_author_duplicates,
    get_author_details,
    get_author_top_papers,
    search_authors,
)


def _make_author(author_id, name, papers=None, aliases=None):
    now = datetime.now(UTC)
    return Author(
        author_id=author_id,
        name=name,
        papers=papers or [],
        aliases=aliases or [],
        fetched_at=now,
        ttl_until=now + timedelta(days=30),
    )


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = connect(tmp_path / "test.db")
    apply_migrations(c)
    c.execute("PRAGMA foreign_keys = OFF")
    return c


def _meta(source: Literal["cache", "api", "offline_cache"] = "api") -> CacheMetadata:
    return CacheMetadata(cached=False, fetched_at=datetime.now(UTC), source=source)


def _make_client(data: dict) -> AsyncMock:
    client = AsyncMock(spec=CachedSemanticScholarClient)
    client.search_authors.return_value = (data, _meta())
    client.get_author.return_value = (data, _meta())
    client.get_author_papers.return_value = (data, _meta())
    return client


SAMPLE_AUTHOR = {
    "authorId": "a1",
    "name": "Dr. Alice Smith",
    "affiliations": ["MIT"],
    "hIndex": 42,
    "paperCount": 100,
    "aliases": ["A. Smith"],
    "papers": [{"paperId": "p1", "title": "P1", "year": 2020, "citationCount": 50}],
}


# ── search_authors ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_authors_returns_results(conn) -> None:
    client = _make_client({"total": 1, "data": [SAMPLE_AUTHOR]})
    result = await search_authors(client, "alice")
    assert result.data.total == 1
    assert result.data.data[0].author_id == "a1"
    assert result.data.data[0].h_index == 42


@pytest.mark.asyncio
async def test_search_authors_passes_query(conn) -> None:
    client = _make_client({"total": 0, "data": []})
    await search_authors(client, "smith", limit=5, offset=10)
    client.search_authors.assert_awaited_once_with("smith", limit=5, offset=10, fields=None)


@pytest.mark.asyncio
async def test_search_authors_handles_empty(conn) -> None:
    client = _make_client({"total": 0, "data": []})
    result = await search_authors(client, "nobody")
    assert result.data.data == []


# ── get_author_details ───────────────────────────────────────


@pytest.mark.asyncio
async def test_get_author_details_returns_author(conn) -> None:
    client = _make_client(SAMPLE_AUTHOR)
    result = await get_author_details(client, conn, "a1")
    assert result.data.author_id == "a1"
    assert result.data.h_index == 42
    assert len(result.data.papers) == 1


@pytest.mark.asyncio
async def test_get_author_details_persists_to_db(conn) -> None:
    from scholar_paper_cli.storage.authors import get_author as get_author_from_db

    client = _make_client(SAMPLE_AUTHOR)
    await get_author_details(client, conn, "a1")
    stored = get_author_from_db(conn, "a1")
    assert stored is not None
    assert stored.h_index == 42


# ── get_author_top_papers ────────────────────────────────────


@pytest.mark.asyncio
async def test_get_author_top_papers_sorts_by_citations(conn) -> None:
    papers_data = {
        "data": [
            {"paperId": "p1", "title": "P1", "citationCount": 10},
            {"paperId": "p2", "title": "P2", "citationCount": 100},
            {"paperId": "p3", "title": "P3", "citationCount": 50},
        ]
    }
    client = _make_client(papers_data)
    result = await get_author_top_papers(client, "a1", limit=2)
    assert len(result.data) == 2
    assert result.data[0].paper_id == "p2"
    assert result.data[1].paper_id == "p3"


@pytest.mark.asyncio
async def test_get_author_top_papers_respects_limit(conn) -> None:
    papers_data = {"data": [{"paperId": f"p{i}", "citationCount": i} for i in range(20)]}
    client = _make_client(papers_data)
    result = await get_author_top_papers(client, "a1", limit=5)
    assert len(result.data) == 5


# ── find_author_duplicates ──────────────────────────────────


@pytest.mark.asyncio
async def test_find_duplicates_groups_similar_names(conn) -> None:
    authors_data = {
        "data": [
            {"authorId": "a1", "name": "John Smith"},
            {"authorId": "a2", "name": "Jon Smith"},  # similar
            {"authorId": "a3", "name": "Jane Doe"},  # different
        ]
    }
    client = _make_client(authors_data)
    result = await find_author_duplicates(client, "smith", threshold=0.7)
    assert len(result.data) == 1
    assert len(result.data[0]) == 2
    assert {a.author_id for a in result.data[0]} == {"a1", "a2"}


@pytest.mark.asyncio
async def test_find_duplicates_returns_empty_when_none(conn) -> None:
    authors_data = {
        "data": [
            {"authorId": "a1", "name": "John Smith"},
            {"authorId": "a2", "name": "Jane Doe"},
        ]
    }
    client = _make_client(authors_data)
    result = await find_author_duplicates(client, "test", threshold=0.8)
    assert result.data == []


# ── consolidate_authors ─────────────────────────────────────


@pytest.mark.asyncio
async def test_consolidate_returns_honest_metadata(conn) -> None:
    from scholar_paper_cli.storage.authors import upsert_author as upsert_author_db

    upsert_author_db(conn, _make_author("canon", "Alice"))
    upsert_author_db(conn, _make_author("dup", "Alice Dup"))

    result = await consolidate_authors(conn, "canon", ["dup"])

    assert result.data.author_id == "canon"
    assert result.meta.source == "db"
    assert result.meta.cached is False


@pytest.mark.asyncio
async def test_consolidate_missing_canonical_raises(conn) -> None:
    with pytest.raises(APINotFoundError):
        await consolidate_authors(conn, "nonexistent", [])


def test_name_similarity_handles_none() -> None:
    """Name similarity must accept None inputs without crashing."""
    from scholar_paper_cli.tools.authors import _name_similarity

    assert _name_similarity(None, "John") == 0.0
    assert _name_similarity("John", None) == 0.0
    assert _name_similarity(None, None) == 0.0
    assert _name_similarity("John", "John") > 0.9
    assert _name_similarity("Alice", "Bob") < 0.5
