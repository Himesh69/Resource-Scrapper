"""
KnowledgeFlow — Telegram Message Formatter

Generates clean HTML-formatted messages for Telegram updates, previews, and status reports.
Uses HTML instead of Markdown to avoid complex character escaping bugs.
"""
from __future__ import annotations

from typing import Any
from core.knowledge_graph import KnowledgeGraph, Platform


def format_preview(kg: KnowledgeGraph) -> str:
    """Format the KnowledgeGraph preview before saving to Notion."""
    title = kg.source.title or "Untitled Insights"
    platform = kg.source.platform.value.upper()
    creator = f"by <b>{kg.source.creator_name}</b>" if kg.source.creator_name else ""
    category = kg.source.primary_category or "Uncategorized"
    difficulty = kg.source.difficulty.value if kg.source.difficulty else "Beginner"
    summary = kg.source.summary or "No summary extracted."
    
    html = [
        f"💡 <b>KNOWLEDGE PREVIEW</b>",
        f"━━━━━━━━━━━━━━━━━━━",
        f"<b>Title:</b> {title}",
        f"<b>Source:</b> {platform} {creator}",
        f"<b>Category:</b> {category} ({difficulty})",
        f"━━━━━━━━━━━━━━━━━━━",
        f"📝 <b>Summary:</b>",
        f"<i>{summary}</i>\n",
    ]

    if kg.topics:
        html.append(f"🏷️ <b>Topics:</b> {', '.join(kg.topics)}")

    if kg.action_items:
        html.append("\n✅ <b>Action Items:</b>")
        for item in kg.action_items[:5]:  # limit to 5 previewed items
            html.append(f"• {item}")

    if kg.resources:
        html.append(f"\n🔗 <b>Resources Found ({len(kg.resources)}):</b>")
        for res in kg.resources[:5]:
            type_label = f"[{res.resource_type.value}]"
            url_str = f" - <a href='{res.url}'>Link</a>" if res.url else ""
            html.append(f"• {res.name} <i>{type_label}</i>{url_str}")

    if len(kg.metadata.warnings) > 0:
        html.append(f"\n⚠️ <b>Warnings ({len(kg.metadata.warnings)}):</b>")
        for warning in kg.metadata.warnings[:3]:
            html.append(f"• <i>{warning}</i>")

    return "\n".join(html)


def format_success(kg: KnowledgeGraph) -> str:
    """Format the final success message after records are saved to Notion."""
    title = kg.source.title or "Content"
    
    # Construct Notion workspace page link if possible, or direct database link
    html = [
        f"✅ <b>Successfully Saved to Notion!</b>",
        f"━━━━━━━━━━━━━━━━━━━",
        f"📥 <b>Source:</b> {title}",
    ]
    
    if kg.resources:
        saved_count = sum(1 for r in kg.resources)
        merged_count = sum(1 for r in kg.resources if r.merged)
        html.append(f"🔗 <b>Resources:</b> {saved_count} saved ({merged_count} merged with existing)")

    html.append(f"\nCheck your Notion workspace to see the enriched insights! 🚀")
    return "\n".join(html)


def format_status(jobs: list[dict[str, Any]]) -> str:
    """Format the active pipeline jobs list."""
    if not jobs:
        return "ℹ️ <b>No active processing jobs.</b> Send me a URL to start!"
        
    html = ["⏳ <b>ACTIVE PIPELINE JOBS</b>\n"]
    for i, job in enumerate(jobs):
        html.append(
            f"<b>{i+1}.</b> <code>{job['job_id'][:8]}</code>"
            f" - {job['status'].upper()}\n"
            f"   <b>URL:</b> {job['url']}\n"
            f"   <b>Running:</b> {job['duration_seconds']}s"
        )
    return "\n".join(html)
