"""Author tools: search, details, top papers, duplicates, consolidate."""

from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Literal

from scholar_paper_mcp.exceptions import APINotFoundError
from scholar_paper_mcp.models import (
    Author,
    AuthorSearchResult,
    CacheMetadata,
    PaperBrief,
    ToolResponse,
)
from scholar_paper_mcp.storage.authors import (
    delete_author as _delete_author_from_db,
)
from scholar_paper_mcp.storage.authors import (
    get_author as _get_author_from_db,
)
from scholar_paper_mcp.storage.authors import (
    upsert_author as _upsert_author_to_db,
)
from scholar_paper_mcp.storage.cache import CachedSemanticScholarClient

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
        _parse_author(a, fetched_at=now, ttl_until=now + timedelta(days=30))
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


def _meta(source: Literal["cache", "api", "offline_cache"] = "cache") -> CacheMetadata:
    return CacheMetadata(
        cached=True,
        fetched_at=datetime.now(UTC),
        source=source,
    )


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
    author = _parse_author(data, fetched_at=now, ttl_until=now + timedelta(days=30))
    _upsert_author_to_db(conn, author)
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
        _parse_author(a, fetched_at=now, ttl_until=now + timedelta(days=30))
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
    canonical = _get_author_from_db(conn, canonical_id)
    if canonical is None:
        raise APINotFoundError(f"author not found: {canonical_id}")

    seen_paper_ids = {p.paper_id for p in canonical.papers}
    seen_aliases = set(canonical.aliases) | ({canonical.name} if canonical.name else set())

    for dup_id in duplicate_ids:
        dup = _get_author_from_db(conn, dup_id)
        if dup is None:
            continue
        for alias in dup.aliases:
            if alias and alias not in seen_aliases:
                canonical.aliases.append(alias)
                seen_aliases.add(alias)
        for paper in dup.papers:
            if paper.paper_id not in seen_paper_ids:
                canonical.papers.append(paper)
                seen_paper_ids.add(paper.paper_id)
        conn.execute(
            "INSERT OR REPLACE INTO paper_authors (paper_id, author_id, author_position) "
            "SELECT paper_id, ?, author_position FROM paper_authors WHERE author_id = ?",
            (canonical_id, dup_id),
        )
        conn.execute("DELETE FROM paper_authors WHERE author_id = ?", (dup_id,))
        _delete_author_from_db(conn, dup_id)

    canonical.paper_count = len(canonical.papers)
    now = datetime.now(UTC)
    canonical.fetched_at = now
    canonical.ttl_until = now + timedelta(days=30)
    _upsert_author_to_db(conn, canonical)
    conn.commit()
    return ToolResponse(data=canonical, meta=_meta("cache"))
