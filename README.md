# Intelligent Send

A Web3 payment platform built on GenLayer Intelligent Contracts and Arc Testnet.

The backend is FastAPI + SQLAlchemy (SQLite default) + web3. Intelligent contracts
run on GenLayer (Studio/Bradbury). The frontend is a single static `index.html`.

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

The app runs without Postgres/Redis (SQLite is the default). Reads, balances,
calldata, and broadcast go to the real chain RPCs. GenLayer AI analysis is
mock by default; set `GENLAYER_MOCK=0` and deploy the contract to go live.

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/v1/chains` | List supported networks |
| GET | `/v1/wallet/{addr}/balances?chainId=5042002` | On-chain balances |
| POST | `/v1/address/validate` | Validate 0x address or ENS |
| POST | `/v1/gas/estimate` | Estimate gas fees |
| POST | `/v1/tx/prepare` | Prepare transaction (basic/intelligent/advanced) |
| POST | `/v1/tx/broadcast` | Broadcast a raw signed tx (`eth_sendRawTransaction`) |
| GET | `/v1/tx/{hash}?chainId=5042002` | Tx status from `eth_getTransactionReceipt` |
| POST | `/v1/ai/analyze` | GenLayer AI risk analysis (returns `mode: mock\|live`) |
| POST | `/v1/smart-transfer/simulate` | Simulate a smart transfer |
| POST | `/v1/smart-transfer/deploy` | Deploy a SmartTransfer instance |
| GET | `/v1/history` | Transaction history |
| GET | `/v1/templates` | List templates |

## Supported Networks

| Chain ID | Name | RPC | Explorer | Native gas |
|----------|------|-----|----------|-----------|
| 5042002 | Arc Testnet | `https://rpc.testnet.arc.network` | `https://testnet.arcscan.app` | USDC |
| 11155111 | Ethereum Sepolia | `https://rpc.sepolia.org` | `https://sepolia.etherscan.io` | ETH |
| 421614 | Arbitrum Sepolia | `https://sepolia-rollup.arbitrum.io/rpc` | `https://sepolia.arbiscan.io` | ETH |
| 84532 | Base Sepolia | `https://sepolia.base.org` | `https://sepolia.basescan.org` | ETH |
| 11155420 | OP Sepolia | `https://sepolia.optimism.io` | `https://sepolia-optimistic.etherscan.io` | ETH |
| 80002 | Polygon Amoy | `https://rpc-amoy.polygon.technology` | `https://amoy.polygonscan.com` | MATIC |

## Arc Testnet notes

- **USDC is the native gas token** on Arc. There is no separate "ARC" token
  contract verified on testnet, so `/v1/chains` does not advertise one.
- The USDC predeploy is `0x3600000000000000000000000000000000000000` (6 decimals).
- **ERC-20 vs native branch:** in `prepare_transfer`, a token in the `tokens`
  map (USDC/EURC) is always an ERC-20 transfer — `to` = the token contract,
  `value` = `"0"`, `data` = `transfer(address,uint256)` calldata
  (`0xa9059cbb` + 32-byte address + 32-byte amount). The `"ARC"`/`"native"`
  branch is a plain value send and is not the gas-token path; the two branches
  are never mixed. Amounts are computed with `Decimal`, not `float`.

## GenLayer

Networks (see https://docs.genlayer.com/developers/networks):

| `GENLAYER_NETWORK` | RPC | Chain ID |
|--------------------|-----|----------|
| `bradbury` | `https://rpc-bradbury.genlayer.com` | 4221 |
| `studio` (default) | `https://studio.genlayer.com/api` | 61999 |
| `studio-dev` | `https://studio-dev.genlayer.com/api` | 61997 |
| `localnet` | `http://localhost:4000/api` | 61127 |

The client is `genlayer-py` (`genlayer_py`), pinned in `requirements.txt`. The
API uses `create_account`/`create_client` and the sync `write_contract`,
`read_contract`, `deploy_contract`, `wait_for_finalization` methods (run in
`asyncio.to_thread`).

### Deploying the contracts

The contracts live in `contracts/genlayer/` (`risk_analyzer.py`,
`smart_transfer.py`). Deploy with:

```bash
python scripts/deploy_genlayer.py
```

This reads the two `.py` files, deploys them, waits for finalization, and
writes the addresses to `deployments/addresses.json` (it exits with an error if
`GENLAYER_ACCOUNT_PK` is missing). You can also deploy manually from the
[GenLayer Studio](https://studio.genlayer.com); in that case copy the deployed
`RiskAnalyzer` address into `GENLAYER_RISK_CONTRACT` in your `.env`.

`SmartTransfer` is deployed as an empty template by the script; real
smart-transfer instances are deployed per-transfer via
`POST /v1/smart-transfer/deploy`.

## Environment Variables

See `.env.example`. Key variables:

- `DATABASE_URL` — SQLite default (`sqlite:///./intelligent_send.db`)
- `GENLAYER_NETWORK` — `bradbury` | `studio` | `studio-dev` | `localnet`
- `GENLAYER_ACCOUNT_PK` — testnet account private key (never commit)
- `GENLAYER_RISK_CONTRACT` — deployed RiskAnalyzer address
- `GENLAYER_MOCK=1` — serve mock analysis instead of hitting GenLayer

## AI Analysis

`POST /v1/ai/analyze` always returns a `mode` field:

- `"mock"` when `GENLAYER_MOCK=1` (fixed low score, no network).
- `"live"` otherwise: it submits an `analyze` write to the RiskAnalyzer
  contract, waits for finalization, and reads `get_last` (a JSON string). If the
  network is down it returns `503`; if the contract is not configured or the key
  is missing it returns `400` — it never fabricates a score.

The RiskAnalyzer contract makes a single non-comparative LLM call
(`gl.eq_principle.prompt_non_comparative`) and optionally renders the target
chain explorer page. When the fetch fails, the prompt input says
`SOURCE_UNAVAILABLE` so the model does not invent OFAC/sanction/verification
facts. This is a heuristic risk score, **not legal compliance**.

## Test

```bash
# Run offline unit tests (default)
pytest tests/ -v -m "not integration"

# Run live network tests
pytest tests/ -v -m integration
```

## Limitations

- `SmartTransfer` recurring execution is not implemented (v2): `interval` is
  stored but enforced off-chain by a relayer, which is not shipped here.
- The relayer (`RELAYER_PK`) is not implemented — the EVM transfer is submitted
  by the user's wallet in the frontend, not by the backend.
- The `can_execute` schedule check uses wall-clock time in the contract (see
  `contracts/genlayer/smart_transfer.py`); a block-timestamp source would be
  more deterministic.
- ENS resolution uses a public resolver and may fail without internet.

## License

Educational purposes only. See the GenLayer docs for details.
