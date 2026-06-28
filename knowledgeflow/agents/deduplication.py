"""
KnowledgeFlow — Deduplication Agent

Normalizes resource URLs and fuzzy-matches resource names to prevent duplicate entries.
Merges internal duplicates in the current KnowledgeGraph and provides methods
to deduplicate and merge against external candidates (e.g. existing Notion database entries).
"""
from __future__ import annotations

import structlog
from thefuzz import fuzz

from agents.base import BaseAgent
from core.exceptions import LLMError, AgentError
from core.knowledge_graph import KnowledgeGraph, Resource
from llm.client import LLMClient
from utils.prompt_loader import render_prompt
from utils.url_parser import normalize_url
from config import app_config

log = structlog.get_logger(__name__)


class DeduplicationAgent(BaseAgent):
    """
    Agent responsible for deduplicating resources within the KnowledgeGraph and merging details.
    """

    def __init__(self, client: LLMClient) -> None:
        super().__init__(name="DeduplicationAgent")
        self.client = client

    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        if not kg.resources:
            self._log.info("deduplication.skipped", reason="No resources to process")
            return kg

        self._log.info("deduplication.start", count=len(kg.resources))

        # 1. Deduplicate resources internally (within the current job)
        unique_resources: list[Resource] = []
        similarity_threshold = app_config.get("deduplication", {}).get("name_similarity_threshold", 85)

        for res in kg.resources:
            # Normalize URL if present
            if res.url:
                res.url = normalize_url(res.url)

            # Check if this resource matches any already accepted unique resource
            match_found = False
            for existing in unique_resources:
                # Direct URL match is a duplicate
                if res.url and existing.url and res.url == existing.url:
                    match_found = True
                    self._merge_resources(existing, res)
                    break
                
                # Name fuzzy match
                score = fuzz.ratio(res.name.lower(), existing.name.lower())
                if score >= similarity_threshold:
                    # If they have conflicting non-empty URLs, don't auto-merge without caution,
                    # but if one is empty or they are close, we merge.
                    if not (res.url and existing.url and res.url != existing.url):
                        match_found = True
                        self._merge_resources(existing, res)
                        break

            if not match_found:
                unique_resources.append(res)

        kg.resources = unique_resources
        self._log.info("deduplication.success", final_count=len(kg.resources))
        return kg

    def _merge_resources(self, target: Resource, source: Resource) -> None:
        """Merge source resource info into target resource (in-place)."""
        self._log.debug("deduplication.merge_internal", target=target.name, source=source.name)
        
        # 1. Choose URL if target doesn't have one
        if not target.url and source.url:
            target.url = source.url

        # 2. Merge descriptions (keep the longer/more detailed one, or join them)
        if source.description and source.description != target.description:
            if not target.description:
                target.description = source.description
            elif len(source.description) > len(target.description):
                target.description = source.description

        # 3. Merge tags (case-insensitive deduplication)
        existing_tags_lower = {t.lower() for t in target.tags}
        for tag in source.tags:
            if tag.lower() not in existing_tags_lower:
                target.tags.append(tag)

        # 4. Max confidence
        target.confidence = max(target.confidence, source.confidence)

    async def deduplicate_against_candidates(
        self,
        new_res: Resource,
        candidates: list[dict[str, Any]]
    ) -> tuple[Resource, bool, str | None]:
        """
        Compare a new resource against a list of existing candidates (e.g. from Notion).
        Uses LLM deduplication when names match fuzzy thresholds to merge details correctly.

        Args:
            new_res: The newly extracted Resource object.
            candidates: List of candidate dictionaries representing database items.
                        Each should have: id, name, url, description, tags.

        Returns:
            (Resource, is_duplicate, matched_candidate_id)
            If is_duplicate is True, the Resource has been merged with candidate details.
        """
        if not candidates:
            return new_res, False, None

        # 1. Check exact URL match
        if new_res.url:
            norm_new_url = normalize_url(new_res.url)
            for cand in candidates:
                cand_url = cand.get("url")
                if cand_url and normalize_url(cand_url) == norm_new_url:
                    self._log.info("deduplication.notion.url_match", name=new_res.name, candidate=cand.get("name"))
                    # Merge and return
                    self._merge_into_resource_from_dict(new_res, cand)
                    return new_res, True, cand.get("id")

        # 2. Check fuzzy name match
        similarity_threshold = app_config.get("deduplication", {}).get("name_similarity_threshold", 85)
        matched_cands = []
        for cand in candidates:
            cand_name = cand.get("name", "")
            score = fuzz.ratio(new_res.name.lower(), cand_name.lower())
            if score >= similarity_threshold:
                matched_cands.append(cand)

        if not matched_cands:
            return new_res, False, None

        # 3. Call LLM for deduplication comparison if name is fuzzy matched
        # Format candidates list for prompt
        candidates_str = ""
        for i, cand in enumerate(matched_cands):
            candidates_str += (
                f"Candidate {i+1}:\n"
                f"  ID: {cand.get('id')}\n"
                f"  Name: {cand.get('name')}\n"
                f"  Type: {cand.get('resource_type') or 'Other'}\n"
                f"  URL: {cand.get('url') or 'N/A'}\n"
                f"  Description: {cand.get('description') or 'N/A'}\n"
                f"  Tags: {', '.join(cand.get('tags', []))}\n\n"
            )

        try:
            prompt = render_prompt(
                "deduplication",
                new_name=new_res.name,
                new_type=new_res.resource_type.value,
                new_url=new_res.url or "N/A",
                new_description=new_res.description or "N/A",
                candidates=candidates_str
            )
        except FileNotFoundError:
            # Fallback to local auto-merge with the first candidate if prompt is missing
            self._merge_into_resource_from_dict(new_res, matched_cands[0])
            return new_res, True, matched_cands[0].get("id")

        messages = [
            {"role": "system", "content": "You are a Deduplication assistant that outputs strict JSON."},
            {"role": "user", "content": prompt}
        ]

        try:
            res_dict = await self.client.complete_json(
                task="deduplication",
                messages=messages,
                agent_name=self.name
            )

            is_dup = res_dict.get("is_duplicate", False)
            matched_id = res_dict.get("matched_candidate_id")

            if is_dup and matched_id:
                self._log.info("deduplication.notion.llm_match", name=new_res.name, candidate_id=matched_id)
                merged_info = res_dict.get("merged_resource", {})
                
                # Apply merged info to our resource object
                new_res.name = merged_info.get("name", new_res.name).strip()
                new_res.url = merged_info.get("url", new_res.url).strip()
                new_res.description = merged_info.get("description", new_res.description).strip()
                
                tags = merged_info.get("tags", [])
                for t in tags:
                    if t.strip() and t.strip().lower() not in [tag.lower() for tag in new_res.tags]:
                        new_res.tags.append(t.strip())

                return new_res, True, matched_id

        except Exception as exc:
            self._log.warning("deduplication.llm_match.failed", error=str(exc))
            # Fallback to local auto-merge with the first candidate if LLM fails
            self._merge_into_resource_from_dict(new_res, matched_cands[0])
            return new_res, True, matched_cands[0].get("id")

        return new_res, False, None

    def _merge_into_resource_from_dict(self, target: Resource, source: dict[str, Any]) -> None:
        """Merge candidate dictionary fields into target Resource object."""
        if not target.url and source.get("url"):
            target.url = source.get("url")
            
        desc = source.get("description", "")
        if desc and desc != target.description:
            if not target.description:
                target.description = desc
            elif len(desc) > len(target.description):
                target.description = desc

        existing_tags_lower = {t.lower() for t in target.tags}
        for tag in source.get("tags", []):
            if tag.lower() not in existing_tags_lower:
                target.tags.append(tag)
