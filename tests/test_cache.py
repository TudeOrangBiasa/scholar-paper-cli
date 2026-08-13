"""Tests for CachedSemanticScholarClient."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from scholar_paper_cli.api.client import SemanticScholarClient
from scholar_paper_cli.api.offline import OfflineDetector
from scholar_paper_cli.exceptions import (
    APIRateLimitError,
    APIServerError,
    APITimeoutError,
    OfflineError,
)
from scholar_paper_cli.storage.cache import CachedSemanticScholarClient, make_cache_key
from scholar_paper_cli.storage.db import apply_migrations, connect

# ── make_cache_key tests ──────────────────────────────────────────


def test_make_cache_key_is_deterministic() -> None:
    k1 = make_cache_key("search_papers", {"query": "ai", "limit": 10})
    k2 = make_cache_key("search_papers", {"query": "ai", "limit": 10})
    assert k1 == k2


def test_make_cache_key_differs_for_different_params() -> None:
    k1 = make_cache_key("search_papers", {"query": "ai"})
    k2 = make_cache_key("search_papers", {"query": "ml"})
    assert k1 != k2


def test_make_cache_key_includes_endpoint() -> None:
    k1 = make_cache_key("search_papers", {"query": "ai"})
    k2 = make_cache_key("get_paper", {"query": "ai"})
    assert k1 != k2


def test_make_cache_key_sorts_list_values() -> None:
    """List params are order-insensitive: equivalent calls share a cache entry."""
    k1 = make_cache_key("get_recommendations", {"positive_ids": ["b", "a", "c"]})
    k2 = make_cache_key("get_recommendations", {"positive_ids": ["a", "b", "c"]})
    assert k1 == k2
    k3 = make_cache_key("get_recommendations", {"positive_ids": ["a", "b"]})
    assert k1 != k3


# ── Helpers ───────────────────────────────────────────────────────


def _conn(tmp_path: Path):
    c = connect(tmp_path / "test.db")
    apply_migrations(c)
    return c


def _client(fake_ss: AsyncMock, conn) -> CachedSemanticScholarClient:
    detector = AsyncMock(spec=OfflineDetector)
    detector.is_online.return_value = True
    return CachedSemanticScholarClient(fake_ss, conn, ttl_days=30, offline=detector)


def _populate_cache(
    conn, key: str, endpoint: str, params: dict, data: dict, *, stale: bool = False
) -> None:
    now = datetime.now(UTC)
    fetched = (now - timedelta(days=60)).isoformat() if stale else now.isoformat()
    ttl = (now - timedelta(days=1)).isoformat() if stale else (now + timedelta(days=30)).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO api_cache (cache_key, endpoint, params_json, data_json, fetched_at, ttl_until) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (key, endpoint, json.dumps(params, default=str), json.dumps(data), fetched, ttl),
    )
    conn.commit()


# ── Cache behavior tests ──────────────────────────────────────────


async def test_cache_hit_returns_without_calling_client(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    cached = _client(ss, conn)
    key = make_cache_key("get_paper", {"paper_id": "abc"})
    _populate_cache(conn, key, "get_paper", {"paper_id": "abc"}, {"paperId": "abc"})
    data, _ = await cached.get_paper("abc")
    assert data == {"paperId": "abc"}
    assert ss.get_paper.call_count == 0


async def test_cache_miss_calls_client_and_persists(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.return_value = {"paperId": "new"}
    cached = _client(ss, conn)
    data, _ = await cached.get_paper("new")
    assert data == {"paperId": "new"}
    ss.get_paper.assert_awaited_once_with("new", fields=None)
    row = conn.execute("SELECT * FROM api_cache").fetchone()
    assert row is not None
    assert row["endpoint"] == "get_paper"


async def test_cache_stale_calls_client_and_updates(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.return_value = {"paperId": "fresh"}
    key = make_cache_key("get_paper", {"paper_id": "stale1"})
    _populate_cache(
        conn, key, "get_paper", {"paper_id": "stale1"}, {"paperId": "stale"}, stale=True
    )
    cached = _client(ss, conn)
    data, _ = await cached.get_paper("stale1")
    assert data == {"paperId": "fresh"}
    ss.get_paper.assert_awaited_once()
    row = conn.execute("SELECT * FROM api_cache WHERE cache_key=?", (key,)).fetchone()
    # ttl_until should be updated (future)
    assert datetime.fromisoformat(row["ttl_until"]) > datetime.now(UTC)


async def test_api_failure_with_stale_cache_returns_offline(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.side_effect = APIServerError("server error")
    key = make_cache_key("get_paper", {"paper_id": "offline1"})
    _populate_cache(
        conn, key, "get_paper", {"paper_id": "offline1"}, {"paperId": "stale"}, stale=True
    )
    cached = _client(ss, conn)
    data, _ = await cached.get_paper("offline1")
    assert data == {"paperId": "stale"}
    ss.get_paper.assert_awaited_once()


async def test_api_failure_with_no_cache_raises_offline_error(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.side_effect = APIServerError("server error")
    cached = _client(ss, conn)
    with pytest.raises(OfflineError):
        await cached.get_paper("nonexistent")


async def test_api_failure_with_timeout_returns_offline_cache(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.side_effect = APITimeoutError("timeout")
    key = make_cache_key("get_paper", {"paper_id": "timeout1"})
    _populate_cache(
        conn, key, "get_paper", {"paper_id": "timeout1"}, {"paperId": "stale"}, stale=True
    )
    cached = _client(ss, conn)
    data, _ = await cached.get_paper("timeout1")
    assert data == {"paperId": "stale"}


# ── CacheMetadata tests ───────────────────────────────────────────


async def test_cache_metadata_source_cache_on_hit(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    key = make_cache_key("get_paper", {"paper_id": "meta1"})
    _populate_cache(conn, key, "get_paper", {"paper_id": "meta1"}, {"paperId": "abc"})
    cached = _client(ss, conn)
    _, meta = await cached.get_paper("meta1")
    assert meta.source == "cache"


async def test_cache_metadata_source_api_on_miss(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.return_value = {"paperId": "new"}
    cached = _client(ss, conn)
    _, meta = await cached.get_paper("new")
    assert meta.source == "api"


async def test_cache_metadata_source_offline_cache_on_failure(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.side_effect = APIServerError("server error")
    key = make_cache_key("get_paper", {"paper_id": "offline2"})
    _populate_cache(
        conn, key, "get_paper", {"paper_id": "offline2"}, {"paperId": "stale"}, stale=True
    )
    cached = _client(ss, conn)
    _, meta = await cached.get_paper("offline2")
    assert meta.source == "offline_cache"


async def test_cache_metadata_offline_flag(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.side_effect = APIServerError("server error")
    key = make_cache_key("get_paper", {"paper_id": "offline3"})
    _populate_cache(
        conn, key, "get_paper", {"paper_id": "offline3"}, {"paperId": "stale"}, stale=True
    )
    cached = _client(ss, conn)
    _, meta = await cached.get_paper("offline3")
    assert meta.offline is True


async def test_cache_metadata_cached_true_on_hit(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    key = make_cache_key("get_paper", {"paper_id": "hit1"})
    _populate_cache(conn, key, "get_paper", {"paper_id": "hit1"}, {"paperId": "abc"})
    cached = _client(ss, conn)
    _, meta = await cached.get_paper("hit1")
    assert meta.cached is True


async def test_cache_metadata_cached_false_on_miss(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.return_value = {"paperId": "new"}
    cached = _client(ss, conn)
    _, meta = await cached.get_paper("new")
    assert meta.cached is False


async def test_cache_metadata_ttl_until_set(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.return_value = {"paperId": "new"}
    cached = _client(ss, conn)
    _, meta = await cached.get_paper("new")
    assert meta.ttl_until is not None
    assert meta.ttl_until > datetime.now(UTC)


async def test_cache_metadata_cache_key_set(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.return_value = {"paperId": "new"}
    cached = _client(ss, conn)
    _, meta = await cached.get_paper("new")
    assert meta.cache_key == make_cache_key("get_paper", {"paper_id": "new"})


# ── Endpoint method tests ─────────────────────────────────────────


async def test_each_endpoint_method_uses_correct_endpoint_name(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.return_value = {"paperId": "abc"}
    cached = _client(ss, conn)
    await cached.get_paper("abc")
    row = conn.execute("SELECT endpoint FROM api_cache").fetchone()
    assert row["endpoint"] == "get_paper"


async def test_each_endpoint_method_passes_params(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.return_value = {"paperId": "abc"}
    cached = _client(ss, conn)
    await cached.get_paper("abc")
    row = conn.execute("SELECT params_json FROM api_cache").fetchone()
    assert "abc" in row["params_json"]


# ── Offline detector integration tests ────────────────────────────


async def test_cache_skips_fetch_when_detector_says_offline(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    detector = AsyncMock(spec=OfflineDetector)
    detector.is_online.return_value = False
    key = make_cache_key("get_paper", {"paper_id": "off-test-1"})
    _populate_cache(
        conn, key, "get_paper", {"paper_id": "off-test-1"}, {"paperId": "old"}, stale=True
    )
    cached = CachedSemanticScholarClient(ss, conn, ttl_days=30, offline=detector)
    data, meta = await cached.get_paper("off-test-1")
    assert data == {"paperId": "old"}
    assert meta.source == "offline_cache"
    ss.get_paper.assert_not_called()


async def test_cache_raises_offline_when_detector_says_offline_and_no_cache(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    detector = AsyncMock(spec=OfflineDetector)
    detector.is_online.return_value = False
    cached = CachedSemanticScholarClient(ss, conn, ttl_days=30, offline=detector)
    with pytest.raises(OfflineError):
        await cached.get_paper("off-test-2")


async def test_cache_marks_offline_on_api_failure(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.side_effect = APIServerError("server error")
    detector = AsyncMock(spec=OfflineDetector)
    detector.is_online.return_value = True
    key = make_cache_key("get_paper", {"paper_id": "off-test-3"})
    _populate_cache(
        conn, key, "get_paper", {"paper_id": "off-test-3"}, {"paperId": "old"}, stale=True
    )
    cached = CachedSemanticScholarClient(ss, conn, ttl_days=30, offline=detector)
    data, meta = await cached.get_paper("off-test-3")
    assert data == {"paperId": "old"}
    assert meta.source == "offline_cache"
    detector.mark_offline.assert_awaited_once()


async def test_cache_returns_stale_on_rate_limit(tmp_path: Path) -> None:
    """429 returns stale cache without marking offline."""
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.side_effect = APIRateLimitError("rate limited")
    detector = AsyncMock(spec=OfflineDetector)
    detector.is_online.return_value = True
    key = make_cache_key("get_paper", {"paper_id": "rate-test-1"})
    _populate_cache(
        conn, key, "get_paper", {"paper_id": "rate-test-1"}, {"paperId": "stale"}, stale=True
    )
    cached = CachedSemanticScholarClient(ss, conn, ttl_days=30, offline=detector)
    data, meta = await cached.get_paper("rate-test-1")
    assert data == {"paperId": "stale"}
    assert meta.source == "offline_cache"
    # Rate-limited is not offline — server is up
    detector.mark_offline.assert_not_awaited()


async def test_corrupt_cache_row_treated_as_miss(tmp_path: Path) -> None:
    """Corrupt data_json in cache should be treated as cache miss, not crash."""
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.return_value = {"paperId": "fresh"}
    key = make_cache_key("get_paper", {"paper_id": "corrupt1"})
    # Insert row with corrupt JSON
    conn.execute(
        "INSERT INTO api_cache (cache_key, endpoint, params_json, data_json, fetched_at, ttl_until) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (key, "get_paper", "{}", "not valid json", "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z"),
    )
    conn.commit()
    cached = _client(ss, conn)
    data, _ = await cached.get_paper("corrupt1")
    assert data == {"paperId": "fresh"}
    ss.get_paper.assert_awaited_once()


async def test_cache_raises_on_rate_limit_with_no_cache(tmp_path: Path) -> None:
    """429 with no cached data raises APIRateLimitError."""
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    ss.get_paper.side_effect = APIRateLimitError("rate limited")
    detector = AsyncMock(spec=OfflineDetector)
    detector.is_online.return_value = True
    cached = CachedSemanticScholarClient(ss, conn, ttl_days=30, offline=detector)
    with pytest.raises(APIRateLimitError):
        await cached.get_paper("missing")


async def test_cache_uses_settings_force_offline_by_default(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    cached = CachedSemanticScholarClient(ss, conn, ttl_days=30)
    assert hasattr(cached, "offline")
    assert cached.offline._force is False


def test_cache_wrapper_ttl_defaults_to_settings(tmp_path: Path) -> None:
    """ttl_days omitted → settings.cache_ttl_days is the policy (issue: knob was inert)."""
    from scholar_paper_cli.config import get_settings

    conn = _conn(tmp_path)
    ss = AsyncMock(spec=SemanticScholarClient)
    cached = CachedSemanticScholarClient(ss, conn)
    assert cached.ttl_days == get_settings().cache_ttl_days


def test_entity_ttl_until_matches_settings() -> None:
    """Entity freshness deadlines derive from the same TTL policy as the wrapper."""
    from scholar_paper_cli.config import get_settings
    from scholar_paper_cli.storage.cache import entity_ttl_until

    now = datetime.now(UTC)
    deadline = entity_ttl_until(now)
    expected = now + timedelta(days=get_settings().cache_ttl_days)
    assert abs((deadline - expected).total_seconds()) < 1
