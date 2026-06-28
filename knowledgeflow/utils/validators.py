"""
KnowledgeFlow — Input Validator

Validates user-submitted content before any processing begins.
Failures here immediately stop the pipeline and notify the user.

Validation order:
  1. Is this a valid URL format?
  2. Is the platform supported?
  3. Is the URL not obviously broken?
  4. Is it a duplicate submission?

No LLM calls — fully deterministic.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from config import app_config
from core.exceptions import (
    DuplicateSubmissionError,
    InputValidationError,
    UnsupportedPlatformError,
)
from core.knowledge_graph import Platform
from utils.url_parser import detect_platform, normalize_url

# Simple URL format check (not RFC-strict, but catches obvious mistakes)
_URL_RE = re.compile(
    r"^https?://"
    r"(?:[A-Z0-9](?:[A-Z0-9\-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,}"
    r"(?::\d+)?(?:/[^\s]*)?$",
    re.IGNORECASE,
)

# Supported platforms (from config.yaml)
_SUPPORTED_PLATFORMS: set[str] = set(
    app_config.get("supported_platforms", [
        "instagram", "youtube", "x", "twitter", "linkedin",
        "pdf", "image", "text",
    ])
)


def validate_url(url: str) -> str:
    """
    Validate a URL and return its normalized form.

    Args:
        url: Raw URL string from the user.

    Returns:
        Normalized URL string.

    Raises:
        InputValidationError: If the URL is malformed.
        UnsupportedPlatformError: If the platform is not supported.
    """
    url = url.strip()

    # Basic format check
    if not url:
        raise InputValidationError("No URL provided.")

    if not _URL_RE.match(url):
        raise InputValidationError(
            f"'{url}' doesn't look like a valid URL. "
            "Please send a link starting with https://"
        )

    # Check for obviously invalid domains
    parsed = urlparse(url)
    if not parsed.netloc:
        raise InputValidationError(f"Could not parse domain from URL: {url}")

    # Platform support check
    platform = detect_platform(url)
    if platform == Platform.UNKNOWN:
        # Extract the domain for the error message
        domain = parsed.netloc.replace("www.", "")
        raise UnsupportedPlatformError(domain)

    return normalize_url(url)


def check_duplicate(url: str, seen_urls: set[str]) -> None:
    """
    Check if this URL has already been submitted in the current session.

    Args:
        url:       Normalized URL to check.
        seen_urls: Set of URLs already processed in this session.

    Raises:
        DuplicateSubmissionError: If the URL was already submitted.
    """
    if normalize_url(url) in seen_urls:
        raise DuplicateSubmissionError(url)


def validate_text_input(text: str) -> str:
    """
    Validate plain text input (minimum length check).

    Returns:
        Stripped text.

    Raises:
        InputValidationError: If text is too short to be meaningful.
    """
    text = text.strip()
    if len(text) < 20:
        raise InputValidationError(
            "Text input is too short (minimum 20 characters). "
            "Please provide more content."
        )
    return text
