"""
KnowledgeFlow — Static LLM Model Router

Reads models.yaml and returns the model configuration for each task.
If a task key is not found, falls back to the 'fallback' model.

Task → Model mapping (see models.yaml) — Google AI Studio (Gemini):
  extraction     → gemini-2.5-flash  (JSON mode, 4096 tokens)
  summary        → gemini-2.5-flash  (Text mode, 4096 tokens)
  classification → gemini-2.5-flash  (JSON mode, 4096 tokens)
  enrichment     → gemini-2.5-flash  (JSON mode, 4096 tokens)
  deduplication  → gemini-2.5-flash  (JSON mode, 512 tokens)
  fallback       → gemini-2.5-flash  (2048 tokens)
"""
from __future__ import annotations

from typing import Any

import structlog

from config import model_config

log = structlog.get_logger(__name__)

# Cache resolved configs so we only log once per task
_resolved: dict[str, dict[str, Any]] = {}


def get_model_config(task: str) -> dict[str, Any]:
    """
    Return the model configuration dict for the given task key.

    Args:
        task: One of: extraction, summary, classification, enrichment,
              deduplication, fallback.

    Returns:
        Dict with at least: model, temperature, max_tokens, json_mode.
    """
    if task in _resolved:
        return _resolved[task]

    models = model_config.get("models", {})
    fallback = model_config.get("fallback", {
        "model": "gemini-3.1-flash-lite",
        "temperature": 0.2,
        "max_tokens": 2048,
        "json_mode": False,
    })

    if task in models:
        cfg = dict(models[task])
    else:
        log.warning(
            "llm.router.unknown_task",
            task=task,
            fallback_model=fallback.get("model"),
        )
        cfg = dict(fallback)

    # Fill in defaults for any missing keys
    cfg.setdefault("temperature", 0.2)
    cfg.setdefault("max_tokens", 2048)
    cfg.setdefault("json_mode", False)

    log.debug("llm.router.resolved", task=task, model=cfg["model"])
    _resolved[task] = cfg
    return cfg
