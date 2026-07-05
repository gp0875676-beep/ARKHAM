# chains/registry.py — builds the active set of chain adapters from config.
"""Registry mapping chain name -> instantiated adapter."""
from chains.base import ChainAdapter
from config import get_settings
from providers.etherscan import EtherscanClient
from providers.rpc import RpcClient
from chains.ethereum import EthereumAdapter
from chains.bsc import BscAdapter
from chains.polygon import PolygonAdapter
from chains.arbitrum import ArbitrumAdapter
from utils.usd import PriceOracle
from utils.logger import get_logger

log = get_logger(__name__)


async def build_adapters(oracle: PriceOracle = None) -> dict[str, ChainAdapter]:
    settings = get_settings()
    adapters = {}

    if oracle is None:
        oracle = PriceOracle()

    if settings.eth_enabled:
        client = EtherscanClient(
            base_url=settings.eth_etherscan_base_url,
            api_key=settings.eth_etherscan_api_key,
            rpm=settings.per_provider_rpm
        )
        rpc = RpcClient(rpc_url=settings.eth_rpc_url, rpm=settings.per_provider_rpm)
        adapters["ethereum"] = EthereumAdapter(client, oracle, rpc)
        log.info("Ethereum adapter initialized (Explorer + RPC failover).")

    if settings.bsc_enabled:
        client = EtherscanClient(
            base_url=settings.bsc_bscscan_base_url,
            api_key=settings.bsc_bscscan_api_key,
            rpm=settings.per_provider_rpm
        )
        rpc = RpcClient(rpc_url=settings.bsc_rpc_url, rpm=settings.per_provider_rpm)
        adapters["bsc"] = BscAdapter(client, oracle, rpc)
        log.info("BSC adapter initialized (Explorer + RPC failover).")

    if settings.polygon_enabled:
        client = EtherscanClient(
            base_url=settings.polygon_polygonscan_base_url,
            api_key=settings.polygon_polygonscan_api_key,
            rpm=settings.per_provider_rpm
        )
        rpc = RpcClient(rpc_url=settings.polygon_rpc_url, rpm=settings.per_provider_rpm)
        adapters["polygon"] = PolygonAdapter(client, oracle, rpc)
        log.info("Polygon adapter initialized (Explorer + RPC failover).")

    if settings.arbitrum_enabled:
        client = EtherscanClient(
            base_url=settings.arbitrum_arbiscan_base_url,
            api_key=settings.arbitrum_arbiscan_api_key,
            rpm=settings.per_provider_rpm
        )
        rpc = RpcClient(rpc_url=settings.arbitrum_rpc_url, rpm=settings.per_provider_rpm)
        adapters["arbitrum"] = ArbitrumAdapter(client, oracle, rpc)
        log.info("Arbitrum adapter initialized (Explorer + RPC failover).")

    return adapters
