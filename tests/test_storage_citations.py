"""Tests for storage.citations CRUD."""

from scholar_paper_mcp.models import CitationEdge, Paper
from scholar_paper_mcp.storage.citations import (
    delete_citations_for_paper,
    get_citations_of,
    get_references_of,
    insert_citation,
    insert_reference,
)
from scholar_paper_mcp.storage.papers import upsert_paper


def _seed_paper(conn, paper_id: str, now) -> None:
    upsert_paper(conn, Paper(paper_id=paper_id, fetched_at=now, ttl_until=now))


def test_insert_citation_and_get_citations_of(conn, now) -> None:
    _seed_paper(conn, "p1", now)
    _seed_paper(conn, "p2", now)
    edge = CitationEdge(from_paper_id="p1", to_paper_id="p2", is_influential=True)
    insert_citation(conn, edge)
    results = get_citations_of(conn, "p2")
    assert len(results) == 1
    assert results[0].from_paper_id == "p1"
    assert results[0].to_paper_id == "p2"
    assert results[0].is_influential is True


def test_insert_reference_and_get_references_of(conn, now) -> None:
    _seed_paper(conn, "p1", now)
    _seed_paper(conn, "p2", now)
    edge = CitationEdge(from_paper_id="p1", to_paper_id="p2", is_influential=True)
    insert_reference(conn, edge)
    results = get_references_of(conn, "p1")
    assert len(results) == 1
    assert results[0].from_paper_id == "p1"
    assert results[0].to_paper_id == "p2"


def test_get_citations_of_empty(conn) -> None:
    assert get_citations_of(conn, "nonexistent") == []


def test_get_references_of_empty(conn) -> None:
    assert get_references_of(conn, "nonexistent") == []


def test_delete_citations_for_paper_removes_both(conn, now) -> None:
    _seed_paper(conn, "p1", now)
    _seed_paper(conn, "p2", now)
    _seed_paper(conn, "p3", now)
    insert_citation(conn, CitationEdge(from_paper_id="p1", to_paper_id="p2"))
    insert_citation(conn, CitationEdge(from_paper_id="p3", to_paper_id="p2"))
    insert_reference(conn, CitationEdge(from_paper_id="p1", to_paper_id="p2"))
    delete_citations_for_paper(conn, "p1")
    assert get_citations_of(conn, "p2") != []
    assert get_citations_of(conn, "p1") == []
    assert get_references_of(conn, "p1") == []


def test_upsert_citation_updates_context_intent(conn, now) -> None:
    _seed_paper(conn, "p1", now)
    _seed_paper(conn, "p2", now)
    edge = CitationEdge(from_paper_id="p1", to_paper_id="p2", context_intent=["background"])
    insert_citation(conn, edge)
    edge2 = CitationEdge(
        from_paper_id="p1",
        to_paper_id="p2",
        context_intent=["method", "result"],
        is_influential=True,
    )
    insert_citation(conn, edge2)
    results = get_citations_of(conn, "p2")
    assert len(results) == 1
    assert results[0].context_intent == ["method", "result"]
    assert results[0].is_influential is True


def test_citation_with_context_intent_roundtrip(conn, now) -> None:
    _seed_paper(conn, "p1", now)
    _seed_paper(conn, "p2", now)
    edge = CitationEdge(
        from_paper_id="p1",
        to_paper_id="p2",
        context_intent=["background", "method"],
        is_influential=True,
    )
    insert_citation(conn, edge)
    results = get_citations_of(conn, "p2")
    assert len(results) == 1
    assert results[0].context_intent == ["background", "method"]
    assert results[0].is_influential is True


def test_reference_drops_context_intent(conn, now) -> None:
    _seed_paper(conn, "p1", now)
    _seed_paper(conn, "p2", now)
    edge = CitationEdge(
        from_paper_id="p1",
        to_paper_id="p2",
        context_intent=["background"],
        is_influential=True,
    )
    insert_reference(conn, edge)
    results = get_references_of(conn, "p1")
    assert len(results) == 1
    assert results[0].context_intent is None
    assert results[0].is_influential is True



def test_insert_citation_creates_stub_papers(conn, now) -> None:
    """Citation edge should auto-create stub papers for both endpoints."""
    edge = CitationEdge(from_paper_id="unknown1", to_paper_id="unknown2", is_influential=True)
    insert_citation(conn, edge)
    # FK no longer fails
    row = conn.execute("SELECT paper_id FROM papers WHERE paper_id = ?", ("unknown1",)).fetchone()
    assert row is not None
    row2 = conn.execute("SELECT paper_id FROM papers WHERE paper_id = ?", ("unknown2",)).fetchone()
    assert row2 is not None


def test_insert_reference_creates_stub_papers(conn, now) -> None:
    """Reference edge should auto-create stub papers for both endpoints."""
    edge = CitationEdge(from_paper_id="ref_src", to_paper_id="ref_dst", is_influential=False)
    insert_reference(conn, edge)
    row = conn.execute("SELECT paper_id FROM papers WHERE paper_id = ?", ("ref_src",)).fetchone()
    assert row is not None
    row2 = conn.execute("SELECT paper_id FROM papers WHERE paper_id = ?", ("ref_dst",)).fetchone()
    assert row2 is not None
