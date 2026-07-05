# chains/base.py — abstract ChainAdapter interface (adapter pattern).
"""All chains implement this interface so the scanner is chain-agnostic."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class TxEvent:
    """Normalized cross-chain transaction event."""
    chain: str
    tx_hash: str
    block_number: int
    timestamp: int
    from_address: str
    to_address: str
    token_address: Optional[str]   # None = native asset transfer
    token_symbol: str
    amount_raw: int  # smallest unit (wei)
    amount_human: float
    usd_value: Optional[float]     # None if price unavailable (NEVER faked)
    direction: str  # "in" | "out" | "internal"
    explorer_url: str


class ChainAdapter(ABC):
    """One adapter per chain. Same output schema (`TxEvent`)."""

    chain: str = "abstract"

    @abstractmethod
    async def fetch_recent_txs(self, wallet: str, since_block: int) -> List[TxEvent]:
        """Return all txs for `wallet` since `since_block`. Empty list = none found."""
        raise NotImplementedError

    @abstractmethod
    async def get_latest_block(self) -> int:
        raise NotImplementedError

    @abstractmethod
    async def is_exchange_address(self, address: str) -> bool:
        raise NotImplementedError
