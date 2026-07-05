# chains/ethereum.py — Ethereum adapter (Etherscan API + RPC).
"""Ethereum ChainAdapter implementation. Also serves as the base EVM adapter."""
from typing import List

from chains.base import ChainAdapter, TxEvent
from providers.etherscan import EtherscanClient
from providers.rpc import RpcClient
from utils.usd import PriceOracle
from utils.logger import get_logger
from config import get_settings

log = get_logger(__name__)


class EvmAdapter(ChainAdapter):
    """Generic EVM Adapter logic. Subclasses set the chain-specific metadata."""
 
    chain: str = "evm"
    native_symbol: str = "ETH"
    explorer_tx_url: str = ""

    def __init__(self, client: EtherscanClient, oracle: PriceOracle, rpc: RpcClient | None = None):
        self.client = client
        self.oracle = oracle
        self.rpc = rpc
        self.settings = get_settings()

    async def fetch_recent_txs(self, wallet: str, since_block: int) -> List[TxEvent]:
        events = []
        wallet_lower = wallet.lower()

        # Normal txs (Native transfers)
        try:
            normal_txs = await self.client.get_normal_txs(wallet, since_block)
            for tx in normal_txs:
                val = int(tx.get("value", "0"))
                if val == 0: continue
                direction = "out" if tx["from"].lower() == wallet_lower else "in"
                amount_human = val / 1e18
                usd_price = await self.oracle.get_usd_price(self.chain, "0x0")
                event = TxEvent(
                    chain=self.chain,
                    tx_hash=tx["hash"],
                    block_number=int(tx["blockNumber"]),
                    timestamp=int(tx["timeStamp"]),
                    from_address=tx["from"],
                    to_address=tx["to"],
                    token_address=None,
                    token_symbol=self.native_symbol,
                    amount_raw=val,
                    amount_human=amount_human,
                    usd_value=usd_price * amount_human if usd_price else None,
                    direction=direction,
                    explorer_url=f"{self.explorer_tx_url}/{tx['hash']}"
                )
                events.append(event)
        except Exception as e:
            log.error("{} normal tx fetch failed: {}", self.chain, e)

        # ERC20 txs
        try:
            erc20_txs = await self.client.get_erc20_transfers(wallet, since_block)
            for tx in erc20_txs:
                val = int(tx.get("value", "0"))
                if val == 0: continue
                direction = "out" if tx["from"].lower() == wallet_lower else "in"
                decimals = int(tx.get("tokenDecimal", "18"))
                amount_human = val / (10 ** decimals)
                token_addr = tx["contractAddress"]
                usd_price = await self.oracle.get_usd_price(self.chain, token_addr)
                event = TxEvent(
                    chain=self.chain,
                    tx_hash=tx["hash"],
                    block_number=int(tx["blockNumber"]),
                    timestamp=int(tx["timeStamp"]),
                    from_address=tx["from"],
                    to_address=tx["to"],
                    token_address=token_addr,
                    token_symbol=tx.get("tokenSymbol", "UNKNOWN"),
                    amount_raw=val,
                    amount_human=amount_human,
                    usd_value=usd_price * amount_human if usd_price else None,
                    direction=direction,
                    explorer_url=f"{self.explorer_tx_url}/{tx['hash']}"
                )
                events.append(event)
        except Exception as e:
            log.error("Explorer API failed for {} ERC20 txs: {}. Blind spot this cycle.", self.chain, e)
            # We explicitly do NOT fall back to RPC here and do NOT fabricate data --
            # standard JSON-RPC cannot list historical transfers for an address.
            return events

        log.debug("Served {} txs for {} via Explorer API", len(events), wallet_lower)
        return events

    async def get_latest_block(self) -> int:
        """Try the Explorer API first. On failure (timeout, HTTP error, rate
        limit), fall back to direct JSON-RPC. Returns 0 only if BOTH fail --
        never fabricates a block number."""
        try:
            data = await self.client.get("", {"module": "proxy", "action": "eth_blockNumber"})
            if data and data.get("result"):
                block = int(data["result"], 16)
                if block > 0:
                    log.debug("Served latest block for {} via Explorer API", self.chain)
                    return block
        except Exception as e:
            log.warning("Explorer API block fetch failed for {}: {}. Attempting RPC fallback...", self.chain, e)

        if self.rpc and self.rpc.rpc_url:
            block = await self.rpc.get_block_number()
            if block:
                log.info("Served latest block for {} via RPC fallback", self.chain)
                return block
            log.error("RPC fallback ALSO failed for {} block fetch.", self.chain)
        else:
            log.error("RPC fallback not configured for {}.", self.chain)

        log.critical("CRITICAL: Both Explorer and RPC failed to get latest block for {}", self.chain)
        return 0

    async def is_exchange_address(self, address: str) -> bool:
        return False  # Handled by ExchangeDirectory in AlertManager


class EthereumAdapter(EvmAdapter):
    chain = "ethereum"
    native_symbol = "ETH"
 
    def __init__(self, client: EtherscanClient, oracle: PriceOracle, rpc: RpcClient | None = None):
        super().__init__(client, oracle, rpc)
        self.explorer_tx_url = self.settings.eth_explorer_tx_url
