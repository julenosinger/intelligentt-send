# Intelligent Send

A Web3 payment platform built on GenLayer Intelligent Contracts and Arc Testnet.

## Quick Start

```bash
# Clone repo
git clone https://github.com/julenosinger/intelligentt-send.git
cd intelligentt-send

# Setup environment
cp .env.example .env
# Edit .env with your values (no secrets committed)

# Create venv and install
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start backend
uvicorn apps.api.main:app --reload --port 8000

# In another terminal, serve the frontend
python -m http.server 5500

# Open http://127.0.0.1:5500/index.html
```

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/chains` | List supported networks |
| GET | `/v1/wallet/{addr}/balances?chainId=5042002` | Get balances on Arc |
| POST | `/v1/address/validate` | Validate 0x address or ENS |
| POST | `/v1/gas/estimate` | Estimate gas fees |
| POST | `/v1/tx/prepare` | Prepare transaction (basic/intelligent/advanced) |
| POST | `/v1/tx/broadcast` | Broadcast signed tx |
| GET | `/v1/tx/{hash}?chainId=5042002` | Check tx status |
| POST | `/v1/ai/analyze` | GenLayer AI risk analysis |
| POST | `/v1/smart-transfer/simulate` | Simulate smart transfer |
| POST | `/v1/smart-transfer/deploy` | Deploy smart transfer |
| GET | `/v1/history` | Transaction history |
| GET | `/health` | Health check |

## Supported Networks

| Chain ID | Name | RPC | Explorer |
|----------|------|-----|----------|
| 5042002 | Arc Testnet | `https://rpc.testnet.arc.network` | `https://testnet.arcscan.app` |
| 11155111 | Ethereum Sepolia | `https://rpc.sepolia.org` | `https://sepolia.etherscan.io` |
| 421614 | Arbitrum Sepolia | `https://sepolia-rollup.arbitrum.io/rpc` | `https://sepolia.arbiscan.io` |
| 84532 | Base Sepolia | `https://sepolia.base.org` | `https://sepolia.basescan.org` |
| 11155420 | OP Sepolia | `https://sepolia.optimism.io` | `https://sepolia-optimistic.etherscan.io` |
| 80002 | Polygon Amoy | `https://rpc-amoy.polygon.technology` | `https://amoy.polygonscan.com` |

## GenLayer

### Bradbury (Testnet)
- RPC: `https://rpc-bradbury.genlayer.com`
- Chain: 4221
- Faucet: `https://testnet-faucet.genlayer.foundation`

### Studio (Chain 61999)
- URL: `https://studio.genlayer.com`

### Deploy Contracts
```bash
python scripts/deploy_genlayer.py
```

## Environment Variables

See `.env.example` for all required variables.

Key variables:
- `DATABASE_URL` - SQLite default or PostgreSQL
- `GENLAYER_RPC` - GenLayer RPC URL
- `GENLAYER_NETWORK` - "studio" or "bradbury"
- `GENLAYER_ACCOUNT_PK` - Your testnet account key
- `GENLAYER_MOCK=1` - Use mock responses when GenLayer is down
- `GENLAYER_RISK_CONTRACT` - Deployed RiskAnalyzer contract address
- `GENLAYER_SMART_TRANSFER_CONTRACT` - Deployed SmartTransfer contract address

## Important Notes

### Arc Testnet Gas
**USDC is the native gas token on Arc**, not ARC. The adapter correctly handles this.

### ERC-20 Calldata
`/v1/tx/prepare` returns proper ERC-20 transfer calldata (`0xa9059cbb` + 32-byte to + 32-byte amount). Verify with Remix or `cast`.

### GenLayer AI Analysis
When `GENLAYER_MOCK=1`, the API returns a mock risk score (fixed 15). When disabled and a contract is deployed, it makes a real write to the RiskAnalyzer contract on GenLayer and waits for finalization. If GenLayer is down, it returns 503 with an explicit message.

### No `api.genlayer.com`
The codebase does not reference `api.genlayer.com` for OFAC or any other service. Web evidence uses `gl.nondet.web.get`/`gl.nondet.web.render` on public explorer pages and official docs. This is not legal compliance.

## Test

```bash
# Run all tests
pytest tests/ -v

# Skip integration tests
pytest tests/ -v -m "not integration"

# Run with GenLayer
pytest tests/ -v -m integration
```

## Limitations

- Smart transfer recurring execution is v2 (backend job scheduler)
- Relayer requires `RELAYER_PK` set and testnet funds
- GenLayer contracts require Studio or Bradbury deployment before API works
- ENS resolution requires public resolver

## License
Educational purposes only. See GenLayer docs for details.