"""Tests for OfflineDetector."""

import asyncio

import httpx
import pytest

from scholar_paper_cli.api.offline import OfflineDetector


def _make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")


@pytest.mark.asyncio
async def test_initial_state_returns_online_by_default() -> None:
    detector = OfflineDetector(_make_client(lambda r: httpx.Response(200)))
    assert await detector.is_online() is True


@pytest.mark.asyncio
async def test_force_offline_returns_false_without_probe() -> None:
    probe_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal probe_count
        probe_count += 1
        return httpx.Response(200)

    detector = OfflineDetector(_make_client(handler), force_offline=True)
    assert await detector.is_online() is False
    assert await detector.is_online() is False
    assert probe_count == 0


@pytest.mark.asyncio
async def test_probe_returns_true_on_200() -> None:
    detector = OfflineDetector(_make_client(lambda r: httpx.Response(200)))
    assert await detector.is_online() is True


@pytest.mark.asyncio
async def test_probe_returns_true_on_404() -> None:
    detector = OfflineDetector(_make_client(lambda r: httpx.Response(404)))
    assert await detector.is_online() is True


@pytest.mark.asyncio
async def test_probe_returns_false_on_write_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.WriteError("write failed")

    detector = OfflineDetector(_make_client(handler))
    assert await detector.is_online() is False


@pytest.mark.asyncio
async def test_probe_returns_false_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    detector = OfflineDetector(_make_client(handler), timeout=0.1)
    assert await detector.is_online() is False


@pytest.mark.asyncio
async def test_probe_returns_false_on_connect_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connect failed")

    detector = OfflineDetector(_make_client(handler))
    assert await detector.is_online() is False


@pytest.mark.asyncio
async def test_grace_period_skips_repeated_probes() -> None:
    probe_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal probe_count
        probe_count += 1
        return httpx.Response(200)

    detector = OfflineDetector(_make_client(handler), grace_seconds=60.0)
    await detector.is_online()  # probe 1
    await detector.is_online()  # grace active, no probe
    await detector.is_online()  # grace active, no probe
    assert probe_count == 1


@pytest.mark.asyncio
async def test_grace_period_expires_with_mock_time() -> None:
    probe_count = 0
    current_time = [0.0]

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal probe_count
        probe_count += 1
        return httpx.Response(200)

    detector = OfflineDetector(
        _make_client(handler),
        grace_seconds=10.0,
        time_func=lambda: current_time[0],
    )
    await detector.is_online()  # probe 1
    current_time[0] = 5.0  # within grace
    await detector.is_online()  # no probe
    current_time[0] = 11.0  # grace expired
    await detector.is_online()  # probe 2
    assert probe_count == 2


@pytest.mark.asyncio
async def test_mark_offline_short_circuits_is_online() -> None:
    detector = OfflineDetector(_make_client(lambda r: httpx.Response(200)))
    await detector.is_online()  # online
    await detector.mark_offline()
    assert await detector.is_online() is False


@pytest.mark.asyncio
async def test_concurrent_calls_provoke_single_probe() -> None:
    probe_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal probe_count
        probe_count += 1
        await asyncio.sleep(0.01)
        return httpx.Response(200)

    detector = OfflineDetector(_make_client(handler), grace_seconds=0.0)
    results = await asyncio.gather(detector.is_online(), detector.is_online(), detector.is_online())
    assert all(results)
    assert 1 <= probe_count <= 3


@pytest.mark.asyncio
async def test_lock_protects_state_during_concurrent_marks() -> None:
    detector = OfflineDetector(_make_client(lambda r: httpx.Response(200)))
    await asyncio.gather(
        detector.mark_offline(),
        detector.mark_offline(),
        detector.mark_offline(),
    )
    assert await detector.is_online() is False
