# ARC REACTOR — Extraction & Audit Notes

## Phases 0-6 (initial audit)
All 46 files extracted, syntax + real-import verified. Fixed: broken
indentation in `chains/base.py` and `utils/markdown.py`; dead stubs in
`providers/rpc.py` and `clustering/storage.py` implemented for real;
silent no-op in `tracking/whale_list.py.add()` replaced with an honest
`NotImplementedError`; stray leftover comment removed from
`clustering/detector.py`.

## Phase 7, Module 1 — Dynamic Watchlist
Your second HTML export truncated two long code blocks (`db/models.py`
and `alerts/telegram_bot.py`) mid-file — almost certainly the chat UI's
code editor virtualizing long blocks during the page save, not GLM
actually giving fragments. You pasted the real, complete versions
directly, which resolved it.

Applied and verified:
- `db/models.py`: added `WalletRepo`, `WatchlistRepo` (kept existing
  `TransactionRepo`, `AlertRepo`, `ClusterRepo`)
- `alerts/telegram_bot.py`: added `/addwhale`, `/removewhale`,
  `/listwhales`, all gated behind `TELEGRAM_ADMIN_IDS`
- `config.py`: added `telegram_admin_ids` field + `admin_ids` property
- `db/migrations.py`: added `watchlist` table
- `tracking/whale_list.py`: now async, merges env list + DB watchlist
- `tracking/scanner.py`, `clustering/detector.py`: updated to `await`
  the now-async `WhaleList` calls
- `.env.example`: added `TELEGRAM_ADMIN_IDS`

**Verification run after integration:**
- 41/41 Python files: 0 syntax errors
- 41/41 modules: 0 real import errors (with actual dependencies installed)
- 0 leftover STUB/TODO markers
- Admin-gating confirmed wired in all 3 new Telegram commands

## Still open (tracked, not yet built)
- `providers/rpc.py` (multi-provider failover) exists but is not yet
  called from `chains/ethereum.py` — see Phase 7, Module 2.
- Modules 2-5 of Phase 7 (failover, replay/backtest, calibration,
  wallet profile) not yet built.

## Phase 7, Modules 2-5 — Real Intelligence Upgrades (final integration)
Sourced from the full GLM build transcript, including its own follow-up
correction. GLM's Module 5 response flagged mid-message that `build_profile()`
referenced a `TransactionRepo.get_wallet_raw_history()` method it had not
yet defined, and supplied that method as a same-turn correction. That
correction is applied here as `TransactionRepo.get_wallet_raw_history()` in
`db/models.py` — it's the only DB query that returns from/to addresses
alongside direction/timestamp, which `WalletProfileBuilder` needs to count
exchange interactions and pair up FIFO holding-duration inflows/outflows.

Applied and verified:
- `providers/rpc.py`: rewritten as a rate-limited, retrying JSON-RPC client
  (`RpcClient.call/get_block_number/get_transaction_receipt`)
- `chains/ethereum.py` (`EvmAdapter`): `get_latest_block()` tries the
  Explorer API first, falls back to `RpcClient.get_block_number()` on
  failure, returns 0 only if both fail. `fetch_recent_txs()` logs a
  "blind spot" warning on Explorer failure rather than fabricating a
  fallback via RPC (standard JSON-RPC cannot list historical transfers
  by address). Same pattern applied to `chains/bsc.py`, `polygon.py`,
  `arbitrum.py`; `chains/registry.py` now injects an `RpcClient` per chain.
- `db/migrations.py`: added `alert_outcomes` table + `ALTER TABLE alerts
  ADD COLUMN IF NOT EXISTS token_address, direction`
- `db/models.py`: `AlertRepo.insert()` now stores `token_address`/`direction`
  and returns the new row's id (`RETURNING id`); added `AlertOutcomeRepo`
  (`create_outcome`, `get_alerts_needing_1h/24h`, `update_price_1h/24h`,
  `get_replay_stats`); added `TransactionRepo.get_profile_stats()`,
  `get_30d_tx_count()`, `get_wallet_history()`, and the
  `get_wallet_raw_history()` correction described above
- `alerts/manager.py`: computes price-per-token at alert time and calls
  `AlertOutcomeRepo.create_outcome()` after a successful `AlertRepo.insert()`
- `tracking/scanner.py`: runs `_evaluate_outcomes()` every 10 scan cycles to
  fill in `price_at_1h`/`price_at_24h` for maturing alerts — no new
  scheduler/process, per the Phase 7 "no new infra" constraint
- `alerts/telegram_bot.py`: added `/replay <days>` (admin-only hit-rate
  report by score bucket) and `/profile <chain> <wallet>` (behavioral stats)
- `scoring/calibration.py` (new): `CalibrationEngine.get_report()` computes
  real hit-rate per score bucket from `alert_outcomes`, 1-hour cache,
  refuses to make a claim below 30 matured samples in a bucket
- `scoring/engine.py`: `Score` gained a `calibration_note` field; `score()`
  now looks up the current bucket's hit-rate and attaches it when
  `n>=30`. Also fixed a pre-existing bug where `score()` referenced
  `event.wallet` (not a field on `TxEvent`) — replaced with the same
  `context["wallet"]` / from-or-to-address fallback used elsewhere in the
  codebase
- `alerts/templates.py` / `alerts/formatter.py`: score line now renders
  `{calibration_note}` inline, e.g. "Score: 82/100 (historically right 68%
  of the time, n=45)"
- `tracking/wallet_profile.py` (new): `WalletProfileBuilder.build_profile()`
  computes `first_seen`, `avg_tx_size_usd`, `rotation_frequency_per_week`,
  `exchange_interaction_count`, and a FIFO-matched
  `holding_duration_estimate_hrs`, using only data already in Postgres

**Verification run after integration:**
- 43/43 Python files: 0 syntax errors (`py_compile`)
- 43/43 modules: 0 real import errors (with actual dependencies installed
  from `requirements.txt`)
- 0 leftover STUB/TODO/NotImplementedError markers outside the intentional
  abstract methods in `chains/base.py`
- Admin-gating confirmed wired on `/addwhale`, `/removewhale`, `/listwhales`,
  `/replay`
- No new hosting services, databases, or env vars beyond what
  `.env.example` already declared (`ETH_RPC_URL` etc. and
  `TELEGRAM_ADMIN_IDS` were already present)

## Tip for future exports
When copying GLM's output, prefer each code block's own "Copy" button
over saving the whole page as HTML — long blocks can get truncated in
a page save if the code editor virtualizes scrolled-off lines.
