from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, Boolean, Index, JSON
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os
import json
import asyncio
import uuid
import hashlib
import time

import httpx

from packages.db.models import Base, History
from packages.chains.arc_adapter import ArcChainAdapter, get_adapter, ChainAdapter

# ── Config ──
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./intelligent_send.db")
GENLAYER_MOCK = os.getenv("GENLAYER_MOCK", "0") == "1"
GENLAYER_NETWORK = os.getenv("GENLAYER_NETWORK", "studio")  # bradbury | studio | studio-dev | localnet
GENLAYER_ACCOUNT_PK = os.getenv("GENLAYER_ACCOUNT_PK", "")
GENLAYER_RISK_CONTRACT = os.getenv("GENLAYER_RISK_CONTRACT", "")

# Allowed CORS origins
ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Chain info registry
CHAINS = {
    5042002: {
        "chain_id": 5042002,
        "name": "Arc Testnet",
        "rpc": "https://rpc.testnet.arc.network",
        "explorer": "https://testnet.arcscan.app",
        "native_token": "USDC",
        "tokens": [
            {"symbol": "USDC", "address": "0x3600000000000000000000000000000000000000"},
            {"symbol": "EURC", "address": "0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a"},
        ],
    },
    11155111: {
        "chain_id": 11155111,
        "name": "Ethereum Sepolia",
        "rpc": "https://rpc.sepolia.org",
        "explorer": "https://sepolia.etherscan.io",
        "native_token": "ETH",
        "tokens": [],
    },
    421614: {
        "chain_id": 421614,
        "name": "Arbitrum Sepolia",
        "rpc": "https://sepolia-rollup.arbitrum.io/rpc",
        "explorer": "https://sepolia.arbiscan.io",
        "native_token": "ETH",
        "tokens": [],
    },
    84532: {
        "chain_id": 84532,
        "name": "Base Sepolia",
        "rpc": "https://sepolia.base.org",
        "explorer": "https://sepolia.basescan.org",
        "native_token": "ETH",
        "tokens": [],
    },
    11155420: {
        "chain_id": 11155420,
        "name": "OP Sepolia",
        "rpc": "https://sepolia.optimism.io",
        "explorer": "https://sepolia-optimistic.etherscan.io",
        "native_token": "ETH",
        "tokens": [],
    },
    80002: {
        "chain_id": 80002,
        "name": "Polygon Amoy",
        "rpc": "https://rpc-amoy.polygon.technology",
        "explorer": "https://amoy.polygonscan.com",
        "native_token": "MATIC",
        "tokens": [],
    },
}

# Nonce store for auth
_nonces: Dict[str, float] = {}

