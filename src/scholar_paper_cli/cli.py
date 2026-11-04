"""spm CLI: 15 subcommands mirroring the MCP tool set, JSON output on stdout.

Commands are declared as data in COMMANDS: argument defaults live once (on the
tool function or in Settings), dependency needs drive build_state, and dispatch
is a table lookup instead of an if-chain.
"""

import argparse
import asyncio
import inspect
import json
import logging
import sys
import traceback
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from scholar_paper_cli import __version__, tools
from scholar_paper_cli.api.client import SemanticScholarClient
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


_MISSING = object()

ArgKind = Literal["pos", "pos_many", "int", "float", "bool", "str", "append"]


@dataclass(frozen=True)
class ArgSpec:
    """One command argument.

    kind: pos | pos_many | int | float | bool | str | append.
    default precedence: settings attr > explicit default > tool signature.
    """

    dest: str
    kind: ArgKind = "pos"
    help: str = ""
    settings: str | None = None
    default: Any = _MISSING


@dataclass(frozen=True)
class CommandSpec:
    """One CLI command: declared needs, argument spec, and its handler.

    func is the underlying tool (for signature-derived defaults).
    needs is a subset of ("client", "conn", "embedder"); embedder_if names a
    flag dest that additionally requires the embedder when set.
    call is the handler for leaf commands; the session parent has none (its
    subcommands route via _SESSION_BY_NAME).
    """

    name: str
    help: str
    call: Callable[[CLIState, argparse.Namespace], Awaitable[ToolResponse[Any]]] | None = None
    func: Callable[..., Any] | None = None
    needs: tuple[str, ...] = ()
    embedder_if: str | None = None
    args: tuple[ArgSpec, ...] = ()
    session: tuple["CommandSpec", ...] = ()


def _arg_default(spec: CommandSpec, arg: ArgSpec, settings) -> Any:
    if arg.settings:
        return getattr(settings, arg.settings)
    if arg.default is not _MISSING:
        return arg.default
    if spec.func is not None:
        return inspect.signature(spec.func).parameters[arg.dest].default
    return None


def _add_args(parser: argparse.ArgumentParser, spec: CommandSpec, settings) -> None:
    for a in spec.args:
        if a.kind == "pos":
            parser.add_argument(a.dest, help=a.help)
        elif a.kind == "pos_many":
            parser.add_argument(a.dest, nargs="+", help=a.help)
        else:
            flag = f"--{a.dest.replace('_', '-')}"
            if a.kind == "bool":
                parser.add_argument(flag, action="store_true", help=a.help)
            else:
                default = _arg_default(spec, a, settings)
                if a.kind == "append":
                    parser.add_argument(flag, action="append", default=default, help=a.help)
                elif a.kind == "int":
                    parser.add_argument(flag, type=int, default=default, help=a.help)
                elif a.kind == "float":
                    parser.add_argument(flag, type=float, default=default, help=a.help)
                else:
                    parser.add_argument(flag, default=default, help=a.help)


