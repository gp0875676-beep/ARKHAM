# db/models.py — thin data access objects (no ORM, just typed queries).
"""DAOs for wallets, transactions, alerts, clusters."""
from db.connection import db


class WalletRepo:
    async def get_tracked(self, chain: str) -> list[str]:
        from tracking.whale_list import WhaleList
        return await WhaleList().get_wallets_for_chain(chain)


class WatchlistRepo:
    async def add(self, chain: str, wallet: str, label: str, added_by: int) -> None:
        await db.execute(
            """
            INSERT INTO watchlist (chain, wallet, label, added_by, active)
            VALUES ($1, $2, $3, $4, TRUE)
            ON CONFLICT (chain, wallet) DO UPDATE SET active = TRUE, label = $3, added_by = $4
            """,
            chain, wallet, label, added_by
        )

    async def remove(self, chain: str, wallet: str) -> None:
        await db.execute(
            "UPDATE watchlist SET active = FALSE WHERE chain = $1 AND wallet = $2",
            chain, wallet
        )

    async def list_active(self, chain: str = None) -> list[dict]:
        if chain:
            rows = await db.fetch("SELECT chain, wallet, label FROM watchlist WHERE chain = $1 AND active = TRUE", chain)
        else:
            rows = await db.fetch("SELECT chain, wallet, label FROM watchlist WHERE active = TRUE")
        return [dict(r) for r in rows]

    async def is_tracked(self, chain: str, wallet: str) -> bool:
        row = await db.fetchrow(
            "SELECT 1 FROM watchlist WHERE chain = $1 AND wallet = $2 AND active = TRUE",
            chain, wallet
        )
        return row is not None


class TransactionRepo:
    async def seen(self, tx_hash: str) -> bool:
        row = await db.fetchrow("SELECT 1 FROM transactions WHERE tx_hash = $1", tx_hash)
        return row is not None

    async def insert(self, event) -> None:
        wallet = event.from_address if event.direction == "out" else event.to_address
        await db.execute(
            """
            INSERT INTO transactions (tx_hash, chain, wallet, from_address, to_address, token_symbol, amount_human, usd_value, direction, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (tx_hash) DO NOTHING
            """,
            event.tx_hash, event.chain, wallet, event.from_address, event.to_address,
            event.token_symbol, event.amount_human, event.usd_value, event.direction, event.timestamp
        )

    async def get_wallets_funded_by(self, chain: str, funder_addr: str) -> list:
        rows = await db.fetch(
            """
            SELECT DISTINCT wallet FROM transactions 
            WHERE chain = $1 AND from_address = $2 AND direction = 'in'
            """,
            chain, funder_addr
        )
        return [r['wallet'] for r in rows]

    async def get_wallet_tx_count(self, chain: str, wallet: str) -> int:
        row = await db.fetchrow(
            "SELECT COUNT(*) as count FROM transactions WHERE chain = $1 AND wallet = $2",
            chain, wallet
        )
        return row['count'] if row else 0

    async def get_profile_stats(self, chain: str, wallet: str) -> dict | None:
        """Basic aggregate stats for wallet profile enrichment (Phase 7, Module 5)."""
        row = await db.fetchrow(
            """
            SELECT MIN(timestamp) as first_seen, COUNT(*) as tx_count, AVG(usd_value) as avg_usd
            FROM transactions
            WHERE chain = $1 AND wallet = $2
            """,
            chain, wallet
        )
        return dict(row) if row else None

    async def get_30d_tx_count(self, chain: str, wallet: str) -> int:
        """Tx count in the trailing 30 days, used for rotation frequency."""
        row = await db.fetchrow(
            """
            SELECT COUNT(*) as count FROM transactions
            WHERE chain = $1 AND wallet = $2
            AND timestamp >= EXTRACT(EPOCH FROM NOW() - INTERVAL '30 days')
            """,
            chain, wallet
        )
        return row['count'] if row else 0

    async def get_wallet_history(self, chain: str, wallet: str) -> list[dict]:
        """Chronological direction/token/timestamp history (no addresses)."""
        rows = await db.fetch(
            """
            SELECT direction, token_symbol, timestamp
            FROM transactions
            WHERE chain = $1 AND wallet = $2
            ORDER BY timestamp ASC
            """,
            chain, wallet
        )
        return [dict(r) for r in rows]

    async def get_wallet_raw_history(self, chain: str, wallet: str) -> list[dict]:
        """Fetches chronological txs with from/to addresses for profile enrichment.
        (Phase 7, Module 5 correction: needed by WalletProfileBuilder to count
        exchange interactions and match FIFO holding-duration pairs, which the
        address-less get_wallet_history() query above cannot support.)"""
        rows = await db.fetch(
            """
            SELECT direction, token_symbol, timestamp, from_address, to_address
            FROM transactions
            WHERE chain = $1 AND wallet = $2
            ORDER BY timestamp ASC
            """,
            chain, wallet
        )
        return [dict(r) for r in rows]


