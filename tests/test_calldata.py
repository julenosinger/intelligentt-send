"""Unit test for ERC-20 calldata encoding."""
import pytest
from web3 import Web3
from eth_abi import encode


def test_erc20_transfer_selector():
    """ERC-20 transfer() selector is 0xa9059cbb."""
    selector = Web3.keccak(text="transfer(address,uint256)")[:4].hex()
    assert selector == "a9059cbb", f"Expected a9059cbb, got {selector}"


def test_erc20_calldata_format():
    """Calldata should be selector(4) + address(32) + amount(32) = 68 bytes."""
    to_addr = "0x1dE27a21f321cD4a25A1D5B6e9D3f7C2b1a0E9d8"
    amount = 100 * 10**6  # USDC has 6 decimals

    calldata = encode(
        ["bytes4", "address", "uint256"],
        [bytes.fromhex("a9059cbb"), bytes.fromhex(to_addr[2:]), amount]
    )

    hex_calldata = "0x" + calldata.hex()
    # Total: 4 + 32 + 32 = 68 bytes = 136 hex chars + 0x prefix
    assert len(hex_calldata) == 138, f"Expected 138 chars, got {len(hex_calldata)}"
    assert hex_calldata.startswith("0xa9059cbb"), "Calldata must start with 0xa9059cbb"
    # Verify to address is in the calldata
    assert to_addr.lower() in hex_calldata.lower()


def test_calldata_decodes_correctly():
    """Decode calldata to verify to and amount."""
    from eth_abi import decode

    to_addr = "0x1dE27a21f321cD4a25A1D5B6e9D3f7C2b1a0E9d8"
    amount = 100 * 10**6

    calldata = encode(
        ["bytes4", "address", "uint256"],
        [bytes.fromhex("a9059cbb"), bytes.fromhex(to_addr[2:]), amount]
    )
    hex_calldata = "0x" + calldata.hex()

    decoded = decode(["bytes4", "address", "uint256"], bytes.fromhex(hex_calldata[2:]))
    assert decoded[0] == bytes.fromhex("a9059cbb")
    assert decoded[1] == bytes.fromhex(to_addr[2:])
    assert decoded[2] == amount


def test_arc_usdc_decimals():
    """USDC on Arc has 6 decimals, not 18."""
    # This confirms that dividing by 10**6 is correct
    raw_balance = 1240500000  # 1240.50 USDC in wei-like units
    formatted = raw_balance / 10**6
    assert formatted == 1240.50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])