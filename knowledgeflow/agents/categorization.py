"""
KnowledgeFlow — Categorization Agent

Uses LLM to classify content into a primary category, subcategory, tags, and difficulty level.
Ensures categories and difficulty levels align with the predefined taxonomy in config.yaml.
"""
from __future__ import annotations

import structlog

from agents.base import BaseAgent
from core.exceptions import LLMError, AgentError
from core.knowledge_graph import KnowledgeGraph, Difficulty
from llm.client import LLMClient
from utils.prompt_loader import render_prompt
from config import app_config

log = structlog.get_logger(__name__)


class CategorizationAgent(BaseAgent):
    """
    Agent responsible for classifying the processed content into taxonomies.
    """

    def __init__(self, client: LLMClient) -> None:
        super().__init__(name="CategorizationAgent")
        self.client = client

    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        self._log.info("categorization.start")

        # 1. Load and render prompt template
        try:
            prompt = render_prompt(
                "categorization",
                title=kg.source.title or "Untitled",
                summary=kg.source.summary or "No summary.",
                topics=", ".join(kg.topics) if kg.topics else "None",
                key_concepts=", ".join(kg.key_concepts) if kg.key_concepts else "None",
            )
        except FileNotFoundError as exc:
            raise AgentError(self.name, f"Prompt template missing: {exc}", recoverable=False)

        messages = [
            {"role": "system", "content": "You are a Content Categorization assistant that outputs strict JSON."},
            {"role": "user", "content": prompt}
        ]

        try:
            # 3. Call LLM
            res_dict = await self.client.complete_json(
                task="classification",
                messages=messages,
                agent_name=self.name
            )

            # 4. Parse and validate against configured taxonomy
            # Resolve allowed categories from config
            allowed_categories = set(
                app_config.get("categories", {}).get("primary", [
                    "Programming", "Artificial Intelligence", "Machine Learning",
                    "Data Science", "DevOps & Cloud", "Cybersecurity",
                    "Entrepreneurship", "Product Management", "Design & UX",
                    "Marketing", "Finance", "Science", "Mathematics",
                    "Health & Wellness", "Personal Development", "Other"
                ])
            )

            primary_cat = res_dict.get("primary_category", "Other").strip()
            # Match case-insensitively but resolve to original cased name
            matched_cat = "Other"
            for cat in allowed_categories:
                if cat.lower() == primary_cat.lower():
                    matched_cat = cat
                    break
            kg.source.primary_category = matched_cat

            # Subcategory
            kg.source.subcategory = res_dict.get("subcategory", "").strip()

            # Tags (lowercase, unique, merge with existing tags)
            tags = res_dict.get("tags", [])
            for t in tags:
                if isinstance(t, str) and t.strip():
                    tag_clean = t.strip().lower()
                    if tag_clean not in kg.source.tags:
                        kg.source.tags.append(tag_clean)

            # Difficulty enum mapping
            diff_str = res_dict.get("difficulty", "Beginner").strip()
            matched_diff = Difficulty.BEGINNER
            for enum_val in Difficulty:
                if enum_val.value.lower() == diff_str.lower():
                    matched_diff = enum_val
                    break
            kg.source.difficulty = matched_diff

            self._log.info(
                "categorization.success",
                category=kg.source.primary_category,
                subcategory=kg.source.subcategory,
                difficulty=kg.source.difficulty.value
            )

        except LLMError:
            raise
        except Exception as exc:
            raise AgentError(self.name, f"Categorization classification failed: {exc}", recoverable=True) from exc

        return kg
