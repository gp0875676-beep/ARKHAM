# tracking/wallet_profile.py — builds behavioral profile from historical DB data.
"""Computes a wallet profile using ONLY data already stored in Postgres.
This is a real signal from real stored data — explicitly labeled behavioral
stats, not a marketing "wallet DNA" claim and not a live indexing claim."""
from dataclasses import dataclass

from db.models import TransactionRepo
from tracking.exchange_addresses import ExchangeDirectory
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class WalletProfile:
    wallet: str
    first_seen: int | None
    tx_count: int
    avg_tx_size_usd: float
    holding_duration_estimate_hrs: float | None
    rotation_frequency_per_week: float
    exchange_interaction_count: int


class WalletProfileBuilder:
    def __init__(self) -> None:
        self.tx_repo = TransactionRepo()
        self.exchange_dir = ExchangeDirectory()

    async def build_profile(self, chain: str, wallet: str) -> WalletProfile | None:
        wallet = wallet.lower()
        stats = await self.tx_repo.get_profile_stats(chain, wallet)
        if not stats or stats["tx_count"] == 0:
            return None

        # Basic stats
        first_seen = stats["first_seen"]
        tx_count = stats["tx_count"]
        avg_usd = float(stats["avg_usd"]) if stats["avg_usd"] else 0.0

        # Rotation frequency (txs per week, trailing 30 days)
        count_30d = await self.tx_repo.get_30d_tx_count(chain, wallet)
        rotation_freq = round(count_30d / 4.29, 2)  # 30 days ~= 4.29 weeks

        # Holding duration & exchange interactions need from/to addresses,
        # which get_wallet_raw_history() provides (see db/models.py correction).
        raw_history = await self.tx_repo.get_wallet_raw_history(chain, wallet)
        pending_inflows: dict[str, list[int]] = {}  # token_symbol -> list of timestamps
        hold_times_secs: list[int] = []
        exchange_interactions = 0

        for tx in raw_history:
            if self.exchange_dir.is_exchange(chain, tx["from_address"]) or self.exchange_dir.is_exchange(chain, tx["to_address"]):
                exchange_interactions += 1

            token = tx["token_symbol"]
            ts = tx["timestamp"]
            if tx["direction"] == "in":
                pending_inflows.setdefault(token, []).append(ts)
            elif tx["direction"] == "out":
                if token in pending_inflows and pending_inflows[token]:
                    # Match with the oldest pending inflow (FIFO)
                    in_ts = pending_inflows[token].pop(0)
                    hold_time = ts - in_ts
                    if hold_time > 0:
                        hold_times_secs.append(hold_time)

        avg_hold_hrs = None
        if hold_times_secs:
            avg_secs = sum(hold_times_secs) / len(hold_times_secs)
            avg_hold_hrs = round(avg_secs / 3600, 2)

        return WalletProfile(
            wallet=wallet,
            first_seen=first_seen,
            tx_count=tx_count,
            avg_tx_size_usd=round(avg_usd, 2),
            holding_duration_estimate_hrs=avg_hold_hrs,
            rotation_frequency_per_week=rotation_freq,
            exchange_interaction_count=exchange_interactions
        )
