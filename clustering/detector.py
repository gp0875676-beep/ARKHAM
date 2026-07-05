# clustering/detector.py — heuristic wallet clustering engine.
"""Detects wallets likely owned by the same entity via:
1) shared funding source (common funder)
2) direct transfers between tracked whales
"""
from typing import List
import asyncio

from db.models import TransactionRepo, ClusterRepo
from tracking.whale_list import WhaleList
from tracking.exchange_addresses import ExchangeDirectory
from utils.logger import get_logger
from config import get_settings

log = get_logger(__name__)


class ClusterDetector:
    def __init__(self) -> None:
        self.tx_repo = TransactionRepo()
        self.cluster_repo = ClusterRepo()
        self.whale_list = WhaleList()
        self.exchange_dir = ExchangeDirectory()
        self.settings = get_settings()

    async def evaluate_event(self, event) -> int | None:
        """Evaluates a transaction event to find or update clusters."""
        try:
            # Heuristic 1: Direct transfer between two tracked whales
            from_tracked = await self.whale_list.is_tracked(event.chain, event.from_address)
            to_tracked = await self.whale_list.is_tracked(event.chain, event.to_address)

            if from_tracked and to_tracked:
                return await self.cluster_repo.assign_to_cluster(
                    event.chain, [event.from_address, event.to_address]
                )

            # Heuristic 2: Shared funding source
            if event.direction == "in" and to_tracked:
                funder = event.from_address

                if self.exchange_dir.is_exchange(event.chain, funder):
                    return None

                funded_wallets = await self.tx_repo.get_wallets_funded_by(event.chain, funder)

                current_wallet = event.to_address
                if current_wallet not in funded_wallets:
                    funded_wallets.append(current_wallet)

                if len(funded_wallets) >= 2:
                    log.info("Cluster detected via shared funder {} for wallets: {}", funder, funded_wallets)
                    return await self.cluster_repo.assign_to_cluster(event.chain, funded_wallets)

        except Exception as e:
            log.error("Cluster evaluation failed: {}", e)

        return None
