# ARC REACTOR — Whale Intelligence & On-Chain Analytics Bot

Autonomous multi-chain whale wallet tracker with exchange-flow detection,
wallet clustering, significance scoring, Telegram alerting, RPC failover,
alert replay/calibration, and behavioral wallet profiling.

## Status
All 6 build phases + Phase 7 (Real Intelligence Upgrades) complete and
verified (43/43 files: syntax-checked and real-import-checked):
- Phase 0: Project skeleton, config, DB, deploy setup
- Phase 1: Single-chain (Ethereum) wallet tracker + Telegram alerts
- Phase 2: Exchange inflow/outflow detection
- Phase 3: Wallet clustering (shared funder + direct-transfer heuristics)
- Phase 4: Significance scoring with plain-English explanations
- Phase 5: Multi-chain (Ethereum, BSC, Polygon, Arbitrum)
- Phase 6: Read-only FastAPI dashboard
- Phase 7, Module 1: Dynamic (DB-backed) watchlist — `/addwhale`, `/removewhale`, `/listwhales`
- Phase 7, Module 2: Multi-provider failover — Explorer API falls back to direct JSON-RPC for `get_latest_block()`
- Phase 7, Module 3: Lightweight alert replay/backtest — `alert_outcomes` table, `/replay <days>`
- Phase 7, Module 4: Confidence calibration v1 — historical hit-rate shown alongside live scores (n>=30)
- Phase 7, Module 5: Wallet profile enrichment — `/profile <chain> <wallet>`

## Setup
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your values
python main.py
```

## Deploy
See `render.yaml`. Deploy as a Render Web Service (dashboard + scanner run
together in `main.py`'s lifespan). Postgres URL is injected by Render.

## Telegram commands
- `/start`, `/status` — basic bot info
- `/addwhale <chain> <address> <label>`, `/removewhale <chain> <address>`, `/listwhales [chain]` — admin-only (`TELEGRAM_ADMIN_IDS`)
- `/replay <days>` — admin-only; hit-rate report broken down by score bucket
- `/profile <chain> <wallet>` — behavioral stats from stored transaction history

## Known limitations (see AUDIT_NOTES.md)
- `fetch_recent_txs()` still relies solely on the Explorer API for historical
  transfers by address — standard JSON-RPC cannot list those without
  scanning every block. On Explorer failure it logs a "blind spot" warning
  and returns what it has rather than fabricating data. RPC failover fully
  covers `get_latest_block()`, so the scanner cursor never stalls.
- Calibration notes only appear once a score bucket has >=30 matured
  (`evaluated_24h=TRUE`) alerts; by design, to avoid fabricating a
  percentage from insufficient data.
