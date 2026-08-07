"""Tests for storage.sessions CRUD."""

from scholar_paper_cli.models import Paper
from scholar_paper_cli.storage.papers import upsert_paper
from scholar_paper_cli.storage.sessions import (
    add_to_session,
    clear_session,
    list_session_papers,
    remove_from_session,
)


def _seed_paper(conn, paper_id: str, now) -> None:
    upsert_paper(conn, Paper(paper_id=paper_id, fetched_at=now, ttl_until=now))


def test_add_to_session_idempotent(conn, now) -> None:
    _seed_paper(conn, "p1", now)
    add_to_session(conn, "s1", "p1")
    add_to_session(conn, "s1", "p1")
    papers = list_session_papers(conn, "s1")
    assert papers == ["p1"]


def test_list_session_papers_oldest_first(conn, now) -> None:
    _seed_paper(conn, "p1", now)
    _seed_paper(conn, "p2", now)
    _seed_paper(conn, "p3", now)
    add_to_session(conn, "s1", "p3")
    add_to_session(conn, "s1", "p1")
    add_to_session(conn, "s1", "p2")
    papers = list_session_papers(conn, "s1")
    assert papers == ["p3", "p1", "p2"]


def test_remove_from_session_removes(conn, now) -> None:
    _seed_paper(conn, "p1", now)
    _seed_paper(conn, "p2", now)
    add_to_session(conn, "s1", "p1")
    add_to_session(conn, "s1", "p2")
    remove_from_session(conn, "s1", "p1")
    papers = list_session_papers(conn, "s1")
    assert papers == ["p2"]


def test_clear_session_empties(conn, now) -> None:
    _seed_paper(conn, "p1", now)
    _seed_paper(conn, "p2", now)
    add_to_session(conn, "s1", "p1")
    add_to_session(conn, "s1", "p2")
    clear_session(conn, "s1")
    assert list_session_papers(conn, "s1") == []
