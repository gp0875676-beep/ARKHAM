# utils/retry.py — tenacity-backed async retry with exponential backoff.
"""Retry decorator factory using tenacity."""
import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


def with_retry(retries: int = 5, base: float = 1.5, max_wait: float = 60.0, exceptions=(Exception,)):
    """Decorator: exponential backoff over the given exception types."""
    def _wrap(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def _inner(*args, **kwargs) -> T:
            for attempt in range(retries):
                try:
                    return await fn(*args, **kwargs)
                except exceptions as e:
                    if attempt == retries - 1:
                        raise
                    wait = min(base ** attempt, max_wait)
                    await asyncio.sleep(wait)
        return _inner
    return _wrap
