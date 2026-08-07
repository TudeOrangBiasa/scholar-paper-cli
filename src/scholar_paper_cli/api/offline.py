"""Offline detector: probe SS API with grace period."""

import asyncio
import time
from collections.abc import Callable

import httpx


class OfflineDetector:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        timeout: float = 2.0,
        grace_seconds: float = 60.0,
        force_offline: bool = False,
        time_func: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = http_client
        self._timeout = timeout
        self._grace = grace_seconds
        self._force = force_offline
        self._time = time_func
        self._last_probe_at: float | None = None
        self._last_result: bool = True
        self._lock = asyncio.Lock()

    async def is_online(self) -> bool:
        if self._force:
            return False
        now = self._time()
        if self._last_probe_at is not None and (now - self._last_probe_at) < self._grace:
            return self._last_result
        async with self._lock:
            if (
                self._last_probe_at is not None
                and (self._time() - self._last_probe_at) < self._grace
            ):
                return self._last_result
            self._last_result = await self._probe()
            self._last_probe_at = self._time()
            return self._last_result

    async def mark_offline(self) -> None:
        async with self._lock:
            self._last_result = False
            self._last_probe_at = self._time()

    async def _probe(self) -> bool:
        try:
            await self._client.head("/", timeout=self._timeout)
            return True
        except httpx.RequestError:
            return False
