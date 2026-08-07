"""Persistent cache wrapper for SemanticScholarClient."""

import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from scholar_paper_cli.api.client import SemanticScholarClient
from scholar_paper_cli.api.offline import OfflineDetector
from scholar_paper_cli.config import get_settings
from scholar_paper_cli.exceptions import (
    APIRateLimitError,
    APIServerError,
    APITimeoutError,
    OfflineError,
)
from scholar_paper_cli.models import CacheMetadata


def make_cache_key(endpoint: str, params: dict[str, Any]) -> str:
    clean = {k: v for k, v in params.items() if v is not None}
    raw = json.dumps({"endpoint": endpoint, "params": clean}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class CachedSemanticScholarClient:
    def __init__(
        self,
        client: SemanticScholarClient,
        conn,
        ttl_days: int = 30,
        *,
        offline: OfflineDetector | None = None,
    ) -> None:
        self.client = client
        self.conn = conn
        self.ttl_days = ttl_days
        self.offline = offline or OfflineDetector(
            httpx.AsyncClient(base_url=str(get_settings().ss_api_base)),
            force_offline=get_settings().offline_mode,
        )

    async def _with_cache(
        self,
        endpoint: str,
        params: dict[str, Any],
        fetch: Callable[[], Awaitable[dict[str, Any]]],
    ) -> tuple[dict[str, Any], CacheMetadata]:
        key = make_cache_key(endpoint, params)
        now = datetime.now(UTC)
        cached: dict[str, Any] | None = None
        try:
            cached = self._read(key)
            if cached and self._is_fresh(cached):
                return json.loads(cached["data_json"]), self._meta(key, now, "cache", cached)
        except (json.JSONDecodeError, KeyError, ValueError):
            cached = None  # corrupt row, treat as miss

        if not await self.offline.is_online():
            if cached:
                return json.loads(cached["data_json"]), self._meta(
                    key, now, "offline_cache", cached, offline=True
                )
            raise OfflineError(f"offline and no cache for {endpoint}")

        try:
            data = await fetch()
        except APIRateLimitError:
            if cached:
                return json.loads(cached["data_json"]), self._meta(
                    key, now, "offline_cache", cached, offline=True
                )
            raise
        except (APIServerError, APITimeoutError) as e:
            await self.offline.mark_offline()
            if cached:
                return json.loads(cached["data_json"]), self._meta(
                    key, now, "offline_cache", cached, offline=True
                )
            raise OfflineError(f"API failed for {endpoint}") from e

        ttl_until = now + timedelta(days=self.ttl_days)
        self._write(key, endpoint, params, data, now, ttl_until)
        return data, self._meta(key, now, "api", cached=None, ttl_until=ttl_until)

    def _read(self, key: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM api_cache WHERE cache_key = ?", (key,)).fetchone()
        return dict(row) if row else None

    def _write(self, key, endpoint, params, data, fetched_at, ttl_until) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO api_cache (cache_key, endpoint, params_json, data_json, fetched_at, ttl_until) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                key,
                endpoint,
                json.dumps(params, default=str),
                json.dumps(data),
                fetched_at.isoformat(),
                ttl_until.isoformat(),
            ),
        )
        self.conn.commit()

    def _is_fresh(self, cached: dict[str, Any]) -> bool:
        return datetime.fromisoformat(cached["ttl_until"]) > datetime.now(UTC)

    def _meta(
        self, key, fetched_at, source, cached, *, offline=False, ttl_until=None
    ) -> CacheMetadata:
        if cached:
            ttl_until = datetime.fromisoformat(cached["ttl_until"])
            fetched_at = datetime.fromisoformat(cached["fetched_at"])
        return CacheMetadata(
            cached=cached is not None,
            fetched_at=fetched_at,
            source=source,
            offline=offline,
            ttl_until=ttl_until,
            cache_key=key,
        )

    async def search_papers(self, query, *, limit=10, offset=0, fields=None):
        params = {"query": query, "limit": limit, "offset": offset, "fields": fields}
        return await self._with_cache(
            "search_papers",
            params,
            lambda: self.client.search_papers(query, limit=limit, offset=offset, fields=fields),
        )

    async def get_paper(self, paper_id, *, fields=None):
        params = {"paper_id": paper_id, "fields": fields}
        return await self._with_cache(
            "get_paper", params, lambda: self.client.get_paper(paper_id, fields=fields)
        )

    async def get_citations(self, paper_id, *, limit=100, offset=0, fields=None):
        params = {"paper_id": paper_id, "limit": limit, "offset": offset, "fields": fields}
        return await self._with_cache(
            "get_citations",
            params,
            lambda: self.client.get_citations(paper_id, limit=limit, offset=offset, fields=fields),
        )

    async def get_references(self, paper_id, *, limit=100, offset=0, fields=None):
        params = {"paper_id": paper_id, "limit": limit, "offset": offset, "fields": fields}
        return await self._with_cache(
            "get_references",
            params,
            lambda: self.client.get_references(paper_id, limit=limit, offset=offset, fields=fields),
        )

    async def search_authors(self, query, *, limit=10, offset=0, fields=None):
        params = {"query": query, "limit": limit, "offset": offset, "fields": fields}
        return await self._with_cache(
            "search_authors",
            params,
            lambda: self.client.search_authors(query, limit=limit, offset=offset, fields=fields),
        )

    async def get_author(self, author_id, *, fields=None):
        params = {"author_id": author_id, "fields": fields}
        return await self._with_cache(
            "get_author", params, lambda: self.client.get_author(author_id, fields=fields)
        )

    async def get_author_papers(self, author_id, *, limit=100, offset=0, fields=None):
        params = {"author_id": author_id, "limit": limit, "offset": offset, "fields": fields}
        return await self._with_cache(
            "get_author_papers",
            params,
            lambda: self.client.get_author_papers(
                author_id, limit=limit, offset=offset, fields=fields
            ),
        )

    async def get_recommendations(
        self, paper_id, *, limit=100, fields=None, positive_ids=None, negative_ids=None
    ):
        params = {
            "paper_id": paper_id,
            "limit": limit,
            "fields": fields,
            "positive_ids": positive_ids,
            "negative_ids": negative_ids,
        }
        return await self._with_cache(
            "get_recommendations",
            params,
            lambda: self.client.get_recommendations(
                paper_id,
                limit=limit,
                fields=fields,
                positive_ids=positive_ids,
                negative_ids=negative_ids,
            ),
        )
