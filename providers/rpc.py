# providers/rpc.py — minimal, rate-limited JSON-RPC client over httpx.
"""Direct JSON-RPC client used as a failover path when an explorer API
(Etherscan/BscScan/PolygonScan/Arbiscan) is unavailable or rate-limited.

Standard JSON-RPC cannot fetch historical ERC-20 transfers for a wallet
without scanning every block, which is too slow for this project's scope.
So this client is only relied on for get_latest_block() failover — it never
fabricates transaction history.
"""
from __future__ import annotations

import asyncio

import httpx

from utils.rate_limiter import RateLimiter
from utils.logger import get_logger
from config import get_settings

log = get_logger(__name__)


class RpcClient:
    """Async JSON-RPC 2.0 client with rate limiting and retries."""

    def __init__(self, rpc_url: str, rpm: int, timeout: float = 15.0) -> None:
        self.rpc_url = rpc_url
        self.limiter = RateLimiter(rpm)
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self.request_id = 0
        self.settings = get_settings()

    async def call(self, method: str, params: list | None = None) -> object | None:
        """Execute a JSON-RPC call and return the `result` field, or None on
        failure (never fabricates a result). Retries with exponential backoff."""
        if not self.rpc_url:
            return None

        self.request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": self.request_id,
        }

        for attempt in range(self.settings.backoff_retries):
            await self.limiter.acquire()
            try:
                resp = await self.client.post(self.rpc_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if "error" in data and data["error"]:
                    log.error("RPC error on {}: {}", method, data["error"])
                    return None
                return data.get("result")
            except (httpx.HTTPError, asyncio.TimeoutError) as e:
                log.warning("RPC call {} failed (attempt {}): {}", method, attempt + 1, e)
                if attempt == self.settings.backoff_retries - 1:
                    return None
                wait = min(
                    self.settings.backoff_base_seconds ** attempt,
                    self.settings.backoff_max_seconds,
                )
                await asyncio.sleep(wait)
        return None

    async def get_block_number(self) -> int | None:
        result = await self.call("eth_blockNumber")
        return int(result, 16) if result else None

    async def get_transaction_receipt(self, tx_hash: str) -> dict | None:
        return await self.call("eth_getTransactionReceipt", [tx_hash])

    async def close(self) -> None:
        await self.client.aclose()
