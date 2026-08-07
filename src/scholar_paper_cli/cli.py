"""spm CLI: 15 subcommands mirroring the MCP tool set, JSON output on stdout.

Dispatch table and error contract:
- success: JSON ToolResponse envelope on stdout, exit 0
- package error: JSON {"error": {"type": <ExceptionClassName>, "message": ...}} on stdout, exit 1
- argparse usage error: stderr usage, exit 2
- internal error: traceback on stderr + JSON InternalError envelope on stdout, exit 1
"""

import argparse
import asyncio
import json
import logging
import sys
import traceback
from dataclasses import dataclass
from typing import Any

from scholar_paper_cli import __version__, tools
from scholar_paper_cli.api.client import SemanticScholarClient
from scholar_paper_cli.api.offline import OfflineDetector
from scholar_paper_cli.config import get_settings, init_cache_dir
from scholar_paper_cli.exceptions import EmbeddingModelNotFoundError, ScholarPaperError
from scholar_paper_cli.models import ToolResponse
from scholar_paper_cli.storage.cache import CachedSemanticScholarClient
from scholar_paper_cli.storage.db import apply_migrations, connect
from scholar_paper_cli.storage.embeddings import Embedder, get_embedder

logger = logging.getLogger(__name__)


@dataclass
class CLIState:
    """Runtime dependencies assembled by build_state."""

    conn: Any
    raw_client: SemanticScholarClient
    cached: CachedSemanticScholarClient
    embedder: Embedder | None


def build_parser() -> argparse.ArgumentParser:
    """Build the spm argument parser with all 15 subcommands."""
    settings = get_settings()
    parser = argparse.ArgumentParser(
        prog="spm",
        description="spm: CLI for Semantic Scholar with persistent cache and offline fallback",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    p = sub.add_parser("search", help="search papers by query")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=settings.default_search_limit)
    p.add_argument("--offset", type=int, default=0)

    p = sub.add_parser("paper", help="get paper details by ID")
    p.add_argument("paper_id")
    p.add_argument(
        "--embed", action="store_true", help="persist a semantic embedding of the abstract"
    )

    p = sub.add_parser("citations", help="list papers that cite a paper")
    p.add_argument("paper_id")
    p.add_argument("--limit", type=int, default=settings.default_citations_limit)
    p.add_argument("--offset", type=int, default=0)

    p = sub.add_parser("references", help="list papers referenced by a paper")
    p.add_argument("paper_id")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--offset", type=int, default=0)

    p = sub.add_parser("author-search", help="search authors by name")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=settings.default_search_limit)
    p.add_argument("--offset", type=int, default=0)

    p = sub.add_parser("author", help="get author details by ID")
    p.add_argument("author_id")

    p = sub.add_parser("author-top", help="list an author's most-cited papers")
    p.add_argument("author_id")
    p.add_argument("--limit", type=int, default=10)

    p = sub.add_parser("author-duplicates", help="group authors by name similarity")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--threshold", type=float, default=0.8)

    p = sub.add_parser("consolidate", help="merge duplicate authors into a canonical author")
    p.add_argument("canonical_id")
    p.add_argument("duplicate_ids", nargs="+")

    p = sub.add_parser("recommend", help="get Semantic Scholar recommendations for a paper")
    p.add_argument("paper_id")
    p.add_argument("--limit", type=int, default=100)

    p = sub.add_parser("related", help="find related papers via local semantic embeddings")
    p.add_argument("paper_id")
    p.add_argument("--k", type=int, default=10)

    session = sub.add_parser("session", help="manage a working session of papers")
    session_sub = session.add_subparsers(
        dest="session_command", metavar="SUBCOMMAND", required=True
    )
    p = session_sub.add_parser("add", help="add a paper to a session")
    p.add_argument("session_id")
    p.add_argument("paper_id")
    p = session_sub.add_parser("list", help="list papers in a session")
    p.add_argument("session_id")
    p = session_sub.add_parser("remove", help="remove a paper from a session")
    p.add_argument("session_id")
    p.add_argument("paper_id")

    p = sub.add_parser("bibtex", help="export session papers as BibTeX")
    p.add_argument("session_id")

    return parser


