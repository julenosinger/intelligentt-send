# Intelligent Send · Cloudflare Pages Deployment Guide

## Overview
Deploy the frontend to Cloudflare Pages while keeping the FastAPI backend external. The frontend will call your existing backend API.

## Prerequisites
- Cloudflare account
- Git repository (already at https://github.com/julenosinger/intelligentt-send)
- Backend FastAPI running (on Render, Fly.io, Railway, or VPS)

## Step 1: Configure API URL

The HTML frontend is configured to use an environment variable for the API base URL.

### Option A: Set via Cloudflare Pages Dashboard
1. Go to Cloudflare Pages > Your Project > Settings > Variables
2. Add variable:
   - **Name**: `VITE_API_BASE_URL`
   - **Value**: `https://your-backend-url.com` (e.g., `https://intelligent-send-backend.onrender.com`)
3. Save and trigger a new deploy

### Option B: Set via Wrangler (CLI)
```bash
npx pages wrangler secret set VITE_API_BASE_URL
# Then set value: https://your-backend-url.com
```

### Default (local development)
If no env var is set, the fallback is `http://127.0.0.1:8000` (for local testing).

## Step 2: Prepare the Frontend

The HTML file `intelligent-send (1).html` is already configured:

- **API_BASE_URL**: Read from `import.meta.env.VITE_API_BASE_URL` or falls back to `http://127.0.0.1:8000`
- **fetch() calls**: All API calls use `${window.API_BASE_URL}/v1/*`
- **Fallback to mock data**: If the API request fails, the app uses local mock data

### Files modified for Cloudflare Pages:
1. `<script>` block added at top of `<body>` to configure `API_BASE_URL`
2. `connectWallet()` now fetches real balances from API
3. `setMax()` now fetches balance from API
4. `runAnalysis()` now fetches risk analysis from API with mock fallback
5. `setMax()` updated to use API instead of hardcoded BALANCES

## Step 3: Deploy to Cloudflare Pages

### Option 1: Via GitHub Integration
1. Go to [Cloudflare Pages](https://dash.cloudflare.com/pages)
2. Click "Import Project" > "GitHub"
3. Select repository: `julenosinger/intelligentt-send`
4. Framework preset: **Vite** (or "Other" if not detected)
5. Build command: `echo "skip"` (we'll use a different approach)
6. Root directory: `/` (root of repo)
7. Add the `VITE_API_BASE_URL` variable in Settings > Variables
8. Click "Deploy"

### Option 2: Via Wrangler CLI
```bash
# Install Cloudflare CLI
npm install -g wrangler

# Login
wrangler login

# Create a new Pages project
wrangler pages project create intelligent-send

# Deploy from dist (we'll use a minimal config)
# The HTML file is at the root, so it will be served directly

# Or deploy via git
echo "VITE_API_BASE_URL=https://your-backend-url.com" > user-variables.txt
wrangler pages deploy --project-name intelligent-send
```

### Build Configuration
Since this is a static HTML file (not a Vite/React app), we need to configure Pages to serve it correctly.

**cloudflare-pages.json** (create this file in repo root):
```json
{
  "automatic_builds": true,
  "base_url": "/",
  "framework": "static"
}
```

Or alternatively, add to `package.json`:
```json
{
  "scripts": {
    "deploy": "wrangler pages deploy"
  }
}
```

## Step 4: Verify Deployment

After deploy, visit your Cloudflare Pages URL (e.g., `intelligent-send.xyz.pages.dev`):

### Test Points:
1. **Page loads** - UI appears correctly
2. **Wallet Connect** - Fetches balances from your backend API
3. **Gas Estimate** - Calls `GET /v1/gas/estimate`
4. **AI Analysis** - Calls `POST /v1/ai/analyze` shows risk score with CSS classes (.ai-msg.ok/.warn/.err)
5. **Address Validation** - `POST /v1/address/validate` resolves ENS
6. **History** - `GET /v1/history` shows transactions

### Troubleshooting:
- **API returns 404/500**: Check that `VITE_API_BASE_URL` is set correctly and your backend is running
- **CORS errors**: Your backend should have `Access-Control-Allow-Origin: *` or the specific origin
- **Fallback to mock data**: If API is down, the app shows local mock data (this is expected behavior)
- **Console errors**: Check Cloudflare Pages > Logs for details

## Step 5: Backend Considerations

Your FastAPI backend should remain accessible from the internet. Recommended options:

### Render.com (Free tier)
- `https://intelligent-send-backend.onrender.com`
- Auto-sleeps after inactivity (wake up with a ping)

### Fly.io
- `https://intelligent-send-fly.app`
- Always-on option available

### Railway
- `https://intelligent-send.up.railway.app`

### Your own VPS
- Any public IP with the FastAPI running

### Health Check (optional but recommended)
Add a cron job or UptimeRobot to ping your backend every few minutes to prevent auto-sleep:

```
https://your-backend-url.com/health (you can add a simple /health endpoint)
```

Or use a free service like UptimeRobot (free tier monitors every 5 minutes).

## Rollback
If something goes wrong:
1. Go to Cloudflare Pages > Deployments
2. Click "Rollback" to previous deployment
3. Or change `VITE_API_BASE_URL` variable to point to the previous backend URL

## Directory Structure (relevant files)
```
/ (root)
  intelligent-send (1).html   ← frontend (deployed to Cloudflare Pages)
  apps/api/main.py            ← FastAPI backend (external)
  contracts/genlayer/         ← GenLayer Intelligent Contracts (Python)
  packages/chains/            ← Chain adapters
  packages/db/                ← Database models
  .gitignore
  README.md
  package.json                ← optional, for wrangler
```

## License
This project is for educational and trading purposes. 
See the [GenLayer documentation](https://docs.genlayer.com/) for more information.