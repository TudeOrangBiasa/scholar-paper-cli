"""Circuit breaker for upstream calls."""

import asyncio
import time

from scholar_paper_cli.exceptions import APIServerError


class CircuitBreaker:
    def __init__(self, failure_threshold: int, reset_timeout: float) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.state = "closed"
        self.opened_at: float | None = None
        self._lock = asyncio.Lock()

    async def call(self, coro):
        async with self._lock:
            if self.state == "open":
                if (
                    self.opened_at is not None
                    and time.monotonic() - self.opened_at >= self.reset_timeout
                ):
                    self.state = "half_open"
                else:
                    raise APIServerError("circuit breaker open")
        try:
            result = await coro
        except Exception:
            await self._on_failure()
            raise
        else:
            await self._on_success()
            return result

    async def _on_failure(self) -> None:
        async with self._lock:
            if self.state == "half_open":
                self.state = "open"
                self.opened_at = time.monotonic()
                return
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.state = "open"
                self.opened_at = time.monotonic()

    async def _on_success(self) -> None:
        async with self._lock:
            self.failures = 0
            self.state = "closed"
            self.opened_at = None
