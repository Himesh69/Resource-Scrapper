"""
KnowledgeFlow — Configuration
Loads settings from .env and YAML files using pydantic-settings.

Usage:
    from config import settings, app_config, model_config
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent


class Settings(BaseSettings):
    """
    Application settings.
    Values are loaded from the .env file in this directory.
    All field names map directly to env var names (case-insensitive).
    """

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Telegram ─────────────────────────────────────────────
    telegram_bot_token: str = Field(
        description="Telegram Bot API token from BotFather"
    )

    # ── LLM Provider ─────────────────────────────────────────
    # Supports Google AI Studio (primary) or OpenRouter (fallback)
    google_ai_api_key: str = Field(
        default="",
        description="Google AI Studio API key (https://aistudio.google.com)",
    )
    google_ai_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        description="Google AI Studio OpenAI-compatible endpoint",
    )

    # OpenRouter (used as fallback if Google AI key is not set)
    openrouter_api_key: str = Field(
        default="",
        description="OpenRouter API key (https://openrouter.ai/keys)",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter base URL — OpenAI-compatible endpoint",
    )
    openrouter_site_url: str = Field(
        default="https://github.com/knowledgeflow",
        description="Sent to OpenRouter as HTTP-Referer for attribution",
    )
    openrouter_app_name: str = Field(
        default="KnowledgeFlow",
        description="Sent to OpenRouter as X-Title for attribution",
    )

    @property
    def llm_api_key(self) -> str:
        """Return the active LLM provider API key (Google AI Studio preferred)."""
        return self.google_ai_api_key or self.openrouter_api_key

    @property
    def llm_base_url(self) -> str:
        """Return the active LLM base URL (Google AI Studio preferred)."""
        if self.google_ai_api_key:
            return self.google_ai_base_url
        return self.openrouter_base_url

    @property
    def llm_provider(self) -> str:
        """Return which LLM provider is active."""
        return "google_ai_studio" if self.google_ai_api_key else "openrouter"

    # ── Notion ───────────────────────────────────────────────
    notion_token: str = Field(
        description="Notion internal integration token"
    )
    notion_sources_db_id: str = Field(
        default="",
        description="Notion Sources database ID",
    )
    notion_resources_db_id: str = Field(
        default="",
        description="Notion Resources database ID",
    )
    notion_categories_db_id: str = Field(
        default="",
        description="Notion Categories database ID",
    )
    notion_creators_db_id: str = Field(
        default="",
        description="Notion Creators database ID",
    )
    notion_knowledge_db_id: str = Field(
        default="",
        description="Notion Knowledge database ID",
    )

    # ── App Behaviour ────────────────────────────────────────
    max_concurrent_jobs: int = Field(
        default=3,
        description="Maximum parallel pipeline jobs",
    )
    keep_cache: bool = Field(
        default=False,
        description="If True, keep intermediate files after processing",
    )
    log_level: str = Field(
        default="INFO",
        description="Log level: DEBUG | INFO | WARNING | ERROR",
    )
    cache_dir: str = Field(
        default=".cache",
        description="Directory for intermediate processing files",
    )

    def notion_configured(self) -> bool:
        """Returns True if all Notion database IDs are set."""
        return all([
            self.notion_sources_db_id,
            self.notion_resources_db_id,
            self.notion_categories_db_id,
            self.notion_creators_db_id,
            self.notion_knowledge_db_id,
        ])


def _load_yaml(filename: str) -> dict[str, Any]:
    """Load a YAML file from the project root. Returns {} if not found."""
    path = BASE_DIR / filename
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# ── Singleton instances (imported by all modules) ─────────────
settings = Settings()
app_config: dict[str, Any] = _load_yaml("config.yaml")
model_config: dict[str, Any] = _load_yaml("models.yaml")
