"""Tests for paper tools."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from unittest.mock import AsyncMock, Mock

import pytest

from scholar_paper_cli.models import CacheMetadata
from scholar_paper_cli.storage.cache import CachedSemanticScholarClient
from scholar_paper_cli.storage.db import apply_migrations, connect
from scholar_paper_cli.storage.embeddings import Embedder
from scholar_paper_cli.tools.papers import (
    get_paper_citations,
    get_paper_details,
    get_paper_references,
    search_papers,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = connect(tmp_path / "test.db")
    apply_migrations(c)
    c.execute("PRAGMA foreign_keys = OFF")
    return c


def _meta(source: Literal["cache", "api", "offline_cache"] = "api") -> CacheMetadata:
    return CacheMetadata(
        cached=False,
        fetched_at=datetime.now(UTC),
        source=source,
    )


def _make_client(data: dict) -> AsyncMock:
    client = AsyncMock(spec=CachedSemanticScholarClient)
    client.search_papers.return_value = (data, _meta())
    client.get_paper.return_value = (data, _meta())
    client.get_citations.return_value = (data, _meta())
    client.get_references.return_value = (data, _meta())
    return client


SAMPLE_PAPER_DATA = {
    "paperId": "abc",
    "title": "Quantum Entanglement",
    "abstract": "About qubits",
    "year": 2024,
    "venue": "Nature Physics",
    "citationCount": 100,
    "externalIds": {"DOI": "10.1234/abc"},
    "authors": [{"authorId": "a1", "name": "Alice"}],
}


# ── search_papers ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_papers_returns_tool_response_with_results(conn) -> None:
    client = _make_client({"total": 1, "offset": 0, "next": 10, "data": [SAMPLE_PAPER_DATA]})
    result = await search_papers(client, "quantum", limit=10)
    assert result.data.total == 1
    assert len(result.data.data) == 1
    assert result.data.data[0].paper_id == "abc"
    assert result.meta.source == "api"


@pytest.mark.asyncio
async def test_search_papers_passes_query_to_client(conn) -> None:
    client = _make_client({"total": 0, "data": []})
    await search_papers(client, "machine learning", limit=20, offset=5)
    client.search_papers.assert_awaited_once_with(
        "machine learning", limit=20, offset=5, fields=None
    )


@pytest.mark.asyncio
async def test_search_papers_handles_empty_results(conn) -> None:
    client = _make_client({"total": 0, "data": []})
    result = await search_papers(client, "nonexistent")
    assert result.data.data == []
    assert result.data.total == 0


# ── get_paper_details ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_paper_details_returns_paper_with_metadata(conn) -> None:
    client = _make_client(SAMPLE_PAPER_DATA)
    result = await get_paper_details(client, conn, None, "abc")
    assert result.data.paper_id == "abc"
    assert result.data.title == "Quantum Entanglement"
    assert result.data.authors[0].author_id == "a1"
    assert result.data.external_ids == {"DOI": "10.1234/abc"}


@pytest.mark.asyncio
async def test_get_paper_details_persists_to_storage(conn) -> None:
    from scholar_paper_cli.storage.papers import get_paper as get_paper_from_db

    client = _make_client(SAMPLE_PAPER_DATA)
    await get_paper_details(client, conn, None, "abc")
    stored = get_paper_from_db(conn, "abc")
    assert stored is not None
    assert stored.title == "Quantum Entanglement"


@pytest.mark.asyncio
async def test_get_paper_details_computes_embedding_when_abstract_present(conn) -> None:
    client = _make_client(SAMPLE_PAPER_DATA)
    embedder = Mock(spec=Embedder)
    fake_emb = [0.1] * 384
    embedder.encode.return_value = [fake_emb]
    result = await get_paper_details(client, conn, embedder, "abc")
    embedder.encode.assert_called_once_with(["About qubits"], mode="passage")
    assert result.data.embedding == fake_emb


@pytest.mark.asyncio
async def test_get_paper_details_skips_embedding_when_no_abstract(conn) -> None:
    data = {**SAMPLE_PAPER_DATA, "abstract": None}
    client = _make_client(data)
    embedder = Mock(spec=Embedder)
    await get_paper_details(client, conn, embedder, "abc")
    embedder.encode.assert_not_called()


@pytest.mark.asyncio
async def test_get_paper_details_skips_embedding_when_embedder_is_none(conn) -> None:
    client = _make_client(SAMPLE_PAPER_DATA)
    result = await get_paper_details(client, conn, None, "abc")
    assert result.data.embedding is None


@pytest.mark.asyncio
async def test_get_paper_details_persists_embedding_to_vec_table(conn) -> None:
    from scholar_paper_cli.storage.embeddings import knn_search

    client = _make_client(SAMPLE_PAPER_DATA)
    embedder = Mock(spec=Embedder)
    fake_emb = [0.1 * i for i in range(384)]
    embedder.encode.return_value = [fake_emb]
    await get_paper_details(client, conn, embedder, "abc")
    results = knn_search(conn, fake_emb, k=1)
    assert len(results) == 1
    assert results[0][0] == "abc"


@pytest.mark.asyncio
async def test_get_paper_details_propagates_cache_metadata(conn) -> None:
    client = AsyncMock(spec=CachedSemanticScholarClient)
    client.get_paper.return_value = (SAMPLE_PAPER_DATA, _meta("cache"))
    result = await get_paper_details(client, conn, None, "abc")
    assert result.meta.source == "cache"


# ── get_paper_citations ────────────────────────────────────────


CITATION_ENTRY = {
    "citingPaper": {"paperId": "citer1", "title": "Citing Paper"},
    "contexts": ["background", "method"],
    "isInfluential": True,
}


@pytest.mark.asyncio
async def test_get_paper_citations_returns_edges(conn) -> None:
    client = _make_client({"data": [CITATION_ENTRY]})
    result = await get_paper_citations(client, conn, "target", limit=10)
    assert len(result.data) == 1
    assert result.data[0].from_paper_id == "citer1"
    assert result.data[0].to_paper_id == "target"
    assert result.data[0].is_influential is True
    assert result.data[0].context_intent == ["background", "method"]


@pytest.mark.asyncio
async def test_get_paper_citations_persists_to_storage(conn) -> None:
    from scholar_paper_cli.storage.citations import get_citations_of

    client = _make_client({"data": [CITATION_ENTRY]})
    await get_paper_citations(client, conn, "target")
    stored = get_citations_of(conn, "target")
    assert len(stored) == 1
    assert stored[0].from_paper_id == "citer1"


@pytest.mark.asyncio
async def test_get_paper_citations_skips_entries_without_paper_id(conn) -> None:
    client = _make_client(
        {
            "data": [
                CITATION_ENTRY,
                {"citingPaper": None, "isInfluential": False},
            ]
        }
    )
    result = await get_paper_citations(client, conn, "target")
    assert len(result.data) == 1


# ── get_paper_references ───────────────────────────────────────


REFERENCE_ENTRY = {
    "citedPaper": {"paperId": "cited1", "title": "Cited Paper"},
    "isInfluential": False,
}


@pytest.mark.asyncio
async def test_get_paper_references_returns_edges(conn) -> None:
    client = _make_client({"data": [REFERENCE_ENTRY]})
    result = await get_paper_references(client, conn, "source", limit=10)
    assert len(result.data) == 1
    assert result.data[0].from_paper_id == "source"
    assert result.data[0].to_paper_id == "cited1"
    assert result.data[0].is_influential is False
    assert result.data[0].context_intent is None


@pytest.mark.asyncio
async def test_get_paper_references_persists_to_storage(conn) -> None:
    from scholar_paper_cli.storage.citations import get_references_of

    client = _make_client({"data": [REFERENCE_ENTRY]})
    await get_paper_references(client, conn, "source")
    stored = get_references_of(conn, "source")
    assert len(stored) == 1
    assert stored[0].to_paper_id == "cited1"


# ── parsers (unit tests) ───────────────────────────────────────


def test_parse_paper_extracts_authors_and_external_ids() -> None:
    from scholar_paper_cli.tools.papers import _parse_paper

    now = datetime.now(UTC)
    paper = _parse_paper(SAMPLE_PAPER_DATA, fetched_at=now, ttl_until=now + timedelta(days=30))
    assert len(paper.authors) == 1
    assert paper.authors[0].name == "Alice"
    assert paper.external_ids == {"DOI": "10.1234/abc"}


def test_parse_paper_handles_missing_open_access_pdf() -> None:
    from scholar_paper_cli.tools.papers import _parse_paper

    data = {**SAMPLE_PAPER_DATA, "openAccessPdf": None}
    now = datetime.now(UTC)
    paper = _parse_paper(data, fetched_at=now, ttl_until=now + timedelta(days=30))
    assert paper.open_access_pdf_url is None
    assert paper.is_open_access is False
