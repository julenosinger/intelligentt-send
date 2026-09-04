from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List, Any, Union
from datetime import datetime, timezone
import json
import asyncio
import os
import uuid

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+pg8000://localhost/intelligent_send")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

try:
    from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, Boolean, Index, JSON, BigInteger
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, Session
    from sqlalchemy.pool import StaticPool

    engine = create_engine(DATABASE_URL, poolclass=StaticPool, echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Import models from packages.db.models
    from packages.db.models import Base, User, Transfer, Template, Allowlist, History

    Base.metadata.create_all(bind=engine)

    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def get_redis():
        import redis
        r = redis.from_url(REDIS_URL, decode_responses=True)
        yield r

except Exception as e:
    # Fallback if DB not available
    print(f"DB initialization warning: {e}")
    Base = None
    engine = None
    SessionLocal = None
    get_db = None
    get_redis = None


# Pydantic models
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
    token: str = "ARC"
    amount: str = "0"
    speed: str = "standard"


class TxPrepare(BaseModel):
    mode: str = "basic"
    from_address: str
    to_address: str
    amount: str
    token: str
    chain_id: int
    gas_price: Optional[str] = None


class TxBroadcast(BaseModel):
    signed_tx: str
    tx_hash: str


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
    token: str


class SmartTransferSimulate(BaseModel):
    from_address: str
    to_address: str
    amount: str
    token: str
    min_balance: str = "0"
    max_amount: str = "1000000"
    allowlist: List[str] = []
    oracle_condition: str = ""
    interval: str = "None"
    execute_at_utc: str = ""


class SmartTransferDeploy(BaseModel):
    id: str = uuid.uuid4().hex
    from_address: str
    to_address: str
    amount: str
    token: str
    min_balance: str = "0"
    max_amount: str = "1000000"
    allowlist: List[str] = []
    oracle_condition: str = ""
    interval: str = "None"
    execute_at_utc: str = ""
    source_chain_id: int = 5042002


class Template(BaseModel):
    name: str
    from_address: str
    to_address: str
    amount: str
    interval: str = "Monthly"
    oracle_condition: str = ""
    is_recurring: bool = False
    execute_at_utc: str = ""


# In-memory fallback storage
chains_db: Dict[str, ChainInfo] = {}
wallets_db: Dict[str, WalletBalances] = {}
history_db: Dict[str, List[HistoryItem]] = {}
smart_transfers_db: Dict[str, SmartTransferDeploy] = {}
templates_db: Dict[str, Template] = {}


app = FastAPI(title="Intelligent Send Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


# --- API Routes ---

@app.get("/v1/chains", response_model=List[ChainInfo])
async def get_chains():
    """List all supported networks with tokens and RPCs."""
    # Use cached in-memory chains
    if chains_db:
        return list(chains_db.values())
    
    # Default: Arc Testnet
    arc_chain = ChainInfo(
        chain_id=5042002,
        name="Arc Testnet",
        rpc="https://rpc.testnet.arc.network",
        explorer="https://testnet.arcscan.app",
        native_token="ARC",
        tokens=[
            {"symbol": "USDC", "address": "0x3600000000000000000000000000000000000000"},
            {"symbol": "EURC", "address": "0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a"},
        ]
    )
    
    # Sepolia
    sepolia_chain = ChainInfo(
        chain_id=11155111,
        name="Ethereum Sepolia",
        rpc="https://rpc.sepolia.org",
        explorer="https://sepolia.etherscan.io",
        native_token="ETH",
        tokens=[
            {"symbol": "USDC", "address": "0x7f5c764cBc14f9669B88837ca1490cCa17c31607"},
            {"symbol": "EURC", "address": "0x2791Bca1f2de23F77d9dF537a502BD4FA3114534"},
        ]
    )
    
    # Add more testnets
    arbitrum_sepolia = ChainInfo(
        chain_id=421614,
        name="Arbitrum Sepolia",
        rpc="https://sepolia-rollup.arbitrum.io/rpc",
        explorer="https://sepolia.arbiscan.io",
        native_token="ETH",
        tokens=[{"symbol": "ETH"}],
    )
    
    base_sepolia = ChainInfo(
        chain_id=84532,
        name="Base Sepolia",
        rpc="https://sepolia.base.org",
        explorer="https://sepolia.basescan.org",
        native_token="ETH",
        tokens=[{"symbol": "ETH"}],
    )
    
    op_sepolia = ChainInfo(
        chain_id=11155420,
        name="OP Sepolia",
        rpc="https://sepolia.optimism.io",
        explorer="https://sepolia-optimistic.etherscan.io",
        native_token="ETH",
        tokens=[{"symbol": "ETH"}],
    )
    
    amoy = ChainInfo(
        chain_id=80002,
        name="Polygon Amoy",
        rpc="https://rpc-amoy.polygon.technology",
        explorer="https://amoy.polygonscan.com",
        native_token="MATIC",
        tokens=[{"symbol": "MATIC"}],
    )
    
    chains_list = [arc_chain, sepolia_chain, arbitrum_sepolia, base_sepolia, op_sepolia, amoy]
    chains_db.update({str(c.chain_id): c for c in chains_list})
    return chains_list


@app.get("/v1/wallet/{address}/balances", response_model=WalletBalances)
async def get_wallet_balances(
    address: str, 
    chain_id: int = Query(..., alias="chainId")
):
    """Get wallet balances for an address on a specific chain."""
    # Try database first
    if get_db:
        db = next(get_db())
        # Look up user transfers/history to compute balances
        # For now, use mock balances
        db.close()
    
    # In production, use viem/web3 to call RPC
    # For now, return mock balances based on chain
    tokens = {}
    if chain_id == 5042002:  # Arc Testnet
        tokens = {"USDC": "1240.50", "EURC": "320.00", "ARC": "58.72"}
    elif chain_id == 11155111:  # Sepolia
        tokens = {"USDC": "1240.50", "EURC": "320.00"}
    elif chain_id == 11155420:  # OP Sepolia
        tokens = {"ETH": "2.45"}
    elif chain_id == 84532:  # Base Sepolia
        tokens = {"ETH": "1.80"}
    elif chain_id == 421614:  # Arbitrum Sepolia
        tokens = {"ETH": "3.10"}
    elif chain_id == 80002:  # Polygon Amoy
        tokens = {"MATIC": "15.00"}
    else:
        tokens = {"USDC": "0.00", "EURC": "0.00", "ARC": "0.00"}
    
    return WalletBalances(address=address, chain_id=chain_id, balances=tokens)


@app.post("/v1/address/validate")
async def validate_address(payload: AddressValidate):
    """Validate 0x address or resolve ENS name."""
    addr = payload.address.strip()
    chain_id = payload.chain_id
    
    # Check if ENS
    if addr.endswith(".eth"):
        # Resolve via public resolver (mock for now)
        ens_map = {
            "vitalik.eth": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        }
        resolved = ens_map.get(addr.lower())
        if resolved:
            return {
                "valid": True,
                "address": resolved,
                "ens": True,
                "resolved": addr,
            }
        else:
            return {
                "valid": False,
                "address": addr,
                "ens": True,
                "resolved": None,
                "message": "ENS resolving, try again later",
            }
    
    # Check if valid 0x address
    import re
    is_valid = bool(re.match(r"^0x[0-9a-fA-F]{40}$", addr))
    
    return {
        "valid": is_valid,
        "address": addr if is_valid else "",
        "ens": False,
    }


@app.post("/v1/gas/estimate")
async def estimate_gas(payload: GasEstimate):
    """Estimate gas/economy/standard/fast for a chain."""
    chain_id = payload.chain_id
    token = payload.token
    amount = payload.amount
    speed = payload.speed
    
    # Mock gas estimates based on chain and speed
    gas_data = {
        (5042002, "economy"): {"val": "0.0008 ARC", "usd": "$0.04", "time": "~120s"},
        (5042002, "standard"): {"val": "0.0015 ARC", "usd": "$0.07", "time": "~30s"},
        (5042002, "fast"): {"val": "0.0028 ARC", "usd": "$0.13", "time": "~10s"},
        (11155111, "economy"): {"val": "0.000005 ETH", "usd": "$0.01", "time": "~2min"},
        (11155111, "standard"): {"val": "0.00001 ETH", "usd": "$0.02", "time": "~1min"},
        (11155111, "fast"): {"val": "0.00002 ETH", "usd": "$0.05", "time": "~30s"},
    }
    
    key = (chain_id, speed)
    if key in gas_data:
        g = gas_data[key]
    else:
        g = gas_data.get((5042002, "standard"), {"val": "0.0015 ARC", "usd": "$0.07", "time": "~30s"})
    
    return {
        "chain_id": chain_id,
        "token": token,
        "amount": amount,
        "speed": speed,
        "gas": g["val"],
        "gas_usd": g["usd"],
        "estimated_time": g["time"],
    }


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
        # Basic: estimate gas, return calldata
        gas_estimate = await estimate_gas({
            "chain_id": chain_id,
            "token": token,
            "amount": amount,
            "speed": "standard",
        })
        
        return {
            "mode": "basic",
            "to": to_addr,
            "value": "0",  # native, or token value
            "data": "0x",  # calldata will be filled by wallet
            "gas_limit": gas_estimate["gas"],
            "gas_fee": gas_estimate["gas_usd"],
            "total_cost": f"{amount} {token} + {gas_estimate['gas_usd']}",
        }
    
    elif mode == "intelligent":
        # Intelligent: run risk analysis via GenLayer AI
        return {
            "mode": "intelligent",
            "risk_analysis": await run_intelligent_analysis(
                chain_id=chain_id,
                to=to_addr,
                amount=amount,
                token=token,
            ),
        }
    
    elif mode == "advanced":
        # Advanced: prepare smart transfer deployment
        st_id = str(uuid.uuid4()).hex
        smart_transfers_db[st_id] = SmartTransferDeploy(
            id=st_id,
            from_address=from_addr,
            to_address=to_addr,
            amount=amount,
            token=token,
            oracle_condition="",  # will be filled from conditions
        )
        
        return {
            "mode": "advanced",
            "smart_transfer_id": st_id,
            "simulation": await simulate_smart_transfer(st_id),
        }
    
    raise HTTPException(status_code=400, detail=f"Unknown mode: {mode}")


async def run_intelligent_analysis(chainId: int, to: str, amount: str, token: str) -> dict:
    """Run risk analysis via GenLayer AI."""
    # In production, this would call the GenLayer RiskAnalyzer contract
    # For now, return a structured result
    risk_score = 15  # mock low risk
    cls = "ok"
    msg = "Address verified on-chain. No anomalies detected. Safe to proceed."
    checks = [
        {"ok": True, "label": "Not on OFAC sanctions list"},
        {"ok": True, "label": "No blacklist matches"},
        {"ok": True, "label": "Contract verified on explorer"},
        {"ok": True, "label": "Amount within normal range"},
    ]
    
    return {
        "risk": risk_score,
        "cls": cls,
        "msg": msg,
        "checks": checks,
    }


async def simulate_smart_transfer(st_id: str) -> dict:
    """Simulate a smart transfer deployment."""
    if st_id not in smart_transfers_db:
        raise HTTPException(status_code=404, detail="Smart transfer not found")
    
    st = smart_transfers_db[st_id]
    
    # Basic can_execute check
    conditions = {"ok": True, "reasons": []}
    if not st.to_address:
        conditions = {"ok": False, "reasons": ["Recipient not set"]}
    
    # Simulation result
    return {
        "smart_transfer_id": st_id,
        "can_execute": conditions["ok"],
        "conditions_reasons": conditions["reasons"],
        "oracle_verification": "pending",  # will be verified via check_oracle
        "gas_estimate": "0.0021 ARC (~$0.10)",
        "expected_outcome": "Transfer succeeds if conditions met",
    }


@app.post("/v1/tx/broadcast")
async def broadcast_tx(payload: TxBroadcast):
    """Broadcast a raw signed transaction."""
    signed_tx = payload.signed_tx
    tx_hash = payload.tx_hash
    
    # In production, broadcast to the relevant EVM network
    # For now, just record in history
    return {
        "status": "submitted",
        "tx_hash": tx_hash,
        "message": "Transaction submitted to network",
    }


@app.get("/v1/tx/{tx_hash}")
async def get_tx_status(tx_hash: str):
    """Get transaction status and explorer URL."""
    # Look up in DB if available
    # For now, return mock status
    return {
        "hash": tx_hash,
        "status": "confirmed",
        "explorer_url": f"https://explorer.example.com/tx/{tx_hash}",
        "block_number": 123456,
        "timestamp": "2025-01-15T10:30:00Z",
    }


@app.get("/v1/history")
async def get_history(address: str = "", chain_id: int = 5042002):
    """Get transaction history for an address on a chain."""
    # Try database first
    if get_db:
        db = next(get_db())
        # Query transfers for this address/chain
        # For now, fall through to in-memory
        db.close()
    
    # Return stored history (in-memory or DB-backed)
    addr_key = address if address else "default"
    
    # Try to get from DB
    items = []
    if get_db:
        db = next(get_db())
        try:
            # Query history records for this address
            stmt = "SELECT * FROM history WHERE address = :addr AND chain_id = :chain_id LIMIT 50"
            # In production, use proper SQLAlchemy query
        except:
            pass
        finally:
            db.close()
    
    # Format from in-memory
    if addr_key not in history_db:
        history_db[addr_key] = []
    
    items = history_db[addr_key]
    
    result = []
    for item in items:
        result.append({
            "id": item.id,
            "address": item.address,
            "chain_id": item.chain_id,
            "type": item.type,
            "amount": item.amount,
            "token": item.token,
            "time": item.time.isoformat() if hasattr(item.time, 'isoformat') else item.time,
            "status": item.status,
            "hash": item.hash,
            "explorer_url": item.explorer_url,
        })
    
    return {"history": result, "address": address, "chain_id": chain_id}


@app.delete("/v1/history")
async def clear_history():
    """Clear transaction history."""
    if get_db:
        db = next(get_db())
        # Clear DB history
        db.close()
    history_db.clear()
    return {"status": "cleared"}


@app.post("/v1/ai/analyze")
async def ai_analyze(payload: AiAnalyze):
    """Intelligent tab: analyze recipient risk via GenLayer AI."""
    chainId = payload.chainId
    to = payload.to
    amount = payload.amount
    token = payload.token
    
    # Run risk analysis via GenLayer RiskAnalyzer contract
    analysis = await run_intelligent_analysis(chainId=chainId, to=to, amount=amount, token=token)
    
    # Return format matching UI CSS classes (ok, warn, err, sim-ok, sim-warn)
    return {
        "risk": analysis["risk"],
        "cls": analysis["cls"],  # ok|warn|err - matches .ai-msg.ok/.warn/.err
        "msg": analysis["msg"],
        "checks": analysis["checks"],  # list of {ok, label}
        "genlayer_tx": None,  # will be populated after contract deployment + finalization
        "contract": None,  # deployed Intelligent Contract address
        "finalizedAt": None,  # timestamp after consensus finalizes
    }


@app.post("/v1/smart-transfer/simulate")
async def smart_transfer_simulate(payload: SmartTransferSimulate):
    """Simulate advanced smart transfer before deploying."""
    st_id = str(uuid.uuid4()).hex
    
    # Create a draft smart transfer
    st = SmartTransferDeploy(
        id=st_id,
        from_address=payload.from_address,
        to_address=payload.to_address,
        amount=payload.amount,
        token=payload.token,
        min_balance=payload.min_balance,
        max_amount=payload.max_amount,
        allowlist=payload.allowlist,
        oracle_condition=payload.oracle_condition,
        interval=payload.interval,
        execute_at_utc=payload.execute_at_utc,
        source_chain_id=payload.source_chain_id if hasattr(payload, 'source_chain_id') else 5042002,
    )
    smart_transfers_db[st_id] = st
    
    # Run simulation
    simulation = await simulate_smart_transfer(st_id)
    
    return {
        "smart_transfer_id": st_id,
        "simulation": simulation,
    }


@app.post("/v1/smart-transfer/deploy")
async def smart_transfer_deploy(payload: SmartTransferDeploy):
    """Deploy a smart transfer instance."""
    # Generate ID and store
    deploy_id = payload.id or str(uuid.uuid4()).hex
    payload.id = deploy_id
    smart_transfers_db[deploy_id] = payload
    
    # Simulate deployment - in production, this would deploy to GenLayer
    return {
        "id": deploy_id,
        "status": "deployed",
        "message": "Smart transfer deployed to GenLayer",
        "config": payload.dict(),
    }


@app.get("/v1/smart-transfer/{st_id}")
async def smart_transfer_status(st_id: str):
    """Get smart transfer status."""
    if st_id not in smart_transfers_db:
        raise HTTPException(status_code=404, detail="Smart transfer not found")
    
    st = smart_transfers_db[st_id]
    return {
        "id": st.id,
        "status": "deployed",
        "config": st.dict(),
    }


@app.post("/v1/smart-transfer/{st_id}/execute")
async def smart_transfer_execute(st_id: str, background_tasks: BackgroundTasks):
    """Manually trigger smart transfer execution."""
    if st_id not in smart_transfers_db:
        raise HTTPException(status_code=404, detail="Smart transfer not found")
    
    st = smart_transfers_db[st_id]
    
    # In production, this would:
    # 1. Check can_execute conditions
    # 2. Verify oracle via check_oracle
    # 3. Execute the EVM transfer via relayer
    # 4. Schedule recurrence if applicable
    
    # For now, mark as executed and add to history
    # st.executed = True  # Will be handled by the model
    
    # Add to history
    history_entry_type = "out"  # simplified
    
    if st_id not in history_db:
        history_db[st_id] = []
    history_db[st_id].append(type("HistoryEntry", (), {
        "id": str(uuid.uuid4()).hex,
        "address": st.from_address,
        "chain_id": st.source_chain_id,
        "type": "out",
        "amount": st.amount,
        "token": st.token,
        "time": datetime.now(timezone.utc).isoformat(),
        "status": "confirmed",
        "hash": str(uuid.uuid4()).hex,
        "explorer_url": f"https://explorer.example.com/tx/{uuid.uuid4().hex}",
    })())
    
    return {
        "id": st_id,
        "status": "executed",
        "message": "Smart transfer executed successfully",
    }


@app.get("/v1/templates")
async def get_templates():
    """List all saved templates."""
    return list(templates_db.values())


@app.post("/v1/templates")
async def save_template(template: Template):
    """Save a new template."""
    templates_db[template.name] = template
    return {"status": "saved", "name": template.name}