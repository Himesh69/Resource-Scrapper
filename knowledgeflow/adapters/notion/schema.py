"""
KnowledgeFlow — Notion Database Schema Config

Defines property name constants and conversion helpers to format
KnowledgeGraph data models into Notion API payload formats.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import settings
from core.knowledge_graph import Platform, ResourceType, Difficulty, JobStatus


def format_title(text: str) -> dict[str, Any]:
    """Format title property for Notion."""
    return {"title": [{"type": "text", "text": {"content": text or ""}}]}


def format_rich_text(text: str) -> dict[str, Any]:
    """Format rich text property for Notion, handling limits (Notion max is 2000 chars)."""
    truncated = (text or "")[:1900]
    return {"rich_text": [{"type": "text", "text": {"content": truncated}}]}


def format_url(url: str) -> dict[str, Any]:
    """Format URL property for Notion."""
    return {"url": url or None}


def format_select(option: str) -> dict[str, Any]:
    """Format select property for Notion."""
    return {"select": {"name": option} if option else None}


def format_multi_select(options: list[str]) -> dict[str, Any]:
    """Format multi-select property for Notion."""
    return {"multi_select": [{"name": opt.strip()} for opt in options if opt.strip()]}


def format_checkbox(val: bool) -> dict[str, Any]:
    """Format checkbox property for Notion."""
    return {"checkbox": val}


def format_date(dt: datetime | None) -> dict[str, Any]:
    """Format date property for Notion."""
    if not dt:
        return {"date": None}
    return {"date": {"start": dt.isoformat()}}


def map_platform(platform: Platform) -> str:
    """Map Platform enum to Notion select option names."""
    mapping = {
        Platform.INSTAGRAM: "Instagram",
        Platform.YOUTUBE: "YouTube",
        Platform.X: "X / Twitter",
        Platform.LINKEDIN: "LinkedIn",
        Platform.PDF: "PDF",
        Platform.IMAGE: "Image",
        Platform.TEXT: "Text",
        Platform.UNKNOWN: "Other",
    }
    return mapping.get(platform, "Other")


def map_job_status(status: JobStatus) -> str:
    """Map JobStatus enum to Notion select option names."""
    mapping = {
        JobStatus.PENDING: "Processing",
        JobStatus.PROCESSING: "Processing",
        JobStatus.COMPLETED: "Completed",
        JobStatus.PARTIAL: "Partial",
        JobStatus.FAILED: "Failed",
    }
    return mapping.get(status, "Processing")


def format_body_blocks(text: str, heading: str = "📋 Full Content") -> list[dict]:
    """Convert long text into Notion page body blocks (heading + paragraphs).

    Notion block text content is limited to 2000 characters per block.
    This function splits the text into properly-sized chunks and returns
    a list of Notion block objects that can be passed as the `children`
    parameter in `pages.create`.

    Args:
        text: The full text content to convert into blocks.
        heading: The heading text for the content section.

    Returns:
        A list of Notion block dictionaries (heading_2 + paragraphs).
    """
    if not text or not text.strip():
        return []

    blocks: list[dict] = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": heading}}]
            },
        }
    ]

    # Split text into chunks of 2000 chars (Notion block text limit)
    chunk_size = 2000
    for i in range(0, len(text), chunk_size):
        chunk = text[i : i + chunk_size]
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                },
            }
        )

    return blocks
