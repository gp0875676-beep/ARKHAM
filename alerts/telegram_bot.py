# alerts/telegram_bot.py — python-telegram-bot polling bot.
"""Telegram bot wrapper. Polling mode (not webhook) for free-tier hosting.
Supports /start, /status, /addwhale, /removewhale, /listwhales, /replay, /profile."""
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from utils.logger import get_logger
from config import get_settings
from utils.markdown import truncate, escape_markdown
from db.models import WatchlistRepo, AlertOutcomeRepo
from tracking.wallet_profile import WalletProfileBuilder

log = get_logger(__name__)


class TelegramBot:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.app = Application.builder().token(self.settings.telegram_bot_token).build()
        self.chat_id = self.settings.telegram_chat_id
        self.watchlist_repo = WatchlistRepo()
        self.outcome_repo = AlertOutcomeRepo()
        self.profile_builder = WalletProfileBuilder()

        # Register Handlers
        self.app.add_handler(CommandHandler("start", self._start))
        self.app.add_handler(CommandHandler("status", self._status))
        self.app.add_handler(CommandHandler("addwhale", self._add_whale))
        self.app.add_handler(CommandHandler("removewhale", self._remove_whale))
        self.app.add_handler(CommandHandler("listwhales", self._list_whales))
        self.app.add_handler(CommandHandler("replay", self._replay))
        self.app.add_handler(CommandHandler("profile", self._profile))

    def _is_admin(self, user_id: int) -> bool:
        if not self.settings.admin_ids:
            return False
        return user_id in self.settings.admin_ids

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("ARC Reactor bot online. Tracking whales.")

    async def _status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Scanner is running.")

    async def _add_whale(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        if not self._is_admin(user_id):
            await update.message.reply_text("❌ Unauthorized. You do not have permission to manage the watchlist.")
            return

        if len(context.args) < 2:
            await update.message.reply_text("Usage: `/addwhale <chain> <address> <label>`", parse_mode="Markdown")
            return

        chain = context.args[0].lower()
        address = context.args[1].lower()
        label = " ".join(context.args[2:]) if len(context.args) > 2 else "Manual Add"

        try:
            await self.watchlist_repo.add(chain, address, label, user_id)
            await update.message.reply_text(f"✅ Added `{address}` to {chain} watchlist.", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error adding whale: {e}")

    async def _remove_whale(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        if not self._is_admin(user_id):
            await update.message.reply_text("❌ Unauthorized. You do not have permission to manage the watchlist.")
            return

        if len(context.args) < 2:
            await update.message.reply_text("Usage: `/removewhale <chain> <address>`", parse_mode="Markdown")
            return

        chain = context.args[0].lower()
        address = context.args[1].lower()

        try:
            await self.watchlist_repo.remove(chain, address)
            await update.message.reply_text(f"🗑️ Removed `{address}` from {chain} watchlist.", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error removing whale: {e}")

    async def _list_whales(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        if not self._is_admin(user_id):
            await update.message.reply_text("❌ Unauthorized.")
            return

        chain = context.args[0].lower() if context.args else None
        try:
            wallets = await self.watchlist_repo.list_active(chain)
            if not wallets:
                await update.message.reply_text("No active wallets found in DB watchlist.")
                return

            msg = "*Active DB Watchlist*\n"
            for w in wallets:
                msg += f"- `{w['chain']}` | `{w['wallet']}` | {escape_markdown(w['label'])}\n"

            await update.message.reply_text(truncate(msg), parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error listing whales: {e}")

    async def _replay(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Phase 7, Module 3: reports whether past alerts actually predicted
        the price move, broken down by score bucket. Only evaluates alerts
        the system already fired for real — not a strategy backtest."""
        user_id = update.effective_user.id
        if not self._is_admin(user_id):
            await update.message.reply_text("❌ Unauthorized.")
            return

        days = 7
        if context.args:
            try:
                days = int(context.args[0])
            except ValueError:
                await update.message.reply_text("Usage: `/replay <days>`", parse_mode="Markdown")
                return

        try:
            stats = await self.outcome_repo.get_replay_stats(days)
            if not stats:
                await update.message.reply_text(
                    f"No completed 24h alerts in the last {days} day(s) yet. "
                    "Outcomes need at least 24 hours to mature."
                )
                return

            buckets = {
                "0-50": {"total": 0, "hits": 0},
                "50-80": {"total": 0, "hits": 0},
                "80-100": {"total": 0, "hits": 0},
            }
            for s in stats:
                score = s["score"] or 0
                direction = s["direction"]
                p_start = float(s["price_at_alert"])
                p_end = float(s["price_at_24h"])
                if p_start <= 0:
                    continue

                b_key = "0-50"
                if score >= 80:
                    b_key = "80-100"
                elif score >= 50:
                    b_key = "50-80"
                buckets[b_key]["total"] += 1

                pct_change = ((p_end - p_start) / p_start) * 100
                if direction == "in" and pct_change > 5:
                    buckets[b_key]["hits"] += 1
                elif direction == "out" and pct_change < -5:
                    buckets[b_key]["hits"] += 1

            msg = f"📊 *Alert Replay Report (Last {days} Days)*\n"
            msg += "Evaluated alerts where price moved >5% in implied direction within 24h.\n\n"
            for b, d in buckets.items():
                if d["total"] > 0:
                    hit_rate = (d["hits"] / d["total"]) * 100
                    msg += f"Score `{b}`: {hit_rate:.1f}% hit rate ({d['hits']}/{d['total']} alerts)\n"
                else:
                    msg += f"Score `{b}`: No data\n"

            await update.message.reply_text(truncate(msg), parse_mode="Markdown")
        except Exception as e:
            log.error("Replay command failed: {}", e)
            await update.message.reply_text(f"❌ Error generating replay report: {e}")

    async def _profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Phase 7, Module 5: behavioral wallet profile built from stored
        transaction history — first seen, avg size, rotation, exchange
        interactions, and estimated holding time."""
        if len(context.args) < 2:
            await update.message.reply_text("Usage: `/profile <chain> <wallet>`", parse_mode="Markdown")
            return

        chain = context.args[0].lower()
        address = context.args[1].lower()
        try:
            profile = await self.profile_builder.build_profile(chain, address)
            if not profile:
                await update.message.reply_text(f"No transaction history found for `{address}` on {chain}.", parse_mode="Markdown")
                return

            first_seen_str = "N/A"
            if profile.first_seen:
                first_seen_str = datetime.fromtimestamp(profile.first_seen, tz=timezone.utc).strftime("%Y-%m-%d")
            hold_str = f"{profile.holding_duration_estimate_hrs} hrs" if profile.holding_duration_estimate_hrs is not None else "N/A"

            msg = (
                f"👤 *Wallet Profile*\n"
                f"Chain: `{escape_markdown(chain)}`\n"
                f"Wallet: `{escape_markdown(profile.wallet)}`\n\n"
                f"*Behavioral Stats (from stored DB history):*\n"
                f"First Seen: {first_seen_str}\n"
                f"Total Tracked Txs: {profile.tx_count}\n"
                f"Avg Tx Size (USD): ${profile.avg_tx_size_usd:,.2f}\n"
                f"Rotation Freq: {profile.rotation_frequency_per_week} txs/week\n"
                f"Exchange Interactions: {profile.exchange_interaction_count}\n"
                f"Avg Holding Time: {hold_str}\n"
            )
            await update.message.reply_text(truncate(msg), parse_mode="Markdown")
        except Exception as e:
            log.error("Profile command failed: {}", e)
            await update.message.reply_text(f"❌ Error generating profile: {e}")

    async def start(self) -> None:
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        log.info("Telegram bot started polling")

    async def stop(self) -> None:
        if self.app.updater:
            await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()

    async def send_alert(self, text: str) -> None:
        safe_text = truncate(text)
        try:
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text=safe_text,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            log.error("Failed to send TG alert: {} | Msg: {}", e, safe_text)
