"""
KnowledgeFlow — Prompt Loader

Loads prompt templates from the prompts/ directory.
Prompts are stored as plain Markdown (.md) files so they can be
edited and version-controlled without touching Python code.

Templates use $variable or ${variable} placeholders (NOT Python {variable})
so that literal JSON braces in the prompt text are preserved safely.

Usage:
    from utils.prompt_loader import render_prompt
    prompt_text = render_prompt("knowledge_extraction", title="...", platform="...")
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@lru_cache(maxsize=None)
def load_prompt(prompt_name: str) -> str:
    """
    Load a raw prompt template by name (no substitution).

    Args:
        prompt_name: The filename without extension (e.g. "knowledge_extraction").

    Returns:
        The raw prompt text as a string.

    Raises:
        FileNotFoundError: If the prompt file doesn't exist.
    """
    path = PROMPTS_DIR / f"{prompt_name}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Prompt '{prompt_name}' not found at {path}. "
            f"Available prompts: {list_prompts()}"
        )
    return path.read_text(encoding="utf-8").strip()


def render_prompt(prompt_name: str, **kwargs: str) -> str:
    """
    Load a prompt template and safely substitute variables.

    Converts {variable} placeholders in the template to $variable style
    before applying substitution, so literal JSON braces are preserved.

    Args:
        prompt_name:   The prompt file name (without .md extension).
        **kwargs: Key-value pairs to substitute into the template.

    Returns:
        The rendered prompt string.
    """
    raw = load_prompt(prompt_name)

    # Convert {placeholder} → $placeholder ONLY for known keys.
    # This preserves literal JSON braces like {"key": "value"}.
    for key in kwargs:
        raw = raw.replace("{" + key + "}", "${" + key + "}")

    template = Template(raw)
    return template.safe_substitute(**kwargs)


def list_prompts() -> list[str]:
    """Return names of all available prompt files."""
    return sorted(p.stem for p in PROMPTS_DIR.glob("*.md"))


def reload_prompts() -> None:
    """Clear the prompt cache (useful during development)."""
    load_prompt.cache_clear()
