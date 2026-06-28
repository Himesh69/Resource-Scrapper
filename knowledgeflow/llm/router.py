"""
KnowledgeFlow — Static LLM Model Router

Reads models.yaml and returns the model configuration for each task.
If a task key is not found, falls back to the 'fallback' model.

Task → Model mapping (see models.yaml):
  extraction    → google/gemini-2.5-flash  (JSON mode)
  summary       → anthropic/claude-3-haiku    (Text mode)
  classification→ google/gemini-2.5-flash  (JSON mode)
  enrichment    → google/gemini-2.5-flash  (JSON mode)
  deduplication → google/gemini-2.5-flash  (JSON mode)
  fallback      → meta-llama/llama-3.1-8b-instruct:free
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
        "model": "meta-llama/llama-3.1-8b-instruct:free",
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
