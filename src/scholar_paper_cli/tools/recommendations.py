"""Recommendation tools: SS API recommendations and local KNN related papers."""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from scholar_paper_cli.exceptions import EmbeddingError
from scholar_paper_cli.models import CacheMetadata, Paper, PaperSearchResult, ToolResponse
from scholar_paper_cli.storage.cache import CachedSemanticScholarClient
from scholar_paper_cli.storage.embeddings import Embedder, knn_search, upsert_embedding
from scholar_paper_cli.storage.papers import get_paper as _get_paper_from_db
from scholar_paper_cli.storage.papers import upsert_paper
from scholar_paper_cli.tools.papers import _parse_paper


def _meta(source: Literal["cache", "api", "offline_cache", "embeddings"] = "api") -> CacheMetadata:
    return CacheMetadata(cached=True, fetched_at=datetime.now(UTC), source=source)


def _parse_recommendation_result(data: dict[str, Any], paper_id: str) -> PaperSearchResult:
    now = datetime.now(UTC)
    papers = [
        _parse_paper(p, fetched_at=now, ttl_until=now + timedelta(days=30))
        for p in data.get("recommendedPapers", [])
    ]
    return PaperSearchResult(
        query=paper_id,
        total=len(papers),
        offset=0,
        next_offset=None,
        data=papers,
    )


async def get_paper_recommendations(
    client: CachedSemanticScholarClient,
    paper_id: str,
    *,
    limit: int = 100,
    positive_ids: list[str] | None = None,
    negative_ids: list[str] | None = None,
    fields: list[str] | None = None,
) -> ToolResponse[PaperSearchResult]:
    data, meta = await client.get_recommendations(
        paper_id,
        limit=limit,
        fields=fields,
        positive_ids=positive_ids,
        negative_ids=negative_ids,
    )
    return ToolResponse(data=_parse_recommendation_result(data, paper_id), meta=meta)


async def get_related_papers(
    client: CachedSemanticScholarClient,
    conn,
    embedder: Embedder | None,
    paper_id: str,
    *,
    k: int = 10,
) -> ToolResponse[list[Paper]]:
    if embedder is None:
        raise EmbeddingError("embedder required for related papers")

    paper = _get_paper_from_db(conn, paper_id)
    if paper is None or paper.embedding is None:
        data, _ = await client.get_paper(paper_id)
        now = datetime.now(UTC)
        paper = _parse_paper(data, fetched_at=now, ttl_until=now + timedelta(days=30))
        if paper.abstract:
            [emb] = embedder.encode([paper.abstract], mode="passage")
            paper.embedding = emb
            upsert_embedding(conn, paper.paper_id, emb)
        upsert_paper(conn, paper)

    if paper.embedding is None:
        raise EmbeddingError(f"paper {paper_id} has no abstract, cannot embed")

    raw_results = knn_search(conn, paper.embedding, k=k + 1)
    related_ids = [(pid, dist) for pid, dist in raw_results if pid != paper_id][:k]

    papers: list[Paper] = []
    for pid, _ in related_ids:
        p = _get_paper_from_db(conn, pid)
        if p is None:
            data, _ = await client.get_paper(pid)
            now = datetime.now(UTC)
            p = _parse_paper(data, fetched_at=now, ttl_until=now + timedelta(days=30))
            upsert_paper(conn, p)
        papers.append(p)

    return ToolResponse(data=papers, meta=_meta("embeddings"))
