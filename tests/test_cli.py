"""Tests for the spm CLI entry point (cli.main + dispatch)."""

import json
import sys
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scholar_paper_cli import cli
from scholar_paper_cli.exceptions import OfflineError
from scholar_paper_cli.models import Author, CacheMetadata, Paper
from scholar_paper_cli.storage.authors import upsert_author as upsert_author_db
from scholar_paper_cli.storage.cache import CachedSemanticScholarClient
from scholar_paper_cli.storage.papers import upsert_paper
from scholar_paper_cli.storage.sessions import add_to_session
from tests.test_papers_tools import SAMPLE_PAPER_DATA

COMMANDS = [
    "search",
    "paper",
    "citations",
    "references",
    "author-search",
    "author",
    "author-top",
    "author-duplicates",
    "consolidate",
    "recommend",
    "related",
    "session",
    "bibtex",
]


def _meta() -> CacheMetadata:
    return CacheMetadata(cached=False, fetched_at=datetime.now(UTC), source="api")


def _make_paper(paper_id: str, **kwargs) -> Paper:
    now = datetime.now(UTC)
    return Paper(
        paper_id=paper_id,
        fetched_at=now,
        ttl_until=now + timedelta(days=30),
        **kwargs,
    )


def _make_client() -> AsyncMock:
    client = AsyncMock(spec=CachedSemanticScholarClient)
    meta = _meta()
    empty = {"data": [], "total": 0, "offset": 0, "next": None}
    client.search_papers.return_value = (
        {"data": [SAMPLE_PAPER_DATA], "total": 1, "offset": 0, "next": None},
        meta,
    )
    client.get_paper.return_value = (SAMPLE_PAPER_DATA, meta)
    client.get_citations.return_value = (
        {"data": [{"citingPaper": {"paperId": "citer1"}, "isInfluential": True}]},
        meta,
    )
    client.get_references.return_value = (
        {"data": [{"citedPaper": {"paperId": "cited1"}, "isInfluential": False}]},
        meta,
    )
    client.search_authors.return_value = (empty, meta)
    client.get_author.return_value = (
        {"authorId": "a1", "name": "Alice", "papers": [], "aliases": []},
        meta,
    )
    client.get_author_papers.return_value = (
        {
            "data": [{"paperId": "p1", "title": "T", "citationCount": 5}],
            "total": 1,
            "offset": 0,
            "next": None,
        },
        meta,
    )
    client.get_recommendations.return_value = ({"recommendedPapers": []}, meta)
    return client


def _install_fake_state(monkeypatch, real_conn, cached=None, embedder=None):
    """Monkeypatch cli.build_state to return a fake state; returns the cached mock."""
    cached = cached or _make_client()

    async def fake_build_state(need_embedder):
        return SimpleNamespace(
            conn=real_conn, raw_client=AsyncMock(), cached=cached, embedder=embedder
        )

    monkeypatch.setattr(cli, "build_state", fake_build_state)
    return cached


# ── meta: version / help / usage ───────────────────────────────


def test_version_flag(capsys) -> None:
    assert cli.main(["--version"]) == 0
    assert "0.1.0" in capsys.readouterr().out


def test_help_lists_all_15_commands(capsys) -> None:
    assert cli.main(["--help"]) == 0
    out = capsys.readouterr().out
    for cmd in COMMANDS:
        assert cmd in out, f"command {cmd} missing from --help"


def test_usage_error_exit_2(capsys) -> None:
    """Missing required positional -> argparse usage error, exit 2."""
    assert cli.main(["search"]) == 2
    assert "usage:" in capsys.readouterr().err


# ── read commands (mock cached client) ─────────────────────────


@pytest.mark.parametrize(
    "argv, method",
    [
        (["search", "quantum"], "search_papers"),
        (["paper", "abc"], "get_paper"),
        (["citations", "abc"], "get_citations"),
        (["references", "abc"], "get_references"),
        (["author-search", "alice"], "search_authors"),
        (["author", "a1"], "get_author"),
        (["author-top", "a1"], "get_author_papers"),
        (["author-duplicates", "alice"], "search_authors"),
        (["recommend", "abc"], "get_recommendations"),
    ],
)
def test_read_commands_emit_json_envelope(monkeypatch, capsys, real_conn, argv, method) -> None:
    cached = _install_fake_state(monkeypatch, real_conn)
    assert cli.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    assert "data" in out
    assert "meta" in out
    getattr(cached, method).assert_awaited()


