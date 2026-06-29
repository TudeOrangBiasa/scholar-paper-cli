"""Session persistence: add/remove/list paper IDs per session_id, ordered by add time."""

from datetime import UTC, datetime


def add_to_session(conn, session_id: str, paper_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO session_papers (session_id, paper_id, added_at) VALUES (?, ?, ?)",
        (session_id, paper_id, datetime.now(UTC).isoformat()),
    )
    conn.commit()


def remove_from_session(conn, session_id: str, paper_id: str) -> None:
    conn.execute(
        "DELETE FROM session_papers WHERE session_id = ? AND paper_id = ?",
        (session_id, paper_id),
    )
    conn.commit()


def list_session_papers(conn, session_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT paper_id FROM session_papers WHERE session_id = ? ORDER BY added_at",
        (session_id,),
    ).fetchall()
    return [r[0] for r in rows]


def clear_session(conn, session_id: str) -> None:
    conn.execute("DELETE FROM session_papers WHERE session_id = ?", (session_id,))
    conn.commit()
