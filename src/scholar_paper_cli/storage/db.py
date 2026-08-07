"""SQLite connection + migration runner."""

import sqlite3
from importlib import resources
from pathlib import Path

import sqlite_vec

from scholar_paper_cli.config import get_settings
from scholar_paper_cli.exceptions import CacheError


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if isinstance(db_path, str) else (db_path or get_settings().cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(path))
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        raise CacheError(f"failed to open database: {path}") from e


def _user_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def apply_migrations(conn: sqlite3.Connection) -> None:
    current = _user_version(conn)
    if current < 1:
        schema = resources.files("scholar_paper_cli.storage").joinpath("schema.sql").read_text()
        conn.executescript(schema)
        conn.execute("PRAGMA user_version = 1")
        current = 1
    if current < 2:
        migration = (
            resources.files("scholar_paper_cli.storage")
            .joinpath("migrations/002_api_cache.sql")
            .read_text()
        )
        conn.executescript(migration)
        conn.execute("PRAGMA user_version = 2")
    conn.commit()
