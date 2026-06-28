"""
KnowledgeFlow — LLM Client

Wraps the OpenAI-compatible API (Google AI Studio or OpenRouter) using the openai SDK.
All LLM calls across the pipeline go through this client.

Features:
  - Async chat completions
  - JSON mode (structured output)
  - Automatic retry with exponential backoff (via llm/retry.py)
  - Task-based model routing (via llm/router.py)
  - Audio transcription via Gemini multimodal (Google AI Studio) or Whisper (OpenRouter)
  - Provider auto-detection from config

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
    Async LLM client supporting Google AI Studio (primary) and OpenRouter (fallback).

    All agents share a single instance of this class (injected by the pipeline).
    """

    def __init__(self) -> None:
        provider = settings.llm_provider
        api_key = settings.llm_api_key
        base_url = settings.llm_base_url

        if not api_key:
            raise RuntimeError(
                "No LLM API key configured. Set GOOGLE_AI_API_KEY or OPENROUTER_API_KEY in .env"
            )

        # Build headers (OpenRouter needs attribution headers; Google AI Studio doesn't)
        headers = {}
        if provider == "openrouter":
            headers = {
                "HTTP-Referer": settings.openrouter_site_url,
                "X-Title": settings.openrouter_app_name,
            }

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers=headers,
        )
        self._provider = provider
        self._log = log.bind(component="LLMClient", provider=provider)
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

        # For Google AI Studio, model names don't need provider prefix
        # (e.g. "gemini-2.5-flash" not "google/gemini-2.5-flash")
        if self._provider == "google_ai_studio" and "/" in model:
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

        Raises:
            LLMResponseParseError — if the response is not valid JSON.
        """
        raw = await self.complete(task=task, messages=messages, agent_name=agent_name)
        try:
            # Strip markdown code fences if present (some models add them)
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError) as exc:
            raise LLMResponseParseError(agent_name, raw) from exc

    async def transcribe(
        self,
        file_path: str | Path,
        agent_name: str = "TranscriptAgent",
    ) -> str:
        """
        Transcribe an audio file.

        - Google AI Studio: Uses Gemini multimodal (send audio as base64 in chat message)
        - OpenRouter: Uses Whisper API

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

        if self._provider == "google_ai_studio":
            return await self._transcribe_gemini(path, agent_name)
        else:
            return await self._transcribe_whisper(path, agent_name)

    async def _transcribe_gemini(self, path: Path, agent_name: str) -> str:
        """Transcribe audio using Gemini's multimodal chat (Google AI Studio)."""
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

    async def _transcribe_whisper(self, path: Path, agent_name: str) -> str:
        """Transcribe audio using OpenRouter's Whisper API."""
        async def _call() -> str:
            try:
                with open(path, "rb") as audio_file:
                    response = await self._client.audio.transcriptions.create(
                        file=audio_file,
                        model="openai/whisper-large-v3",
                    )
                    return response.text
            except Exception as exc:
                raise LLMError(agent_name, f"OpenRouter audio transcription failed: {exc}") from exc

        return await with_retry(
            _call,
            agent_name=agent_name,
            task="transcription",
        )
