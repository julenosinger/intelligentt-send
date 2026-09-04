"""Unit test for ERC-20 calldata encoding."""
import pytest
from decimal import Decimal
from web3 import Web3
from eth_abi import encode, decode


def _build_calldata(to_addr: str, amount: str, decimals: int = 6) -> str:
    """Build ERC-20 transfer(address,uint256) calldata the correct way.

    selector (4 bytes, literal) + ABI-encode(address, uint256).
    Amount is computed with Decimal, never float.
    """
    selector = bytes.fromhex("a9059cbb")  # transfer(address,uint256)
    amount_int = int(Decimal(amount) * 10**decimals)
    payload = encode(
        ["address", "uint256"],
        [Web3.to_checksum_address(to_addr), amount_int],
    )
    return "0x" + selector.hex() + payload.hex()


def test_erc20_transfer_selector():
    """ERC-20 transfer(address,uint256) selector is 0xa9059cbb."""
    selector = Web3.keccak(text="transfer(address,uint256)")[:4].hex()
    assert selector == "a9059cbb", f"Expected a9059cbb, got {selector}"


def test_erc20_calldata_format():
    """Calldata = selector(4) + address(32) + amount(32) = 68 bytes = 138 hex chars."""
    to_addr = "0x1dE27a21f321cD4a25A1D5B6e9D3f7C2b1a0E9d8"
    calldata = _build_calldata(to_addr, "100")

    # 0x + 136 hex chars (4 + 32 + 32 bytes)
    assert len(calldata) == 138, f"Expected 138 chars, got {len(calldata)}"
    assert calldata.startswith("0xa9059cbb"), "Calldata must start with 0xa9059cbb"


def test_calldata_decodes_recipient_and_amount():
    """Decode data[10:] as (address, uint256) and confirm recipient + amount."""
    to_addr = "0x1dE27a21f321cD4a25A1D5B6e9D3f7C2b1a0E9d8"
    amount = "100"
    calldata = _build_calldata(to_addr, amount)

    # Skip the 4-byte selector (10 hex chars incl. 0x)
    decoded = decode(["address", "uint256"], bytes.fromhex(calldata[10:]))
    assert decoded[0].lower() == to_addr.lower(), f"recipient mismatch: {decoded[0]}"
    assert decoded[1] == int(Decimal(amount) * 10**6), f"amount mismatch: {decoded[1]}"


def test_amount_uses_decimal_not_float():
    """Amount is computed with Decimal, so 0.1 USDC is exact (no float drift)."""
    to_addr = "0x1dE27a21f321cD4a25A1D5B6e9D3f7C2b1a0E9d8"
    calldata = _build_calldata(to_addr, "0.1")
    decoded = decode(["address", "uint256"], bytes.fromhex(calldata[10:]))
    assert decoded[1] == 100000  # 0.1 * 10**6, exactly


def test_arc_usdc_decimals():
    """USDC on Arc has 6 decimals, not 18."""
    raw_balance = 1240500000  # 1240.50 USDC in base units
    formatted = raw_balance / 10**6
    assert formatted == 1240.50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
