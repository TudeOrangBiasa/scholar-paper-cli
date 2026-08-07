"""FTS5 lexical search over papers (title + abstract)."""

import re

_FTS_SPECIAL = re.compile(r'[^\w\s\-"]')


def _sanitize_query(query: str) -> str:
    """Strip FTS5 special chars from query, keep word chars and dashes."""
    cleaned = _FTS_SPECIAL.sub(" ", query).strip()
    if not cleaned:
        return '""'
    return " ".join(f'"{w}"' for w in cleaned.split())


def fts_search(conn, query: str, k: int = 10) -> list[str]:
    """FTS5 search. Returns list of paper_ids, ordered by FTS5 rank."""
    fts_query = _sanitize_query(query)
    if fts_query == '""':
        return []
    rows = conn.execute(
        "SELECT p.paper_id FROM papers p "
        "JOIN papers_fts ON papers_fts.rowid = p.rowid "
        "WHERE papers_fts MATCH ? "
        "ORDER BY rank LIMIT ?",
        (fts_query, k),
    ).fetchall()
    return [r["paper_id"] for r in rows]
