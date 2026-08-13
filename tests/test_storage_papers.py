"""Tests for storage.papers CRUD."""

from datetime import timedelta

import pytest
from pydantic import HttpUrl

from scholar_paper_cli.models import AuthorBrief, Paper
from scholar_paper_cli.storage.db import apply_migrations, connect
from scholar_paper_cli.storage.papers import (
    count_papers,
    delete_paper,
    get_paper,
    get_paper_by_arxiv,
    get_paper_by_doi,
    list_papers,
    upsert_paper,
)


def test_upsert_get_roundtrip_with_all_fields(conn, now) -> None:
    paper = Paper(
        paper_id="p1",
        title="Quantum Entanglement",
        abstract="About qubits",
        year=2024,
        venue="Nature Physics",
        publication_types=["JournalArticle"],
        fields_of_study=["Physics"],
        citation_count=100,
        reference_count=50,
        influential_citation_count=30,
        is_open_access=True,
        open_access_pdf_url=HttpUrl("https://example.com/paper.pdf"),
        external_ids={"DOI": "10.1234/abc", "ArXiv": "2401.12345"},
        authors=[AuthorBrief(author_id="a1", name="Alice")],
        embedding=[0.1 * i for i in range(384)],
        raw={"source": "api"},
        fetched_at=now,
        ttl_until=now + timedelta(days=30),
    )
    upsert_paper(conn, paper)
    result = get_paper(conn, "p1")
    assert result is not None
    assert result.title == "Quantum Entanglement"
    assert result.abstract == "About qubits"
    assert result.year == 2024
    assert result.venue == "Nature Physics"
    assert result.publication_types == ["JournalArticle"]
    assert result.fields_of_study == ["Physics"]
    assert result.citation_count == 100
    assert result.reference_count == 50
    assert result.influential_citation_count == 30
    assert result.is_open_access is True
    assert result.external_ids == {"DOI": "10.1234/abc", "ArXiv": "2401.12345"}
    assert len(result.authors) == 1
    assert result.authors[0].author_id == "a1"
    assert result.embedding == pytest.approx([0.1 * i for i in range(384)])
    assert result.raw == {"source": "api"}
    assert result.fetched_at == now
    assert result.ttl_until == now + timedelta(days=30)


def test_upsert_updates_existing(conn, now) -> None:
    upsert_paper(conn, Paper(paper_id="p1", title="Old", fetched_at=now, ttl_until=now))
    upsert_paper(conn, Paper(paper_id="p1", title="New", fetched_at=now, ttl_until=now))
    result = get_paper(conn, "p1")
    assert result is not None
    assert result.title == "New"


def test_get_paper_returns_none_for_missing(conn) -> None:
    assert get_paper(conn, "nonexistent") is None


def test_get_paper_by_doi_finds(conn, now) -> None:
    upsert_paper(
        conn,
        Paper(
            paper_id="p1",
            external_ids={"DOI": "10.1234/abc"},
            fetched_at=now,
            ttl_until=now,
        ),
    )
    result = get_paper_by_doi(conn, "10.1234/abc")
    assert result is not None
    assert result.paper_id == "p1"


def test_get_paper_by_doi_returns_none(conn) -> None:
    assert get_paper_by_doi(conn, "10.nonexistent") is None


def test_get_paper_by_arxiv_finds(conn, now) -> None:
    upsert_paper(
        conn,
        Paper(
            paper_id="p1",
            external_ids={"ArXiv": "2401.12345"},
            fetched_at=now,
            ttl_until=now,
        ),
    )
    result = get_paper_by_arxiv(conn, "2401.12345")
    assert result is not None
    assert result.paper_id == "p1"


def test_delete_paper_removes(conn, now) -> None:
    upsert_paper(conn, Paper(paper_id="p1", fetched_at=now, ttl_until=now))
    delete_paper(conn, "p1")
    assert get_paper(conn, "p1") is None


def test_list_papers_paginates(conn, now) -> None:
    for i in range(10):
        upsert_paper(
            conn,
            Paper(
                paper_id=f"p{i:03d}",
                title=f"Paper {i}",
                fetched_at=now,
                ttl_until=now,
            ),
        )
    page1 = list_papers(conn, limit=3, offset=0)
    assert len(page1) == 3
    assert page1[0].paper_id == "p000"
    page2 = list_papers(conn, limit=3, offset=3)
    assert len(page2) == 3
    assert page2[0].paper_id == "p003"


def test_list_papers_empty(conn) -> None:
    assert list_papers(conn) == []


def test_count_papers(conn, now) -> None:
    assert count_papers(conn) == 0
    upsert_paper(conn, Paper(paper_id="p1", fetched_at=now, ttl_until=now))
    upsert_paper(conn, Paper(paper_id="p2", fetched_at=now, ttl_until=now))
    assert count_papers(conn) == 2


def test_open_access_pdf_url_roundtrip(conn, now) -> None:
    url = HttpUrl("https://example.com/open.pdf")
    upsert_paper(
        conn,
        Paper(paper_id="p1", open_access_pdf_url=url, fetched_at=now, ttl_until=now),
    )
    result = get_paper(conn, "p1")
    assert result is not None
    assert str(result.open_access_pdf_url) == "https://example.com/open.pdf"


def test_embedding_none_roundtrip(conn, now) -> None:
    upsert_paper(
        conn,
        Paper(paper_id="p1", embedding=None, fetched_at=now, ttl_until=now),
    )
    result = get_paper(conn, "p1")
    assert result is not None
    assert result.embedding is None


def test_upsert_paper_persists_across_connection_close(tmp_path) -> None:
    """Verify conn.commit() ensures data survives connection restart."""
    db = tmp_path / "test.db"
    conn1 = connect(db)
    apply_migrations(conn1)
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    paper = Paper(paper_id="p1", title="T", fetched_at=now, ttl_until=now + timedelta(days=30))
    upsert_paper(conn1, paper)
    conn1.close()
    conn2 = connect(db)
    assert get_paper(conn2, "p1") is not None
    conn2.close()


def test_delete_paper_persists_across_connection_close(tmp_path) -> None:
    db = tmp_path / "test.db"
    conn1 = connect(db)
    apply_migrations(conn1)
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    upsert_paper(conn1, Paper(paper_id="p1", fetched_at=now, ttl_until=now + timedelta(days=30)))
    conn1.commit()
    delete_paper(conn1, "p1")
    conn1.close()
    conn2 = connect(db)
    assert get_paper(conn2, "p1") is None
    conn2.close()


def test_delete_paper_removes_embedding(tmp_path) -> None:
    from scholar_paper_cli.storage.embeddings import knn_search, upsert_embedding

    db = tmp_path / "test.db"
    conn1 = connect(db)
    apply_migrations(conn1)
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    upsert_paper(conn1, Paper(paper_id="p1", fetched_at=now, ttl_until=now + timedelta(days=30)))
    conn1.commit()
    upsert_embedding(conn1, "p1", [0.1] * 384)
    delete_paper(conn1, "p1")
    assert knn_search(conn1, [0.1] * 384, k=1) == []
    conn1.close()
