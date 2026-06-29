"""Storage layer: SQLite-backed papers, authors, citations, references, sessions + cache wrapper."""

from scholar_paper_mcp.storage.authors import (
    count_authors,
    get_author,
    list_authors,
    search_authors_by_name,
    upsert_author,
)
from scholar_paper_mcp.storage.cache import CachedSemanticScholarClient, make_cache_key
from scholar_paper_mcp.storage.citations import (
    delete_citations_for_paper,
    get_citations_of,
    get_references_of,
    insert_citation,
    insert_reference,
)
from scholar_paper_mcp.storage.embeddings import (
    Embedder,
    get_embedder,
    knn_search,
    upsert_embedding,
)
from scholar_paper_mcp.storage.fts import fts_search
from scholar_paper_mcp.storage.papers import (
    count_papers,
    delete_paper,
    get_paper,
    get_paper_by_arxiv,
    get_paper_by_doi,
    link_paper_author,
    list_paper_authors,
    list_papers,
    unlink_paper_author,
    upsert_paper,
)
from scholar_paper_mcp.storage.sessions import (
    add_to_session,
    clear_session,
    list_session_papers,
    remove_from_session,
)

__all__ = [
    "CachedSemanticScholarClient",
    "Embedder",
    "add_to_session",
    "clear_session",
    "count_authors",
    "count_papers",
    "delete_citations_for_paper",
    "delete_paper",
    "fts_search",
    "get_author",
    "get_citations_of",
    "get_embedder",
    "get_paper",
    "get_paper_by_arxiv",
    "get_paper_by_doi",
    "get_references_of",
    "insert_citation",
    "insert_reference",
    "knn_search",
    "link_paper_author",
    "list_authors",
    "list_paper_authors",
    "list_papers",
    "list_session_papers",
    "make_cache_key",
    "remove_from_session",
    "search_authors_by_name",
    "unlink_paper_author",
    "upsert_author",
    "upsert_embedding",
    "upsert_paper",
]
