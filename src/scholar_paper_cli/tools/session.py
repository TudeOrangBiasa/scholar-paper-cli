"""Session tools: add, remove, list papers in a working session."""

from scholar_paper_cli.models import Paper, ToolResponse
from scholar_paper_cli.storage.cache import (
    CachedSemanticScholarClient,
    make_metadata,
)
from scholar_paper_cli.storage.papers import (
    get_paper as _get_paper_from_db,
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
from scholar_paper_cli.tools.papers import ensure_paper


async def add_paper_to_session(
    client: CachedSemanticScholarClient,
    conn,
    session_id: str,
    paper_id: str,
    *,
    fields: list[str] | None = None,
) -> ToolResponse[Paper]:
    paper, meta = await ensure_paper(client, conn, paper_id, fields=fields)
    _add_to_session(conn, session_id, paper_id)
    return ToolResponse(data=paper, meta=meta)


async def remove_from_session(
    conn,
    session_id: str,
    paper_id: str,
) -> ToolResponse[bool]:
    _remove_from_session(conn, session_id, paper_id)
    return ToolResponse(data=True, meta=make_metadata("db"))


async def list_session_papers(
    conn,
    session_id: str,
) -> ToolResponse[list[Paper]]:
    paper_ids = _list_session_paper_ids(conn, session_id)
    papers = [_get_paper_from_db(conn, pid) for pid in paper_ids]
    papers = [p for p in papers if p is not None]
    return ToolResponse(data=papers, meta=make_metadata("db"))
