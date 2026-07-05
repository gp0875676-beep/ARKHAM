# db/migrations.py — idempotent schema bootstrap.
"""Runs on boot to create tables if missing."""
from db.connection import db
from utils.logger import get_logger

log = get_logger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    tx_hash TEXT PRIMARY KEY,
    chain TEXT NOT NULL,
    wallet TEXT NOT NULL,
    from_address TEXT NOT NULL,
    to_address TEXT NOT NULL,
    token_symbol TEXT,
    amount_human NUMERIC,
    usd_value NUMERIC,
    direction TEXT,
    timestamp BIGINT
);
CREATE INDEX IF NOT EXISTS idx_transactions_wallet ON transactions(wallet);
CREATE INDEX IF NOT EXISTS idx_transactions_from ON transactions(from_address);
CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp);

CREATE TABLE IF NOT EXISTS clusters (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cluster_members (
    cluster_id INT REFERENCES clusters(id) ON DELETE CASCADE,
    chain TEXT NOT NULL,
    wallet TEXT NOT NULL,
    PRIMARY KEY (cluster_id, chain, wallet)
);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    tx_hash TEXT NOT NULL,
    chain TEXT NOT NULL,
    wallet TEXT NOT NULL,
    token_symbol TEXT,
    amount_human NUMERIC,
    usd_value NUMERIC,
    score INT,
    explanation TEXT,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at);

-- Phase 7: Module 1 (Dynamic Watchlist)
CREATE TABLE IF NOT EXISTS watchlist (
    chain TEXT NOT NULL,
    wallet TEXT NOT NULL,
    label TEXT,
    added_by BIGINT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (chain, wallet)
);

-- Phase 7: Module 3 (Alert Replay / Outcomes)
-- We store token_address and direction on alerts so outcomes can be evaluated.
-- ALTER TABLE ADD COLUMN IF NOT EXISTS so existing deployments upgrade in place.
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS token_address TEXT;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS direction TEXT;
CREATE TABLE IF NOT EXISTS alert_outcomes (
    alert_id INT PRIMARY KEY REFERENCES alerts(id) ON DELETE CASCADE,
    price_at_alert NUMERIC,
    price_at_1h NUMERIC,
    price_at_24h NUMERIC,
    evaluated_1h BOOLEAN DEFAULT FALSE,
    evaluated_24h BOOLEAN DEFAULT FALSE,
    evaluated_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_outcomes_1h ON alert_outcomes(evaluated_1h);
CREATE INDEX IF NOT EXISTS idx_outcomes_24h ON alert_outcomes(evaluated_24h);
"""


async def ensure_schema() -> None:
    if not db.pool:
        return
    await db.execute(SCHEMA_SQL)
    log.info("DB schema verified (watchlist + alert_outcomes tables ensured).")
