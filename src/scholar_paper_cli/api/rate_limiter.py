"""Token bucket rate limiter."""

import asyncio
import time


class TokenBucket:
    def __init__(self, rate: float, capacity: int) -> None:
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()

    async def acquire(self, n: int = 1) -> None:
        while True:
            self._refill()
            if self.tokens >= n:
                self.tokens -= n
                return
            wait = (n - self.tokens) / self.rate
            await asyncio.sleep(wait)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(float(self.capacity), self.tokens + elapsed * self.rate)
        self.last_refill = now
