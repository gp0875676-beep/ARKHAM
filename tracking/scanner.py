# tracking/scanner.py — main polling loop over all enabled chains.
"""Scanner orchestrator. Polls each adapter on POLL_INTERVAL_SECONDS,
applies filters, dedups, routes qualifying events to the AlertManager,
and periodically evaluates 1h/24h alert outcomes for replay/calibration."""
import asyncio

from chains.base import ChainAdapter
from alerts.manager import AlertManager
from tracking.whale_list import WhaleList
from tracking.filters import passes_threshold
from db.models import AlertOutcomeRepo
from utils.usd import PriceOracle
from utils.logger import get_logger
from config import get_settings

log = get_logger(__name__)

# Run the outcome evaluator every N scan cycles rather than adding a second
# scheduler/process — no new infrastructure, per Phase 7 hard constraints.
OUTCOME_EVAL_EVERY_N_CYCLES = 10


class Scanner:
    """Drives the whole pipeline. One instance per process."""

    def __init__(self, adapters: dict[str, ChainAdapter], alert_manager: AlertManager) -> None:
        self.adapters = adapters
        self.alert_manager = alert_manager
        self.whale_list = WhaleList()
        self.settings = get_settings()
        self.running = False
        self.last_blocks = {}  # chain -> block_number
        self.outcome_repo = AlertOutcomeRepo()
        self.oracle = PriceOracle()
        self.cycle_count = 0

    async def start(self) -> None:
        self.running = True
        log.info("Scanner started. Polling every {}s", self.settings.poll_interval_seconds)
        for chain, adapter in self.adapters.items():
            block = await adapter.get_latest_block()
            if block > 0:
                self.last_blocks[chain] = max(0, block - 10)
                log.info("Starting {} scan from block {}", chain, self.last_blocks[chain])
            else:
                self.last_blocks[chain] = 0
                log.warning("Could not fetch latest block for {}. Defaulting to 0.", chain)

        while self.running:
            try:
                await self._scan_cycle()
                self.cycle_count += 1
                if self.cycle_count % OUTCOME_EVAL_EVERY_N_CYCLES == 0:
                    await self._evaluate_outcomes()
            except Exception as e:
                log.error("Scanner cycle error: {}", e)
            await asyncio.sleep(self.settings.poll_interval_seconds)

    async def stop(self) -> None:
        self.running = False

    async def _scan_cycle(self) -> None:
        for chain, adapter in self.adapters.items():
            wallets = await self.whale_list.get_wallets_for_chain(chain)
            if not wallets:
                continue
            latest_block = await adapter.get_latest_block()
            if latest_block <= self.last_blocks[chain]:
                continue
            tasks = [adapter.fetch_recent_txs(w, self.last_blocks[chain]) for w in wallets]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    log.error("Error fetching txs: {}", res)
                    continue
                for event in res:
                    if passes_threshold(event, self.settings.min_usd_threshold):
                        await self.alert_manager.handle(event)
            self.last_blocks[chain] = latest_block

    async def _evaluate_outcomes(self) -> None:
        """Checks price movement 1h and 24h after alerts fired (Phase 7, Module 3).
        This only evaluates alerts the system already sent for real — it is
        NOT a historical strategy backtest."""
        try:
            pending_1h = await self.outcome_repo.get_alerts_needing_1h()
            for p in pending_1h:
                current_price = await self.oracle.get_usd_price(p["chain"], p["token_address"] or "0x0")
                if current_price is not None:
                    await self.outcome_repo.update_price_1h(p["id"], current_price)

            pending_24h = await self.outcome_repo.get_alerts_needing_24h()
            for p in pending_24h:
                current_price = await self.oracle.get_usd_price(p["chain"], p["token_address"] or "0x0")
                if current_price is not None:
                    await self.outcome_repo.update_price_24h(p["id"], current_price)
        except Exception as e:
            log.error("Outcome evaluation failed: {}", e)