COMMANDS: dict[str, CommandSpec] = {
    spec.name: spec
    for spec in (
        CommandSpec(
            "search",
            "search papers by query",
            func=tools.papers.search_papers,
            needs=("client",),
            args=(
                ArgSpec("query"),
                ArgSpec("limit", "int", "max results", settings="default_search_limit"),
                ArgSpec("offset", "int", "pagination offset"),
                ArgSpec("fields", "str", "comma-separated paper fields to fetch"),
            ),
            call=lambda s, a: tools.papers.search_papers(
                s.cached, a.query, limit=a.limit, offset=a.offset, fields=a.fields
            ),
        ),
        CommandSpec(
            "paper",
            "get paper details by ID",
            func=tools.papers.get_paper_details,
            needs=("client", "conn"),
            embedder_if="embed",
            args=(
                ArgSpec("paper_id"),
                ArgSpec("embed", "bool", "persist a semantic embedding of the abstract"),
                ArgSpec("fields", "str", "comma-separated paper fields to fetch"),
            ),
            call=lambda s, a: tools.papers.get_paper_details(
                s.cached,
                s.conn,
                s.embedder if a.embed else None,
                a.paper_id,
                fields=a.fields,
            ),
        ),
        CommandSpec(
            "citations",
            "list papers that cite a paper",
            func=tools.papers.get_paper_citations,
            needs=("client", "conn"),
            args=(
                ArgSpec("paper_id"),
                ArgSpec("limit", "int", "max results", settings="default_citations_limit"),
                ArgSpec("offset", "int", "pagination offset"),
                ArgSpec("fields", "str", "comma-separated paper fields to fetch"),
            ),
            call=lambda s, a: tools.papers.get_paper_citations(
                s.cached, s.conn, a.paper_id, limit=a.limit, offset=a.offset, fields=a.fields
            ),
        ),
        CommandSpec(
            "references",
            "list papers referenced by a paper",
            func=tools.papers.get_paper_references,
            needs=("client", "conn"),
            args=(
                ArgSpec("paper_id"),
                ArgSpec("limit", "int", "max results", settings="default_citations_limit"),
                ArgSpec("offset", "int", "pagination offset"),
                ArgSpec("fields", "str", "comma-separated paper fields to fetch"),
            ),
            call=lambda s, a: tools.papers.get_paper_references(
                s.cached, s.conn, a.paper_id, limit=a.limit, offset=a.offset, fields=a.fields
            ),
        ),
        CommandSpec(
            "author-search",
            "search authors by name",
            func=tools.authors.search_authors,
            needs=("client",),
            args=(
                ArgSpec("query"),
                ArgSpec("limit", "int", "max results", settings="default_search_limit"),
                ArgSpec("offset", "int", "pagination offset"),
                ArgSpec("fields", "str", "comma-separated author fields to fetch"),
            ),
            call=lambda s, a: tools.authors.search_authors(
                s.cached, a.query, limit=a.limit, offset=a.offset, fields=a.fields
            ),
        ),
        CommandSpec(
            "author",
            "get author details by ID",
            func=tools.authors.get_author_details,
            needs=("client", "conn"),
            args=(
                ArgSpec("author_id"),
                ArgSpec("fields", "str", "comma-separated author fields to fetch"),
            ),
            call=lambda s, a: tools.authors.get_author_details(
                s.cached, s.conn, a.author_id, fields=a.fields
            ),
        ),
        CommandSpec(
            "author-top",
            "list an author's most-cited papers",
            func=tools.authors.get_author_top_papers,
            needs=("client",),
            args=(
                ArgSpec("author_id"),
                ArgSpec("limit", "int", "max results", settings="default_papers_limit"),
                ArgSpec("fields", "str", "comma-separated paper fields to fetch"),
            ),
            call=lambda s, a: tools.authors.get_author_top_papers(
                s.cached, a.author_id, limit=a.limit, fields=a.fields
            ),
        ),
        CommandSpec(
            "author-duplicates",
            "group authors by name similarity",
            func=tools.authors.find_author_duplicates,
            needs=("client",),
            args=(
                ArgSpec("query"),
                ArgSpec("limit", "int", "max authors to compare"),
                ArgSpec("threshold", "float", "similarity threshold 0..1"),
            ),
            call=lambda s, a: tools.authors.find_author_duplicates(
                s.cached, a.query, limit=a.limit, threshold=a.threshold
            ),
        ),
        CommandSpec(
            "consolidate",
            "merge duplicate authors into a canonical author",
            func=tools.authors.consolidate_authors,
            needs=("conn",),
            args=(
                ArgSpec("canonical_id"),
                ArgSpec("duplicate_ids", "pos_many", "author ids to merge into canonical"),
            ),
            call=lambda s, a: tools.authors.consolidate_authors(
                s.conn, a.canonical_id, a.duplicate_ids
            ),
        ),
        CommandSpec(
            "recommend",
            "get Semantic Scholar recommendations for a paper",
            func=tools.recommendations.get_paper_recommendations,
            needs=("client",),
            args=(
                ArgSpec("paper_id"),
                ArgSpec("limit", "int", "max results"),
                ArgSpec("fields", "str", "comma-separated paper fields to fetch"),
                ArgSpec("positive_ids", "append", "paper ids to bias toward"),
                ArgSpec("negative_ids", "append", "paper ids to bias against"),
            ),
            call=lambda s, a: tools.recommendations.get_paper_recommendations(
                s.cached,
                a.paper_id,
                limit=a.limit,
                fields=a.fields,
                positive_ids=a.positive_ids,
                negative_ids=a.negative_ids,
            ),
        ),
        CommandSpec(
            "related",
            "find related papers via local semantic embeddings",
            func=tools.recommendations.get_related_papers,
            needs=("client", "conn", "embedder"),
            args=(
                ArgSpec("paper_id"),
                ArgSpec("k", "int", "number of related papers"),
            ),
            call=lambda s, a: tools.recommendations.get_related_papers(
                s.cached, s.conn, s.embedder, a.paper_id, k=a.k
            ),
        ),
        CommandSpec(
            "session",
            "manage a working session of papers",
            session=(
                CommandSpec(
                    "add",
                    "add a paper to a session",
                    func=tools.session.add_paper_to_session,
                    needs=("client", "conn"),
                    args=(
                        ArgSpec("session_id"),
                        ArgSpec("paper_id"),
                        ArgSpec("fields", "str", "comma-separated paper fields to fetch"),
                    ),
                    call=lambda s, a: tools.session.add_paper_to_session(
                        s.cached, s.conn, a.session_id, a.paper_id, fields=a.fields
                    ),
                ),
                CommandSpec(
                    "list",
                    "list papers in a session",
                    func=tools.session.list_session_papers,
                    needs=("conn",),
                    args=(ArgSpec("session_id"),),
                    call=lambda s, a: tools.session.list_session_papers(s.conn, a.session_id),
                ),
                CommandSpec(
                    "remove",
                    "remove a paper from a session",
                    func=tools.session.remove_from_session,
                    needs=("conn",),
                    args=(
                        ArgSpec("session_id"),
                        ArgSpec("paper_id"),
                    ),
                    call=lambda s, a: tools.session.remove_from_session(
                        s.conn, a.session_id, a.paper_id
                    ),
                ),
            ),
        ),
        CommandSpec(
            "bibtex",
            "export session papers as BibTeX",
            func=tools.bibtex.export_session_bibtex,
            needs=("conn",),
            args=(ArgSpec("session_id"),),
            call=lambda s, a: tools.bibtex.export_session_bibtex(s.conn, a.session_id),
        ),
    )
}

