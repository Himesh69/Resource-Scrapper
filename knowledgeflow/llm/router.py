"""
KnowledgeFlow — Static LLM Model Router

Reads models.yaml and returns the model configuration for each task.
If a task key is not found, falls back to the 'fallback' model.

Task → Model mapping (see models.yaml) — ALL :free variants:
  extraction    → google/gemma-4-26b-a4b-it:free        (JSON mode, 1024 tokens)
  summary       → meta-llama/llama-3.3-70b-instruct:free (Text mode, 1024 tokens)
  classification→ google/gemma-4-26b-a4b-it:free        (JSON mode, 512 tokens)
  enrichment    → google/gemma-4-26b-a4b-it:free        (JSON mode, 1024 tokens)
  deduplication → google/gemma-4-26b-a4b-it:free        (JSON mode, 256 tokens)
  fallback      → google/gemma-4-26b-a4b-it:free        (512 tokens)
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
        "model": "google/gemma-4-26b-a4b-it:free",
        "temperature": 0.2,
        "max_tokens": 1024,
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
