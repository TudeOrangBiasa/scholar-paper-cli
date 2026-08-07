"""Tests for TokenBucket rate limiter."""

import time

import pytest

from scholar_paper_cli.api.rate_limiter import TokenBucket


def test_initial_tokens_equals_capacity() -> None:
    bucket = TokenBucket(rate=1.0, capacity=10)
    assert bucket.tokens == 10.0
    assert bucket.rate == 1.0


async def test_acquire_decrements_tokens() -> None:
    bucket = TokenBucket(rate=10.0, capacity=10)
    await bucket.acquire(1)
    assert bucket.tokens == 9.0


async def test_acquire_decrements_by_n() -> None:
    bucket = TokenBucket(rate=10.0, capacity=10)
    await bucket.acquire(3)
    assert bucket.tokens == 7.0


def test_refill_increases_tokens() -> None:
    bucket = TokenBucket(rate=10.0, capacity=100)
    bucket.tokens = 0.0
    bucket.last_refill = time.monotonic() - 1.0
    bucket._refill()
    assert bucket.tokens == pytest.approx(10.0, rel=0.2)


def test_refill_caps_at_capacity() -> None:
    bucket = TokenBucket(rate=10.0, capacity=10)
    bucket.tokens = 5.0
    bucket.last_refill = time.monotonic() - 10.0
    bucket._refill()
    assert bucket.tokens == 10.0
