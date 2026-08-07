from scholar_paper_cli.tools.authors import (
    consolidate_authors,
    find_author_duplicates,
    get_author_details,
    get_author_top_papers,
    search_authors,
)
from scholar_paper_cli.tools.bibtex import (
    export_bibtex,
    export_session_bibtex,
    format_bibtex_entry,
)
from scholar_paper_cli.tools.papers import (
    get_paper_citations,
    get_paper_details,
    get_paper_references,
    search_papers,
)
from scholar_paper_cli.tools.recommendations import (
    get_paper_recommendations,
    get_related_papers,
)
from scholar_paper_cli.tools.session import (
    add_paper_to_session,
    list_session_papers_tool,
    remove_from_session_tool,
)

__all__ = [
    "add_paper_to_session",
    "consolidate_authors",
    "export_bibtex",
    "export_session_bibtex",
    "find_author_duplicates",
    "format_bibtex_entry",
    "get_author_details",
    "get_author_top_papers",
    "get_paper_citations",
    "get_paper_details",
    "get_paper_recommendations",
    "get_paper_references",
    "get_related_papers",
    "list_session_papers_tool",
    "remove_from_session_tool",
    "search_authors",
    "search_papers",
]
