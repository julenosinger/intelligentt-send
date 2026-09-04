# Intelligent Send · Cloudflare Pages Deployment Guide

## Overview
Deploy the static HTML frontend to Cloudflare Pages. The FastAPI backend runs separately (on Render, Fly.io, Railway, or your own VPS).

## Configuration

The HTML uses `window.API_BASE` set via:
1. URL query param: `?api=https://your-backend.com`
2. `localStorage.getItem('API_BASE')`
3. Default: `http://127.0.0.1:8000`

**No Vite, no import.meta.env, no build step.**

## Step 1: Prepare the Frontend

The `index.html` is a static file:
- No framework required
- No build step
- Calls `${API_BASE}/v1/*` endpoints

## Step 2: Deploy to Cloudflare Pages

### Via Dashboard
1. Go to Cloudflare Pages > Your Project > Settings > Variables
2. Add variable: `API_BASE` = `https://your-backend-url.com`
3. Framework preset: **None**
4. Build command: **empty**
5. Output directory: **/** (root)
6. Upload `index.html`

### Via Wrangler CLI
```bash
wrangler pages deploy --project-name intelligent-send
```

## Step 3: Backend
Your FastAPI backend must be accessible and support CORS from your Cloudflare Pages URL.

Update `ALLOWED_ORIGINS` in `apps/api/main.py` to include your Pages URL.

## Step 4: Verify
- Page loads correctly
- Connect Wallet fetches balances from backend
- AI Analysis calls `/v1/ai/analyze`
- Transaction prepare calls `/v1/tx/prepare`

## Important Notes
- The HTML does NOT use `import.meta.env` or Vite
- No `package.json` needed for hosting
- Static file served directly by Cloudflare Pages

## Directory Structure
```
/ (root)
  index.html               ← frontend (deployed to Cloudflare Pages)
  apps/api/main.py         ← FastAPI backend (external)
  contracts/genlayer/      ← GenLayer Intelligent Contracts
  packages/chains/         ← Chain adapters
  packages/db/             ← Database models
  tests/                   ← pytest tests
  scripts/                 ← Utility scripts
  .gitignore
  .env.example
  requirements.txt
```