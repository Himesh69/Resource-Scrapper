"""
KnowledgeFlow — Custom Exception Taxonomy

Hierarchy:
  KnowledgeFlowError
  ├── InputError
  │   ├── InputValidationError
  │   ├── UnsupportedPlatformError
  │   └── DuplicateSubmissionError
  ├── DownloadError
  │   └── PrivateContentError
  ├── AgentError
  │   ├── OCRError
  │   ├── TranscriptionError
  │   └── LLMError
  │       ├── LLMTimeoutError
  │       ├── LLMRateLimitError
  │       └── LLMResponseParseError
  ├── NotionError
  │   └── NotionRateLimitError
  ├── PipelineError
  └── CacheError

Design rule: AgentErrors are RECOVERABLE by default — the pipeline
catches them, records a warning in the KnowledgeGraph, and continues.
Non-recoverable errors stop the pipeline immediately.
"""
from __future__ import annotations


# ── Base ──────────────────────────────────────────────────────

class KnowledgeFlowError(Exception):
    """Base exception for all KnowledgeFlow errors."""


# ── Input Errors ──────────────────────────────────────────────

class InputError(KnowledgeFlowError):
    """Base for input-related errors — always stops the pipeline."""


class InputValidationError(InputError):
    """Malformed or invalid input (bad URL, unsupported file type, etc.)."""


class UnsupportedPlatformError(InputError):
    """The submitted URL is from a platform we don't support."""

    def __init__(self, platform: str) -> None:
        self.platform = platform
        super().__init__(
            f"Platform '{platform}' is not supported. "
            "Supported platforms: Instagram, YouTube, X/Twitter, LinkedIn, PDF, Image, Text."
        )


class DuplicateSubmissionError(InputError):
    """This exact URL was already submitted in the current session."""

    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(f"Already submitted in this session: {url}")


# ── Download Errors ───────────────────────────────────────────

class DownloadError(KnowledgeFlowError):
    """Media download failed (network error, yt-dlp error, etc.)."""


class PrivateContentError(DownloadError):
    """Content is private, age-restricted, or requires login."""

    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(
            f"Content at {url} is private or inaccessible. "
            "Only public content is supported."
        )


# ── Agent Errors ──────────────────────────────────────────────

class AgentError(KnowledgeFlowError):
    """
    An agent failed during processing.
    
    If recoverable=True (default), the pipeline records a warning
    and continues with remaining agents.
    If recoverable=False, the pipeline terminates immediately.
    """

    def __init__(
        self,
        agent_name: str,
        message: str,
        recoverable: bool = True,
    ) -> None:
        self.agent_name = agent_name
        self.recoverable = recoverable
        super().__init__(f"[{agent_name}] {message}")


class OCRError(AgentError):
    """OCR frame extraction or text detection failed (recoverable)."""

    def __init__(self, message: str) -> None:
        super().__init__("OCRAgent", message, recoverable=True)


class TranscriptionError(AgentError):
    """Audio transcription API call failed (recoverable)."""

    def __init__(self, message: str) -> None:
        super().__init__("TranscriptAgent", message, recoverable=True)


# ── LLM Errors ────────────────────────────────────────────────

class LLMError(AgentError):
    """Base class for LLM-related errors."""

    def __init__(
        self,
        agent_name: str,
        message: str,
        recoverable: bool = True,
    ) -> None:
        super().__init__(agent_name, message, recoverable=recoverable)


class LLMTimeoutError(LLMError):
    """LLM request timed out — retriable with exponential backoff."""


class LLMRateLimitError(LLMError):
    """Google AI Studio rate limit hit — retriable after delay."""


class LLMResponseParseError(LLMError):
    """
    LLM returned a response we couldn't parse as valid JSON.
    Marked non-recoverable so the agent logs a warning and skips gracefully.
    """

    def __init__(self, agent_name: str, raw_response: str) -> None:
        self.raw_response = raw_response
        super().__init__(
            agent_name,
            f"Failed to parse LLM JSON response. Preview: {raw_response[:300]}",
            recoverable=True,
        )


# ── Notion Errors ─────────────────────────────────────────────

class NotionError(KnowledgeFlowError):
    """Notion API call failed."""


class NotionRateLimitError(NotionError):
    """Notion enforces ~3 requests/second — retriable after delay."""


# ── Pipeline & Cache ──────────────────────────────────────────

class PipelineError(KnowledgeFlowError):
    """Pipeline orchestration-level error (should not normally occur)."""


class CacheError(KnowledgeFlowError):
    """File cache read/write failed (non-critical, logs warning)."""
