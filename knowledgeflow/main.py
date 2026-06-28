"""
KnowledgeFlow — Entrypoint

Starts the Telegram bot, which drives all user interactions.
The bot hands URLs/files to the pipeline orchestrator and
sends progress updates back to the user.

Run:
    python main.py
    # or via Docker:
    docker-compose up
"""
import sys

import structlog

from config import settings
from utils.logging_config import configure_logging

log = structlog.get_logger(__name__)


def main() -> None:
    # 1. Set up structured logging first
    configure_logging(level=settings.log_level)

    log.info(
        "knowledgeflow.starting",
        version="1.0.0",
        log_level=settings.log_level,
        max_concurrent_jobs=settings.max_concurrent_jobs,
        keep_cache=settings.keep_cache,
    )

    # 2. Validate critical config
    if not settings.notion_configured():
        log.warning(
            "notion.not_configured",
            msg="Notion database IDs are missing. Run: python scripts/setup_notion.py",
        )

    # 3. Import and start Telegram bot (deferred to avoid circular imports)
    from adapters.telegram.bot import start_telegram_bot

    log.info("telegram.bot.starting")
    start_telegram_bot()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
