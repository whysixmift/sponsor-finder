import sys
import os
import asyncio
import threading
from telegram.ext import ApplicationBuilder
from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from app.config.settings import settings
from app.database.db import init_db
from app.bot.handlers import setup_bot
from app.bot.server import run_bot_http_server
from app.web.server import run_web_server
from app.agents.scheduler_agent import scheduler_agent
from app.ai.evaluator import evaluator
from app.utils.logger import logger

async def run_startup_diagnostics(application=None) -> None:
    logger.info("Running Sponsor Finder startup diagnostics...")
    
    # 1. Database check
    db_status = "OK"
    try:
        await init_db()
    except Exception as e:
        db_status = f"FAILED ({e})"
        logger.critical(f"Database initialization failed: {e}")
        sys.exit(1)

    # 2. Telegram Bot check
    tg_status = "Awaiting Token"
    bot_username = "Unconfigured"
    if application and settings.TELEGRAM_BOT_TOKEN and not settings.TELEGRAM_BOT_TOKEN.startswith("mock_"):
        try:
            bot_info = await application.bot.get_me()
            bot_username = f"@{bot_info.username}"
            tg_status = "OK"
        except Exception as e:
            tg_status = f"FAILED ({e})"

    # 3. AI / LLM Evaluator check
    ai_status = "OK"
    latency = 0
    try:
        success, msg, latency = await evaluator.verify_connectivity()
        if not success:
            ai_status = f"WARNING ({msg})"
        else:
            ai_status = f"OK ({latency} ms)"
    except Exception as e:
        ai_status = f"FAILED ({e})"

    # Diagnostics Grid
    grid = "\n" + "=" * 60 + "\n"
    grid += "       SPONSOR FINDER STARTUP DIAGNOSTICS GRID\n"
    grid += "=" * 60 + "\n"
    grid += f"[+] Database & Catalog Seed : {db_status}\n"
    grid += f"[+] Telegram Bot API       : {tg_status} ({bot_username})\n"
    grid += f"[+] AI Evaluator Engine    : {ai_status}\n"
    grid += f"[+] Bot Health Port        : {settings.BOT_PORT}\n"
    grid += f"[+] Web SaaS Port          : {settings.WEB_PORT}\n"
    grid += f"[+] Scheduler Engine       : Active ({settings.CHECK_INTERVAL_MINUTES}m interval)\n"
    grid += "=" * 60 + "\n"
    logger.info(grid)

async def post_init(application) -> None:
    await run_startup_diagnostics(application)

    # Register bot command menu popup
    try:
        commands = [
            BotCommand("start", "Mulai navigasi menu utama"),
            BotCommand("proposal", "Lihat rincian proposal event aktif"),
            BotCommand("match", "Cari sponsor paling relevan dengan AI"),
            BotCommand("catalog", "Jelajahi direktori perusahaan sponsor"),
            BotCommand("outreach", "Kelola draft dan antrean email sponsor"),
            BotCommand("discover", "Live crawl program CSR & kemitraan baru"),
            BotCommand("connect_google", "Hubungkan Gmail untuk 1-click email"),
            BotCommand("help", "Panduan lengkap penggunaan bot")
        ]
        await application.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        logger.info("Telegram Bot command menu popup registered successfully.")
    except Exception as e:
        logger.warning(f"Could not register command menu popup: {e}")

    # Start periodic scheduler
    scheduler_agent.start_scheduler()

def run_bot_branch() -> None:
    logger.info(f"Starting Sponsor Finder Bot Branch on Port {settings.BOT_PORT}...")

    # If mock or unconfigured token, run HTTP health service instead of polling crash
    if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN.startswith("mock_") or settings.TELEGRAM_BOT_TOKEN.startswith("your_"):
        logger.warning(
            f"TELEGRAM_BOT_TOKEN is not configured or in mock mode. "
            f"Telegram polling paused. Starting Bot HTTP Service on Port {settings.BOT_PORT}..."
        )
        asyncio.run(init_db())
        scheduler_agent.start_scheduler()
        asyncio.run(run_bot_http_server())
        return

    try:
        application = (
            ApplicationBuilder()
            .token(settings.TELEGRAM_BOT_TOKEN)
            .concurrent_updates(True)
            .post_init(post_init)
            .build()
        )
        setup_bot(application)
        application.run_polling()
    except Exception as e:
        logger.critical(f"Exception during bot runtime: {e}", exc_info=True)
        asyncio.run(run_bot_http_server())

def run_web_branch() -> None:
    logger.info(f"Starting Sponsor Finder Web SaaS Branch on Port {settings.WEB_PORT}...")
    try:
        asyncio.run(init_db())
        asyncio.run(run_web_server())
    except Exception as e:
        logger.critical(f"Exception during web runtime: {e}", exc_info=True)
        sys.exit(1)

def main() -> None:
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    if mode == "web":
        run_web_branch()
    elif mode == "bot":
        run_bot_branch()
    elif mode == "all":
        logger.info("=" * 60)
        logger.info("   BOOTING SPONSOR FINDER SAAS - DUAL-PORT ARCHITECTURE")
        logger.info(f"   [1] Bot Service Branch : PORT {settings.BOT_PORT}")
        logger.info(f"   [2] Web SaaS Branch    : PORT {settings.WEB_PORT}")
        logger.info("=" * 60)

        # Run Web Platform in background thread
        web_thread = threading.Thread(
            target=run_web_branch,
            name=f"WebPlatform-Port{settings.WEB_PORT}",
            daemon=True
        )
        web_thread.start()

        # Run Bot Branch in main thread
        run_bot_branch()
    else:
        print(f"Unknown mode: '{mode}'. Usage: python main.py [all|bot|web]")
        sys.exit(1)

if __name__ == "__main__":
    main()
