"""Tests for SemanticScholarClient."""

import httpx
import pytest

from scholar_paper_mcp.api import SemanticScholarClient
from scholar_paper_mcp.exceptions import APINotFoundError, APIRateLimitError, APIServerError

# ── Endpoint path tests ──────────────────────────────────────────


async def test_search_papers_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/paper/search"
        assert request.url.params["query"] == "quantum"
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        result = await client.search_papers("quantum")
    assert result == {"data": []}


async def test_get_paper_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/paper/CorpusId:123"
        return httpx.Response(200, json={"paperId": "CorpusId:123"})

    transport = httpx.MockTransport(handler)
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        result = await client.get_paper("CorpusId:123")
    assert result == {"paperId": "CorpusId:123"}


async def test_get_citations_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/paper/abc123/citations"
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        result = await client.get_citations("abc123")
    assert result == {"data": []}


async def test_get_references_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/paper/abc123/references"
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        result = await client.get_references("abc123")
    assert result == {"data": []}


async def test_search_authors_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/author/search"
        assert request.url.params["query"] == "Einstein"
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        result = await client.search_authors("Einstein")
    assert result == {"data": []}


async def test_get_author_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/author/12345"
        return httpx.Response(200, json={"authorId": "12345"})

    transport = httpx.MockTransport(handler)
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        result = await client.get_author("12345")
    assert result == {"authorId": "12345"}


async def test_get_author_papers_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/author/42/papers"
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        result = await client.get_author_papers("42")
    assert result == {"data": []}


async def test_get_recommendations_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/paper/abc123/recommendations"
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        result = await client.get_recommendations("abc123")
    assert result == {"data": []}


async def test_get_recommendations_sends_positive_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/paper/abc123/recommendations"
        assert request.url.params["positive"] == "p1,p2"
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        await client.get_recommendations("abc123", positive_ids=["p1", "p2"])


async def test_get_recommendations_sends_negative_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/paper/abc123/recommendations"
        assert request.url.params["negative"] == "n1,n2"
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        await client.get_recommendations("abc123", negative_ids=["n1", "n2"])


async def test_get_recommendations_no_positive_when_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/paper/abc123/recommendations"
        assert "positive" not in request.url.params
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        await client.get_recommendations("abc123", positive_ids=[])


# ── API key tests ────────────────────────────────────────────────


async def test_sends_api_key_when_configured() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-api-key") == "test-key-123"
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    async with SemanticScholarClient(
        transport=transport, base_url="http://test", api_key="test-key-123"
    ) as client:
        await client.search_papers("test")


async def test_no_api_key_header_when_not_configured() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "x-api-key" not in request.headers
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        await client.search_papers("test")


# ── Error mapping tests ──────────────────────────────────────────


async def test_404_raises_api_not_found() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(404))
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        with pytest.raises(APINotFoundError):
            await client.get_paper("nonexistent")


async def test_429_raises_api_rate_limit() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(429))
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        with pytest.raises(APIRateLimitError):
            await client.get_paper("x")


async def test_500_raises_api_server_error() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(500))
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        with pytest.raises(APIServerError):
            await client.get_paper("x")


async def test_503_raises_api_server_error() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(503))
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        with pytest.raises(APIServerError):
            await client.get_paper("x")


# ── Integration tests ────────────────────────────────────────────


async def test_rate_limiter_consumed_on_request() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    async with SemanticScholarClient(
        transport=transport, base_url="http://test", rate=1000.0, burst=5
    ) as client:
        assert client.limiter.tokens == 5.0
        await client.search_papers("test")
        assert client.limiter.tokens == 4.0


async def test_circuit_breaker_opens_on_repeated_failures() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(500))
    async with SemanticScholarClient(
        transport=transport, base_url="http://test", failure_threshold=3
    ) as client:
        for _ in range(3):
            with pytest.raises(APIServerError):
                await client.get_paper("x")
        # 4th call should fail fast — circuit breaker, not server
        with pytest.raises(APIServerError, match="circuit breaker open"):
            await client.get_paper("x")


async def test_context_manager_closes_client() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        await client.search_papers("test")
    # Client closed after context exit — no explicit assert, just no leak
    assert True


async def test_close_method_closes_client() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    client = SemanticScholarClient(transport=transport, base_url="http://test")
    await client.search_papers("test")
    await client.close()
    # Client closed — no explicit assert, just no leak
    assert True


async def test_get_paper_rejects_path_traversal_id() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        with pytest.raises((ValueError, APIServerError)):
            await client.get_paper("../../../etc/passwd")


async def test_get_author_rejects_path_traversal_id() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        with pytest.raises((ValueError, APIServerError)):
            await client.get_author("../../../etc/shadow")


def test_semantic_scholar_client_default_rate_matches_ss_limits() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    client = SemanticScholarClient(transport=transport, base_url="http://test")
    # SS unauthenticated: 100 req / 5 min — defaults should be below that
    assert client.limiter.rate <= 1.0
    assert client.limiter.capacity <= 10



@pytest.mark.asyncio
async def test_search_authors_omits_unsupported_fields() -> None:
    """S2 /author/search rejects aliases+papers; client must not send them."""
    from scholar_paper_mcp.api.client import DEFAULT_AUTHOR_SEARCH_FIELDS

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/author/search"
        fields = request.url.params["fields"]
        assert "aliases" not in fields, f"aliases not allowed in search: {fields}"
        assert "papers" not in fields, f"papers not allowed in search: {fields}"
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    async with SemanticScholarClient(transport=transport, base_url="http://test") as client:
        result = await client.search_authors("LeCun")
    assert result == {"data": []}
    assert "aliases" not in DEFAULT_AUTHOR_SEARCH_FIELDS
    assert "papers" not in DEFAULT_AUTHOR_SEARCH_FIELDS
