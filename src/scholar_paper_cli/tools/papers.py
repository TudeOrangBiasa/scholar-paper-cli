"""Paper tools: search, details, citations, references."""

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import HttpUrl

from scholar_paper_cli.models import (
    AuthorBrief,
    CitationEdge,
    Paper,
    PaperSearchResult,
    ToolResponse,
)
from scholar_paper_cli.storage.cache import CachedSemanticScholarClient
from scholar_paper_cli.storage.citations import (
    insert_citation,
    insert_reference,
)
from scholar_paper_cli.storage.embeddings import Embedder, upsert_embedding
from scholar_paper_cli.storage.papers import upsert_paper

# ── SS response parsers ─────────────────────────────────────────


def _parse_paper(data: dict[str, Any], *, fetched_at: datetime, ttl_until: datetime) -> Paper:
    oa = data.get("openAccessPdf")
    pdf_url = HttpUrl(oa["url"]) if isinstance(oa, dict) and oa.get("url") else None
    authors = [
        AuthorBrief(author_id=a["authorId"], name=a.get("name", ""))
        for a in data.get("authors", [])
        if a.get("authorId")
    ]
    return Paper(
        paper_id=data["paperId"],
        title=data.get("title"),
        abstract=data.get("abstract"),
        year=data.get("year"),
        venue=data.get("venue"),
        publication_types=data.get("publicationTypes", []),
        fields_of_study=data.get("fieldsOfStudy", []),
        citation_count=data.get("citationCount", 0),
        reference_count=data.get("referenceCount", 0),
        influential_citation_count=data.get("influentialCitationCount", 0),
        is_open_access=bool(data.get("isOpenAccess", False)),
        open_access_pdf_url=pdf_url,
        external_ids=data.get("externalIds", {}),
        authors=authors,
        embedding=None,
        raw=data,
        fetched_at=fetched_at,
        ttl_until=ttl_until,
    )


def _parse_search_result(data: dict[str, Any], query: str) -> PaperSearchResult:
    now = datetime.now(UTC)
    papers = [
        _parse_paper(p, fetched_at=now, ttl_until=now + timedelta(days=30))
        for p in data.get("data", [])
    ]
    return PaperSearchResult(
        query=query,
        total=data.get("total", 0),
        offset=data.get("offset", 0),
        next_offset=data.get("next"),
        data=papers,
    )


def _parse_citation(entry: dict[str, Any], target_paper_id: str) -> CitationEdge | None:
    citing = entry.get("citingPaper") or {}
    citing_id = citing.get("paperId")
    if not citing_id:
        return None
    return CitationEdge(
        from_paper_id=citing_id,
        to_paper_id=target_paper_id,
        context_intent=entry.get("contexts") or entry.get("contextIntent"),
        is_influential=bool(entry.get("isInfluential", False)),
    )


def _parse_reference(entry: dict[str, Any], source_paper_id: str) -> CitationEdge | None:
    cited = entry.get("citedPaper") or {}
    cited_id = cited.get("paperId")
    if not cited_id:
        return None
    return CitationEdge(
        from_paper_id=source_paper_id,
        to_paper_id=cited_id,
        context_intent=None,
        is_influential=bool(entry.get("isInfluential", False)),
    )


# ── Tool functions ──────────────────────────────────────────────


async def search_papers(
    client: CachedSemanticScholarClient,
    query: str,
    *,
    limit: int = 10,
    offset: int = 0,
    fields: list[str] | None = None,
) -> ToolResponse[PaperSearchResult]:
    data, meta = await client.search_papers(query, limit=limit, offset=offset, fields=fields)
    return ToolResponse(data=_parse_search_result(data, query), meta=meta)


async def get_paper_details(
    client: CachedSemanticScholarClient,
    conn,
    embedder: Embedder | None,
    paper_id: str,
    *,
    fields: list[str] | None = None,
) -> ToolResponse[Paper]:
    data, meta = await client.get_paper(paper_id, fields=fields)
    now = datetime.now(UTC)
    paper = _parse_paper(data, fetched_at=now, ttl_until=now + timedelta(days=30))
    if paper.abstract and embedder is not None:
        [embedding] = embedder.encode([paper.abstract], mode="passage")
        upsert_embedding(conn, paper.paper_id, embedding)
        paper.embedding = embedding
    upsert_paper(conn, paper)
    return ToolResponse(data=paper, meta=meta)


async def get_paper_citations(
    client: CachedSemanticScholarClient,
    conn,
    paper_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
    fields: list[str] | None = None,
) -> ToolResponse[list[CitationEdge]]:
    data, meta = await client.get_citations(paper_id, limit=limit, offset=offset, fields=fields)
    edges: list[CitationEdge] = []
    for entry in data.get("data", []):
        edge = _parse_citation(entry, paper_id)
        if edge is not None:
            edges.append(edge)
    for edge in edges:
        insert_citation(conn, edge)
    return ToolResponse(data=edges, meta=meta)


async def get_paper_references(
    client: CachedSemanticScholarClient,
    conn,
    paper_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
    fields: list[str] | None = None,
) -> ToolResponse[list[CitationEdge]]:
    data, meta = await client.get_references(paper_id, limit=limit, offset=offset, fields=fields)
    edges: list[CitationEdge] = []
    for entry in data.get("data", []):
        edge = _parse_reference(entry, paper_id)
        if edge is not None:
            edges.append(edge)
    for edge in edges:
        insert_reference(conn, edge)
    return ToolResponse(data=edges, meta=meta)
