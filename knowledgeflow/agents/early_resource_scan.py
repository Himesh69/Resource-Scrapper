"""
KnowledgeFlow — Early Resource Scan Agent

A lightweight, zero-LLM agent that runs immediately after MetadataAgent.
Scans the description and pinned comment for explicit URLs.

If URLs are found, it sets `kg.metadata.early_resources_found = True`,
signalling the pipeline to skip expensive video processing (download,
OCR, transcription) and go directly to LLM-based resource extraction.

Also generates a basic caption-based summary so TranscriptAgent can be skipped.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

import structlog

from agents.base import BaseAgent
from core.knowledge_graph import KnowledgeGraph

log = structlog.get_logger(__name__)

# Match explicit URLs and well-known short-link / link-in-bio domains
_URL_RE = re.compile(
    r'(?:'
    r'https?://[^\s<>"\')\]]+|'              # Explicit http/https URLs
    r'\b(?:bit\.ly|tinyurl\.com|t\.co|'      # Short-link domains
    r'linktr\.ee|lnk\.to|stan\.store|'       # Link-in-bio services
    r'beacons\.ai|carrd\.co|tap\.bio|'
    r'msha\.ke|hoo\.be)'
    r'/[^\s<>"\')\]]*|'                       # …followed by a path
    r'\b[a-zA-Z0-9-]+\.(?:com|io|ai|co|org|net|dev|app)/[^\s<>"\')\]]*'  # bare domain WITH a path
    r')',
    re.IGNORECASE
)

# Platform domains that don't count as "found resources"
_PLATFORM_DOMAINS = frozenset({
    "instagram.com", "youtube.com", "youtu.be",
    "tiktok.com", "twitter.com", "x.com",
    "facebook.com", "fb.com", "linkedin.com",
    "threads.net", "snapchat.com", "pinterest.com",
})


def _is_platform_url(url: str) -> bool:
    """Return True if this URL points to a content-hosting platform."""
    try:
        netloc = urlparse(url if "://" in url else f"https://{url}").netloc.lower().lstrip("www.")
        return any(netloc == d or netloc.endswith("." + d) for d in _PLATFORM_DOMAINS)
    except Exception:
        return False


class EarlyResourceScanAgent(BaseAgent):
    """
    Scans description and pinned comment for URLs before any expensive processing.

    If actionable URLs are found (not just platform links), sets
    ``kg.metadata.early_resources_found = True`` so the pipeline can
    skip download/OCR/transcription.
    """

    def __init__(self) -> None:
        super().__init__(name="EarlyResourceScanAgent")

    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        self._log.info("early_scan.start")

        # Collect text to scan
        texts = [
            kg.source.description or "",
            kg.source.pinned_comment or "",
        ]
        raw_text = "\n".join(texts)

        if not raw_text.strip():
            self._log.info("early_scan.no_text", reason="No description or pinned comment available")
            return kg

        # Find all URLs
        found_urls: set[str] = set()
        for match in _URL_RE.findall(raw_text):
            url = match.strip().rstrip(".,;!)?]}")
            if not _is_platform_url(url):
                found_urls.add(url)

        if found_urls:
            kg.metadata.early_resources_found = True
            self._log.info(
                "early_scan.resources_found",
                count=len(found_urls),
                urls=list(found_urls)[:5],
            )

            # Generate a basic summary from caption so TranscriptAgent can be skipped
            if not kg.source.summary:
                caption = kg.source.description or ""
                title = kg.source.title or ""
                creator = kg.source.creator_name or "Unknown creator"
                # Use first 500 chars of caption as a lightweight summary
                summary_text = caption[:500].strip()
                if summary_text:
                    kg.source.summary = f"{creator} shares resources and insights. {summary_text}"
                elif title:
                    kg.source.summary = f"{creator} shares: {title}"
        else:
            self._log.info("early_scan.no_resources", reason="No actionable URLs found in text")

        return kg
