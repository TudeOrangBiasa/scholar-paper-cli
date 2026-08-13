"""BibTeX export for session papers."""

from scholar_paper_cli.models import Paper, ToolResponse
from scholar_paper_cli.tools.session import list_session_papers


def _sanitize_cite_key(paper_id: str) -> str:
    return paper_id.replace(":", "_").replace("/", "_").replace(".", "_").replace("-", "_")


def _escape(text: str) -> str:
    return text.replace("{", "\\{").replace("}", "\\}")


def format_bibtex_entry(paper: Paper) -> str:
    cite_key = _sanitize_cite_key(paper.paper_id)
    fields: list[str] = []
    if paper.title:
        fields.append(f"  title = {{{_escape(paper.title)}}}")
    if paper.authors:
        authors = " and ".join(_escape(a.name) for a in paper.authors)
        fields.append(f"  author = {{{authors}}}")
    if paper.year:
        fields.append(f"  year = {{{paper.year}}}")
    if paper.venue:
        fields.append(f"  journal = {{{_escape(paper.venue)}}}")
    doi = paper.external_ids.get("DOI")
    if doi:
        fields.append(f"  doi = {{{doi}}}")
    arxiv = paper.external_ids.get("ArXiv")
    if arxiv:
        fields.append(f"  eprint = {{{arxiv}}}")
        fields.append("  archiveprefix = {arXiv}")
    body = ",\n".join(fields) if fields else "  note = {no metadata}"
    return f"@article{{{cite_key},\n{body}\n}}\n"


def export_bibtex(papers: list[Paper]) -> str:
    return "".join(format_bibtex_entry(p) for p in papers)


async def export_session_bibtex(
    conn,
    session_id: str,
) -> ToolResponse[str]:
    result = await list_session_papers(conn, session_id)
    bibtex = export_bibtex(result.data)
    return ToolResponse(data=bibtex, meta=result.meta)
