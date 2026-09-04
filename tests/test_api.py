"""Unit tests for the Intelligent Send backend (offline, no network needed)."""
import pytest
from fastapi.testclient import TestClient

import apps.api.main as main
from apps.api.main import app, CHAINS

client = TestClient(app)


def test_health():
    """GET /health returns 200."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_chains_has_arc_and_sepolia():
    """GET /v1/chains includes 5042002 and 11155111."""
    resp = client.get("/v1/chains")
    assert resp.status_code == 200
    chains = resp.json()
    chain_ids = [c["chain_id"] for c in chains]
    assert 5042002 in chain_ids
    assert 11155111 in chain_ids


def test_arc_native_token_is_usdc():
    """Arc (5042002) native gas token is USDC, and USDC address is 40 hex chars."""
    arc = CHAINS[5042002]
    assert arc["native_token"] == "USDC"
    usdc = [t for t in arc["tokens"] if t["symbol"] == "USDC"][0]
    assert len(usdc["address"]) == 42  # 0x + 40 hex
    assert usdc["address"] == "0x3600000000000000000000000000000000000000"


def test_validate_valid_address():
    """POST /v1/address/validate accepts valid 0x address."""
    resp = client.post("/v1/address/validate", json={"address": "0x742d35Cc6634C0532925a3b8D4C9B3a7e1f23450", "chain_id": 5042002})
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


def test_validate_invalid_address():
    """POST /v1/address/validate rejects invalid address."""
    resp = client.post("/v1/address/validate", json={"address": "not-an-address", "chain_id": 5042002})
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


def test_prepare_erc20_calldata():
    """POST /v1/tx/prepare returns valid ERC-20 transfer calldata for USDC."""
    from eth_abi import decode
    from decimal import Decimal

    to_address = "0x1dE27a21f321cD4a25A1D5B6e9D3f7C2b1a0E9d8"
    resp = client.post("/v1/tx/prepare", json={
        "mode": "basic",
        "from_address": "0x742d35Cc6634C0532925a3b8D4C9B3a7e1f23450",
        "to_address": to_address,
        "amount": "100",
        "token": "USDC",
        "chain_id": 5042002,
    })
    assert resp.status_code == 200
    data = resp.json()
    # to = token contract, value = 0, data = calldata
    assert data["to"].lower() == "0x3600000000000000000000000000000000000000"
    assert data["value"] == "0"
    assert data["data"].startswith("0xa9059cbb"), f"calldata: {data['data']}"
    assert len(data["data"]) == 138  # 0x + 136 hex chars

    # decode data[10:] as (address, uint256) and confirm recipient + amount
    decoded = decode(["address", "uint256"], bytes.fromhex(data["data"][10:]))
    assert decoded[0].lower() == to_address.lower()
    assert decoded[1] == int(Decimal("100") * 10**6)


def test_prepare_returns_to_and_value():
    """POST /v1/tx/prepare returns proper to and value fields."""
    resp = client.post("/v1/tx/prepare", json={
        "mode": "basic",
        "from_address": "0x742d35Cc6634C0532925a3b8D4C9B3a7e1f23450",
        "to_address": "0x1dE27a21f321cD4a25A1D5B6e9D3f7C2b1a0E9d8",
        "amount": "100",
        "token": "USDC",
        "chain_id": 5042002,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "to" in data
    assert "value" in data
    assert "gas_limit" in data


def test_ai_analyze_mock_mode(monkeypatch):
    """POST /v1/ai/analyze returns mode=mock when GENLAYER_MOCK=1."""
    monkeypatch.setattr(main, "GENLAYER_MOCK", True)
    resp = client.post("/v1/ai/analyze", json={
        "chainId": 5042002,
        "to": "0x742d35Cc6634C0532925a3b8D4C9B3a7e1f23450",
        "amount": "100",
        "token": "USDC",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "mock"
    assert "risk" in data
    assert "cls" in data
    assert "msg" in data
    assert "checks" in data


def test_ai_analyze_live_requires_pk(monkeypatch):
    """POST /v1/ai/analyze returns 400 when live but no PK/contract configured."""
    monkeypatch.setattr(main, "GENLAYER_MOCK", False)
    monkeypatch.setattr(main, "GENLAYER_ACCOUNT_PK", "")
    monkeypatch.setattr(main, "GENLAYER_RISK_CONTRACT", "")
    resp = client.post("/v1/ai/analyze", json={
        "chainId": 5042002,
        "to": "0x742d35Cc6634C0532925a3b8D4C9B3a7e1f23450",
        "amount": "100",
        "token": "USDC",
    })
    assert resp.status_code == 400


def test_wallet_balances_returns_dict():
    """GET /v1/wallet/:addr/balances returns balances dict."""
    resp = client.get("/v1/wallet/0x742d35Cc6634C0532925a3b8D4C9B3a7e1f23450/balances?chainId=5042002")
    assert resp.status_code == 200
    data = resp.json()
    assert "balances" in data
    assert "address" in data
    assert "chain_id" in data


def test_history_endpoint():
    """GET /v1/history returns history list."""
    resp = client.get("/v1/history?address=0x742d35Cc6634C0532925a3b8D4C9B3a7e1f23450&chain_id=5042002")
    assert resp.status_code == 200
    data = resp.json()
    assert "history" in data
    assert "address" in data


def test_gas_estimate():
    """POST /v1/gas/estimate returns gas data."""
    resp = client.post("/v1/gas/estimate", json={
        "chain_id": 5042002,
        "token": "USDC",
        "amount": "100",
        "speed": "standard",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "gas" in data
    assert "gas_usd" in data
    assert "estimated_time" in data


def test_simulate_smart_transfer():
    """POST /v1/smart-transfer/simulate returns simulation."""
    resp = client.post("/v1/smart-transfer/simulate", json={
        "from_address": "0x742d35Cc6634C0532925a3b8D4C9B3a7e1f23450",
        "to_address": "0x1dE27a21f321cD4a25A1D5B6e9D3f7C2b1a0E9d8",
        "amount": "100",
        "token": "USDC",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "smart_transfer_id" in data
    assert "simulation" in data


def test_chain_ids_list():
    """CHAINS dict contains expected chain IDs."""
    assert 5042002 in CHAINS
    assert 11155111 in CHAINS
    assert isinstance(CHAINS[5042002]["name"], str)
    assert isinstance(CHAINS[11155111]["name"], str)


@pytest.mark.integration
def test_broadcast_returns_hash():
    """POST /v1/tx/broadcast returns a tx_hash (requires a valid signed tx + live RPC)."""
    resp = client.post("/v1/tx/broadcast", json={
        "signed_tx": "0xabc123def456",
        "chain_id": 5042002,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "tx_hash" in data
    assert "status" in data
    assert data["status"] == "submitted"
