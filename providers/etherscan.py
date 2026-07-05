# providers/etherscan.py — Etherscan-family API client (works for all *scan.com).
"""Etherscan-compatible client. Same shape powers BscScan/PolygonScan/Arbiscan."""
from providers.base import BaseProvider


class EtherscanClient(BaseProvider):
    """Fetches normal + internal + ERC-20 txs for a wallet."""

    async def get_normal_txs(self, wallet: str, start_block: int) -> list:
        params = {
            "module": "account",
            "action": "txlist",
            "address": wallet,
            "startblock": start_block,
            "endblock": 99999999,
            "sort": "asc"
        }
        data = await self.get("", params)
        if data.get("status") == "1":
            return data.get("result", [])
        return []

    async def get_erc20_transfers(self, wallet: str, start_block: int) -> list:
        params = {
            "module": "account",
            "action": "tokentx",
            "address": wallet,
            "startblock": start_block,
            "endblock": 99999999,
            "sort": "asc"
        }
        data = await self.get("", params)
        if data.get("status") == "1":
            return data.get("result", [])
        return []
