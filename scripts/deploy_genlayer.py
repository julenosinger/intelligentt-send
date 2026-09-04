"""Deploy the RiskAnalyzer and SmartTransfer Intelligent Contracts to GenLayer.

Usage:
    python scripts/deploy_genlayer.py

Requires GENLAYER_ACCOUNT_PK (and optionally GENLAYER_NETWORK, default "studio").
Writes the deployed addresses to deployments/addresses.json.

NOTE: SmartTransfer is deployed here as a template with empty config. Real
smart-transfer instances are deployed per-transfer via POST /v1/smart-transfer/deploy
with their own constructor arguments.
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts" / "genlayer"
ADDRESSES = ROOT / "deployments" / "addresses.json"

GENLAYER_NETWORK = os.getenv("GENLAYER_NETWORK", "studio").lower()
GENLAYER_ACCOUNT_PK = os.getenv("GENLAYER_ACCOUNT_PK", "")


def build_client():
    from genlayer_py import create_account, create_client
    from genlayer_py import chains as gl_chains

    chain_map = {
        "bradbury": gl_chains.testnet_bradbury,
        "studio": gl_chains.studionet,
        "studionet": gl_chains.studionet,
        "studio-dev": gl_chains.studio_devnet,
        "localnet": gl_chains.localnet,
    }
    chain = chain_map.get(GENLAYER_NETWORK, gl_chains.studionet)
    account = create_account(GENLAYER_ACCOUNT_PK) if GENLAYER_ACCOUNT_PK else None
    return create_client(chain=chain, account=account)


def deploy(client, code: str, args: list) -> str:
    tx_hash = client.deploy_contract(code=code, args=args)
    tx = client.wait_for_finalization(tx_hash)

    decoded = tx.get("tx_data_decoded") if isinstance(tx, dict) else None
    addr = decoded.get("contract_address") if isinstance(decoded, dict) else None
    if not addr and isinstance(tx, dict):
        addr = tx.get("recipient")

    if not addr or addr == "0x" + "0" * 40:
        raise RuntimeError(f"Deploy finalized without a contract address (tx {tx_hash})")
    return addr


def main() -> None:
    if not GENLAYER_ACCOUNT_PK:
        print("ERROR: GENLAYER_ACCOUNT_PK is not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    client = build_client()

    risk_code = (CONTRACTS / "risk_analyzer.py").read_text(encoding="utf-8")
    st_code = (CONTRACTS / "smart_transfer.py").read_text(encoding="utf-8")

    print(f"Deploying RiskAnalyzer on {GENLAYER_NETWORK} ...")
    risk_addr = deploy(client, risk_code, [])

    print(f"Deploying SmartTransfer template on {GENLAYER_NETWORK} ...")
    st_args = ["", "", "", "0", "0", "0", "[]", "", "None", "", "5042002"]
    st_addr = deploy(client, st_code, st_args)

    result = {
        "network": GENLAYER_NETWORK,
        "risk_analyzer": risk_addr,
        "smart_transfer": st_addr,
    }
    ADDRESSES.parent.mkdir(parents=True, exist_ok=True)
    ADDRESSES.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"Saved to {ADDRESSES}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
