"""Author tools: search, details, top papers, duplicates, consolidate."""

from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any

from scholar_paper_cli.models import (
    Author,
    AuthorSearchResult,
    PaperBrief,
    ToolResponse,
)
from scholar_paper_cli.storage.authors import merge_author, upsert_author
from scholar_paper_cli.storage.cache import (
    CachedSemanticScholarClient,
    entity_ttl_until,
    make_metadata,
)

# ── SS response parsers ─────────────────────────────────────────


def _parse_author(data: dict[str, Any], *, fetched_at: datetime, ttl_until: datetime) -> Author:
    papers = [
        PaperBrief(
            paper_id=p["paperId"],
            title=p.get("title"),
            year=p.get("year"),
            citation_count=p.get("citationCount", 0),
            venue=p.get("venue"),
        )
        for p in data.get("papers", [])
        if p.get("paperId")
    ]
    return Author(
        author_id=data["authorId"],
        name=data.get("name", ""),
        affiliations=data.get("affiliations", []),
        h_index=data.get("hIndex"),
        paper_count=data.get("paperCount"),
        papers=papers,
        aliases=data.get("aliases", []),
        fetched_at=fetched_at,
        ttl_until=ttl_until,
    )


def _parse_search_result(data: dict[str, Any], query: str) -> AuthorSearchResult:
    now = datetime.now(UTC)
    authors = [
        _parse_author(a, fetched_at=now, ttl_until=entity_ttl_until(now))
        for a in data.get("data", [])
    ]
    return AuthorSearchResult(
        query=query,
        total=data.get("total", 0),
        offset=data.get("offset", 0),
        next_offset=data.get("next"),
        data=authors,
    )


# ── Helpers ─────────────────────────────────────────────────────


def _name_similarity(a: str | None, b: str | None) -> float:
    a_str = (a or "").lower()
    b_str = (b or "").lower()
    if not a_str and not b_str:
        return 0.0
    return SequenceMatcher(None, a_str, b_str).ratio()


# ── Tool functions ──────────────────────────────────────────────


async def search_authors(
    client: CachedSemanticScholarClient,
    query: str,
    *,
    limit: int = 10,
    offset: int = 0,
    fields: list[str] | None = None,
) -> ToolResponse[AuthorSearchResult]:
    data, meta = await client.search_authors(query, limit=limit, offset=offset, fields=fields)
    return ToolResponse(data=_parse_search_result(data, query), meta=meta)


async def get_author_details(
    client: CachedSemanticScholarClient,
    conn,
    author_id: str,
    *,
    fields: list[str] | None = None,
) -> ToolResponse[Author]:
    data, meta = await client.get_author(author_id, fields=fields)
    now = datetime.now(UTC)
    author = _parse_author(data, fetched_at=now, ttl_until=entity_ttl_until(now))
    upsert_author(conn, author)
    return ToolResponse(data=author, meta=meta)


async def get_author_top_papers(
    client: CachedSemanticScholarClient,
    author_id: str,
    *,
    limit: int = 10,
    fields: list[str] | None = None,
) -> ToolResponse[list[PaperBrief]]:
    data, meta = await client.get_author_papers(author_id, limit=100, offset=0, fields=fields)
    papers = [
        PaperBrief(
            paper_id=p["paperId"],
            title=p.get("title"),
            year=p.get("year"),
            citation_count=p.get("citationCount", 0),
            venue=p.get("venue"),
        )
        for p in data.get("data", [])
        if p.get("paperId")
    ]
    papers.sort(key=lambda x: x.citation_count, reverse=True)
    return ToolResponse(data=papers[:limit], meta=meta)


async def find_author_duplicates(
    client: CachedSemanticScholarClient,
    query: str,
    *,
    limit: int = 50,
    threshold: float = 0.8,
) -> ToolResponse[list[list[Author]]]:
    data, meta = await client.search_authors(query, limit=limit, offset=0)
    now = datetime.now(UTC)
    authors = [
        _parse_author(a, fetched_at=now, ttl_until=entity_ttl_until(now))
        for a in data.get("data", [])
    ]
    groups: list[list[Author]] = []
    seen: set[str] = set()
    for i, a in enumerate(authors):
        if a.author_id in seen:
            continue
        group = [a]
        for b in authors[i + 1 :]:
            if b.author_id in seen:
                continue
            if _name_similarity(a.name, b.name) >= threshold:
                group.append(b)
                seen.add(b.author_id)
        if len(group) > 1:
            seen.add(a.author_id)
            groups.append(group)
    return ToolResponse(data=groups, meta=meta)


async def consolidate_authors(
    conn,
    canonical_id: str,
    duplicate_ids: list[str],
) -> ToolResponse[Author]:
    canonical, _summary = merge_author(conn, canonical_id, duplicate_ids)
    return ToolResponse(data=canonical, meta=make_metadata("db"))
