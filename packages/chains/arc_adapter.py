import re
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
        token: str = "ARC",
        speed: str = "standard",
    ) -> Dict[str, str]:
        raise NotImplementedError

    async def prepare_transfer(
        self,
        from_address: str,
        to_address: str,
        amount: str,
        token: str = "ARC",
    ) -> Dict[str, Any]:
        raise NotImplementedError

    async def send_raw_tx(self, signed_tx: str) -> str:
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

        # ARC native balance
        try:
            arc_balance = self.w3.eth.get_balance(addresses)
            arc_amount = float(self.w3.from_wei(arc_balance, "ether"))
            if arc_amount > 0:
                balances["ARC"] = f"{arc_amount:.2f}"
            else:
                balances["ARC"] = "0.00"
        except Exception:
            balances["ARC"] = "0.00"

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
        fee_token = "0 ARC"

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

        For USDC (Arc native gas): ERC-20 transfer calldata = selector + to(32 bytes) + amount(32 bytes)
        For native ARC: calldata is empty, value = amount
        """
        token_addr = self.get_token_address(token)

        if token == "ARC" or token == "native" or token == self.native_token:
            # Native transfer: calldata empty, value = amount
            calldata = "0x"
            value = amount
            to_addr = to_address
        elif token and token in self.tokens:
            # ERC-20 transfer: selector + to(32 bytes) + amount(32 bytes)
            calldata = self._erc20_transfer_calldata(from_address, to_address, amount)
            value = "0"
            to_addr = to_address
        else:
            raise ValueError(f"Unknown token: {token}")

        gas_estimate = await self.estimate_gas(
            from_address=from_address,
            to_address=to_address,
            value=value,
            data=calldata,
            token=token,
        )

        # Determine the 'to' field in response: use token contract address for ERC-20, or native address
        response_to = token_addr if token and token in self.tokens else (to_address or token_addr or "0x0000000000000000000000000000000000000000")

        return {
            "to": response_to,
            "value": value,
            "data": calldata,
            "gas_limit": gas_estimate["gas"],
            "gas_fee": gas_estimate["gas_usd"],
            "total_cost": f"{amount} {token} + {gas_estimate['gas_fee']}",
        }

    def _erc20_transfer_calldata(
        self,
        from_addr: str,
        to_addr: str,
        amount: str,
    ) -> str:
        """Generate ERC-20 transfer calldata: selector + to(32 bytes) + amount(32 bytes).

        ERC-20 transfer(uint256 amount) = 0xa9059cbb
        Full encoding: 0xa9059cbb + address(to) padded 32 bytes + amount padded 32 bytes
        """
        transfer_selector = "0xa9059cbb"

        to_address_checksum = self.w3.to_checksum_address(to_addr)
        amount_int = int(float(amount) * 10**6)  # USDC has 6 decimals on Arc

        # Encode: selector + to_address(32 bytes) + amount(32 bytes)
        # Using eth_abi encode for proper padding
        encoded = encode(
            ["bytes4", "address", "uint256"],
            [transfer_selector, to_address_checksum, amount_int]
        )

        # eth_abi returns hex with 0x prefix, already 32+32+4 = 64 bytes total
        return "0x" + encoded.hex()[2:]

    async def send_raw_tx(self, signed_tx: str) -> str:
        """Send a raw signed transaction.

        In production, this would use eth_sendRawTransaction via the RPC.
        For now, simulate sending and return a tx hash.
        """
        # In production, send via: self.w3.eth.send_raw_transaction(signed_tx)
        # Return transaction hash
        return self.w3.to_hex(self.w3.keccak(text=signed_tx))


# Factory to get chain adapter by chainId
chain_adapters: Dict[int, ChainAdapter] = {}


def get_adapter(chain_id: int, rpc_url: str = None) -> ChainAdapter:
    """Get the appropriate chain adapter for the given chain_id.

    Returns an ArcChainAdapter for chain 5042002, or raises HTTPException for unknown chains.
    """
    if chain_id not in chain_adapters:
        if chain_id == 5042002:
            chain_adapters[chain_id] = ArcChainAdapter(rpc_url=rpc_url)
        else:
            # For other chains, create a generic EVM adapter
            from packages.chains.evm_adapter import EVMChainAdapter
            chain_adapters[chain_id] = EVMChainAdapter(rpc_url=rpc_url)
    return chain_adapters[chain_id]