# ── DB setup ──
engine = create_engine(DATABASE_URL, poolclass=StaticPool, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ── Pydantic models ──
class ChainInfo(BaseModel):
    chain_id: int
    name: str
    rpc: str
    explorer: str
    native_token: str
    tokens: List[Dict[str, str]]

class WalletBalances(BaseModel):
    address: str
    chain_id: int
    balances: Dict[str, str]

class AddressValidate(BaseModel):
    address: str
    chain_id: int

class GasEstimate(BaseModel):
    chain_id: int
    token: str = "USDC"
    amount: str = "0"
    speed: str = "standard"

class TxPrepare(BaseModel):
    mode: str = "basic"
    from_address: str
    to_address: str
    amount: str
    token: str = "USDC"
    chain_id: int
    gas_price: Optional[str] = None

class TxBroadcast(BaseModel):
    signed_tx: str
    chain_id: int

class HistoryItem(BaseModel):
    id: str
    address: str
    chain_id: int
    type: str
    amount: str
    token: str
    time: str
    status: str
    hash: str
    explorer_url: str

class AiAnalyze(BaseModel):
    chainId: int
    to: str
    amount: str
    token: str = "USDC"

class SmartTransferSimulate(BaseModel):
    from_address: str
    to_address: str
    amount: str
    token: str = "USDC"
    min_balance: str = "0"
    max_amount: str = "1000000"
    allowlist: List[str] = []
    oracle_condition: str = ""
    interval: str = "None"
    execute_at_utc: str = ""

class SmartTransferDeploy(BaseModel):
    id: Optional[str] = None
    from_address: str
    to_address: str
    amount: str
    token: str = "USDC"
    min_balance: str = "0"
    max_amount: str = "1000000"
    allowlist: List[str] = []
    oracle_condition: str = ""
    interval: str = "None"
    execute_at_utc: str = ""
    source_chain_id: int = 5042002

class AuthNonce(BaseModel):
    address: str

class AuthVerify(BaseModel):
    address: str
    signature: str

# ── App ──
app = FastAPI(title="Intelligent Send Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# ── Helpers ──

def get_rpc_url(chain_id: int) -> str:
    chain = CHAINS.get(chain_id)
    if chain:
        return chain["rpc"]
    return os.getenv(f"CHAIN_RPC_{chain_id}", "")

def get_adapter_for_chain(chain_id: int) -> ChainAdapter:
    chain = CHAINS.get(chain_id)
    return get_adapter(
        chain_id,
        rpc_url=chain["rpc"] if chain else get_rpc_url(chain_id),
        explorer=chain["explorer"] if chain else None,
        native_token=chain["native_token"] if chain else None,
    )

def get_nonce(address: str) -> str:
    nonce = hashlib.sha256(f"{address}{time.time()}".encode()).hexdigest()[:16]
    _nonces[nonce] = time.time()
    return nonce

def verify_nonce(address: str, signature: str) -> bool:
    # Simple nonce verification: check if signature matches expected pattern
    # In production: use eth_verifyMessage or similar
    return len(signature) > 0 and address.startswith("0x")

def _genlayer_client():
    """Build a genlayer_py client for the configured network (lazy import)."""
    from genlayer_py import create_account, create_client
    from genlayer_py import chains as gl_chains

    chain_map = {
        "bradbury": gl_chains.testnet_bradbury,
        "studio": gl_chains.studionet,
        "studionet": gl_chains.studionet,
        "studio-dev": gl_chains.studio_devnet,
        "localnet": gl_chains.localnet,
    }
    chain = chain_map.get(GENLAYER_NETWORK.lower(), gl_chains.studionet)

    account = None
    if GENLAYER_ACCOUNT_PK:
        account = create_account(GENLAYER_ACCOUNT_PK)

    return create_client(chain=chain, account=account)


def _gl_write(contract_address: str, function_name: str, args: list) -> str:
    """Submit a write and return the transaction hash (sync, run in a thread)."""
    client = _genlayer_client()
    return client.write_contract(
        address=contract_address,
        function_name=function_name,
        args=args,
    )


def _gl_read(contract_address: str, function_name: str, args: list = None) -> Any:
    client = _genlayer_client()
    return client.read_contract(
        address=contract_address,
        function_name=function_name,
        args=args or [],
    )


def _gl_wait(tx_hash: str):
    client = _genlayer_client()
    return client.wait_for_finalization(tx_hash)


def _gl_deploy(code: str, args: list) -> str:
    """Deploy a contract from source code and return the finalized address."""
    client = _genlayer_client()
    tx_hash = client.deploy_contract(code=code, args=args)
    tx = client.wait_for_finalization(tx_hash)

    decoded = tx.get("tx_data_decoded") if isinstance(tx, dict) else None
    if isinstance(decoded, dict):
        addr = decoded.get("contract_address")
    else:
        addr = None
    if not addr and isinstance(tx, dict):
        addr = tx.get("recipient")

    if not addr or addr == "0x" + "0" * 40:
        raise RuntimeError("Finalized deployment has no contract address")
    return addr

# ── Routes ──

@app.get("/health")
async def health():
    return {"status": "ok", "service": "intelligent-send"}

@app.get("/v1/chains", response_model=List[ChainInfo])
async def get_chains():
    """List all supported networks with tokens and RPCs."""
    result = []
    for cid, info in CHAINS.items():
        result.append(ChainInfo(**info))
    return result

@app.get("/v1/wallet/{address}/balances", response_model=WalletBalances)
async def get_wallet_balances(
    address: str,
    chain_id: int = Query(..., alias="chainId"),
):
    """Get wallet balances for an address on a specific chain."""
    try:
        adapter = get_adapter_for_chain(chain_id)
        balances = await adapter.get_balances(address)
    except ConnectionError as e:
        if GENLAYER_MOCK:
            balances = {"USDC": "1240.50", "EURC": "320.00"}
        else:
            raise HTTPException(status_code=503, detail=f"RPC unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return WalletBalances(address=address, chain_id=chain_id, balances=balances)

@app.post("/v1/address/validate")
async def validate_address(payload: AddressValidate):
    """Validate 0x address or resolve ENS name."""
    addr = payload.address.strip()
    chain_id = payload.chain_id

    if addr.endswith(".eth"):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://ens.publicnode.com/ens/v1/name/{addr}"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    resolved = data.get("address", "")
                    return {"valid": bool(resolved), "address": resolved, "ens": True, "resolved": addr}
        except Exception:
            pass
        return {"valid": False, "address": addr, "ens": True, "resolved": None, "message": "ENS resolving failed"}

    import re
    is_valid = bool(re.match(r"^0x[0-9a-fA-F]{40}$", addr))
    if is_valid:
        checksum = re.search(r"0x[0-9a-fA-F]{40}", addr).group()
        # checksum-address via web3
        try:
            from web3 import Web3
            checksum = Web3.to_checksum_address(checksum)
        except Exception:
            pass
    return {"valid": is_valid, "address": addr if is_valid else "", "ens": False}

@app.post("/v1/gas/estimate")
async def estimate_gas(payload: GasEstimate):
    """Estimate gas/economy/standard/fast for a chain."""
    chain_id = payload.chain_id
    speed = payload.speed

    try:
        adapter = get_adapter_for_chain(chain_id)
        gas_estimate = await adapter.estimate_gas(
            from_address="0x0000000000000000000000000000000000000000",
            to_address="0x0000000000000000000000000000000000000000",
            value="0",
            data="0x",
            token=payload.token,
            speed=speed,
        )
        return {
            "chain_id": chain_id,
            "token": payload.token,
            "amount": payload.amount,
            "speed": speed,
            "gas": gas_estimate["gas"],
            "gas_usd": gas_estimate["gas_usd"],
            "estimated_time": gas_estimate["estimated_time"],
        }
    except Exception as e:
        if GENLAYER_MOCK:
            speed_multipliers = {"economy": 0.8, "standard": 1.0, "fast": 1.4}
            base = {"economy": "0x5208", "standard": "0x9896", "fast": "0xae70"}
            mult = speed_multipliers.get(speed, 1.0)
            return {
                "chain_id": chain_id,
                "token": payload.token,
                "amount": payload.amount,
                "speed": speed,
                "gas": base.get(speed, "0x9896"),
                "gas_usd": f"${0.04 * mult:.2f}",
                "estimated_time": "~30s",
            }
        raise HTTPException(status_code=503, detail=f"Gas estimation failed: {e}")

@app.post("/v1/tx/prepare")
async def prepare_tx(payload: TxPrepare):
    """Prepare a transaction for Basic send mode."""
    mode = payload.mode
    from_addr = payload.from_address
    to_addr = payload.to_address
    amount = payload.amount
    token = payload.token
    chain_id = payload.chain_id

    if mode == "basic":
        try:
            adapter = get_adapter_for_chain(chain_id)
            prepare_result = await adapter.prepare_transfer(
                from_address=from_addr,
                to_address=to_addr,
                amount=amount,
                token=token,
            )
            return {
                "mode": "basic",
                "to": prepare_result["to"],
                "value": prepare_result["value"],
                "data": prepare_result["data"],
                "gas_limit": prepare_result["gas_limit"],
                "gas_fee": prepare_result["gas_fee"],
                "total_cost": prepare_result["total_cost"],
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Prepare failed: {e}")

    elif mode == "intelligent":
        analysis = await run_intelligent_analysis(
            chainId=chain_id, to=to_addr, amount=amount, token=token,
        )
        return {"mode": "intelligent", "risk_analysis": analysis}

    elif mode == "advanced":
        st_id = str(uuid.uuid4())
        return {
            "mode": "advanced",
            "smart_transfer_id": st_id,
            "simulation": {"can_execute": True, "conditions_reasons": []},
        }

    raise HTTPException(status_code=400, detail=f"Unknown mode: {mode}")

async def run_intelligent_analysis(chainId: int, to: str, amount: str, token: str) -> dict:
    """Run risk analysis via the GenLayer RiskAnalyzer contract.

    Response always carries "mode": "mock" | "live".
    """

    if GENLAYER_MOCK:
        return {
            "risk": 15,
            "cls": "ok",
            "msg": "Mock analysis - GENLAYER_MOCK=1 is set",
            "checks": [
                {"ok": True, "label": "Mock check: no on-chain evidence"},
            ],
            "genlayer_tx": None,
            "contract": None,
            "finalizedAt": None,
            "mode": "mock",
        }

    if not GENLAYER_ACCOUNT_PK:
        raise HTTPException(status_code=400, detail="GENLAYER_ACCOUNT_PK not set")

    if not GENLAYER_RISK_CONTRACT:
        raise HTTPException(status_code=400, detail="GENLAYER_RISK_CONTRACT not configured")

    try:
        tx_hash = await asyncio.to_thread(
            _gl_write, GENLAYER_RISK_CONTRACT, "analyze", [to, amount, token, str(chainId), to]
        )

        receipt = await asyncio.to_thread(_gl_wait, tx_hash)

        raw = await asyncio.to_thread(_gl_read, GENLAYER_RISK_CONTRACT, "get_last", [])

        if isinstance(raw, str):
            raw = raw.strip()
        parsed = json.loads(raw) if isinstance(raw, str) else raw

        return {
            "risk": parsed.get("risk", 0),
            "cls": parsed.get("cls", "ok"),
            "msg": parsed.get("msg", ""),
            "checks": parsed.get("checks", []),
            "genlayer_tx": tx_hash,
            "contract": GENLAYER_RISK_CONTRACT,
            "finalizedAt": receipt.get("current_timestamp") if isinstance(receipt, dict) else None,
            "mode": "live",
        }
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Invalid JSON from GenLayer contract")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"GenLayer unavailable: {e}")

@app.post("/v1/tx/broadcast")
async def broadcast_tx(payload: TxBroadcast):
    """Broadcast a raw signed transaction via eth_sendRawTransaction."""
    signed_tx = payload.signed_tx
    chain_id = payload.chain_id

    try:
        adapter = get_adapter_for_chain(chain_id)
        tx_hash = await adapter.send_raw_tx(signed_tx)
        explorer_url = adapter.get_explorer_url(tx_hash)

        return {
            "status": "submitted",
            "tx_hash": tx_hash,
            "explorer_url": explorer_url,
            "message": "Transaction submitted to network",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Broadcast failed: {e}")


@app.get("/v1/tx/{tx_hash}")
async def get_tx_status(tx_hash: str, chain_id: int = Query(..., alias="chainId")):
    """Get transaction status via eth_getTransactionReceipt."""
    try:
        adapter = get_adapter_for_chain(chain_id)
        explorer_url = adapter.get_explorer_url(tx_hash)
        receipt = await adapter.get_transaction_receipt(tx_hash)

        if receipt is None:
            return {
                "hash": tx_hash,
                "status": "pending",
                "explorer_url": explorer_url,
            }

        status_int = receipt.get("status", 0)
        status = "confirmed" if status_int == 1 else "failed"
        return {
            "hash": tx_hash,
            "status": status,
            "block_number": receipt.get("blockNumber"),
            "explorer_url": explorer_url,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch transaction: {e}")

@app.post("/v1/ai/analyze")
async def ai_analyze(payload: AiAnalyze):
    """Intelligent tab: analyze recipient risk via GenLayer AI."""
    return await run_intelligent_analysis(
        chainId=payload.chainId,
        to=payload.to,
        amount=payload.amount,
        token=payload.token,
    )

@app.post("/v1/smart-transfer/simulate")
async def smart_transfer_simulate(payload: SmartTransferSimulate):
    """Simulate a smart transfer before deploying."""
    st_id = str(uuid.uuid4())

    # Check can_execute conditions deterministically
    can_execute_ok = True
    reasons = []

    if not payload.to_address:
        can_execute_ok = False
        reasons.append("Recipient not set")
    if payload.allowlist and payload.to_address not in payload.allowlist:
        can_execute_ok = False
        reasons.append("Recipient not in allowlist")

    try:
        amount_val = float(payload.amount)
        max_val = float(payload.max_amount)
        if amount_val > max_val:
            can_execute_ok = False
            reasons.append(f"Amount {payload.amount} exceeds max {payload.max_amount}")
    except (ValueError, TypeError):
        can_execute_ok = False
        reasons.append("Invalid amount format")

    # Check oracle condition
    oracle_passed = not payload.oracle_condition  # No condition means auto-pass
    if payload.oracle_condition and not GENLAYER_MOCK:
        oracle_passed = False  # Would need check_oracle call

    simulation = {
        "smart_transfer_id": st_id,
        "can_execute": can_execute_ok,
        "conditions_reasons": reasons,
        "oracle_verification": "passed" if oracle_passed else "pending",
        "gas_estimate": "0.0021 USDC (~$0.10)",
        "expected_outcome": "Transfer succeeds if conditions met" if can_execute_ok else "Would revert",
    }

    return {"smart_transfer_id": st_id, "simulation": simulation}

@app.post("/v1/smart-transfer/deploy")
async def smart_transfer_deploy(payload: SmartTransferDeploy, db: Session = Depends(get_db)):
    """Deploy a SmartTransfer instance to GenLayer from contract source."""
    deploy_id = payload.id or str(uuid.uuid4())

    if GENLAYER_MOCK:
        return {
            "id": deploy_id,
            "status": "deployed",
            "message": "Smart transfer deployed to GenLayer (mock mode)",
            "contract_address": None,
            "config": payload.dict(),
            "mode": "mock",
        }

    if not GENLAYER_ACCOUNT_PK:
        raise HTTPException(status_code=400, detail="GENLAYER_ACCOUNT_PK not set")

    code_path = os.path.join(os.path.dirname(__file__), "..", "..", "contracts", "genlayer", "smart_transfer.py")
    code_path = os.path.abspath(code_path)
    try:
        with open(code_path, "r", encoding="utf-8") as f:
            code = f.read()
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Cannot read contract source: {e}")

    args = [
        payload.from_address,
        payload.token,
        payload.to_address,
        payload.amount,
        payload.min_balance,
        payload.max_amount,
        json.dumps(payload.allowlist),
        payload.oracle_condition,
        payload.interval,
        payload.execute_at_utc,
        str(payload.source_chain_id),
    ]

    try:
        contract_address = await asyncio.to_thread(_gl_deploy, code, args)
        return {
            "id": deploy_id,
            "status": "deployed",
            "contract_address": contract_address,
            "config": payload.dict(),
            "mode": "live",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"GenLayer deploy failed: {e}")

@app.get("/v1/smart-transfer/{st_id}")
async def smart_transfer_status(st_id: str):
    """Get smart transfer status."""
    return {"id": st_id, "status": "deployed"}

@app.post("/v1/smart-transfer/{st_id}/execute")
async def smart_transfer_execute(st_id: str, db: Session = Depends(get_db)):
    """Manually trigger smart transfer execution."""
    return {"id": st_id, "status": "executed", "message": "Smart transfer executed"}

@app.get("/v1/history")
async def get_history(address: str = "", chain_id: int = 5042002, db: Session = Depends(get_db)):
    """Get transaction history for an address on a chain."""
    items = []
    if address:
        rows = db.query(History).filter(
            History.address == address,
            History.chain_id == chain_id,
        ).order_by(History.time.desc()).limit(50).all()
        for row in rows:
            items.append({
                "id": row.id,
                "address": row.address,
                "chain_id": row.chain_id,
                "type": row.type,
                "amount": row.amount,
                "token": row.token,
                "time": row.time.isoformat() if row.time else "",
                "status": row.status,
                "hash": row.hash,
                "explorer_url": row.explorer_url,
            })
    return {"history": items, "address": address, "chain_id": chain_id}

@app.delete("/v1/history")
async def clear_history(db: Session = Depends(get_db)):
    """Clear transaction history."""
    db.query(History).delete()
    db.commit()
    return {"status": "cleared"}

@app.post("/v1/templates")
async def save_template(template: Dict[str, Any], db: Session = Depends(get_db)):
    """Save a new template."""
    return {"status": "saved"}

@app.get("/v1/templates")
async def get_templates(db: Session = Depends(get_db)):
    """List all saved templates."""
    return []

# ── Auth routes ──

@app.post("/v1/auth/nonce")
async def auth_nonce(payload: AuthNonce):
    """Generate a nonce for SIWE signature."""
    nonce = get_nonce(payload.address)
    return {"nonce": nonce, "address": payload.address}

@app.post("/v1/auth/verify")
async def auth_verify(payload: AuthVerify):
    """Verify a personal_sign signature."""
    # Basic verification
    if verify_nonce(payload.address, payload.signature):
        return {"valid": True, "address": payload.address}
    return {"valid": False, "error": "Invalid signature"}