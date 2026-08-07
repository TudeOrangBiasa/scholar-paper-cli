"""Tests for storage.fts — FTS5 lexical search."""

from scholar_paper_cli.storage.db import apply_migrations, connect


def _seed_paper(conn, paper_id: str, title: str = "", abstract: str = "") -> None:
    conn.execute(
        "INSERT INTO papers (paper_id, title, abstract, fetched_at, ttl_until) "
        "VALUES (?, ?, ?, '2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z')",
        (paper_id, title, abstract),
    )


def test_fts_search_finds_exact_word_match(tmp_path) -> None:
    from scholar_paper_cli.storage.fts import fts_search

    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    _seed_paper(conn, "p1", title="quantum entanglement fundamentals")

    results = fts_search(conn, "quantum")
    assert results == ["p1"]


def test_fts_search_finds_abstract_match(tmp_path) -> None:
    from scholar_paper_cli.storage.fts import fts_search

    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    _seed_paper(conn, "p1", title="Paper", abstract="quantum entanglement abstract")

    results = fts_search(conn, "quantum")
    assert results == ["p1"]


def test_fts_search_returns_empty_for_no_match(tmp_path) -> None:
    from scholar_paper_cli.storage.fts import fts_search

    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    _seed_paper(conn, "p1", title="quantum physics")

    results = fts_search(conn, "nonexistentword")
    assert results == []


def test_fts_search_sanitizes_special_chars(tmp_path) -> None:
    from scholar_paper_cli.storage.fts import fts_search

    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    _seed_paper(conn, "p1", title="quantum physics")

    # FTS5 special chars like *, (, ), etc should be sanitized and not crash
    results = fts_search(conn, "test:query!")
    assert results == []


def test_fts_search_returns_empty_for_empty_query(tmp_path) -> None:
    from scholar_paper_cli.storage.fts import fts_search

    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    _seed_paper(conn, "p1", title="quantum physics")

    results = fts_search(conn, "")
    assert results == []


def test_fts_search_returns_empty_for_whitespace_query(tmp_path) -> None:
    from scholar_paper_cli.storage.fts import fts_search

    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    _seed_paper(conn, "p1", title="quantum physics")

    results = fts_search(conn, "   ")
    assert results == []


def test_fts_search_respects_limit(tmp_path) -> None:
    from scholar_paper_cli.storage.fts import fts_search

    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    for i in range(5):
        _seed_paper(conn, f"p{i}", title=f"quantum paper {i}")

    results = fts_search(conn, "quantum", k=2)
    assert len(results) == 2


def test_fts_search_synced_via_triggers(tmp_path) -> None:
    """Regression: FTS sync triggers keep papers_fts in sync."""
    from scholar_paper_cli.storage.fts import fts_search

    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)

    # Insert
    _seed_paper(conn, "p1", title="quantum entanglement")
    assert fts_search(conn, "quantum") == ["p1"]

    # Update
    conn.execute(
        "UPDATE papers SET title='quantum computing' WHERE paper_id='p1'",
    )
    assert fts_search(conn, "computing") == ["p1"]
    assert fts_search(conn, "entanglement") == []

    # Delete
    conn.execute("DELETE FROM papers WHERE paper_id='p1'")
    assert fts_search(conn, "quantum") == []


def test_fts_search_multi_word(tmp_path) -> None:
    from scholar_paper_cli.storage.fts import fts_search

    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    _seed_paper(conn, "p1", title="quantum entanglement")
    _seed_paper(conn, "p2", title="quantum computing")

    results = fts_search(conn, "quantum entanglement")
    assert results == ["p1"]
