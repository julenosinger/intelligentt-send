import re
from decimal import Decimal
from typing import Dict, List, Any, Optional
from eth_abi import encode
from web3 import Web3
from web3.types import Wei


class ChainAdapter:
    """Base protocol for chain adapters.

    Subclasses must implement: get_balances, estimate_gas, prepare_transfer, send_raw, explorer_tx
    """

    def get_chain_id(self) -> int:
        raise NotImplementedError

    def get_rpc_url(self) -> str:
        raise NotImplementedError

    def get_explorer_url(self, tx_hash: str) -> str:
        raise NotImplementedError

    def get_token_address(self, symbol: str) -> Optional[str]:
        raise NotImplementedError

    async def get_balances(self, address: str) -> Dict[str, str]:
        raise NotImplementedError

    async def estimate_gas(
        self,
        from_address: str,
        to_address: str,
        value: str = "0",
        data: str = "0x",
        token: str = "USDC",
        speed: str = "standard",
    ) -> Dict[str, str]:
        raise NotImplementedError

    async def prepare_transfer(
        self,
        from_address: str,
        to_address: str,
        amount: str,
        token: str = "USDC",
    ) -> Dict[str, Any]:
        raise NotImplementedError

    async def send_raw_tx(self, signed_tx: str) -> str:
        raise NotImplementedError

    async def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


