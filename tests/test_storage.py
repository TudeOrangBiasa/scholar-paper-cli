"""Tests for storage module — connect, migrations, schema."""

import sqlite3
from pathlib import Path

from scholar_paper_cli.storage.db import apply_migrations, connect


def test_connect_opens_database_file(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    conn = connect(db)
    assert db.exists()
    assert isinstance(conn, sqlite3.Connection)
    conn.close()


def test_connect_loads_sqlite_vec_extension(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    cur = conn.execute("SELECT name FROM pragma_module_list WHERE name='vec0'")
    assert cur.fetchone() is not None
    conn.close()


def test_connect_enables_foreign_keys(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    (fk,) = conn.execute("PRAGMA foreign_keys").fetchone()
    assert fk == 1
    conn.close()


def test_connect_uses_wal_journal_mode(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    (journal,) = conn.execute("PRAGMA journal_mode").fetchone()
    assert journal == "wal"
    conn.close()


def test_apply_migrations_creates_core_tables(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    for name in (
        "papers",
        "authors",
        "paper_authors",
        "citations",
        "paper_references",
        "session_papers",
    ):
        assert name in tables, f"missing table: {name}"
    conn.close()


def test_apply_migrations_creates_vec_table(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='embeddings_vec'"
    ).fetchone()
    assert row is not None
    assert "CREATE VIRTUAL TABLE" in row[0]
    assert "vec0" in row[0]
    conn.close()


def test_apply_migrations_creates_fts5_with_sync(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)

    # FTS5 virtual table exists
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='papers_fts'"
    ).fetchone()
    assert row is not None
    assert "fts5" in row[0]

    # Insert triggers FTS sync
    conn.execute(
        "INSERT INTO papers (paper_id, title, abstract, fetched_at, ttl_until) "
        "VALUES ('p1', 'quantum entanglement', 'abstract here', '2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z')"
    )
    rows = conn.execute("SELECT title FROM papers_fts WHERE papers_fts MATCH 'quantum'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "quantum entanglement"

    # Update syncs
    conn.execute("UPDATE papers SET title='quantum computing' WHERE paper_id='p1'")
    rows = conn.execute(
        "SELECT title FROM papers_fts WHERE papers_fts MATCH 'computing'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "quantum computing"

    # Delete removes from FTS
    conn.execute("DELETE FROM papers WHERE paper_id='p1'")
    rows = conn.execute("SELECT title FROM papers_fts WHERE papers_fts MATCH 'quantum'").fetchall()
    assert len(rows) == 0

    conn.close()


def test_apply_migrations_idempotent(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    apply_migrations(conn)  # no error
    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert "papers" in tables
    conn.close()


def test_apply_migrations_sets_user_version(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    (ver,) = conn.execute("PRAGMA user_version").fetchone()
    assert ver >= 1
    conn.close()


def test_paper_authors_cascade_on_paper_delete(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    conn.execute(
        "INSERT INTO papers (paper_id, title, abstract, fetched_at, ttl_until) "
        "VALUES ('p1', 'title', 'abstract', '2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO authors (author_id, name, fetched_at, ttl_until) "
        "VALUES ('a1', 'Author One', '2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO paper_authors (paper_id, author_id, author_position) VALUES ('p1', 'a1', 0)"
    )
    conn.execute("DELETE FROM papers WHERE paper_id='p1'")
    remaining = conn.execute("SELECT COUNT(*) FROM paper_authors WHERE author_id='a1'").fetchone()[
        0
    ]
    assert remaining == 0
    conn.close()
