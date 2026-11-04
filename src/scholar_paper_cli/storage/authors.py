"""Author persistence: upsert, get, search by name, count, list, merge."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from scholar_paper_cli.config import get_settings
from scholar_paper_cli.exceptions import APINotFoundError
from scholar_paper_cli.models import Author, PaperBrief


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


def _upsert_author_sql(conn, author: Author) -> None:
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


def upsert_author(conn, author: Author) -> None:
    _upsert_author_sql(conn, author)
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


def _delete_author_sql(conn, author_id: str) -> None:
    conn.execute("DELETE FROM authors WHERE author_id = ?", (author_id,))


def delete_author(conn, author_id: str) -> None:
    _delete_author_sql(conn, author_id)
    conn.commit()


def search_authors_by_name(conn, name: str, *, limit: int = 20) -> list[Author]:
    rows = conn.execute(
        "SELECT * FROM authors WHERE name LIKE ? COLLATE NOCASE LIMIT ?",
        (f"%{name}%", limit),
    ).fetchall()
    return [_row_to_author(r) for r in rows]


@dataclass
class MergeSummary:
    """Observable outcome of an author consolidation."""

    aliases_merged: int = 0
    papers_re_parented: int = 0
    dups_merged: int = 0
    dups_skipped: int = 0


def merge_author(
    conn,
    canonical_id: str,
    duplicate_ids: list[str],
) -> tuple[Author, MergeSummary]:
    """Merge duplicate authors into one canonical author.

    Merges aliases (deduplicated), re-parents paper_authors rows preserving
    author_position, deletes the duplicates, and refreshes the canonical row.
    Missing duplicates are skipped and reported, never fatal. Owns one
    transaction: either all duplicates merge or none.
    """
    started = not conn.in_transaction
    if started:
        conn.execute("BEGIN IMMEDIATE")
    try:
        canonical = get_author(conn, canonical_id)
        if canonical is None:
            raise APINotFoundError(f"author not found: {canonical_id}")

        summary = MergeSummary()
        seen_paper_ids = {p.paper_id for p in canonical.papers}
        seen_aliases = set(canonical.aliases) | ({canonical.name} if canonical.name else set())

        for dup_id in duplicate_ids:
            dup = get_author(conn, dup_id)
            if dup is None:
                summary.dups_skipped += 1
                continue
            for alias in dup.aliases:
                if alias and alias not in seen_aliases:
                    canonical.aliases.append(alias)
                    seen_aliases.add(alias)
                    summary.aliases_merged += 1
            for paper in dup.papers:
                if paper.paper_id not in seen_paper_ids:
                    canonical.papers.append(paper)
                    seen_paper_ids.add(paper.paper_id)
            conn.execute(
                "INSERT OR REPLACE INTO paper_authors (paper_id, author_id, author_position) "
                "SELECT paper_id, ?, author_position FROM paper_authors WHERE author_id = ?",
                (canonical_id, dup_id),
            )
            deleted = conn.execute("DELETE FROM paper_authors WHERE author_id = ?", (dup_id,))
            summary.papers_re_parented += deleted.rowcount
            _delete_author_sql(conn, dup_id)
            summary.dups_merged += 1

        canonical.paper_count = len(canonical.papers)
        canonical.fetched_at = datetime.now(UTC)
        canonical.ttl_until = canonical.fetched_at + timedelta(days=get_settings().cache_ttl_days)
        _upsert_author_sql(conn, canonical)
        if started:
            conn.commit()
    except BaseException:
        if started:
            conn.rollback()
        raise
    return canonical, summary
