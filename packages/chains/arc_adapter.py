import re
from typing import Dict, List, Any, Optional
from web3 import Web3
from web3.types import Wei


class ArcChainAdapter:
    """Chain adapter for Arc Testnet (chainId 5042002)."""
    
    def __init__(self, rpc_url: str = "https://rpc.testnet.arc.network"):
        self.rpc_url = rpc_url
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.chain_id = 5042002
        self.native_token = "ARC"
        
        # Arc Testnet token addresses
        self.tokens = {
            "ARC": "0x0000000000000000000000000000000000000000",  # native
            "USDC": "0x3600000000000000000000000000000000000000",  # native/special
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
        
        # Get native ARC balance
        try:
            arc_balance = self.w3.eth.get_balance(addresses)
            arc_amount = float(self.w3.from_wei(arc_balance, "ether"))
            if arc_amount > 0:
                balances["ARC"] = f"{arc_amount:.2f}"
        except Exception:
            balances["ARC"] = "0.00"
        
        # Get USDC balance (mock USDC contract)
        usdc_addr = self.tokens["USDC"]
        try:
            usdc_contract = self.w3.eth.contract(address=usdc_addr, abi=self._usdc_abi())
            usdc_balance = usdc_contract.functions.balanceOf(addresses).call()
            usdc_amount = float(self.w3.from_wei(usdc_balance, 6))  # USDC has 6 decimals
            if usdc_amount > 0:
                balances["USDC"] = f"{usdc_amount:.2f}"
            else:
                balances["USDC"] = "0.00"
        except Exception:
            balances["USDC"] = "0.00"
        
        # Get EURC balance
        euros_addr = self.tokens["EURC"]
        try:
            eurc_contract = self.w3.eth.contract(address=euros_addr, abi=self._erc20_abi())
            eurc_balance = eurc_contract.functions.balanceOf(addresses).call()
            eurc_amount = float(self.w3.from_wei(eurc_balance, 18) if eurc_balance else 0)
            # EURC typically has 6 decimals on Ethereum, but let's be safe
            eurc_amount = float(self.w3.from_wei(eurc_balance, 6)) if eurc_balance else 0.0
            if eurc_amount > 0:
                balances["EURC"] = f"{eurc_amount:.2f}"
            else:
                balances["EURC"] = "0.00"
        except Exception:
            balances["EURC"] = "0.00"
        
        return balances
    
    def _usdc_abi(self) -> List[Dict[str, Any]]:
        return [
            {"constant": True, "inputs": [{"name": "owner", "type": "address"}],
             "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
             "type": "function"},
            {"constant": True, "inputs": [],
             "name": "decimals", "outputs": [{"name": "", "type": "uint8"}],
             "type": "function"},
        ]
    
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
        token: str = "ARC",
        speed: str = "standard",
    ) -> Dict[str, str]:
        """Estimate gas for a transfer."""
        # Mock gas estimates for Arc Testnet
        gas_estimates = {
            "economy": {"gas": "0x5208", "fee": "0.0008 ARC", "usd": "$0.04", "time": "~120s"},
            "standard": {"gas": "0x9896", "fee": "0.0015 ARC", "usd": "$0.07", "time": "~30s"},
            "fast": {"gas": "0xae70", "fee": "0.0028 ARC", "usd": "$0.13", "time": "~10s"},
        }
        
        speed_key = speed
        if speed_key not in gas_estimates:
            speed_key = "standard"
        
        gas_data = gas_estimates[speed_key]
        
        # Try to estimate actual gas via RPC
        try:
            tx = {
                "from": self.w3.to_checksum_address(from_address),
                "to": self.w3.to_checksum_address(to_address) if to_address.startswith("0x") else "0x0000000000000000000000000000000000000000",
                "value": self.w3.to_wei(value, "ether") if value else "0x0",
                "data": data,
                "gas": "0xFFFFFFFF",  # start with max
                "chainId": self.chain_id,
            }
            estimated = self.w3.eth.estimate_gas(tx)
            gas_data["gas"] = hex(estimated)
            
            # Calculate fee
            if token == "ARC":
                base_fee = self.w3.eth.gas_price
                priority_fee = self.w3.to_wei(0.0001, "ether")
                max_fee = base_fee + priority_fee
                fee_wei = max_fee * estimated
                fee_arc = float(self.w3.from_wei(fee_wei, "ether"))
                gas_data["fee"] = f"{fee_arc:.4f} ARC"
                gas_data["usd"] = f"~${fee_arc * 5:.2f}"  # rough estimate
                gas_data["time"] = "~10s"
        except Exception as e:
            pass  # use mock values
        
        return {
            "gas": gas_data["gas"],
            "fee": gas_data["fee"],
            "gas_usd": gas_data["usd"],
            "estimated_time": gas_data["time"],
        }
    
    async def prepare_transfer(
        self,
        from_address: str,
        to_address: str,
        amount: str,
        token: str = "ARC",
    ) -> Dict[str, Any]:
        """Prepare a token transfer (calldata + to + value + gas)."""
        token_addr = self.get_token_address(token)
        
        if token == "ARC" or token == "native":
            # Native transfer
            calldata = "0x"
            value = amount
            to_addr = to_address
        elif token and token in self.tokens:
            # ERC-20 transfer
            calldata = self._erc20_calculates(
                from_address, to_address, amount, token_addr
            )
            value = "0"
            to_addr = to_addr
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
            "to": to_address if token != "ARC" else token_addr or "0x0000000000000000000000000000000000000000",
            "value": value,
            "data": calldata,
            "gas_limit": gas_estimate["gas"],
            "gas_fee": gas_estimate["gas_usd"],
            "total_cost": f"{amount} {token} + {gas_estimate['fee']}",
        }
    
    def _erc20_calculates(
        self,
        from_addr: str,
        to_addr: str,
        amount: str,
        token_contract: str,
    ) -> str:
        """Generate ERC-20 transfer calldata."""
        # ERC-20 transfer(uint256 amount) = 0xa9059cbb
        transfer_selector = "0xa9059cbb"
        
        # Encode amount as 32 bytes
        amount_wei = int(float(amount) * 10**6)  # assuming 6 decimals for ARC USDC
        amount_bytes = hex(amount_wei)[2:].zfill(64)
        
        # Pad to 32 bytes
        amount_padded = amount_bytes[-64:] if len(amount_bytes) <= 64 else amount_bytes[-64:]
        
        # Concatenate selector + amount
        calldata = transfer_selector + amount_padded
        return "0x" + calldata[2:]
    
    async def send_raw_tx(self, signed_tx: str) -> str:
        """Send a raw signed transaction."""
        # In production, this would send to the RPC
        # For now, return a mock hash
        return signed_tx[:64] + "…"  # mock tx hash


# Factory to get chain adapter by chainId
chain_adapters: Dict[int, ArcChainAdapter] = {}

def get_adapter(chain_id: int, rpc_url: str = None) -> ArcChainAdapter:
    if chain_id not in chain_adapters:
        chain_adapters[chain_id] = ArcChainAdapter(rpc_url=rpc_url)
    return chain_adapters[chain_id]