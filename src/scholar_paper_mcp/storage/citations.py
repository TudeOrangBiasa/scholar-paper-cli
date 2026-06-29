"""Citation + reference edge persistence. Stub paper rows auto-inserted to satisfy FK."""

import json
import sqlite3

from scholar_paper_mcp.models import CitationEdge


def _ensure_paper_stub(conn: sqlite3.Connection, paper_id: str) -> None:
    """Insert minimal paper row so FK constraints on citations/references pass.

    Real paper metadata arrives later via get_paper_details; this row only
    satisfies the FK requirement.
    """
    conn.execute(
        """INSERT OR IGNORE INTO papers (paper_id, fetched_at, ttl_until)
        VALUES (?, datetime('now'), datetime('now'))""",
        (paper_id,),
    )


def insert_citation(conn: sqlite3.Connection, edge: CitationEdge) -> None:
    _ensure_paper_stub(conn, edge.from_paper_id)
    _ensure_paper_stub(conn, edge.to_paper_id)
    conn.execute(
        """INSERT INTO citations (from_paper_id, to_paper_id, context_intent, is_influential)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(from_paper_id, to_paper_id) DO UPDATE SET
            context_intent = excluded.context_intent,
            is_influential = excluded.is_influential""",
        (
            edge.from_paper_id,
            edge.to_paper_id,
            json.dumps(edge.context_intent) if edge.context_intent else None,
            int(edge.is_influential),
        ),
    )
    conn.commit()


def insert_reference(conn: sqlite3.Connection, edge: CitationEdge) -> None:
    _ensure_paper_stub(conn, edge.from_paper_id)
    _ensure_paper_stub(conn, edge.to_paper_id)
    conn.execute(
        """INSERT INTO paper_references (from_paper_id, to_paper_id, is_influential)
        VALUES (?, ?, ?)
        ON CONFLICT(from_paper_id, to_paper_id) DO UPDATE SET
            is_influential = excluded.is_influential""",
        (edge.from_paper_id, edge.to_paper_id, int(edge.is_influential)),
    )
    conn.commit()


def get_citations_of(conn, paper_id: str, *, limit: int = 100) -> list[CitationEdge]:
    rows = conn.execute(
        "SELECT * FROM citations WHERE to_paper_id = ? LIMIT ?",
        (paper_id, limit),
    ).fetchall()
    return [_row_to_citation(r) for r in rows]


def get_references_of(conn, paper_id: str, *, limit: int = 100) -> list[CitationEdge]:
    rows = conn.execute(
        "SELECT * FROM paper_references WHERE from_paper_id = ? LIMIT ?",
        (paper_id, limit),
    ).fetchall()
    return [_row_to_reference(r) for r in rows]


def delete_citations_for_paper(conn, paper_id: str) -> None:
    conn.execute(
        "DELETE FROM citations WHERE from_paper_id = ? OR to_paper_id = ?", (paper_id, paper_id)
    )
    conn.execute(
        "DELETE FROM paper_references WHERE from_paper_id = ? OR to_paper_id = ?",
        (paper_id, paper_id),
    )
    conn.commit()


def _row_to_citation(row) -> CitationEdge:
    return CitationEdge(
        from_paper_id=row["from_paper_id"],
        to_paper_id=row["to_paper_id"],
        context_intent=json.loads(row["context_intent"]) if row["context_intent"] else None,
        is_influential=bool(row["is_influential"]),
    )


def _row_to_reference(row) -> CitationEdge:
    return CitationEdge(
        from_paper_id=row["from_paper_id"],
        to_paper_id=row["to_paper_id"],
        context_intent=None,
        is_influential=bool(row["is_influential"]),
    )
