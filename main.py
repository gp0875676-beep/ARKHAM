# main.py — ARC REACTOR entry point. Boots FastAPI dashboard + Scanner loop + Telegram bot.
"""ARC REACTOR — main entry point.

Combines the FastAPI dashboard web server and the background scanner task 
into a single process, optimized for Render's free tier Web Service.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from utils.logger import get_logger
from config import get_settings
from db.connection import db
from db.migrations import ensure_schema
from chains.registry import build_adapters
from alerts.telegram_bot import TelegramBot
from alerts.manager import AlertManager
from tracking.scanner import Scanner
from dashboard.app import create_app

log = get_logger(__name__)
settings = get_settings()

# Globals for background tasks
scanner_task = None
scanner_instance = None
bot_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    global scanner_task, scanner_instance, bot_instance
 
    log.info("ARC REACTOR booting | env={} log={}", settings.env, settings.log_level)
 
    # Check required vars
    settings.require("telegram_bot_token", "telegram_chat_id")
    if settings.eth_enabled:
        settings.require("eth_etherscan_api_key")
 
    # DB Initialization
    await db.connect()
    await ensure_schema()
 
    # Providers & Adapters
    adapters = await build_adapters()
 
    # Alerts & Bot
    bot_instance = TelegramBot()
    await bot_instance.start()
 
    from db.models import TransactionRepo
    tx_repo = TransactionRepo()
    alert_manager = AlertManager(bot_instance, tx_repo)
 
    # Scanner
    scanner_instance = Scanner(adapters, alert_manager)
    scanner_task = asyncio.create_task(scanner_instance.start())
    log.info("ARC REACTOR background scanner started successfully.")
 
    try:
        yield
    finally:
        # Shutdown sequence
        log.info("Shutting down ARC REACTOR...")
        if scanner_instance:
            await scanner_instance.stop()
        if scanner_task:
            scanner_task.cancel()
            try:
                await scanner_task
            except asyncio.CancelledError:
                pass
        if bot_instance:
            await bot_instance.stop()
        await db.close()
        log.info("Shutdown complete.")

# Create FastAPI app using the lifespan context
app = create_app(lifespan=lifespan)

# Fallback root route if dashboard isn't mounted for some reason
@app.get("/ping")
async def ping():
    return JSONResponse({"status": "alive"})
