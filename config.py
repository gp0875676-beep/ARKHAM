# config.py — typed settings loaded from env. Single source of truth.
"""Typed configuration via pydantic-settings.

All configurable values live here. No other module should read os.environ directly.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Runtime ----
    env: str = "development"
    log_level: str = "INFO"

    # ---- Telegram ----
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")
    # Comma-separated list of Telegram User IDs allowed to run /addwhale, /removewhale, etc.
    telegram_admin_ids: str = Field(default="")

    # ---- Database ----
    database_url: str = Field(default="")

    # ---- Scanner ----
    poll_interval_seconds: int = 30
    min_usd_threshold: float = 10_000.0
    dedup_window_seconds: int = 600
    max_workers_per_chain: int = 4
    backoff_base_seconds: float = 1.5
    backoff_max_seconds: float = 60.0
    backoff_retries: int = 5
    per_provider_rpm: int = 300

    # ---- Pricing ----
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    coingecko_api_key: str = ""
    price_cache_ttl_seconds: int = 60

    # ---- Ethereum ----
    eth_enabled: bool = True
    eth_rpc_url: str = ""
    eth_etherscan_api_key: str = ""
    eth_etherscan_base_url: str = "https://api.etherscan.io/api"
    eth_explorer_tx_url: str = "https://etherscan.io/tx"
    whale_wallets_eth: str = ""  # Comma-separated list of whale addresses to track

    # ---- BSC ----
    bsc_enabled: bool = False
    bsc_rpc_url: str = ""
    bsc_bscscan_api_key: str = ""
    bsc_bscscan_base_url: str = "https://api.bscscan.com/api"
    bsc_explorer_tx_url: str = "https://bscscan.com/tx"
    whale_wallets_bsc: str = ""

    # ---- Polygon ----
    polygon_enabled: bool = False
    polygon_rpc_url: str = ""
    polygon_polygonscan_api_key: str = ""
    polygon_polygonscan_base_url: str = "https://api.polygonscan.com/api"
    polygon_explorer_tx_url: str = "https://polygonscan.com/tx"
    whale_wallets_polygon: str = ""

    # ---- Arbitrum ----
    arbitrum_enabled: bool = False
    arbitrum_rpc_url: str = ""
    arbitrum_arbiscan_api_key: str = ""
    arbitrum_arbiscan_base_url: str = "https://api.arbiscan.io/api"
    arbitrum_explorer_tx_url: str = "https://arbiscan.io/tx"
    whale_wallets_arbitrum: str = ""

    # ---- Clustering (Phase 3) ----
    cluster_min_common_funding_txs: int = 2
    cluster_min_cotx_count: int = 3
    cluster_timing_window_seconds: int = 120

    # ---- Scoring (Phase 4) ----
    score_weight_usd: float = 0.45
    score_weight_wallet_history: float = 0.20
    score_weight_cluster_size: float = 0.15
    score_weight_exchange_proximity: float = 0.20

    # ---- Dashboard (Phase 6) ----
    dashboard_enabled: bool = False
    dashboard_port: int = 10000

    # ---- Exchange Directory (Phase 2) ----
    # JSON string mapping chain -> {address: exchange_name}
    exchange_wallets_json: str = "{}"

    # ---- Validators ----
    @field_validator("score_weight_usd", "score_weight_wallet_history",
                     "score_weight_cluster_size", "score_weight_exchange_proximity")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("score weights must be >= 0")
        return v

    @property
    def enabled_chains(self) -> List[str]:
        out = []
        if self.eth_enabled: out.append("ethereum")
        if self.bsc_enabled: out.append("bsc")
        if self.polygon_enabled: out.append("polygon")
        if self.arbitrum_enabled: out.append("arbitrum")
        return out

    @property
    def admin_ids(self) -> List[int]:
        if not self.telegram_admin_ids:
            return []
        try:
            return [int(x.strip()) for x in self.telegram_admin_ids.split(",") if x.strip()]
        except ValueError:
            return []

    def require(self, *names: str) -> None:
        """Fail fast if any required env var is empty."""
        missing = [n for n in names if not getattr(self, n)]
        if missing:
            raise RuntimeError(f"Missing required env vars: {missing}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
