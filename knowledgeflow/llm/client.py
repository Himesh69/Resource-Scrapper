"""
KnowledgeFlow — LLM Client

Wraps Google AI Studio's OpenAI-compatible API using the openai SDK.
All LLM calls across the pipeline go through this client.

Features:
  - Async chat completions
  - JSON mode (structured output)
  - Automatic retry with exponential backoff (via llm/retry.py)
  - Task-based model routing (via llm/router.py)
  - Audio transcription via Gemini multimodal

Usage:
    from llm.client import LLMClient
    client = LLMClient()
    response = await client.complete(task="extraction", messages=[...])
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import structlog
from openai import AsyncOpenAI, APITimeoutError, RateLimitError, APIError

from config import settings, model_config
from core.exceptions import (
    LLMError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMResponseParseError,
)
from llm.retry import with_retry
from llm.router import get_model_config

log = structlog.get_logger(__name__)


class LLMClient:
    """
    Async LLM client for Google AI Studio (Gemini).

    All agents share a single instance of this class (injected by the pipeline).
    """

    def __init__(self) -> None:
        api_key = settings.llm_api_key
        base_url = settings.llm_base_url

        if not api_key:
            raise RuntimeError(
                "No LLM API key configured. Set GOOGLE_AI_API_KEY in .env"
            )

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self._log = log.bind(component="LLMClient", provider="google_ai_studio")
        self._log.info("llm.client.initialized", base_url=base_url)

    async def complete(
        self,
        task: str,
        messages: list[dict[str, str]],
        agent_name: str = "unknown",
        *,
        override_model: str | None = None,
        override_temperature: float | None = None,
        override_max_tokens: int | None = None,
    ) -> str:
        """
        Send a chat completion request for the given task.

        Args:
            task:               Task key from models.yaml (e.g. "extraction", "summary").
            messages:           Chat messages in OpenAI format.
            agent_name:         Name of the calling agent (for logging).
            override_model:     Bypass routing and use this model directly.
            override_temperature: Override the temperature from models.yaml.
            override_max_tokens:  Override max_tokens from models.yaml.

        Returns:
            The assistant's response text (str).

        Raises:
            LLMTimeoutError     — on timeout (retriable)
            LLMRateLimitError   — on rate limit (retriable)
            LLMError            — on other API errors
        """
        model_cfg = get_model_config(task)
        model      = override_model or model_cfg["model"]
        temperature = override_temperature if override_temperature is not None else model_cfg.get("temperature", 0.2)
        max_tokens  = override_max_tokens or model_cfg.get("max_tokens", 2048)
        json_mode   = model_cfg.get("json_mode", False)

        # Google AI Studio model names don't need provider prefix
        # (e.g. "gemini-2.5-flash" not "google/gemini-2.5-flash")
        if "/" in model:
            model = model.split("/", 1)[1]

        call_kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            call_kwargs["response_format"] = {"type": "json_object"}

        log_ctx = self._log.bind(agent=agent_name, task=task, model=model)
        log_ctx.debug("llm.request", message_count=len(messages))

        async def _call() -> str:
            try:
                response = await self._client.chat.completions.create(**call_kwargs)
                content = response.choices[0].message.content or ""
                log_ctx.debug(
                    "llm.response",
                    tokens_used=response.usage.total_tokens if response.usage else None,
                    finish_reason=response.choices[0].finish_reason,
                )
                return content
            except APITimeoutError as exc:
                raise LLMTimeoutError(agent_name, f"LLM timeout: {exc}") from exc
            except RateLimitError as exc:
                # HTTP 402 = billing/credit exhausted, NOT a transient rate limit
                if "402" in str(exc) or getattr(exc, 'status_code', 0) == 402:
                    raise LLMError(agent_name, f"LLM billing error [402]: credits exhausted. {exc}") from exc
                raise LLMRateLimitError(agent_name, f"LLM rate limit: {exc}") from exc
            except APIError as exc:
                raise LLMError(agent_name, f"LLM API error [{exc.status_code}]: {exc.message}") from exc

        return await with_retry(
            _call,
            agent_name=agent_name,
            task=task,
        )

    async def complete_json(
        self,
        task: str,
        messages: list[dict[str, str]],
        agent_name: str = "unknown",
    ) -> dict[str, Any]:
        """
        Same as `complete()` but parses and returns the JSON response.

        Includes repair logic for truncated JSON (e.g. when max_tokens cuts
        the response mid-stream).  It attempts to close unclosed braces and
        brackets so that partial data can still be salvaged.

        Raises:
            LLMResponseParseError — if the response is not valid JSON even
                                    after repair attempts.
        """
        raw = await self.complete(task=task, messages=messages, agent_name=agent_name)

        # ── Pipeline: direct parse → extract embedded → truncated repair ──
        cleaned = self._strip_fences(raw)

        # 1. Direct parse
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            pass

        # 2. Try to extract a JSON object from preamble text
        #    e.g. "Here is the JSON requested:\n{...}"
        extracted = self._extract_json_from_text(raw)
        if extracted is not None:
            self._log.debug(
                "llm.json_extracted_from_preamble",
                agent=agent_name,
                task=task,
            )
            return extracted

        # 3. Attempt to repair truncated JSON
        repaired = self._repair_truncated_json(raw)
        if repaired is not None:
            self._log.warning(
                "llm.json_repaired",
                agent=agent_name,
                task=task,
                hint="Response was truncated; partial data salvaged.",
            )
            return repaired

        raise LLMResponseParseError(agent_name, raw)

    @staticmethod
    def _strip_fences(raw: str) -> str:
        """Strip markdown code fences if present."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return cleaned.strip()

    @staticmethod
    def _extract_json_from_text(raw: str) -> dict[str, Any] | None:
        """
        Find and parse the first top-level JSON object in the raw text.

        Handles cases where the model wraps JSON in markdown fences or
        prepends conversational text like "Here is the JSON requested:".
        """
        # First strip markdown fences
        text = raw.strip()
        if "```" in text:
            # Try to extract content between fences
            import re
            fence_match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
            if fence_match:
                try:
                    return json.loads(fence_match.group(1).strip())
                except (json.JSONDecodeError, ValueError):
                    text = fence_match.group(1).strip()

        # Find the first '{' and try progressively larger substrings
        first_brace = text.find('{')
        if first_brace == -1:
            return None

        # Find the last '}' and try to parse that span
        last_brace = text.rfind('}')
        if last_brace <= first_brace:
            return None

        candidate = text[first_brace:last_brace + 1]
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            return None

    @staticmethod
    def _repair_truncated_json(raw: str) -> dict[str, Any] | None:
        """
        Best-effort repair of truncated JSON by closing unclosed delimiters.

        Returns the parsed dict on success, or None if repair fails.
        """
        cleaned = raw.strip()
        # Strip markdown fences
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            cleaned = cleaned.strip()

        if not cleaned:
            return None

        # Trim trailing comma or colon that would make JSON invalid
        cleaned = cleaned.rstrip().rstrip(",").rstrip(":")

        # Remove a trailing incomplete string value (unmatched quote)
        # e.g.  "description": "A set of practices combining...
        # Count unescaped quotes
        in_string = False
        last_quote_idx = -1
        i = 0
        while i < len(cleaned):
            ch = cleaned[i]
            if ch == '\\' and in_string:
                i += 2  # skip escaped char
                continue
            if ch == '"':
                in_string = not in_string
                last_quote_idx = i
            i += 1

        # If we ended inside a string, close it
        if in_string and last_quote_idx >= 0:
            cleaned = cleaned + '"'

        # Remove trailing comma again after string closure
        cleaned = cleaned.rstrip().rstrip(",")

        # Close unclosed brackets/braces
        stack: list[str] = []
        in_str = False
        j = 0
        while j < len(cleaned):
            ch = cleaned[j]
            if ch == '\\' and in_str:
                j += 2
                continue
            if ch == '"':
                in_str = not in_str
            elif not in_str:
                if ch in ('{', '['):
                    stack.append(ch)
                elif ch == '}':
                    if stack and stack[-1] == '{':
                        stack.pop()
                elif ch == ']':
                    if stack and stack[-1] == '[':
                        stack.pop()
            j += 1

        # Append closing delimiters in reverse order
        for opener in reversed(stack):
            cleaned += ']' if opener == '[' else '}'

        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return None

    async def transcribe(
        self,
        file_path: str | Path,
        agent_name: str = "TranscriptAgent",
    ) -> str:
        """
        Transcribe an audio file using Gemini multimodal (audio as base64 in chat message).

        Args:
            file_path: Path to the audio file on disk.
            agent_name: Name of the calling agent for logging.

        Returns:
            Transcribed text.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file for transcription not found: {path}")

        self._log.debug("audio.transcribe.start", file=path.name, size=path.stat().st_size)

        # Read and encode audio as base64
        audio_bytes = path.read_bytes()
        audio_b64 = base64.b64encode(audio_bytes).decode()

        # Determine MIME type
        suffix = path.suffix.lower()
        mime_map = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac",
        }
        mime = mime_map.get(suffix, "audio/mpeg")

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Transcribe this audio file verbatim. "
                            "Output ONLY the transcribed text, nothing else. "
                            "No timestamps, no speaker labels, no commentary."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{audio_b64}"},
                    },
                ],
            }
        ]

        model_cfg = get_model_config("summary")
        model = model_cfg["model"]
        if "/" in model:
            model = model.split("/", 1)[1]

        async def _call() -> str:
            try:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=4096,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:
                raise LLMError(agent_name, f"Gemini audio transcription failed: {exc}") from exc

        return await with_retry(
            _call,
            agent_name=agent_name,
            task="transcription",
        )
