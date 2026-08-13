"""Recommendation tools: SS API recommendations and local KNN related papers."""

from datetime import UTC, datetime
from typing import Any

from scholar_paper_cli.exceptions import EmbeddingError
from scholar_paper_cli.models import Paper, PaperSearchResult, ToolResponse
from scholar_paper_cli.storage.cache import (
    CachedSemanticScholarClient,
    entity_ttl_until,
    make_metadata,
)
from scholar_paper_cli.storage.embeddings import Embedder, knn_search
from scholar_paper_cli.tools.papers import ensure_paper, parse_paper


def _parse_recommendation_result(data: dict[str, Any], paper_id: str) -> PaperSearchResult:
    now = datetime.now(UTC)
    papers = [
        parse_paper(p, fetched_at=now, ttl_until=entity_ttl_until(now))
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

    paper, _ = await ensure_paper(client, conn, paper_id, embedder=embedder)
    if paper.embedding is None:
        raise EmbeddingError(f"paper {paper_id} has no abstract, cannot embed")

    raw_results = knn_search(conn, paper.embedding, k=k + 1)
    related_ids = [(pid, dist) for pid, dist in raw_results if pid != paper_id][:k]

    papers: list[Paper] = []
    for pid, _ in related_ids:
        p, _ = await ensure_paper(client, conn, pid)
        papers.append(p)

    return ToolResponse(data=papers, meta=make_metadata("embeddings"))
