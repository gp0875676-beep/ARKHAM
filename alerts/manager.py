# alerts/manager.py — orchestrates alert construction + dispatch.
"""Receives TxEvents from the scanner, enriches with cluster/exchange context,
runs the ScoringEngine, formats via formatter, dispatches to Telegram, and saves to DB."""
from alerts.formatter import AlertFormatter
from alerts.telegram_bot import TelegramBot
from db.models import TransactionRepo, ClusterRepo, AlertRepo, AlertOutcomeRepo
from clustering.detector import ClusterDetector
from scoring.engine import ScoringEngine
from tracking.exchange_addresses import ExchangeDirectory
from utils.logger import get_logger

log = get_logger(__name__)


class AlertManager:
    def __init__(self, bot: TelegramBot, tx_repo: TransactionRepo) -> None:
        self.bot = bot
        self.tx_repo = tx_repo
        self.alert_repo = AlertRepo()
        self.outcome_repo = AlertOutcomeRepo()
        self.formatter = AlertFormatter()
        self.exchange_dir = ExchangeDirectory()
        self.cluster_detector = ClusterDetector()
        self.cluster_repo = ClusterRepo()
        self.scoring_engine = ScoringEngine()

    async def handle(self, event) -> None:
        # Dedup check
        if await self.tx_repo.seen(event.tx_hash):
            return
 
        await self.tx_repo.insert(event)
 
        # Context enrichment
        context = {
            "wallet": event.from_address if event.direction == "out" else event.to_address
        }
 
        # 1. Exchange Flow Context
        out_ex = self.exchange_dir.get_exchange_name(event.chain, event.to_address)
        in_ex = self.exchange_dir.get_exchange_name(event.chain, event.from_address)

        if event.direction == "out" and out_ex:
            context["exchange"] = out_ex
            context["reason"] = "Whale moved funds to an exchange — historically precedes selling pressure."
        elif event.direction == "in" and in_ex:
            context["exchange"] = in_ex
            context["reason"] = "Whale received funds from an exchange — likely accumulation or OTC deal."
 
        # 2. Cluster Context
        await self.cluster_detector.evaluate_event(event)
 
        cluster_id = await self.cluster_repo.get_cluster_by_wallet(event.chain, context["wallet"])
        if cluster_id:
            members = await self.cluster_repo.get_members(cluster_id)
            if len(members) > 1:
                context["cluster_id"] = cluster_id
                context["cluster_members"] = members
                context["cluster_count"] = len(members)
 
        # 3. Scoring & Confidence
        score = await self.scoring_engine.score(event, context)
        context["score"] = score
 
        msg = self.formatter.render(event, context)
 
        # Dispatch to Telegram
        await self.bot.send_alert(msg)
 
        # Save to DB for Dashboard & Replay Outcomes
        try:
            alert_id = await self.alert_repo.insert(event, score, msg)
            if alert_id:
                # Price per token at alert time, needed to evaluate outcomes later.
                price_at_alert = None
                if event.usd_value and event.amount_human and event.amount_human > 0:
                    price_at_alert = event.usd_value / event.amount_human
                await self.outcome_repo.create_outcome(alert_id, price_at_alert)
        except Exception as e:
            log.error("Failed to save alert/outcome to DB: {}", e)
