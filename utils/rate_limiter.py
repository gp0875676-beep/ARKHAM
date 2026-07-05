# utils/rate_limiter.py — async token-bucket limiter, one per provider.
"""Per-provider async rate limiter using the token-bucket algorithm."""
import asyncio
import time


class RateLimiter:
    """Async token-bucket limiter. Call `await limiter.acquire()` before each request."""

    def __init__(self, rpm: int) -> None:
        self.rpm = rpm
        self.min_interval = 60.0 / rpm if rpm > 0 else 0
        self.last_call = 0.0
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        if self.min_interval == 0:
            return
        async with self.lock:
            now = time.monotonic()
            wait = self.last_call + self.min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self.last_call = time.monotonic()
