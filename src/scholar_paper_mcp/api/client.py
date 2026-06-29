"""Semantic Scholar HTTP client with rate limiting and circuit breaker."""

import re
from typing import Any

import httpx

from scholar_paper_mcp.api.circuit_breaker import CircuitBreaker
from scholar_paper_mcp.api.rate_limiter import TokenBucket
from scholar_paper_mcp.config import get_settings
from scholar_paper_mcp.exceptions import APINotFoundError, APIRateLimitError, APIServerError

_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:\-]+$")


def _validate_id(value: str, name: str) -> None:
    if not _ID_PATTERN.match(value):
        raise ValueError(f"invalid {name}: {value!r}")


DEFAULT_PAPER_FIELDS = (
    "paperId,title,abstract,year,venue,publicationTypes,fieldsOfStudy,"
    "citationCount,referenceCount,influentialCitationCount,isOpenAccess,"
    "openAccessPdf,externalIds,authors"
)
DEFAULT_AUTHOR_FIELDS = "authorId,name,affiliations,hIndex,paperCount,aliases,papers"
# /author/search rejects aliases + papers; use minimal fields.
DEFAULT_AUTHOR_SEARCH_FIELDS = "authorId,name,affiliations,hIndex,paperCount"


class SemanticScholarClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        rate: float = 0.5,
        burst: int = 5,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or str(settings.ss_api_base)).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.api_key
        self.limiter = TokenBucket(rate, burst)
        self.breaker = CircuitBreaker(failure_threshold, reset_timeout)
        headers = {"User-Agent": "scholar-paper-mcp/0.1.0"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "SemanticScholarClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        await self.limiter.acquire()

        async def _req() -> Any:
            r = await self._client.get(path, params=params)
            if r.status_code == 200:
                return r.json() if r.content else {}
            if r.status_code == 404:
                raise APINotFoundError(f"not found: {r.url}")
            if r.status_code == 429:
                raise APIRateLimitError(f"rate limited: {r.url}")
            if r.status_code >= 500:
                raise APIServerError(f"server error {r.status_code}: {r.url}")
            raise APIServerError(f"unexpected status {r.status_code}: {r.url}")

        return await self.breaker.call(_req())

    async def search_papers(
        self, query: str, *, limit: int = 10, offset: int = 0, fields: str | None = None
    ) -> dict[str, Any]:
        return await self._get(
            "/paper/search",
            {
                "query": query,
                "limit": limit,
                "offset": offset,
                "fields": fields or DEFAULT_PAPER_FIELDS,
            },
        )

    async def get_paper(self, paper_id: str, *, fields: str | None = None) -> dict[str, Any]:
        _validate_id(paper_id, "paper_id")
        return await self._get(
            f"/paper/{paper_id}",
            {
                "fields": fields or DEFAULT_PAPER_FIELDS,
            },
        )

    async def get_citations(
        self, paper_id: str, *, limit: int = 100, offset: int = 0, fields: str | None = None
    ) -> dict[str, Any]:
        return await self._get(
            f"/paper/{paper_id}/citations",
            {
                "limit": limit,
                "offset": offset,
                "fields": fields or f"paperId,{DEFAULT_PAPER_FIELDS}",
            },
        )

    async def get_references(
        self, paper_id: str, *, limit: int = 100, offset: int = 0, fields: str | None = None
    ) -> dict[str, Any]:
        return await self._get(
            f"/paper/{paper_id}/references",
            {
                "limit": limit,
                "offset": offset,
                "fields": fields or f"paperId,{DEFAULT_PAPER_FIELDS}",
            },
        )

    async def search_authors(
        self, query: str, *, limit: int = 10, offset: int = 0, fields: str | None = None
    ) -> dict[str, Any]:
        return await self._get(
            "/author/search",
            {
                "query": query,
                "limit": limit,
                "offset": offset,
                "fields": fields or DEFAULT_AUTHOR_SEARCH_FIELDS,
            },
        )

    async def get_author(self, author_id: str, *, fields: str | None = None) -> dict[str, Any]:
        _validate_id(author_id, "author_id")
        return await self._get(
            f"/author/{author_id}",
            {
                "fields": fields or DEFAULT_AUTHOR_FIELDS,
            },
        )

    async def get_author_papers(
        self, author_id: str, *, limit: int = 100, offset: int = 0, fields: str | None = None
    ) -> dict[str, Any]:
        return await self._get(
            f"/author/{author_id}/papers",
            {
                "limit": limit,
                "offset": offset,
                "fields": fields or DEFAULT_PAPER_FIELDS,
            },
        )

    async def get_recommendations(
        self,
        paper_id: str,
        *,
        limit: int = 100,
        fields: str | None = None,
        positive_ids: list[str] | None = None,
        negative_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "limit": limit,
            "fields": fields or DEFAULT_PAPER_FIELDS,
        }
        if positive_ids:
            params["positive"] = ",".join(positive_ids)
        if negative_ids:
            params["negative"] = ",".join(negative_ids)
        return await self._get(f"/paper/{paper_id}/recommendations", params)
