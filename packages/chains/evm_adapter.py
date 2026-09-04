"""EVM chain adapter for Sepolia, Base, Arbitrum, Optimism, Polygon testnets."""
from typing import Dict, List, Any, Optional
from web3 import Web3
from web3.types import Wei
from packages.chains.arc_adapter import ChainAdapter


class EVMChainAdapter(ChainAdapter):
    """Generic EVM adapter for any EVM-compatible chain with RPC support."""

    def __init__(
        self,
        rpc_url: str,
        chain_id: int,
        explorer: str,
        native_token: str = "ETH",
    ):
        self.rpc_url = rpc_url
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.chain_id = chain_id
        self.explorer = explorer
        self.native_token = native_token

    def get_chain_id(self) -> int:
        return self.chain_id

    def get_rpc_url(self) -> str:
        return self.rpc_url

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"{self.explorer.rstrip('/')}/tx/{tx_hash}"

    def get_token_address(self, symbol: str) -> Optional[str]:
        return None

    async def get_balances(self, address: str) -> Dict[str, str]:
        if not self.w3.is_connected():
            raise ConnectionError("Not connected to RPC")
        addr = self.w3.to_checksum_address(address)
        balance = self.w3.eth.get_balance(addr)
        return {self.native_token: str(self.w3.from_wei(balance, "ether"))}

    async def estimate_gas(
        self,
        from_address: str,
        to_address: str,
        value: str = "0",
        data: str = "0x",
        token: str = "ETH",
        speed: str = "standard",
    ) -> Dict[str, str]:
        try:
            estimated = self.w3.eth.estimate_gas({
                "from": self.w3.to_checksum_address(from_address),
                "to": self.w3.to_checksum_address(to_address) if to_address else None,
                "value": self.w3.to_wei(value, "ether") if value else "0x0",
                "data": data,
                "chainId": self.chain_id,
            })
            base_fee = self.w3.eth.gas_price
            return {
                "gas": hex(estimated),
                "fee": f"{float(self.w3.from_wei(int(base_fee) * estimated, 'ether')):.4f} {token}",
                "gas_usd": f"~${base_fee * estimated / 1e18:.4f}",
                "estimated_time": "~15s",
            }
        except Exception:
            return {"gas": "0x5208", "fee": "0.001 ETH", "gas_usd": "$0.02", "estimated_time": "~15s"}

    async def prepare_transfer(
        self,
        from_address: str,
        to_address: str,
        amount: str,
        token: str = "ETH",
    ) -> Dict[str, Any]:
        return {
            "to": to_address,
            "value": amount,
            "data": "0x",
            "gas_limit": "0x5208",
            "gas_fee": "0.001 ETH",
            "total_cost": f"{amount} {token} + 0.001 ETH",
        }

    async def send_raw_tx(self, signed_tx: str) -> str:
        """Broadcast a raw signed transaction via eth_sendRawTransaction."""
        h = self.w3.eth.send_raw_transaction(signed_tx)
        return self.w3.to_hex(h)

    async def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
        except Exception:
            return None
        if receipt is None:
            return None
        return dict(receipt)
