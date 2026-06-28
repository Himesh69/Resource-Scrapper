"""
KnowledgeFlow — Telegram Bot Entrypoint

Initializes dependencies (LLMClient, FileCache, JobManager, Handlers),
registers command/message routes, and starts polling for updates.
"""
from __future__ import annotations

import structlog
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from config import settings
from cache.file_cache import FileCache
from llm.client import LLMClient
from core.job_manager import JobManager
from adapters.telegram.handlers import TelegramHandlers

log = structlog.get_logger(__name__)


def build_application(
    job_manager: JobManager,
    llm_client: LLMClient,
    cache: FileCache,
) -> Application:
    """Build and configure the python-telegram-bot Application."""
    token = settings.telegram_bot_token
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set.")

    # Initialize handlers class
    handlers = TelegramHandlers(job_manager, llm_client, cache)

    # Build Application
    app = Application.builder().token(token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_cmd))
    app.add_handler(CommandHandler("status", handlers.status_cmd))
    app.add_handler(CommandHandler("cancel", handlers.cancel_cmd))
    app.add_handler(CommandHandler("settings", handlers.settings_cmd))
    
    # Callback queries (for inline buttons)
    app.add_handler(CallbackQueryHandler(handlers.handle_callback_query))

    # General text messages (URLs) - filter out command messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))

    log.info("telegram.bot.built", token_prefix=token[:8])
    return app


def start_telegram_bot() -> None:
    """
    Synchronous blocking entrypoint to run the Telegram bot.
    Initializes singleton dependencies and starts polling.
    """
    log.info("telegram.bot.starting")
    
    # Initialize dependencies
    cache = FileCache()
    llm_client = LLMClient()
    job_manager = JobManager()

    # Build and run the app
    app = build_application(job_manager, llm_client, cache)
    
    log.info("telegram.bot.polling_active")
    app.run_polling()
