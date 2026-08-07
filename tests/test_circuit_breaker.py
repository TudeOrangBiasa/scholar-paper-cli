"""Tests for CircuitBreaker."""

import time

import pytest

from scholar_paper_cli.api.circuit_breaker import CircuitBreaker
from scholar_paper_cli.exceptions import APIServerError


async def test_initial_state_closed() -> None:
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=60.0)
    assert cb.state == "closed"
    assert cb.failures == 0


async def test_failure_increments_counter() -> None:
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=60.0)

    async def fail() -> None:
        raise ValueError("nope")

    with pytest.raises(ValueError):
        await cb.call(fail())
    assert cb.failures == 1
    assert cb.state == "closed"


async def test_opens_after_threshold_failures() -> None:
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=60.0)

    async def fail() -> None:
        raise ValueError("nope")

    for _ in range(3):
        with pytest.raises(ValueError):
            await cb.call(fail())
    assert cb.state == "open"
    assert cb.opened_at is not None


async def test_call_raises_when_open() -> None:
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=60.0)
    cb.state = "open"
    cb.opened_at = time.monotonic()

    async def ok() -> str:
        return "ok"

    with pytest.raises(APIServerError, match="circuit breaker open"):
        await cb.call(ok())


async def test_success_resets_counter() -> None:
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=60.0)

    async def fail() -> None:
        raise ValueError("nope")

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(fail())
    assert cb.failures == 2

    async def ok() -> str:
        return "ok"

    result = await cb.call(ok())
    assert result == "ok"
    assert cb.failures == 0
    assert cb.state == "closed"


async def test_open_circuit_allows_call_after_reset_timeout() -> None:
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=60.0)
    cb.state = "open"
    cb.opened_at = time.monotonic() - 120.0

    async def ok() -> str:
        return "ok"

    result = await cb.call(ok())
    assert result == "ok"
    assert cb.state == "closed"


async def test_success_in_half_open_closes_circuit() -> None:
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=60.0)
    cb.state = "half_open"

    async def ok() -> str:
        return "ok"

    result = await cb.call(ok())
    assert result == "ok"
    assert cb.state == "closed"
