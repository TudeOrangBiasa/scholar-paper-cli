"""Storage layer: SQLite-backed papers, authors, citations, references, sessions + cache wrapper."""

from scholar_paper_cli.storage.authors import (
    MergeSummary,
    count_authors,
    get_author,
    list_authors,
    merge_author,
    search_authors_by_name,
    upsert_author,
)
from scholar_paper_cli.storage.cache import CachedSemanticScholarClient, make_cache_key
from scholar_paper_cli.storage.citations import (
    delete_citations_for_paper,
    get_citations_of,
    get_references_of,
    insert_citation,
    insert_reference,
)
from scholar_paper_cli.storage.embeddings import (
    Embedder,
    get_embedder,
    knn_search,
    upsert_embedding,
)
from scholar_paper_cli.storage.fts import fts_search
from scholar_paper_cli.storage.papers import (
    count_papers,
    delete_paper,
    get_paper,
    get_paper_by_arxiv,
    get_paper_by_doi,
    list_papers,
    upsert_paper,
)
from scholar_paper_cli.storage.sessions import (
    add_to_session,
    clear_session,
    list_session_papers,
    remove_from_session,
)

__all__ = [
    "CachedSemanticScholarClient",
    "Embedder",
    "MergeSummary",
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
    "list_authors",
    "list_papers",
    "list_session_papers",
    "make_cache_key",
    "merge_author",
    "remove_from_session",
    "search_authors_by_name",
    "upsert_author",
    "upsert_embedding",
    "upsert_paper",
]
