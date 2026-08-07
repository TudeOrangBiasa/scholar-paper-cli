"""Tests for storage.authors CRUD."""

from datetime import timedelta

from scholar_paper_cli.models import Author, PaperBrief
from scholar_paper_cli.storage.authors import (
    count_authors,
    get_author,
    list_authors,
    search_authors_by_name,
    upsert_author,
)


def test_upsert_get_roundtrip_all_fields(conn, now) -> None:
    author = Author(
        author_id="a1",
        name="Dr. Alice Smith",
        affiliations=["MIT", "Stanford"],
        h_index=42,
        paper_count=100,
        aliases=["A. Smith", "Alice S."],
        papers=[PaperBrief(paper_id="p1", title="Quantum Paper", year=2024)],
        fetched_at=now,
        ttl_until=now + timedelta(days=30),
    )
    upsert_author(conn, author)
    result = get_author(conn, "a1")
    assert result is not None
    assert result.name == "Dr. Alice Smith"
    assert result.affiliations == ["MIT", "Stanford"]
    assert result.h_index == 42
    assert result.paper_count == 100
    assert result.aliases == ["A. Smith", "Alice S."]
    assert len(result.papers) == 1
    assert result.papers[0].paper_id == "p1"
    assert result.fetched_at == now
    assert result.ttl_until == now + timedelta(days=30)


def test_get_author_returns_none_for_missing(conn) -> None:
    assert get_author(conn, "nonexistent") is None


def test_search_authors_by_name_case_insensitive(conn, now) -> None:
    upsert_author(conn, Author(author_id="a1", name="Alice Smith", fetched_at=now, ttl_until=now))
    upsert_author(conn, Author(author_id="a2", name="Bob Jones", fetched_at=now, ttl_until=now))
    upsert_author(conn, Author(author_id="a3", name="ALICE JOHNSON", fetched_at=now, ttl_until=now))
    results = search_authors_by_name(conn, "alice")
    assert len(results) == 2
    ids = {r.author_id for r in results}
    assert ids == {"a1", "a3"}


def test_search_authors_by_name_limit(conn, now) -> None:
    for i in range(5):
        upsert_author(
            conn,
            Author(author_id=f"a{i}", name=f"Test Author {i}", fetched_at=now, ttl_until=now),
        )
    results = search_authors_by_name(conn, "Test", limit=2)
    assert len(results) == 2


def test_count_authors(conn, now) -> None:
    assert count_authors(conn) == 0
    upsert_author(conn, Author(author_id="a1", name="Alice", fetched_at=now, ttl_until=now))
    upsert_author(conn, Author(author_id="a2", name="Bob", fetched_at=now, ttl_until=now))
    assert count_authors(conn) == 2


def test_list_authors_paginates(conn, now) -> None:
    for i in range(5):
        upsert_author(
            conn,
            Author(author_id=f"a{i:03d}", name=f"Author {i}", fetched_at=now, ttl_until=now),
        )
    page1 = list_authors(conn, limit=2, offset=0)
    assert len(page1) == 2
    assert page1[0].author_id == "a000"
    page2 = list_authors(conn, limit=2, offset=2)
    assert len(page2) == 2
    assert page2[0].author_id == "a002"


def test_upsert_author_updates_existing(conn, now) -> None:
    upsert_author(conn, Author(author_id="a1", name="Old Name", fetched_at=now, ttl_until=now))
    upsert_author(conn, Author(author_id="a1", name="New Name", fetched_at=now, ttl_until=now))
    result = get_author(conn, "a1")
    assert result is not None
    assert result.name == "New Name"
