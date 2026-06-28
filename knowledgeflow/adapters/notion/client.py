"""
KnowledgeFlow — Notion API Client Wrapper

Wraps the official notion-client AsyncClient.
Enforces the Notion rate limit of ~3 requests/second using a 400ms throttle.
Implements automatic retries for transient Notion API errors and 429 Rate Limits.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Coroutine

import structlog
from notion_client import AsyncClient
from notion_client.errors import APIResponseError

from config import settings, app_config
from core.exceptions import NotionError, NotionRateLimitError

log = structlog.get_logger(__name__)


class NotionClientWrapper:
    """
    Thread-safe, rate-limited wrapper around AsyncClient.
    """

    def __init__(self, token: str | None = None) -> None:
        auth_token = token or settings.notion_token
        self.client = AsyncClient(auth=auth_token)
        # 400ms delay between consecutive requests to avoid 429 rate limit
        cfg_delay = app_config.get("notion", {}).get("request_delay_ms", 400)
        self._delay = float(cfg_delay) / 1000.0
        self._lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._log = log.bind(component="NotionClient")

    async def _throttle(self) -> None:
        """Enforces a minimum time delay between consecutive API requests."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._delay:
                sleep_time = self._delay - elapsed
                await asyncio.sleep(sleep_time)
            self._last_request_time = time.monotonic()

    async def request(
        self,
        api_func: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        max_retries: int = 3,
        **kwargs: Any
    ) -> Any:
        """
        Execute a Notion API call with throttling and exponential backoff retry.
        """
        delay = 1.0
        last_exc = None

        for attempt in range(1, max_retries + 1):
            await self._throttle()
            try:
                self._log.debug("notion.api_request.start", func=api_func.__name__, attempt=attempt)
                result = await api_func(*args, **kwargs)
                self._log.debug("notion.api_request.success", func=api_func.__name__)
                return result
            except APIResponseError as exc:
                last_exc = exc
                status = exc.status
                
                # Check for rate limit error (429)
                if status == 429:
                    self._log.warning(
                        "notion.api_rate_limit",
                        func=api_func.__name__,
                        attempt=attempt,
                        wait_seconds=delay * 2,
                    )
                    await asyncio.sleep(delay * 2)
                    delay *= 2
                    continue
                
                # Check for temporary server errors (500, 502, 504)
                if status in (500, 502, 504):
                    self._log.warning(
                        "notion.api_server_error",
                        status=status,
                        func=api_func.__name__,
                        attempt=attempt,
                        wait_seconds=delay,
                    )
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                
                # Other Notion API errors (e.g. 400 Bad Request, 404 Not Found) are non-retriable
                self._log.error(
                    "notion.api_error.non_retriable",
                    status=status,
                    code=getattr(exc, "code", "unknown"),
                    message=str(exc),
                )
                raise NotionError(f"Notion API error [{status}]: {str(exc)}") from exc
            except Exception as exc:
                last_exc = exc
                self._log.warning(
                    "notion.request.unexpected_error",
                    func=api_func.__name__,
                    error=str(exc),
                    attempt=attempt,
                )
                await asyncio.sleep(delay)
                delay *= 2

        self._log.error("notion.request.failed_after_retries", attempts=max_retries)
        raise NotionError(f"Notion API request failed after {max_retries} attempts. Last error: {last_exc}")
