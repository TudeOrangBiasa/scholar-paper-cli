"""Tests for storage module — v2 api_cache migration."""

from pathlib import Path

from scholar_paper_cli.storage.db import apply_migrations, connect


def test_fresh_db_has_api_cache_table(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    assert "api_cache" in tables
    conn.close()


def test_v1_db_upgrades_to_v2(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS papers (paper_id TEXT PRIMARY KEY, fetched_at TEXT, ttl_until TEXT);"
    )
    conn.execute("PRAGMA user_version = 1")
    apply_migrations(conn)
    (ver,) = conn.execute("PRAGMA user_version").fetchone()
    assert ver == 2
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    assert "api_cache" in tables
    conn.close()


def test_migrations_idempotent_after_v2(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)
    apply_migrations(conn)
    (ver,) = conn.execute("PRAGMA user_version").fetchone()
    assert ver == 2
    conn.close()