async def build_state(need_embedder: bool) -> CLIState:
    """Assemble dependencies: cache dir, DB, API client, optional embedder."""
    init_cache_dir()
    settings = get_settings()
    conn = connect()
    raw_client: SemanticScholarClient | None = None
    try:
        apply_migrations(conn)
        raw_client = SemanticScholarClient()
        offline = OfflineDetector(raw_client._client, force_offline=settings.offline_mode)
        cached = CachedSemanticScholarClient(raw_client, conn, offline=offline)
        embedder: Embedder | None = None
        if settings.embedding_model != "none" and need_embedder:
            try:
                embedder = get_embedder()
            except EmbeddingModelNotFoundError as e:
                logger.warning("embedding model not available: %s", e)
        return CLIState(conn=conn, raw_client=raw_client, cached=cached, embedder=embedder)
    except Exception:
        if raw_client is not None:
            await raw_client.close()
        conn.close()
        raise


async def _dispatch(state: CLIState, args: argparse.Namespace) -> ToolResponse[Any]:
    cached = state.cached
    conn = state.conn
    if args.command == "search":
        return await tools.papers.search_papers(
            cached, args.query, limit=args.limit, offset=args.offset
        )
    if args.command == "paper":
        embedder = state.embedder if args.embed else None
        return await tools.papers.get_paper_details(cached, conn, embedder, args.paper_id)
    if args.command == "citations":
        return await tools.papers.get_paper_citations(
            cached, conn, args.paper_id, limit=args.limit, offset=args.offset
        )
    if args.command == "references":
        return await tools.papers.get_paper_references(
            cached, conn, args.paper_id, limit=args.limit, offset=args.offset
        )
    if args.command == "author-search":
        return await tools.authors.search_authors(
            cached, args.query, limit=args.limit, offset=args.offset
        )
    if args.command == "author":
        return await tools.authors.get_author_details(cached, conn, args.author_id)
    if args.command == "author-top":
        return await tools.authors.get_author_top_papers(cached, args.author_id, limit=args.limit)
    if args.command == "author-duplicates":
        return await tools.authors.find_author_duplicates(
            cached, args.query, limit=args.limit, threshold=args.threshold
        )
    if args.command == "consolidate":
        return await tools.authors.consolidate_authors(conn, args.canonical_id, args.duplicate_ids)
    if args.command == "recommend":
        return await tools.recommendations.get_paper_recommendations(
            cached, args.paper_id, limit=args.limit
        )
    if args.command == "related":
        return await tools.recommendations.get_related_papers(
            cached, conn, state.embedder, args.paper_id, k=args.k
        )
    if args.command == "session":
        if args.session_command == "add":
            return await tools.session.add_paper_to_session(
                cached, conn, args.session_id, args.paper_id
            )
        if args.session_command == "list":
            return await tools.session.list_session_papers_tool(conn, args.session_id)
        if args.session_command == "remove":
            return await tools.session.remove_from_session_tool(
                conn, args.session_id, args.paper_id
            )
        raise ValueError(f"unknown session subcommand: {args.session_command}")
    if args.command == "bibtex":
        return await tools.bibtex.export_session_bibtex(conn, args.session_id)
    raise ValueError(f"unknown command: {args.command}")


async def run_command(args: argparse.Namespace) -> int:
    """Run one command: build state, dispatch, print JSON envelope."""
    need_embedder = args.command == "related" or (
        args.command == "paper" and bool(getattr(args, "embed", False))
    )
    state = await build_state(need_embedder)
    try:
        result = await _dispatch(state, args)
    finally:
        try:
            await state.raw_client.close()
        except Exception:
            logger.exception("error closing httpx client")
        state.conn.close()
    print(result.model_dump_json())
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns process exit code."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    try:
        return asyncio.run(run_command(args))
    except ScholarPaperError as e:
        print(json.dumps({"error": {"type": type(e).__name__, "message": str(e)}}))
        return 1
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"error": {"type": "InternalError", "message": str(e)}}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
