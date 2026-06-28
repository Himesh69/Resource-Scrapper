"""
KnowledgeFlow — Knowledge Builder Agent

Uses LLM to extract key concepts, entities, relationships, action items, and topics from content context.
Validates extracted entities and relationships using Pydantic.
"""
from __future__ import annotations

import structlog

from agents.base import BaseAgent
from core.exceptions import LLMError, AgentError
from core.knowledge_graph import KnowledgeGraph, Entity, Relationship
from llm.client import LLMClient
from utils.prompt_loader import render_prompt

log = structlog.get_logger(__name__)


class KnowledgeBuilderAgent(BaseAgent):
    """
    Agent responsible for extracting structured knowledge elements (topics, entities, actions).
    """

    def __init__(self, client: LLMClient) -> None:
        super().__init__(name="KnowledgeBuilderAgent")
        self.client = client

    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        self._log.info("knowledge_builder.start")

        # 1. Load and render prompt template
        try:
            prompt = render_prompt(
                "knowledge_extraction",
                platform=kg.source.platform.value,
                title=kg.source.title or "Untitled",
                creator=kg.source.creator_name or "Unknown",
                caption=kg.source.description or "No caption.",
                pinned_comment=kg.source.pinned_comment or "No pinned comment.",
                summary=kg.source.summary or "No summary available.",
                ocr_text=kg.metadata.ocr_text or "No OCR text extracted.",
            )
        except FileNotFoundError as exc:
            raise AgentError(self.name, f"Prompt template missing: {exc}", recoverable=False)

        messages = [
            {"role": "system", "content": "You are a Knowledge Graph extraction assistant that outputs strict JSON."},
            {"role": "user", "content": prompt}
        ]

        try:
            # 3. Call LLM in JSON mode
            res_dict = await self.client.complete_json(
                task="extraction",
                messages=messages,
                agent_name=self.name
            )

            # 4. Parse and validate elements using Pydantic models
            # Extract Topics
            topics = res_dict.get("topics", [])
            for t in topics:
                if isinstance(t, str) and t.strip():
                    topic_clean = t.strip()
                    if topic_clean not in kg.topics:
                        kg.topics.append(topic_clean)

            # Extract Entities
            entities_list = res_dict.get("entities", [])
            for ent_data in entities_list:
                try:
                    # Clean type to match lowercase
                    if "entity_type" in ent_data and isinstance(ent_data["entity_type"], str):
                        ent_data["entity_type"] = ent_data["entity_type"].lower().strip()
                    
                    entity = Entity.model_validate(ent_data)
                    # Check if already present
                    if not any(e.name.lower() == entity.name.lower() for e in kg.entities):
                        kg.entities.append(entity)
                except Exception as val_exc:
                    self._log.warning("knowledge_builder.entity_validation_failed", data=ent_data, error=str(val_exc))

            # Extract Relationships
            relationships_list = res_dict.get("relationships", [])
            for rel_data in relationships_list:
                try:
                    relationship = Relationship.model_validate(rel_data)
                    # Check if already present
                    if not any(
                        r.from_entity.lower() == relationship.from_entity.lower() and
                        r.to_entity.lower() == relationship.to_entity.lower() and
                        r.relation.lower() == relationship.relation.lower()
                        for r in kg.relationships
                    ):
                        kg.relationships.append(relationship)
                except Exception as val_exc:
                    self._log.warning("knowledge_builder.relationship_validation_failed", data=rel_data, error=str(val_exc))

            # Extract Action Items
            action_items = res_dict.get("action_items", [])
            for item in action_items:
                if isinstance(item, str) and item.strip():
                    item_clean = item.strip()
                    if item_clean not in kg.action_items:
                        kg.action_items.append(item_clean)

            # Extract Key Concepts
            key_concepts = res_dict.get("key_concepts", [])
            for concept in key_concepts:
                if isinstance(concept, str) and concept.strip():
                    concept_clean = concept.strip()
                    if concept_clean not in kg.key_concepts:
                        kg.key_concepts.append(concept_clean)

            self._log.info(
                "knowledge_builder.success",
                topics=len(kg.topics),
                entities=len(kg.entities),
                relationships=len(kg.relationships),
                action_items=len(kg.action_items),
                key_concepts=len(kg.key_concepts)
            )

        except LLMError:
            raise
        except Exception as exc:
            raise AgentError(self.name, f"Failed to extract structured knowledge: {exc}", recoverable=True) from exc

        return kg
