# scoring/calibration.py — confidence calibration based on historical hit-rates.
"""Computes actual hit-rate per score bucket from alert_outcomes.
This is a real, honest calibration signal built from your own system's track
record, NOT a trained ML model. It explicitly requires >=30 samples in a
bucket before making any claim about that bucket."""
import time

from db.models import AlertOutcomeRepo
from utils.logger import get_logger

log = get_logger(__name__)

MIN_SAMPLES = 30


class CalibrationEngine:
    def __init__(self) -> None:
        self.repo = AlertOutcomeRepo()
        self.cache: dict | None = None
        self.last_fetch = 0.0
        self.cache_ttl = 3600  # 1 hour — avoids hitting the DB on every alert

    async def get_report(self) -> dict:
        """Returns a dict mapping score bucket -> {total, hits, hit_rate}."""
        now = time.time()
        if self.cache and (now - self.last_fetch) < self.cache_ttl:
            return self.cache

        try:
            # Look back 30 days for matured (evaluated_24h=TRUE) outcomes.
            stats = await self.repo.get_replay_stats(30)
            buckets = {
                "0-50": {"total": 0, "hits": 0, "hit_rate": 0.0},
                "50-80": {"total": 0, "hits": 0, "hit_rate": 0.0},
                "80-100": {"total": 0, "hits": 0, "hit_rate": 0.0},
            }
            for s in stats:
                score = s["score"] or 0
                direction = s["direction"]
                p_start = float(s["price_at_alert"])
                p_end = float(s["price_at_24h"])

                b_key = "0-50"
                if score >= 80:
                    b_key = "80-100"
                elif score >= 50:
                    b_key = "50-80"

                buckets[b_key]["total"] += 1
                if p_start > 0:
                    pct_change = ((p_end - p_start) / p_start) * 100
                    # Implied direction: 'in' = expect price UP, 'out' = expect price DOWN
                    if direction == "in" and pct_change > 5:
                        buckets[b_key]["hits"] += 1
                    elif direction == "out" and pct_change < -5:
                        buckets[b_key]["hits"] += 1

            for b in buckets.values():
                if b["total"] > 0:
                    b["hit_rate"] = (b["hits"] / b["total"]) * 100

            self.cache = buckets
            self.last_fetch = now
            return buckets
        except Exception as e:
            log.error("Failed to generate calibration report: {}", e)
            return self.cache or {}
