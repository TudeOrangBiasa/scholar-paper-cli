"""FastMCP server entry point. Wires dependencies via lifespan, registers 15 tools."""

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, cast

from fastmcp import Context, FastMCP

from scholar_paper_mcp import tools
from scholar_paper_mcp.api.client import SemanticScholarClient
from scholar_paper_mcp.api.offline import OfflineDetector
from scholar_paper_mcp.config import get_settings, init_cache_dir
from scholar_paper_mcp.exceptions import EmbeddingModelNotFoundError
from scholar_paper_mcp.storage.cache import CachedSemanticScholarClient
from scholar_paper_mcp.storage.db import apply_migrations, connect
from scholar_paper_mcp.storage.embeddings import Embedder, get_embedder

logger = logging.getLogger(__name__)


@dataclass
class ServerState:
    conn: Any
    raw_client: SemanticScholarClient
    cached: CachedSemanticScholarClient
    embedder: Embedder | None


@asynccontextmanager
async def lifespan(server: FastMCP):
    init_cache_dir()
    settings = get_settings()
    conn = connect()
    try:
        apply_migrations(conn)
        raw_client = SemanticScholarClient()
        try:
            offline = OfflineDetector(
                raw_client._client,
                force_offline=settings.offline_mode,
            )
            cached = CachedSemanticScholarClient(raw_client, conn, offline=offline)
            embedder: Embedder | None = None
            if settings.embedding_model != "none":
                try:
                    embedder = get_embedder()
                except EmbeddingModelNotFoundError as e:
                    logger.warning("embedding model not available: %s", e)
            state = ServerState(conn=conn, raw_client=raw_client, cached=cached, embedder=embedder)
            yield state
        finally:
            try:
                await raw_client.close()
            except Exception:
                logger.exception("error closing httpx client")
    finally:
        conn.close()


mcp = FastMCP("scholar-paper-mcp", lifespan=lifespan)


# Paper tools
async def search_papers(ctx: Context, query: str, limit: int = 10, offset: int = 0) -> str:
    """Search papers by query. Returns paginated Paper list with metadata."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.papers.search_papers(state.cached, query, limit=limit, offset=offset)
    return result.model_dump_json()


async def get_paper_details(ctx: Context, paper_id: str) -> str:
    """Fetch full paper by ID. Caches + embeds abstract if embedder loaded."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.papers.get_paper_details(
        state.cached, state.conn, state.embedder, paper_id
    )
    return result.model_dump_json()


async def get_paper_citations(
    ctx: Context, paper_id: str, limit: int = 100, offset: int = 0
) -> str:
    """List papers that cite this paper. Persists edges to local cache."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.papers.get_paper_citations(
        state.cached, state.conn, paper_id, limit=limit, offset=offset
    )
    return result.model_dump_json()


async def get_paper_references(
    ctx: Context, paper_id: str, limit: int = 100, offset: int = 0
) -> str:
    """List papers this paper references. Persists edges to local cache."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.papers.get_paper_references(
        state.cached, state.conn, paper_id, limit=limit, offset=offset
    )
    return result.model_dump_json()


# Author tools
async def search_authors(ctx: Context, query: str, limit: int = 10, offset: int = 0) -> str:
    """Search authors by name. Returns minimal Author records."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.authors.search_authors(state.cached, query, limit=limit, offset=offset)
    return result.model_dump_json()


async def get_author_details(ctx: Context, author_id: str) -> str:
    """Fetch full author profile by ID with top papers and aliases."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.authors.get_author_details(state.cached, state.conn, author_id)
    return result.model_dump_json()


async def get_author_top_papers(ctx: Context, author_id: str, limit: int = 10) -> str:
    """List author's most-cited papers."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.authors.get_author_top_papers(state.cached, author_id, limit=limit)
    return result.model_dump_json()


async def find_author_duplicates(
    ctx: Context, query: str, limit: int = 50, threshold: float = 0.8
) -> str:
    """Group search results by name similarity. Returns clusters of likely duplicates."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.authors.find_author_duplicates(
        state.cached, query, limit=limit, threshold=threshold
    )
    return result.model_dump_json()


async def consolidate_authors(ctx: Context, canonical_id: str, duplicate_ids: list[str]) -> str:
    """Merge duplicate authors into canonical. Updates papers, aliases, embeddings."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.authors.consolidate_authors(state.conn, canonical_id, duplicate_ids)
    return result.model_dump_json()


# Recommendation tools
async def get_paper_recommendations(ctx: Context, paper_id: str, limit: int = 100) -> str:
    """Get S2 recommendations for a paper. Up to 100, sorted by relevance."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.recommendations.get_paper_recommendations(
        state.cached, paper_id, limit=limit
    )
    return result.model_dump_json()


async def get_related_papers(ctx: Context, paper_id: str, k: int = 10) -> str:
    """KNN over local embeddings to find semantically similar papers."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.recommendations.get_related_papers(
        state.cached, state.conn, state.embedder, paper_id, k=k
    )
    return result.model_dump_json()


# Session tools
async def add_paper_to_session(ctx: Context, session_id: str, paper_id: str) -> str:
    """Add a paper to a session by ID. Auto-fetches if not in cache."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.session.add_paper_to_session(
        state.cached, state.conn, session_id, paper_id
    )
    return result.model_dump_json()


async def list_session_papers_tool(ctx: Context, session_id: str) -> str:
    """List all papers in a session, oldest first."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.session.list_session_papers_tool(state.conn, session_id)
    return result.model_dump_json()


async def remove_from_session_tool(ctx: Context, session_id: str, paper_id: str) -> str:
    """Remove a paper from a session. Returns True on success."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.session.remove_from_session_tool(state.conn, session_id, paper_id)
    return result.model_dump_json()


# BibTeX tool
async def export_session_bibtex(ctx: Context, session_id: str) -> str:
    """Export all session papers as concatenated BibTeX entries."""
    state = cast(ServerState, ctx.lifespan_context)
    result = await tools.bibtex.export_session_bibtex(state.conn, session_id)
    return result.model_dump_json()


mcp.tool()(search_papers)
mcp.tool()(get_paper_details)
mcp.tool()(get_paper_citations)
mcp.tool()(get_paper_references)
mcp.tool()(search_authors)
mcp.tool()(get_author_details)
mcp.tool()(get_author_top_papers)
mcp.tool()(find_author_duplicates)
mcp.tool()(consolidate_authors)
mcp.tool()(get_paper_recommendations)
mcp.tool()(get_related_papers)
mcp.tool()(add_paper_to_session)
mcp.tool()(list_session_papers_tool)
mcp.tool()(remove_from_session_tool)
mcp.tool()(export_session_bibtex)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
