"""Tests for recommendation tools."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from unittest.mock import AsyncMock, Mock

import pytest

from scholar_paper_cli.models import CacheMetadata, Paper
from scholar_paper_cli.storage.cache import CachedSemanticScholarClient
from scholar_paper_cli.storage.db import apply_migrations, connect
from scholar_paper_cli.storage.embeddings import Embedder, upsert_embedding
from scholar_paper_cli.tools.recommendations import (
    get_paper_recommendations,
    get_related_papers,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = connect(tmp_path / "test.db")
    apply_migrations(c)
    return c


def _meta(source: Literal["cache", "api", "offline_cache", "embeddings"] = "api") -> CacheMetadata:
    return CacheMetadata(cached=False, fetched_at=datetime.now(UTC), source=source)


def _seed_paper_with_embedding(conn, paper_id, embedding, abstract="abs") -> None:
    now = datetime.now(UTC)
    paper = Paper(
        paper_id=paper_id,
        title=f"Title {paper_id}",
        abstract=abstract,
        embedding=embedding,
        fetched_at=now,
        ttl_until=now + timedelta(days=30),
    )
    from scholar_paper_cli.storage.papers import upsert_paper

    upsert_paper(conn, paper)
    upsert_embedding(conn, paper_id, embedding)


# ── get_paper_recommendations ──────────────────────────────


SAMPLE_RECOMMENDATION = {
    "recommendedPapers": [
        {"paperId": "rec1", "title": "Rec1", "citationCount": 10},
        {"paperId": "rec2", "title": "Rec2", "citationCount": 20},
    ]
}


@pytest.mark.asyncio
async def test_recommendations_returns_tool_response(conn) -> None:
    client = AsyncMock(spec=CachedSemanticScholarClient)
    client.get_recommendations.return_value = (SAMPLE_RECOMMENDATION, _meta())
    result = await get_paper_recommendations(client, "src")
    assert result.data.query == "src"
    assert len(result.data.data) == 2
    assert result.data.data[0].paper_id == "rec1"


@pytest.mark.asyncio
async def test_recommendations_passes_positive_and_negative_ids(conn) -> None:
    client = AsyncMock(spec=CachedSemanticScholarClient)
    client.get_recommendations.return_value = (SAMPLE_RECOMMENDATION, _meta())
    await get_paper_recommendations(
        client, "src", positive_ids=["p1", "p2"], negative_ids=["n1"], limit=20
    )
    client.get_recommendations.assert_awaited_once_with(
        "src", limit=20, fields=None, positive_ids=["p1", "p2"], negative_ids=["n1"]
    )


@pytest.mark.asyncio
async def test_recommendations_handles_empty(conn) -> None:
    client = AsyncMock(spec=CachedSemanticScholarClient)
    client.get_recommendations.return_value = ({"recommendedPapers": []}, _meta())
    result = await get_paper_recommendations(client, "src")
    assert result.data.data == []


# ── get_related_papers ────────────────────────────────────


def _unit_vec(i: int) -> list[float]:
    v = [0.0] * 384
    v[i % 384] = 1.0
    v[(i + 1) % 384] = 0.5
    return v


@pytest.mark.asyncio
async def test_related_papers_uses_knn_search(conn) -> None:
    _seed_paper_with_embedding(conn, "src", _unit_vec(0))
    _seed_paper_with_embedding(conn, "similar", _unit_vec(0))
    _seed_paper_with_embedding(conn, "different", _unit_vec(100))

    client = AsyncMock(spec=CachedSemanticScholarClient)
    embedder = Mock(spec=Embedder)
    embedder.encode.return_value = [_unit_vec(0)]

    result = await get_related_papers(client, conn, embedder, "src", k=2)
    assert len(result.data) == 2
    assert "src" not in [p.paper_id for p in result.data]
    assert "similar" in [p.paper_id for p in result.data]
    assert result.meta.source == "embeddings"


@pytest.mark.asyncio
async def test_related_papers_fetches_target_when_not_in_db(conn) -> None:
    target_data = {"paperId": "new", "title": "New", "abstract": "test abstract"}
    client = AsyncMock(spec=CachedSemanticScholarClient)
    client.get_paper.return_value = (target_data, _meta())
    embedder = Mock(spec=Embedder)
    embedder.encode.return_value = [_unit_vec(0)]

    await get_related_papers(client, conn, embedder, "new", k=1)
    client.get_paper.assert_awaited_once()
    embedder.encode.assert_called_once()


@pytest.mark.asyncio
async def test_related_papers_raises_without_embedder(conn) -> None:
    from scholar_paper_cli.exceptions import EmbeddingError

    client = AsyncMock(spec=CachedSemanticScholarClient)
    with pytest.raises(EmbeddingError):
        await get_related_papers(client, conn, None, "src")


@pytest.mark.asyncio
async def test_related_papers_fetches_full_paper_for_related_ids(conn) -> None:
    from scholar_paper_cli.storage.embeddings import upsert_embedding as ups_emb

    _seed_paper_with_embedding(conn, "src", _unit_vec(0))
    # Embedding without a papers row — KNN finds it, but get_paper from DB misses
    ups_emb(conn, "rel1", _unit_vec(0))

    client = AsyncMock(spec=CachedSemanticScholarClient)
    client.get_paper.return_value = ({"paperId": "rel1", "title": "Rel1"}, _meta())
    embedder = Mock(spec=Embedder)
    embedder.encode.return_value = [_unit_vec(0)]

    await get_related_papers(client, conn, embedder, "src", k=1)
    client.get_paper.assert_awaited()


@pytest.mark.asyncio
async def test_related_papers_skips_self_in_knn_results(conn) -> None:
    _seed_paper_with_embedding(conn, "src", _unit_vec(0))
    _seed_paper_with_embedding(conn, "other", _unit_vec(0))

    client = AsyncMock(spec=CachedSemanticScholarClient)
    embedder = Mock(spec=Embedder)
    embedder.encode.return_value = [_unit_vec(0)]

    result = await get_related_papers(client, conn, embedder, "src", k=5)
    paper_ids = [p.paper_id for p in result.data]
    assert "src" not in paper_ids
