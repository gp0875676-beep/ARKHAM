# scoring/engine.py — significance score (0-100) + plain-English explanation.
"""Converts a TxEvent + context into a (score, explanation) tuple."""
from dataclasses import dataclass
from typing import Dict, Tuple

from chains.base import TxEvent
from db.models import TransactionRepo
from scoring.weights import Weights
from scoring.calibration import CalibrationEngine
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class Score:
    value: int                       # 0-100
    explanation: str                 # short, plain-English
    factors: dict[str, float]        # raw 0-100 score per factor
    calibration_note: str = ""       # e.g. " (historically right 68% of the time, n=45)"


class ScoringEngine:
    def __init__(self) -> None:
        self.weights = Weights()
        self.tx_repo = TransactionRepo()
        self.calibration = CalibrationEngine()

    async def score(self, event: TxEvent, context: dict) -> Score:
        """Calculates the final 0-100 score based on 4 factors."""
 
        wallet = context.get("wallet") or (event.to_address if event.direction == "in" else event.from_address)

        # 1. USD Value Factor (0-100)
        # $50k = 50 pts, $100k+ = 100 pts
        usd_val = event.usd_value or 0.0
        score_usd = min(100.0, (usd_val / 100_000.0) * 100.0)
 
        # 2. Wallet History Factor (0-100)
        # New wallets (0 history) acting like whales are highly suspicious/important.
        # Frequent wallets are less anomalous.
        try:
            tx_count = await self.tx_repo.get_wallet_tx_count(event.chain, wallet)
            # 0 txs = 100 pts. 5+ txs = 20 pts.
            score_wallet_hist = max(20.0, 100.0 - (tx_count * 20.0))
        except Exception as e:
            log.warning("Could not fetch wallet history for scoring: {}", e)
            tx_count = 0
            score_wallet_hist = 50.0  # Neutral fallback

        # 3. Cluster Size Factor (0-100)
        # Isolated wallet = 0 pts. 2 wallets = 50 pts. 3+ wallets = 100 pts.
        cluster_count = context.get("cluster_count", 1)
        if cluster_count <= 1:
            score_cluster = 0.0
        elif cluster_count == 2:
            score_cluster = 50.0
        else:
            score_cluster = 100.0

        # 4. Exchange Proximity Factor (0-100)
        # Interaction with an exchange is highly actionable.
        score_exchange = 100.0 if context.get("exchange") else 0.0

        # Calculate weighted final score
        final_score = (
            (score_usd * self.weights.usd) +
            (score_wallet_hist * self.weights.wallet_history) +
            (score_cluster * self.weights.cluster_size) +
            (score_exchange * self.weights.exchange_proximity)
        )
 
        # Clamp to 0-100 and round
        final_score = max(0, min(100, int(final_score)))
 
        explanation = self._build_explanation(
            final_score, usd_val, tx_count, cluster_count, context.get("exchange")
        )
 
        factors = {
            "usd": score_usd,
            "wallet_history": score_wallet_hist,
            "cluster_size": score_cluster,
            "exchange_proximity": score_exchange
        }

        # 5. Confidence calibration (Phase 7, Module 4) — real, honest hit-rate
        # from this system's own track record. No claim below 30 samples.
        calib_note = ""
        try:
            report = await self.calibration.get_report()
            bucket_key = "0-50"
            if final_score >= 80:
                bucket_key = "80-100"
            elif final_score >= 50:
                bucket_key = "50-80"
            bucket = report.get(bucket_key)
            if bucket and bucket["total"] >= 30:
                calib_note = f" (historically right {bucket['hit_rate']:.0f}% of the time, n={bucket['total']})"
        except Exception as e:
            log.warning("Calibration lookup failed, showing raw score only: {}", e)

        return Score(value=final_score, explanation=explanation, factors=factors, calibration_note=calib_note)

    def _build_explanation(self, score: int, usd: float, tx_count: int, cluster_count: int, exchange: str | None) -> str:
        """Generates a short, human-readable explanation for the score."""
        parts = []
 
        if score >= 80:
            parts.append("Critical alert")
        elif score >= 50:
            parts.append("High significance")
        else:
            parts.append("Moderate activity")
 
        if usd >= 100_000:
            parts.append(f"large transfer (${usd:,.0f})")
        elif usd >= 10_000:
            parts.append(f"notable transfer (${usd:,.0f})")
 
        if exchange:
            parts.append(f"involves {exchange}")
 
        if cluster_count > 1:
            parts.append(f"part of a {cluster_count}-wallet cluster")
 
        if tx_count == 0:
            parts.append("first seen activity for this wallet")
 
        # Format the string
        if len(parts) > 1:
            return parts[0] + ": " + ", ".join(parts[1:]).capitalize() + "."
        return parts[0] + "."
