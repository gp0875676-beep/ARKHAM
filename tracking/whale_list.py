# tracking/whale_list.py — load + refresh tracked whale wallets.
"""Whale list loader. Merges static env-based seed list with the DB-backed
dynamic watchlist. Returns a dict[chain -> list[wallet]]."""
from config import get_settings
from db.models import WatchlistRepo


class WhaleList:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.repo = WatchlistRepo()

    def _get_env_wallets(self, chain: str) -> list[str]:
        wallets_str = ""
        if chain == "ethereum":
            wallets_str = self.settings.whale_wallets_eth
        elif chain == "bsc":
            wallets_str = self.settings.whale_wallets_bsc
        elif chain == "polygon":
            wallets_str = self.settings.whale_wallets_polygon
        elif chain == "arbitrum":
            wallets_str = self.settings.whale_wallets_arbitrum

        if not wallets_str:
            return []
        return [w.strip().lower() for w in wallets_str.split(",") if w.strip()]

    async def get_wallets_for_chain(self, chain: str) -> list[str]:
        env_wallets = self._get_env_wallets(chain)
        db_wallets = []
        try:
            db_wallets_raw = await self.repo.list_active(chain)
            db_wallets = [w['wallet'].lower() for w in db_wallets_raw]
        except Exception:
            # Fallback gracefully to env-only if DB is unavailable
            pass
        # Union of env and DB, case-insensitive
        return list(set(env_wallets + db_wallets))

    async def is_tracked(self, chain: str, address: str) -> bool:
        if not address:
            return False
        wallets = await self.get_wallets_for_chain(chain)
        return address.lower() in wallets
