"""Tests for session + BibTeX tools."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from scholar_paper_cli.models import AuthorBrief, CacheMetadata, Paper
from scholar_paper_cli.storage.cache import CachedSemanticScholarClient
from scholar_paper_cli.storage.db import apply_migrations, connect
from scholar_paper_cli.storage.papers import upsert_paper
from scholar_paper_cli.storage.sessions import add_to_session
from scholar_paper_cli.tools.bibtex import (
    export_bibtex,
    export_session_bibtex,
    format_bibtex_entry,
)
from scholar_paper_cli.tools.session import (
    add_paper_to_session,
    list_session_papers,
    remove_from_session,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = connect(tmp_path / "test.db")
    apply_migrations(c)
    return c


def _make_paper(paper_id: str, **kwargs: Any) -> Paper:
    now = datetime.now(UTC)
    data: dict[str, Any] = {
        "paper_id": paper_id,
        "title": f"Title {paper_id}",
        "abstract": "abstract",
        "year": 2024,
        "fetched_at": now,
        "ttl_until": now + timedelta(days=30),
    }
    data.update(kwargs)
    return Paper.model_validate(data)


# ── add_paper_to_session ───────────────────────────────────


@pytest.mark.asyncio
async def test_add_paper_uses_existing_in_db(conn) -> None:
    upsert_paper(conn, _make_paper("p1"))
    client = AsyncMock(spec=CachedSemanticScholarClient)
    result = await add_paper_to_session(client, conn, "s1", "p1")
    assert result.data.paper_id == "p1"
    client.get_paper.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_paper_fetches_from_api_when_not_in_db(conn) -> None:
    client = AsyncMock(spec=CachedSemanticScholarClient)
    client.get_paper.return_value = (
        {"paperId": "new", "title": "New"},
        CacheMetadata(cached=False, fetched_at=datetime.now(UTC), source="api"),
    )
    result = await add_paper_to_session(client, conn, "s1", "new")
    assert result.data.paper_id == "new"
    client.get_paper.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_paper_links_to_session(conn) -> None:
    from scholar_paper_cli.storage.sessions import list_session_papers

    upsert_paper(conn, _make_paper("p1"))
    client = AsyncMock(spec=CachedSemanticScholarClient)
    await add_paper_to_session(client, conn, "s1", "p1")
    assert "p1" in list_session_papers(conn, "s1")


# ── remove_from_session_tool ─────────────────────────────


@pytest.mark.asyncio
async def test_remove_paper_from_session(conn) -> None:
    upsert_paper(conn, _make_paper("p1"))
    add_to_session(conn, "s1", "p1")
    result = await remove_from_session(conn, "s1", "p1")
    assert result.data is True
    from scholar_paper_cli.storage.sessions import list_session_papers

    assert list_session_papers(conn, "s1") == []


@pytest.mark.asyncio
async def test_remove_paper_not_in_session_returns_true(conn) -> None:
    result = await remove_from_session(conn, "s1", "missing")
    assert result.data is True


# ── list_session_papers_tool ─────────────────────────────


@pytest.mark.asyncio
async def test_list_session_returns_full_papers(conn) -> None:
    upsert_paper(conn, _make_paper("p1"))
    upsert_paper(conn, _make_paper("p2"))
    add_to_session(conn, "s1", "p1")
    add_to_session(conn, "s1", "p2")
    result = await list_session_papers(conn, "s1")
    assert len(result.data) == 2
    assert {p.paper_id for p in result.data} == {"p1", "p2"}


@pytest.mark.asyncio
async def test_list_session_empty(conn) -> None:
    result = await list_session_papers(conn, "nonexistent")
    assert result.data == []


@pytest.mark.asyncio
async def test_list_session_skips_missing_papers(conn) -> None:
    """If session paper_id has been deleted from DB, skip it (don't crash)."""
    from scholar_paper_cli.storage.papers import delete_paper

    upsert_paper(conn, _make_paper("p1"))
    add_to_session(conn, "s1", "p1")
    delete_paper(conn, "p1")
    result = await list_session_papers(conn, "s1")
    assert result.data == []


# ── format_bibtex_entry / export_bibtex ──────────────────


def test_format_bibtex_entry_escapes_braces() -> None:
    paper = _make_paper("p1", title="A {Study} of Braces")
    bib = format_bibtex_entry(paper)
    assert "A \\{Study\\} of Braces" in bib


def test_format_bibtex_entry_basic() -> None:
    paper = _make_paper(
        "abc",
        title="My Paper",
        year=2024,
        venue="Nature",
        authors=[AuthorBrief(author_id="a1", name="Alice")],
    )
    bib = format_bibtex_entry(paper)
    assert bib.startswith("@article{abc,")
    assert "title = {My Paper}" in bib
    assert "year = {2024}" in bib
    assert "journal = {Nature}" in bib
    assert "author = {Alice}" in bib


def test_format_bibtex_entry_includes_doi_and_arxiv() -> None:
    paper = _make_paper(
        "abc",
        external_ids={
            "DOI": "10.1234/abc",
            "ArXiv": "2401.12345",
        },
    )
    bib = format_bibtex_entry(paper)
    assert "doi = {10.1234/abc}" in bib
    assert "eprint = {2401.12345}" in bib
    assert "archiveprefix = {arXiv}" in bib


def test_format_bibtex_entry_sanitizes_cite_key() -> None:
    paper = _make_paper("DOI:10.1234/abc.v1")
    bib = format_bibtex_entry(paper)
    assert "@article{DOI_10_1234_abc_v1," in bib


def test_format_bibtex_entry_handles_missing_fields() -> None:
    paper = _make_paper("p1")  # no title, no authors, no year
    bib = format_bibtex_entry(paper)
    assert bib.startswith("@article{p1,")


def test_format_bibtex_entry_multiple_authors_joined_with_and() -> None:
    paper = _make_paper(
        "p1",
        authors=[
            AuthorBrief(author_id="a1", name="Alice"),
            AuthorBrief(author_id="a2", name="Bob"),
        ],
    )
    bib = format_bibtex_entry(paper)
    assert "author = {Alice and Bob}" in bib


def test_export_bibtex_concatenates_entries() -> None:
    papers = [_make_paper("p1"), _make_paper("p2")]
    bib = export_bibtex(papers)
    assert bib.count("@article{") == 2


# ── export_session_bibtex ──────────────────────────────


@pytest.mark.asyncio
async def test_export_session_bibtex_uses_session_papers(conn) -> None:
    upsert_paper(conn, _make_paper("p1", title="First"))
    upsert_paper(conn, _make_paper("p2", title="Second"))
    add_to_session(conn, "s1", "p1")
    add_to_session(conn, "s1", "p2")
    result = await export_session_bibtex(conn, "s1")
    assert "First" in result.data
    assert "Second" in result.data
    assert result.data.count("@article{") == 2


@pytest.mark.asyncio
async def test_export_session_bibtex_empty_session(conn) -> None:
    result = await export_session_bibtex(conn, "empty")
    assert result.data == ""