_SESSION_BY_NAME: dict[str, CommandSpec] = {sub.name: sub for sub in COMMANDS["session"].session}


def build_parser() -> argparse.ArgumentParser:
    """Build the spm argument parser from the command descriptors."""
    settings = get_settings()
    parser = argparse.ArgumentParser(
        prog="spm",
        description="spm: CLI for Semantic Scholar with persistent cache and offline fallback",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)
    for spec in COMMANDS.values():
        if spec.session:
            p = sub.add_parser(spec.name, help=spec.help)
            ssub = p.add_subparsers(dest="session_command", metavar="SUBCOMMAND", required=True)
            for s in spec.session:
                sp = ssub.add_parser(s.name, help=s.help)
                _add_args(sp, s, settings)
        else:
            p = sub.add_parser(spec.name, help=spec.help)
            _add_args(p, spec, settings)
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
        cached = CachedSemanticScholarClient(raw_client, conn, force_offline=settings.offline_mode)
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
    spec = COMMANDS.get(args.command)
    if spec is None:
        raise ValueError(f"unknown command: {args.command}")
    if spec.session:
        sub = _SESSION_BY_NAME.get(args.session_command)
        if sub is None:
            raise ValueError(f"unknown session subcommand: {args.session_command}")
        if sub.call is None:
            raise ValueError(f"session subcommand has no handler: {args.session_command}")
        return await sub.call(state, args)
    if spec.call is None:
        raise ValueError(f"command has no handler: {args.command}")
    return await spec.call(state, args)


def _need_embedder(spec: CommandSpec, args: argparse.Namespace) -> bool:
    if "embedder" in spec.needs:
        return True
    return spec.embedder_if is not None and bool(getattr(args, spec.embedder_if, False))


async def run_command(args: argparse.Namespace) -> int:
    """Run one command: build state, dispatch, print JSON envelope."""
    spec = COMMANDS[args.command]
    if spec.session:
        spec = _SESSION_BY_NAME[args.session_command]
    state = await build_state(_need_embedder(spec, args))
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
