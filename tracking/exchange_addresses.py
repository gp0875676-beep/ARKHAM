# tracking/exchange_addresses.py — known exchange hot wallets, per chain.
"""Static-but-extensible list of exchange-controlled addresses, used by
Phase 2 to flag exchange inflow/outflow. No external dependency."""
import json
from typing import Dict, Optional

from config import get_settings
from utils.logger import get_logger

log = get_logger(__name__)


class ExchangeDirectory:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.addresses = self._load()

    def _load(self) -> Dict[str, Dict[str, str]]:
        """Parses the EXCHANGE_WALLETS_JSON from env.
        Expected: {"ethereum": {"0x...": "Binance"}}"""
        if not self.settings.exchange_wallets_json:
            return {}
        try:
            data = json.loads(self.settings.exchange_wallets_json)
            # Lowercase all addresses for case-insensitive matching
            clean_data = {}
            for chain, wallets in data.items():
                clean_data[chain.lower()] = {addr.lower(): name for addr, name in wallets.items()}
            return clean_data
        except json.JSONDecodeError as e:
            log.error("Failed to parse EXCHANGE_WALLETS_JSON: {}", e)
            return {}

    def is_exchange(self, chain: str, address: str) -> bool:
        """Check if a given address belongs to a known exchange."""
        return self.get_exchange_name(chain, address) is not None

    def get_exchange_name(self, chain: str, address: str) -> Optional[str]:
        """Return the name of the exchange if the address is known, else None."""
        if not address:
            return None
        chain_data = self.addresses.get(chain.lower(), {})
        return chain_data.get(address.lower())