def test_paper_embed_flag_requests_embedder(monkeypatch, capsys, real_conn) -> None:
    seen: list[bool] = []
    cached = _make_client()

    async def fake_build_state(need_embedder):
        seen.append(need_embedder)
        return SimpleNamespace(conn=real_conn, raw_client=AsyncMock(), cached=cached, embedder=None)

    monkeypatch.setattr(cli, "build_state", fake_build_state)
    assert cli.main(["paper", "abc", "--embed"]) == 0
    assert seen == [True]
    out = json.loads(capsys.readouterr().out)
    assert out["data"]["paper_id"] == "abc"


# ── related: deterministic degradation (embedder None) ─────────


def test_related_without_embedder_errors_json(monkeypatch, capsys, real_conn) -> None:
    _install_fake_state(monkeypatch, real_conn, embedder=None)
    assert cli.main(["related", "abc"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["error"]["type"] == "EmbeddingError"


# ── session / consolidate / bibtex (real conn, rows first) ─────


def test_session_add_command(monkeypatch, capsys, real_conn) -> None:
    _install_fake_state(monkeypatch, real_conn)
    assert cli.main(["session", "add", "s1", "abc"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["data"]["paper_id"] == "abc"


def test_session_list_command(monkeypatch, capsys, real_conn) -> None:
    upsert_paper(real_conn, _make_paper("p1", title="First"))
    add_to_session(real_conn, "s1", "p1")
    _install_fake_state(monkeypatch, real_conn)
    assert cli.main(["session", "list", "s1"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [p["paper_id"] for p in out["data"]] == ["p1"]


def test_session_remove_command(monkeypatch, capsys, real_conn) -> None:
    upsert_paper(real_conn, _make_paper("p1"))
    add_to_session(real_conn, "s1", "p1")
    _install_fake_state(monkeypatch, real_conn)
    assert cli.main(["session", "remove", "s1", "p1"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["data"] is True


def test_consolidate_command(monkeypatch, capsys, real_conn) -> None:
    now = datetime.now(UTC)
    upsert_author_db(
        real_conn,
        Author(
            author_id="canon",
            name="Alice",
            papers=[],
            aliases=[],
            fetched_at=now,
            ttl_until=now + timedelta(days=30),
        ),
    )
    upsert_author_db(
        real_conn,
        Author(
            author_id="dup",
            name="Alice Dup",
            papers=[],
            aliases=[],
            fetched_at=now,
            ttl_until=now + timedelta(days=30),
        ),
    )
    _install_fake_state(monkeypatch, real_conn)
    assert cli.main(["consolidate", "canon", "dup"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["data"]["author_id"] == "canon"


def test_bibtex_command(monkeypatch, capsys, real_conn) -> None:
    upsert_paper(real_conn, _make_paper("p1", title="First"))
    add_to_session(real_conn, "s1", "p1")
    _install_fake_state(monkeypatch, real_conn)
    assert cli.main(["bibtex", "s1"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert "@article{" in out["data"]


# ── error contract ─────────────────────────────────────────────


def test_error_contract_offline(monkeypatch, capsys, real_conn) -> None:
    cached = _make_client()
    cached.search_papers.side_effect = OfflineError("offline and no cache")
    _install_fake_state(monkeypatch, real_conn, cached=cached)
    assert cli.main(["search", "quantum"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["error"]["type"] == "OfflineError"
    assert "offline" in out["error"]["message"]


def test_error_contract_internal(monkeypatch, capsys, real_conn) -> None:
    cached = _make_client()
    cached.search_papers.side_effect = RuntimeError("boom")
    _install_fake_state(monkeypatch, real_conn, cached=cached)
    assert cli.main(["search", "quantum"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["error"]["type"] == "InternalError"
    assert out["error"]["message"] == "boom"


# ── lazy-import regression guard ───────────────────────────────


def test_lazy_embedding_import() -> None:
    """Importing cli must not pull the heavy ONNX stack (onnxruntime, tokenizers).

    numpy is imported by sqlite_vec at import time regardless; it is cheap.
    """
    for heavy in ("onnxruntime", "tokenizers"):
        assert heavy not in sys.modules, f"{heavy} imported eagerly"
