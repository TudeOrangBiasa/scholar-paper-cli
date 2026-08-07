"""Session tools: add, remove, list papers in a working session."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from scholar_paper_cli.models import CacheMetadata, Paper, ToolResponse
from scholar_paper_cli.storage.cache import CachedSemanticScholarClient
from scholar_paper_cli.storage.papers import (
    get_paper as _get_paper_from_db,
)
from scholar_paper_cli.storage.papers import (
    upsert_paper,
)
from scholar_paper_cli.storage.sessions import (
    add_to_session as _add_to_session,
)
from scholar_paper_cli.storage.sessions import (
    list_session_papers as _list_session_paper_ids,
)
from scholar_paper_cli.storage.sessions import (
    remove_from_session as _remove_from_session,
)
from scholar_paper_cli.tools.papers import _parse_paper


def _meta(source: Literal["cache", "api", "offline_cache", "embeddings"]) -> CacheMetadata:
    return CacheMetadata(cached=True, fetched_at=datetime.now(UTC), source=source)


async def add_paper_to_session(
    client: CachedSemanticScholarClient,
    conn,
    session_id: str,
    paper_id: str,
    *,
    fields: list[str] | None = None,
) -> ToolResponse[Paper]:
    paper = _get_paper_from_db(conn, paper_id)
    if paper is None:
        data, _ = await client.get_paper(paper_id, fields=fields)
        now = datetime.now(UTC)
        paper = _parse_paper(data, fetched_at=now, ttl_until=now + timedelta(days=30))
        upsert_paper(conn, paper)
    _add_to_session(conn, session_id, paper_id)
    return ToolResponse(data=paper, meta=_meta("cache"))


async def remove_from_session_tool(
    conn,
    session_id: str,
    paper_id: str,
) -> ToolResponse[bool]:
    _remove_from_session(conn, session_id, paper_id)
    return ToolResponse(data=True, meta=_meta("cache"))


async def list_session_papers_tool(
    conn,
    session_id: str,
) -> ToolResponse[list[Paper]]:
    paper_ids = _list_session_paper_ids(conn, session_id)
    papers = [_get_paper_from_db(conn, pid) for pid in paper_ids]
    papers = [p for p in papers if p is not None]
    return ToolResponse(data=papers, meta=_meta("cache"))
