"""
KnowledgeFlow — URL Parser & Platform Detector

Responsible for:
  1. Detecting which platform a URL belongs to
  2. Detecting the content type (reel, short, video, post, etc.)
  3. Normalizing URLs (removing tracking parameters)

No LLM calls — fully deterministic regex/URL parsing.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from core.knowledge_graph import ContentType, Platform


# ── Platform detection patterns ───────────────────────────────────────────────

_PLATFORM_PATTERNS: list[tuple[re.Pattern, Platform]] = [
    (re.compile(r"instagram\.com", re.I), Platform.INSTAGRAM),
    (re.compile(r"(youtube\.com|youtu\.be)", re.I), Platform.YOUTUBE),
    (re.compile(r"(x\.com|twitter\.com)", re.I), Platform.X),
    (re.compile(r"linkedin\.com", re.I), Platform.LINKEDIN),
]

# ── Content type detection patterns ───────────────────────────────────────────

_CONTENT_TYPE_PATTERNS: list[tuple[re.Pattern, ContentType]] = [
    # Instagram
    (re.compile(r"instagram\.com/(reel|reels)/", re.I), ContentType.REEL),
    (re.compile(r"instagram\.com/p/", re.I),             ContentType.POST),
    # YouTube
    (re.compile(r"youtube\.com/shorts/", re.I),           ContentType.SHORT),
    (re.compile(r"(youtube\.com/watch|youtu\.be/)", re.I), ContentType.VIDEO),
    # LinkedIn
    (re.compile(r"linkedin\.com/posts/", re.I),           ContentType.POST),
    (re.compile(r"linkedin\.com/pulse/", re.I),           ContentType.ARTICLE),
    # X / Twitter
    (re.compile(r"(x\.com|twitter\.com)/\w+/status/", re.I), ContentType.POST),
]

# Tracking parameters to strip from URLs
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "igshid", "gclid", "ref", "feature", "si",
})


def detect_platform(url: str) -> Platform:
    """Detect which platform a URL belongs to."""
    for pattern, platform in _PLATFORM_PATTERNS:
        if pattern.search(url):
            return platform
    return Platform.UNKNOWN


def detect_content_type(url: str) -> ContentType:
    """Detect the content type from the URL structure."""
    for pattern, content_type in _CONTENT_TYPE_PATTERNS:
        if pattern.search(url):
            return content_type
    return ContentType.UNKNOWN


def normalize_url(url: str) -> str:
    """
    Strip tracking parameters and normalize a URL.
    - Removes known tracking params (utm_*, fbclid, etc.)
    - Lowercases the scheme and host
    - Strips trailing slashes
    """
    try:
        url = url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
            
        parsed = urlparse(url)
        # Lowercase scheme and host
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        # Filter out tracking params
        params = parse_qs(parsed.query, keep_blank_values=True)
        cleaned_params = {
            k: v for k, v in params.items()
            if k.lower() not in _TRACKING_PARAMS
        }
        clean_query = urlencode(cleaned_params, doseq=True)
        normalized = urlunparse((
            scheme, netloc,
            parsed.path.rstrip("/"),
            parsed.params,
            clean_query,
            "",   # strip fragment
        ))
        return normalized
    except Exception:
        return url.strip()


def parse_url(url: str) -> dict[str, str]:
    """
    Full URL parse — returns platform, content_type, and normalized_url.

    Returns:
        {
            "platform": "instagram",
            "content_type": "reel",
            "normalized_url": "https://instagram.com/reel/abc123",
        }
    """
    normalized = normalize_url(url)
    return {
        "platform": detect_platform(normalized).value,
        "content_type": detect_content_type(normalized).value,
        "normalized_url": normalized,
    }
