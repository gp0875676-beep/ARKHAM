# scoring/weights.py — loads scoring weights from config, validates sum.
"""Reads score_weight_* from settings, validates they sum to ~1.0."""
from config import get_settings
from utils.logger import get_logger

log = get_logger(__name__)


class Weights:
    def __init__(self) -> None:
        s = get_settings()
        self.usd = s.score_weight_usd
        self.wallet_history = s.score_weight_wallet_history
        self.cluster_size = s.score_weight_cluster_size
        self.exchange_proximity = s.score_weight_exchange_proximity
 
        total = self.usd + self.wallet_history + self.cluster_size + self.exchange_proximity
        if not (0.99 <= total <= 1.01):
            log.warning("Scoring weights sum to {}, not 1.0. Scores may be skewed.", total)
