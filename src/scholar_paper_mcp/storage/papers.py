"""Paper persistence: upsert, get, search by DOI/ArXiv, count, list. Embedding stored as float32 blob."""

import json
import struct
from datetime import datetime

from scholar_paper_mcp.models import AuthorBrief, Paper


def _embed_to_blob(embedding: list[float] | None) -> bytes | None:
    if embedding is None:
        return None
    return struct.pack(f"{len(embedding)}f", *embedding)


def _blob_to_embed(data: bytes | None) -> list[float] | None:
    if data is None:
        return None
    return list(struct.unpack(f"{len(data) // 4}f", data))


def _row_to_paper(row) -> Paper:
    return Paper(
        paper_id=row["paper_id"],
        title=row["title"],
        abstract=row["abstract"],
        year=row["year"],
        venue=row["venue"],
        publication_types=json.loads(row["publication_types"]) if row["publication_types"] else [],
        fields_of_study=json.loads(row["fields_of_study"]) if row["fields_of_study"] else [],
        citation_count=row["citation_count"],
        reference_count=row["reference_count"],
        influential_citation_count=row["influential_citation_count"],
        is_open_access=bool(row["is_open_access"]),
        open_access_pdf_url=row["open_access_pdf_url"],
        external_ids=json.loads(row["external_ids"]) if row["external_ids"] else {},
        authors=[AuthorBrief(**a) for a in json.loads(row["authors_json"])]
        if row["authors_json"]
        else [],
        embedding=_blob_to_embed(row["embedding"]),
        raw=json.loads(row["raw_json"]) if row["raw_json"] else None,
        fetched_at=datetime.fromisoformat(row["fetched_at"]),
        ttl_until=datetime.fromisoformat(row["ttl_until"]),
    )


_UPDATE_COLS = """title = excluded.title, abstract = excluded.abstract,
year = excluded.year, venue = excluded.venue,
publication_types = excluded.publication_types,
fields_of_study = excluded.fields_of_study,
citation_count = excluded.citation_count,
reference_count = excluded.reference_count,
influential_citation_count = excluded.influential_citation_count,
is_open_access = excluded.is_open_access,
open_access_pdf_url = excluded.open_access_pdf_url,
external_ids = excluded.external_ids,
authors_json = excluded.authors_json,
embedding = excluded.embedding,
raw_json = excluded.raw_json,
fetched_at = excluded.fetched_at,
ttl_until = excluded.ttl_until"""


def upsert_paper(conn, paper: Paper) -> None:
    conn.execute(
        f"""INSERT INTO papers (
            paper_id, title, abstract, year, venue,
            publication_types, fields_of_study,
            citation_count, reference_count, influential_citation_count,
            is_open_access, open_access_pdf_url,
            external_ids, authors_json, embedding, raw_json,
            fetched_at, ttl_until
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(paper_id) DO UPDATE SET {_UPDATE_COLS}""",
        (
            paper.paper_id,
            paper.title,
            paper.abstract,
            paper.year,
            paper.venue,
            json.dumps(paper.publication_types),
            json.dumps(paper.fields_of_study),
            paper.citation_count,
            paper.reference_count,
            paper.influential_citation_count,
            int(paper.is_open_access),
            str(paper.open_access_pdf_url) if paper.open_access_pdf_url else None,
            json.dumps(paper.external_ids),
            json.dumps([a.model_dump() for a in paper.authors]),
            _embed_to_blob(paper.embedding),
            json.dumps(paper.raw) if paper.raw else None,
            paper.fetched_at.isoformat(),
            paper.ttl_until.isoformat(),
        ),
    )
    conn.commit()


def get_paper(conn, paper_id: str) -> Paper | None:
    row = conn.execute("SELECT * FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
    return _row_to_paper(row) if row else None


def get_paper_by_doi(conn, doi: str) -> Paper | None:
    row = conn.execute(
        "SELECT * FROM papers WHERE json_extract(external_ids, '$.DOI') = ?",
        (doi,),
    ).fetchone()
    return _row_to_paper(row) if row else None


def get_paper_by_arxiv(conn, arxiv_id: str) -> Paper | None:
    row = conn.execute(
        "SELECT * FROM papers WHERE json_extract(external_ids, '$.ArXiv') = ?",
        (arxiv_id,),
    ).fetchone()
    return _row_to_paper(row) if row else None


def delete_paper(conn, paper_id: str) -> None:
    conn.execute("DELETE FROM embeddings_vec WHERE paper_id = ?", (paper_id,))
    conn.execute("DELETE FROM papers WHERE paper_id = ?", (paper_id,))
    conn.commit()


def list_papers(conn, *, limit: int = 20, offset: int = 0) -> list[Paper]:
    rows = conn.execute(
        "SELECT * FROM papers ORDER BY paper_id LIMIT ? OFFSET ?", (limit, offset)
    ).fetchall()
    return [_row_to_paper(r) for r in rows]


def count_papers(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]


def link_paper_author(conn, paper_id: str, author_id: str, position: int = 0) -> None:
    conn.execute(
        "INSERT INTO paper_authors (paper_id, author_id, author_position) VALUES (?, ?, ?) "
        "ON CONFLICT(paper_id, author_id) DO UPDATE SET author_position = excluded.author_position",
        (paper_id, author_id, position),
    )
    conn.commit()


def unlink_paper_author(conn, paper_id: str, author_id: str) -> None:
    conn.execute(
        "DELETE FROM paper_authors WHERE paper_id = ? AND author_id = ?", (paper_id, author_id)
    )
    conn.commit()


def list_paper_authors(conn, paper_id: str) -> list[tuple[str, int]]:
    rows = conn.execute(
        "SELECT author_id, author_position FROM paper_authors WHERE paper_id = ? ORDER BY author_position",
        (paper_id,),
    ).fetchall()
    return [(r["author_id"], r["author_position"]) for r in rows]
