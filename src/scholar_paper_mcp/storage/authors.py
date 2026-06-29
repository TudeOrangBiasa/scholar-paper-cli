"""Author persistence: upsert, get, search by name, count, list."""

import json
from datetime import datetime

from scholar_paper_mcp.models import Author, PaperBrief


def _row_to_author(row) -> Author:
    return Author(
        author_id=row["author_id"],
        name=row["name"],
        affiliations=json.loads(row["affiliations"]) if row["affiliations"] else [],
        h_index=row["h_index"],
        paper_count=row["paper_count"],
        aliases=json.loads(row["aliases"]) if row["aliases"] else [],
        papers=[PaperBrief(**p) for p in json.loads(row["papers_json"])]
        if row["papers_json"]
        else [],
        fetched_at=datetime.fromisoformat(row["fetched_at"]),
        ttl_until=datetime.fromisoformat(row["ttl_until"]),
    )


def upsert_author(conn, author: Author) -> None:
    conn.execute(
        """INSERT INTO authors (
            author_id, name, affiliations, h_index, paper_count,
            aliases, papers_json, fetched_at, ttl_until
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(author_id) DO UPDATE SET
            name = excluded.name,
            affiliations = excluded.affiliations,
            h_index = excluded.h_index,
            paper_count = excluded.paper_count,
            aliases = excluded.aliases,
            papers_json = excluded.papers_json,
            fetched_at = excluded.fetched_at,
            ttl_until = excluded.ttl_until""",
        (
            author.author_id,
            author.name,
            json.dumps(author.affiliations),
            author.h_index,
            author.paper_count,
            json.dumps(author.aliases),
            json.dumps([p.model_dump() for p in author.papers]),
            author.fetched_at.isoformat(),
            author.ttl_until.isoformat(),
        ),
    )
    conn.commit()


def get_author(conn, author_id: str) -> Author | None:
    row = conn.execute("SELECT * FROM authors WHERE author_id = ?", (author_id,)).fetchone()
    return _row_to_author(row) if row else None


def list_authors(conn, *, limit: int = 20, offset: int = 0) -> list[Author]:
    rows = conn.execute(
        "SELECT * FROM authors ORDER BY author_id LIMIT ? OFFSET ?", (limit, offset)
    ).fetchall()
    return [_row_to_author(r) for r in rows]


def count_authors(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM authors").fetchone()[0]


def delete_author(conn, author_id: str) -> None:
    conn.execute("DELETE FROM authors WHERE author_id = ?", (author_id,))
    conn.commit()


def search_authors_by_name(conn, name: str, *, limit: int = 20) -> list[Author]:
    rows = conn.execute(
        "SELECT * FROM authors WHERE name LIKE ? COLLATE NOCASE LIMIT ?",
        (f"%{name}%", limit),
    ).fetchall()
    return [_row_to_author(r) for r in rows]