class AlertRepo:
    async def insert(self, event, score, message) -> int | None:
        wallet = event.from_address if event.direction == "out" else event.to_address
        row = await db.fetchrow(
            """
            INSERT INTO alerts (tx_hash, chain, wallet, token_address, token_symbol, amount_human, usd_value, direction, score, explanation, message)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id
            """,
            event.tx_hash, event.chain, wallet, event.token_address, event.token_symbol,
            event.amount_human, event.usd_value, event.direction,
            score.value if score else 0,
            score.explanation if score else "",
            message
        )
        return row['id'] if row else None

    async def recent(self, limit: int = 50) -> list:
        rows = await db.fetch(
            """
            SELECT tx_hash, chain, wallet, token_symbol, amount_human, usd_value, score, explanation, message, created_at
            FROM alerts ORDER BY created_at DESC LIMIT $1
            """,
            limit
        )
        return rows


class AlertOutcomeRepo:
    """Phase 7, Module 3: tracks whether an alert's implied price direction
    actually played out at 1h / 24h after it fired. Only evaluates alerts the
    system already sent for real — this is NOT a historical strategy backtest."""

    async def create_outcome(self, alert_id: int, price_at_alert: float | None) -> None:
        if price_at_alert is None:
            # Cannot track an outcome if we never knew the price at alert time.
            return
        await db.execute(
            """
            INSERT INTO alert_outcomes (alert_id, price_at_alert, evaluated_1h, evaluated_24h)
            VALUES ($1, $2, FALSE, FALSE)
            ON CONFLICT (alert_id) DO NOTHING
            """,
            alert_id, price_at_alert
        )

    async def get_alerts_needing_1h(self) -> list[dict]:
        rows = await db.fetch(
            """
            SELECT a.id, a.chain, a.token_address, o.price_at_alert
            FROM alerts a
            JOIN alert_outcomes o ON a.id = o.alert_id
            WHERE a.created_at <= NOW() - INTERVAL '1 hour'
            AND o.evaluated_1h = FALSE
            LIMIT 50
            """
        )
        return [dict(r) for r in rows]

    async def get_alerts_needing_24h(self) -> list[dict]:
        rows = await db.fetch(
            """
            SELECT a.id, a.chain, a.token_address, o.price_at_alert
            FROM alerts a
            JOIN alert_outcomes o ON a.id = o.alert_id
            WHERE a.created_at <= NOW() - INTERVAL '24 hours'
            AND o.evaluated_24h = FALSE
            LIMIT 50
            """
        )
        return [dict(r) for r in rows]

    async def update_price_1h(self, alert_id: int, price: float) -> None:
        await db.execute(
            "UPDATE alert_outcomes SET price_at_1h = $2, evaluated_1h = TRUE WHERE alert_id = $1",
            alert_id, price
        )

    async def update_price_24h(self, alert_id: int, price: float) -> None:
        await db.execute(
            "UPDATE alert_outcomes SET price_at_24h = $2, evaluated_24h = TRUE, evaluated_at = NOW() WHERE alert_id = $1",
            alert_id, price
        )

    async def get_replay_stats(self, days: int = 7) -> list[dict]:
        """Matured (evaluated_24h=TRUE) alerts within the lookback window, for
        both the /replay command and the CalibrationEngine."""
        rows = await db.fetch(
            """
            SELECT a.score, a.direction, o.price_at_alert, o.price_at_24h
            FROM alerts a
            JOIN alert_outcomes o ON a.id = o.alert_id
            WHERE a.created_at >= NOW() - ($1 || ' days')::INTERVAL
            AND o.evaluated_24h = TRUE
            AND o.price_at_alert > 0
            """,
            str(days)
        )
        return [dict(r) for r in rows]


class ClusterRepo:
    async def get_cluster_by_wallet(self, chain: str, wallet: str) -> int | None:
        row = await db.fetchrow(
            "SELECT cluster_id FROM cluster_members WHERE chain = $1 AND wallet = $2",
            chain, wallet
        )
        return row['cluster_id'] if row else None

    async def get_members(self, cluster_id: int) -> list[str]:
        rows = await db.fetch(
            "SELECT wallet FROM cluster_members WHERE cluster_id = $1",
            cluster_id
        )
        return [r['wallet'] for r in rows]

    async def assign_to_cluster(self, chain: str, wallets: list[str]) -> int:
        if not wallets: return 0
        existing_cluster_id = None
        for w in wallets:
            cid = await self.get_cluster_by_wallet(chain, w)
            if cid:
                existing_cluster_id = cid
                break
        
        if not existing_cluster_id:
            row = await db.fetchrow("INSERT INTO clusters DEFAULT VALUES RETURNING id")
            existing_cluster_id = row['id']
            
        for w in wallets:
            await db.execute(
                """
                INSERT INTO cluster_members (cluster_id, chain, wallet)
                VALUES ($1, $2, $3)
                ON CONFLICT (cluster_id, chain, wallet) DO NOTHING
                """,
                existing_cluster_id, chain, w
            )
        return existing_cluster_id

    async def get_all_clusters(self) -> list:
        rows = await db.fetch(
            """
            SELECT c.id, COUNT(cm.wallet) as member_count, array_agg(cm.wallet) as wallets
            FROM clusters c
            JOIN cluster_members cm ON c.id = cm.cluster_id
            GROUP BY c.id
            ORDER BY c.id DESC
            LIMIT 50
            """
        )
        return rows