class ArcChainAdapter(ChainAdapter):
    """Chain adapter for Arc Testnet (chainId 5042002).

    Arc testnet: native gas token is USDC (0x3600000000000000000000000000000000000000)
    """

    def __init__(self, rpc_url: str = "https://rpc.testnet.arc.network"):
        self.rpc_url = rpc_url
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.chain_id = 5042002
        self.native_token = "USDC"  # Arc native gas token is USDC

        # Arc Testnet token addresses (checksummed)
        self.tokens = {
            "USDC": "0x3600000000000000000000000000000000000000",
            "EURC": "0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a",
        }

    def get_chain_id(self) -> int:
        return self.chain_id

    def get_rpc_url(self) -> str:
        return self.rpc_url

    def get_explorer_url(self, tx_hash: str) -> str:
        return f"https://testnet.arcscan.app/tx/{tx_hash}"

    def get_token_address(self, symbol: str) -> Optional[str]:
        return self.tokens.get(symbol.upper())

    async def get_balances(self, address: str) -> Dict[str, str]:
        """Get token balances for an address on Arc Testnet."""
        if not self.w3.is_connected():
            raise ConnectionError("Not connected to Arc Testnet RPC")

        addresses = self.w3.to_checksum_address(address)
        balances = {}

        # Get USDC balance (6 decimals on Arc)
        usdc_addr = self.tokens["USDC"]
        try:
            usdc_contract = self.w3.eth.contract(address=usdc_addr, abi=self._erc20_abi())
            usdc_balance = usdc_contract.functions.balanceOf(addresses).call()
            # USDC has 6 decimals on Arc - manual division, NOT from_wei(..., 6)
            usdc_amount = usdc_balance / 10**6
            balances["USDC"] = f"{usdc_amount:.2f}"
        except Exception:
            balances["USDC"] = "0.00"

        # Get EURC balance (18 decimals typically)
        euros_addr = self.tokens["EURC"]
        try:
            eurc_contract = self.w3.eth.contract(address=euros_addr, abi=self._erc20_abi())
            eurc_balance = eurc_contract.functions.balanceOf(addresses).call()
            eurc_amount = eurc_balance / 10**18
            if eurc_amount > 0:
                balances["EURC"] = f"{eurc_amount:.2f}"
            else:
                balances["EURC"] = "0.00"
        except Exception:
            balances["EURC"] = "0.00"

        return balances

    def _erc20_abi(self) -> List[Dict[str, Any]]:
        return [
            {"constant": True, "inputs": [{"name": "owner", "type": "address"}],
             "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
             "type": "function"},
            {"constant": True, "inputs": [],
             "name": "decimals", "outputs": [{"name": "", "type": "uint8"}],
             "type": "function"},
        ]

    async def estimate_gas(
        self,
        from_address: str,
        to_address: str,
        value: str = "0",
        data: str = "0x",
        token: str = "USDC",
        speed: str = "standard",
    ) -> Dict[str, str]:
        """Estimate gas for a transfer on Arc Testnet."""
        # Base gas estimates for Arc (in wei-like format, converted to hex)
        base_gas = {
            "economy": 21000,
            "standard": 21500,
            "fast": 23000,
        }

        speed_key = speed if speed in base_gas else "standard"
        gas_limit = base_gas[speed_key]

        # Try to estimate actual gas via RPC
        try:
            from_addr_checksum = self.w3.to_checksum_address(from_address)
            to_addr_checksum = self.w3.to_checksum_address(to_address) if to_address and to_address.startswith("0x") else "0x0000000000000000000000000000000000000000"

            tx = {
                "from": from_addr_checksum,
                "to": to_addr_checksum,
                "value": self.w3.to_wei(value, "ether") if value else "0x0",
                "data": data,
                "gas": hex(gas_limit),
                "chainId": self.chain_id,
            }
            estimated = self.w3.eth.estimate_gas(tx)
            gas_limit = estimated
        except Exception:
            pass  # use base values

        # Calculate fee - Arc uses USDC for gas
        fee_usd = "0.00"
        fee_token = "0 USDC"

        try:
            # Get base fee from latest block
            base_fee = self.w3.eth.gas_price
            priority_fee = self.w3.to_wei(0.0001, "ether")
            max_fee = base_fee + priority_fee
            fee_wei = max_fee * gas_limit
            fee_usdc_amount = float(self.w3.from_wei(int(fee_wei), "ether"))
            fee_token = f"{fee_usdc_amount:.4f} {self.native_token}"
            fee_usd = f"~${fee_usdc_amount * 5:.2f}"
        except Exception:
            fee_token = f"0.001 {self.native_token}"
            fee_usd = "$0.04"

        return {
            "gas": hex(gas_limit),
            "fee": fee_token,
            "gas_usd": fee_usd,
            "estimated_time": "~10s",
        }

    async def prepare_transfer(
        self,
        from_address: str,
        to_address: str,
        amount: str,
        token: str = "USDC",
    ) -> Dict[str, Any]:
        """Prepare a token transfer (calldata + to + value + gas).

        ERC-20 branch (USDC/EURC): to = token contract, value = "0", data = ERC-20
        transfer calldata. USDC on Arc is BOTH the native gas token and an ERC-20;
        a USDC *transfer* is always an ERC-20 call to the USDC contract, never a
        native value transfer (see README). The "native" branch is a plain value
        send with no token contract involved.
        """
        token_addr = self.get_token_address(token)

        if token and token in self.tokens:
            # ERC-20 transfer: to = token contract, value = 0, data = calldata
            calldata = self._erc20_transfer_calldata(to_address, amount)
            value = "0"
            response_to = token_addr
        elif token == "native":
            # Native value transfer (no token contract involved)
            calldata = "0x"
            value = amount
            response_to = to_address
        else:
            raise ValueError(f"Unknown token: {token}")

        gas_estimate = await self.estimate_gas(
            from_address=from_address,
            to_address=to_address,
            value=value,
            data=calldata,
            token=token,
        )

        return {
            "to": response_to,
            "value": value,
            "data": calldata,
            "gas_limit": gas_estimate["gas"],
            "gas_fee": gas_estimate["gas_usd"],
            "total_cost": f"{amount} {token} + {gas_estimate['fee']}",
        }

    def _erc20_transfer_calldata(
        self,
        to_addr: str,
        amount: str,
    ) -> str:
        """Generate ERC-20 transfer calldata: selector + to(32 bytes) + amount(32 bytes).

        ERC-20 transfer(address,uint256) selector = 0xa9059cbb.
        Result is 138 hex chars (0x + 136 = 4 + 32 + 32 bytes).
        """
        selector = bytes.fromhex("a9059cbb")  # transfer(address,uint256)
        to_address_checksum = self.w3.to_checksum_address(to_addr)
        amount_int = int(Decimal(amount) * 10**6)  # USDC has 6 decimals; no float

        payload = encode(
            ["address", "uint256"],
            [to_address_checksum, amount_int],
        )
        return "0x" + selector.hex() + payload.hex()

    async def send_raw_tx(self, signed_tx: str) -> str:
        """Broadcast a raw signed transaction via eth_sendRawTransaction.

        Accepts a 0x-prefixed hex string. Raises on RPC error (the API layer
        turns that into a 502/503).
        """
        h = self.w3.eth.send_raw_transaction(signed_tx)
        return self.w3.to_hex(h)

    async def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Return the transaction receipt via eth_getTransactionReceipt.

        Returns None if the transaction is not yet mined.
        """
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
        except Exception:
            return None
        if receipt is None:
            return None
        return dict(receipt)


# Factory to get chain adapter by chainId
chain_adapters: Dict[int, ChainAdapter] = {}


def get_adapter(
    chain_id: int,
    rpc_url: str = None,
    explorer: str = None,
    native_token: str = None,
) -> ChainAdapter:
    """Get the appropriate chain adapter for the given chain_id.

    Returns an ArcChainAdapter for chain 5042002, or a generic EVM adapter for
    the other registered EVM testnets. The registry (apps/api/main.py CHAINS)
    supplies rpc_url, explorer and native_token.
    """
    if chain_id not in chain_adapters:
        if chain_id == 5042002:
            chain_adapters[chain_id] = ArcChainAdapter(rpc_url=rpc_url or "https://rpc.testnet.arc.network")
        else:
            from packages.chains.evm_adapter import EVMChainAdapter
            chain_adapters[chain_id] = EVMChainAdapter(
                rpc_url=rpc_url or "https://rpc.sepolia.org",
                chain_id=chain_id,
                explorer=explorer or "https://sepolia.etherscan.io",
                native_token=native_token or "ETH",
            )
    return chain_adapters[chain_id]