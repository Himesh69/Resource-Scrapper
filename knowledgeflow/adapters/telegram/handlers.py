"""
KnowledgeFlow — Telegram Command & Callback Handlers

Defines commands (/start, /status, /cancel, /settings, etc.),
url message listener, and the inline keyboard callback query handler.
Uses an in-memory dictionary to hold KnowledgeGraphs awaiting user approval.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict

import structlog
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import settings
from core.exceptions import InputValidationError
from core.knowledge_graph import KnowledgeGraph, JobStatus, Platform
from core.job_manager import JobManager
from core.pipeline import Pipeline
from adapters.notion.sync import NotionSync
from adapters.telegram.formatter import format_preview, format_success, format_status
from cache.file_cache import FileCache
from llm.client import LLMClient
from utils.validators import validate_url

log = structlog.get_logger(__name__)

# Temporary store for completed KnowledgeGraphs awaiting approval (job_id -> KnowledgeGraph)
AWAITING_APPROVAL: Dict[str, KnowledgeGraph] = {}

# User preferences: user_id -> auto_save (defaults to True)
USER_PREFERENCES: Dict[int, bool] = {}


class TelegramHandlers:
    """
    Groups all handlers and holds references to managers, clients, and pipelines.
    """

    def __init__(self, job_manager: JobManager, llm_client: LLMClient, cache: FileCache) -> None:
        self.job_manager = job_manager
        self.llm_client = llm_client
        self.cache = cache
        self.notion_sync = NotionSync()
        self._log = log.bind(component="TelegramHandlers")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler for /start command."""
        user = update.effective_user
        name = user.first_name if user else "there"
        
        welcome_text = (
            f"👋 Hello {name}!\n\n"
            f"Welcome to <b>KnowledgeFlow</b>! I am an AI-driven personal knowledge ingestion bot.\n\n"
            f"<b>How to use me:</b>\n"
            f"1. Send me any URL (Instagram Reels, YouTube Videos, PDFs, etc.).\n"
            f"2. I'll process the content, extract structured insights, action items, topics, and references.\n"
            f"3. I'll save them directly to your <b>Notion Workspace</b>!\n\n"
            f"<b>Available Commands:</b>\n"
            f"• /status — Check active processing jobs.\n"
            f"• /cancel — Cancel your active jobs.\n"
            f"• /settings — Toggle Auto-Save vs Preview Approval mode.\n"
            f"• /help — Show this help message again.\n\n"
            f"Send me a link to get started! 🚀"
        )
        await update.message.reply_html(welcome_text)

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler for /help command."""
        await self.start(update, context)

    async def settings_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler for /settings command."""
        user_id = update.effective_user.id
        auto_save = USER_PREFERENCES.get(user_id, True)

        # Toggle or show setting
        if context.args and context.args[0].lower() in ("true", "false", "toggle"):
            arg = context.args[0].lower()
            if arg == "true":
                USER_PREFERENCES[user_id] = True
            elif arg == "false":
                USER_PREFERENCES[user_id] = False
            else:  # toggle
                USER_PREFERENCES[user_id] = not auto_save
            auto_save = USER_PREFERENCES[user_id]
            await update.message.reply_html(
                f"⚙️ <b>Settings Updated!</b>\n\n"
                f"Auto-Save Mode is now: <b>{'ENABLED (directly syncs to Notion)' if auto_save else 'DISABLED (requires approval keyboard)'}</b>"
            )
            return

        # Show current settings & buttons to toggle
        status_text = "ENABLED ✅" if auto_save else "DISABLED ❌"
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Enable Auto-Save", callback_data="set_auto_true"),
                InlineKeyboardButton("Disable Auto-Save", callback_data="set_auto_false")
            ]
        ])

        await update.message.reply_html(
            f"⚙️ <b>KNOWLEDGEFLOW SETTINGS</b>\n\n"
            f"<b>Auto-Save to Notion:</b> {status_text}\n"
            f"<i>When disabled, you will get a preview of the knowledge and must tap 'Save' before it goes to Notion.</i>",
            reply_markup=markup
        )

    async def status_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler for /status command."""
        jobs = self.job_manager.get_active_jobs()
        await update.message.reply_html(format_status(jobs))

    async def cancel_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler for /cancel command."""
        user_id = update.effective_user.id
        jobs = self.job_manager.get_active_jobs()
        user_jobs = [j for j in jobs if j["user_id"] == user_id]

        if not user_jobs:
            await update.message.reply_html("ℹ️ You have no active jobs to cancel.")
            return

        cancelled_count = 0
        for job in user_jobs:
            if self.job_manager.cancel(job["job_id"]):
                cancelled_count += 1

        await update.message.reply_html(f"🛑 Cancelled <b>{cancelled_count}</b> of your active jobs.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Intercepts messages, validates URLs, and submits them to the Pipeline."""
        text = update.message.text.strip()
        user_id = update.effective_user.id

        # 1. URL validation
        try:
            normalized_url = validate_url(text)
        except InputValidationError as exc:
            await update.message.reply_html(f"❌ <b>Error:</b> {exc}")
            return
        except Exception as exc:
            await update.message.reply_html(f"❌ <b>Error validating URL:</b> {exc}")
            return

        # 2. Check if already active in job manager
        active_jobs = self.job_manager.get_active_jobs()
        if any(j["url"] == normalized_url for j in active_jobs):
            await update.message.reply_html("⏳ This URL is already being processed. Please wait!")
            return

        # 3. Create KnowledgeGraph and Job
        kg = KnowledgeGraph.create_for_url(
            url=normalized_url,
            telegram_user_id=user_id,
        )
        job_id = kg.metadata.job_id

        # Send initial status message
        status_msg = await update.message.reply_html(
            f"⏳ <b>KnowledgeFlow Pipeline Ingesting...</b>\n\n"
            f"Platform: <code>{kg.source.platform.value.upper()}</code>\n"
            f"Job ID: <code>{job_id[:8]}</code>\n\n"
            f"<i>Processing started. I'll notify you as soon as I'm done.</i>"
        )
        kg.metadata.telegram_message_id = status_msg.message_id

        # Define processing task coroutine
        pipeline = Pipeline(self.llm_client, self.cache)
        job_coro = pipeline.run(kg)

        # Submit to JobManager
        self.job_manager.submit(
            job_id=job_id,
            url=normalized_url,
            telegram_user_id=user_id,
            job_coro=job_coro,
            on_complete=self.on_pipeline_complete
        )

    async def on_pipeline_complete(self, kg: KnowledgeGraph) -> None:
        """Callback executed by the JobManager when a pipeline job completes."""
        user_id = kg.metadata.telegram_user_id
        message_id = kg.metadata.telegram_message_id
        job_id = kg.metadata.job_id
        
        # Resolve target bot instance
        from telegram import Bot
        bot = Bot(token=settings.telegram_bot_token)

        self._log.debug("pipeline_complete.callback", job_id=job_id, status=kg.metadata.status.value)

        # 1. Handle pipeline failure
        if kg.metadata.status == JobStatus.FAILED:
            warnings_str = "\n".join(f"• {w}" for w in kg.metadata.warnings) if kg.metadata.warnings else "Unknown error."
            fail_text = (
                f"❌ <b>Processing Failed</b>\n\n"
                f"Job ID: <code>{job_id[:8]}</code>\n\n"
                f"<b>Warnings / Errors:</b>\n{warnings_str}"
            )
            try:
                await bot.edit_message_text(chat_id=user_id, message_id=message_id, text=fail_text, parse_mode="HTML")
            except Exception:
                await bot.send_message(chat_id=user_id, text=fail_text, parse_mode="HTML")
            self.cache.cleanup_job(job_id)
            return

        # 2. Determine auto-save vs approval mode
        auto_save = USER_PREFERENCES.get(user_id, True)

        if auto_save:
            # Mode A: Auto-Save directly to Notion
            try:
                # Update message to "saving"
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text="💾 <b>Syncing insights directly to Notion...</b>",
                    parse_mode="HTML"
                )
                
                # Run sync
                await self.notion_sync.sync(kg)
                
                # Show final success message
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text=format_success(kg),
                    parse_mode="HTML"
                )
            except Exception as exc:
                self._log.exception("autosave.failed", job_id=job_id, error=str(exc))
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text=f"⚠️ <b>Pipeline succeeded, but Notion sync failed:</b>\n<i>{exc}</i>",
                    parse_mode="HTML"
                )
            finally:
                self.cache.cleanup_job(job_id)
        else:
            # Mode B: Approval Mode. Present preview + approval buttons.
            AWAITING_APPROVAL[job_id] = kg
            preview_html = format_preview(kg)
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Save to Notion", callback_data=f"save_{job_id}"),
                    InlineKeyboardButton("❌ Discard", callback_data=f"discard_{job_id}")
                ]
            ])
            try:
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text=preview_html,
                    reply_markup=markup,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            except Exception as exc:
                self._log.exception("edit_preview_message.failed", job_id=job_id, error=str(exc))
                await bot.send_message(
                    chat_id=user_id,
                    text=preview_html,
                    reply_markup=markup,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles click events from Inline Keyboard buttons."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id

        # 1. Handle settings toggle button clicks
        if data == "set_auto_true":
            USER_PREFERENCES[user_id] = True
            await query.edit_message_text(
                "⚙️ <b>Settings Updated!</b>\n\nAuto-Save Mode is now: <b>ENABLED ✅</b>",
                parse_mode="HTML"
            )
            return
        elif data == "set_auto_false":
            USER_PREFERENCES[user_id] = False
            await query.edit_message_text(
                "⚙️ <b>Settings Updated!</b>\n\nAuto-Save Mode is now: <b>DISABLED ❌</b>",
                parse_mode="HTML"
            )
            return

        # 2. Handle Save/Discard callback queries
        if "_" not in data:
            return

        action, job_id = data.split("_", 1)
        kg = AWAITING_APPROVAL.get(job_id)

        if not kg:
            await query.edit_message_text("❌ <b>Error:</b> Job preview has expired or is no longer available.")
            return

        if action == "save":
            await query.edit_message_text("💾 <b>Syncing insights directly to Notion...</b>", parse_mode="HTML")
            try:
                await self.notion_sync.sync(kg)
                await query.edit_message_text(format_success(kg), parse_mode="HTML")
            except Exception as exc:
                self._log.exception("manual_save.failed", job_id=job_id, error=str(exc))
                await query.edit_message_text(f"⚠️ <b>Notion sync failed:</b>\n<i>{exc}</i>", parse_mode="HTML")
            finally:
                if job_id in AWAITING_APPROVAL:
                    del AWAITING_APPROVAL[job_id]
                self.cache.cleanup_job(job_id)
        elif action == "discard":
            await query.edit_message_text("❌ <b>Job Discarded.</b> Intermediate cache files have been cleared.", parse_mode="HTML")
            if job_id in AWAITING_APPROVAL:
                del AWAITING_APPROVAL[job_id]
            self.cache.cleanup_job(job_id)
