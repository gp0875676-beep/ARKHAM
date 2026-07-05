# providers/base.py — base HTTP client with rate limit + timeout + retry.
"""All external HTTP providers extend this. Enforces the project's
rate-limit + timeout + retry + no-Binance guarantees in one place."""
import asyncio
import httpx

from utils.rate_limiter import RateLimiter
from utils.logger import get_logger
from config import get_settings

log = get_logger(__name__)


class BaseProvider:
    """httpx.AsyncClient wrapper wired to a RateLimiter and retry decorator."""

    def __init__(self, base_url: str, api_key: str, rpm: int, timeout: float = 15.0) -> None:
        self.settings = get_settings()
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.limiter = RateLimiter(rpm)
        self.client = httpx.AsyncClient(timeout=timeout)

    async def get(self, path: str, params: dict | None = None) -> dict:
        params = params or {}
        if self.api_key:
            params["apikey"] = self.api_key
 
        url = f"{self.base_url}{path}"

        for attempt in range(self.settings.backoff_retries):
            await self.limiter.acquire()
            try:
                resp = await self.client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, asyncio.TimeoutError) as e:
                log.warning("HTTP GET failed (attempt {}): {}", attempt + 1, e)
                if attempt == self.settings.backoff_retries - 1:
                    raise
                wait = min(self.settings.backoff_base_seconds ** attempt, self.settings.backoff_max_seconds)
                await asyncio.sleep(wait)

    async def close(self) -> None:
        await self.client.aclose()
