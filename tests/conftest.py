"""Shared fixtures for storage tests."""

import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scholar_paper_mcp.storage.db import apply_migrations, connect


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    c = connect(tmp_path / "test.db")
    apply_migrations(c)
    yield c
    c.close()


@pytest.fixture
def real_conn(tmp_path: Path) -> sqlite3.Connection:
    """Writable connection without yield-close (callers close it)."""
    c = connect(tmp_path / "test.db")
    apply_migrations(c)
    c.execute("PRAGMA foreign_keys = OFF")
    return c


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc)
