# utils/usd.py — USD price lookup via Coingecko (never Binance).
"""Token USD price oracle. Strictly Coingecko (or another non-Binance source)."""
import time
import httpx

from utils.logger import get_logger
from config import get_settings

log = get_logger(__name__)

# Mapping of internal chain names to Coingecko asset platform IDs
ASSET_PLATFORMS = {
    "ethereum": "ethereum",
    "bsc": "binance-smart-chain",
    "polygon": "polygon-pos",
    "arbitrum": "arbitrum-one"
}

# Mapping of internal chain names to Coingecko native token IDs
NATIVE_TOKEN_IDS = {
    "ethereum": "ethereum",
    "bsc": "binancecoin",
    "polygon": "matic-network",
    "arbitrum": "arbitrum"
}


class PriceOracle:
    """Async price oracle with TTL cache. Returns None if price unavailable — never fakes."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=10.0)
        self.cache = {}  # token_addr -> (price, timestamp)
        self.ttl = self.settings.price_cache_ttl_seconds

    async def get_usd_price(self, chain: str, token_address: str) -> float | None:
        token_address = token_address.lower()
        cache_key = f"{chain}:{token_address}"
 
        if cache_key in self.cache:
            price, ts = self.cache[cache_key]
            if time.time() - ts < self.ttl:
                return price

        try:
            if token_address == "0x0":
                # Native asset (ETH, BNB, MATIC, ARB)
                token_id = NATIVE_TOKEN_IDS.get(chain)
                if not token_id: return None
 
                url = f"{self.settings.coingecko_base_url}/simple/price"
                params = {"ids": token_id, "vs_currencies": "usd"}
                resp = await self.client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                price = data.get(token_id, {}).get("usd")
            else:
                # ERC20 / BEP20 / etc Token
                platform = ASSET_PLATFORMS.get(chain)
                if not platform: return None
 
                url = f"{self.settings.coingecko_base_url}/simple/token_price/{platform}"
                params = {"contract_addresses": token_address, "vs_currencies": "usd"}
                resp = await self.client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                price = data.get(token_address, {}).get("usd")

            if price is not None:
                self.cache[cache_key] = (float(price), time.time())
                return float(price)
            return None
        except Exception as e:
            log.warning("Price fetch failed for {} on {}: {}", token_address, chain, e)
            return None

    async def close(self) -> None:
        await self.client.aclose()
