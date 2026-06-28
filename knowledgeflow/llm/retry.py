"""
KnowledgeFlow — LLM Retry Logic

Implements exponential backoff retry for transient LLM failures:
  - LLMTimeoutError   → retry
  - LLMRateLimitError → retry with extra delay
  - LLMError 402      → re-raise immediately (billing error, not transient)
  - Other errors      → re-raise immediately

Retry schedule (configurable via config.yaml):
  Attempt 1 → wait 2s → Attempt 2 → wait 4s → Attempt 3 → fail
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypeVar

import structlog

from config import app_config
from core.exceptions import LLMError, LLMRateLimitError, LLMTimeoutError

log = structlog.get_logger(__name__)

T = TypeVar("T")


async def with_retry(
    coro_factory: Callable[[], Awaitable[T]],
    agent_name: str = "unknown",
    task: str = "unknown",
) -> T:
    """
    Retry an async callable with exponential backoff.

    Args:
        coro_factory: A zero-argument async callable (returned fresh each call).
        agent_name:   Name of the calling agent (for logging).
        task:         Task name (for logging).

    Returns:
        The result of a successful call.

    Raises:
        LLMError (or subclass) after all retries are exhausted.
    """
    pipeline_cfg = app_config.get("pipeline", {})
    max_retries: int = pipeline_cfg.get("max_retries", 3)
    initial_delay: float = float(pipeline_cfg.get("retry_initial_delay", 2))
    max_delay: float = float(pipeline_cfg.get("retry_max_delay", 30))

    last_error: Exception | None = None
    delay = initial_delay

    for attempt in range(1, max_retries + 1):
        try:
            return await coro_factory()

        except LLMRateLimitError as exc:
            last_error = exc
            # Try to extract exact wait time from Google's quota error message
            import re
            wait = min(delay * 2, max_delay)
            exc_str = str(exc)
            match = re.search(r"Please retry in ([0-9.]+)s", exc_str, re.IGNORECASE)
            if match:
                try:
                    # Parse requested delay and add 1.5 seconds safety padding
                    parsed_seconds = float(match.group(1)) + 1.5
                    wait = max(wait, parsed_seconds)
                except ValueError:
                    pass

            log.warning(
                "llm.rate_limit",
                agent=agent_name,
                task=task,
                attempt=attempt,
                max=max_retries,
                wait_seconds=wait,
            )
            await asyncio.sleep(wait)
            delay = min(delay * 2, max_delay)


        except LLMTimeoutError as exc:
            last_error = exc
            wait = min(delay, max_delay)
            log.warning(
                "llm.timeout",
                agent=agent_name,
                task=task,
                attempt=attempt,
                max=max_retries,
                wait_seconds=wait,
            )
            await asyncio.sleep(wait)
            delay = min(delay * 2, max_delay)

        except LLMError as exc:
            # Check for 402 billing error — never retry, credits are exhausted
            if "402" in str(exc):
                log.error(
                    "llm.error_billing",
                    agent=agent_name,
                    task=task,
                    error=str(exc),
                    hint="Top up OpenRouter credits at https://openrouter.ai/settings/credits",
                )
                raise
            # Non-retriable LLM error (e.g. bad request, parse failure)
            log.error(
                "llm.error_non_retriable",
                agent=agent_name,
                task=task,
                error=str(exc),
            )
            raise

    log.error(
        "llm.retries_exhausted",
        agent=agent_name,
        task=task,
        attempts=max_retries,
        last_error=str(last_error),
    )
    raise last_error  # type: ignore[misc]
