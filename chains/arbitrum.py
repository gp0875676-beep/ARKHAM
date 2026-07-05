# chains/arbitrum.py — Arbitrum adapter (Arbiscan API + RPC).
from chains.ethereum import EvmAdapter
from providers.etherscan import EtherscanClient
from providers.rpc import RpcClient
from utils.usd import PriceOracle
from config import get_settings


class ArbitrumAdapter(EvmAdapter):
    chain = "arbitrum"
    native_symbol = "ARB"

    def __init__(self, client: EtherscanClient, oracle: PriceOracle, rpc: RpcClient | None = None):
        super().__init__(client, oracle, rpc)
        self.explorer_tx_url = self.settings.arbitrum_explorer_tx_url
