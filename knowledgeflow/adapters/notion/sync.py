"""
KnowledgeFlow — Notion Sync Adapter

Responsible for syncing the fully populated KnowledgeGraph into the 5 Notion databases:
1. Creators: checks for existing creator by username/name, creates or returns page reference.
2. Sources: creates a record for the ingestion job.
3. Knowledge: creates a record for the extracted insights.
4. Resources: deduplicates against existing records (by URL or fuzzy name),
   creates new or updates existing, and links to the Source title.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from adapters.notion.client import NotionClientWrapper
from adapters.notion.schema import (
    format_title,
    format_rich_text,
    format_url,
    format_select,
    format_multi_select,
    format_checkbox,
    format_date,
    format_body_blocks,
    map_platform,
    map_job_status,
)
from config import settings
from core.exceptions import NotionError
from core.knowledge_graph import KnowledgeGraph, Resource, ResourceType

log = structlog.get_logger(__name__)


class NotionSync:
    """
    Coordinates syncing the KnowledgeGraph model to Notion databases.
    """

    def __init__(self, client: NotionClientWrapper | None = None) -> None:
        self.client = client or NotionClientWrapper()
        self._log = log.bind(component="NotionSync")

    async def sync(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        """
        Sync a KnowledgeGraph to Notion.
        
        Requires NOTION_SOURCES_DB_ID, NOTION_RESOURCES_DB_ID, etc. to be set.
        """
        if not settings.notion_configured():
            raise NotionError(
                "Notion database IDs are not configured. "
                "Run scripts/setup_notion.py or populate your .env file."
            )

        self._log.info("sync.start", job_id=kg.metadata.job_id)

        try:
            # 1. Sync Creator info (if available)
            creator_page_id = None
            if kg.source.creator_username or kg.source.creator_name:
                creator_page_id = await self._sync_creator(kg)

            # 2. Sync Source record
            source_page_id = await self._sync_source(kg)
            kg.notion_source_page_id = source_page_id

            # 3. Sync Knowledge record
            knowledge_page_id = await self._sync_knowledge(kg)
            kg.notion_knowledge_page_id = knowledge_page_id

            # 4. Sync Resources (with Notion duplicate check)
            await self._sync_resources(kg)

            self._log.info("sync.completed", job_id=kg.metadata.job_id)
        except Exception as exc:
            self._log.error("sync.failed", error=str(exc))
            raise NotionError(f"Notion synchronization failed: {exc}") from exc

        return kg

    async def _sync_creator(self, kg: KnowledgeGraph) -> str:
        """Finds or creates a record in the Creators database."""
        db_id = settings.notion_creators_db_id
        username = kg.source.creator_username
        name = kg.source.creator_name or username or "Unknown Creator"
        
        # Query by Username or Name to check existence
        query_filter = None
        if username:
            query_filter = {"property": "Username", "rich_text": {"equals": username}}
        else:
            query_filter = {"property": "Name", "title": {"equals": name}}

        # Execute Notion query
        query_res = await self.client.request(
            self.client.client.databases.query,
            database_id=db_id,
            filter=query_filter
        )
        
        results = query_res.get("results", [])
        if results:
            # Found existing creator
            page_id = results[0]["id"]
            self._log.debug("sync.creator.found_existing", name=name, id=page_id)
            return page_id

        # Create new creator record
        properties = {
            "Name": format_title(name),
            "Platform": format_select(map_platform(kg.source.platform)),
            "Username": format_rich_text(username),
            "Profile URL": format_url(kg.source.creator_profile_url),
        }
        
        create_res = await self.client.request(
            self.client.client.pages.create,
            parent={"database_id": db_id},
            properties=properties
        )
        page_id = create_res["id"]
        self._log.debug("sync.creator.created_new", name=name, id=page_id)
        return page_id

    async def _sync_source(self, kg: KnowledgeGraph) -> str:
        """Create a record in the Sources database."""
        db_id = settings.notion_sources_db_id
        title = kg.source.title or "Ingested Content"
        warnings_str = "\n".join(kg.metadata.warnings) if kg.metadata.warnings else ""

        properties = {
            "Title": format_title(title),
            "URL": format_url(kg.input_url),
            "Platform": format_select(map_platform(kg.source.platform)),
            "Summary": format_rich_text(kg.source.summary),
            "Status": format_select(map_job_status(kg.metadata.status)),
            "Tags": format_multi_select(kg.source.tags),
            "Processed At": format_date(kg.metadata.created_at),
            "Job ID": format_rich_text(kg.metadata.job_id),
            "Warnings": format_rich_text(warnings_str),
        }

        res = await self.client.request(
            self.client.client.pages.create,
            parent={"database_id": db_id},
            properties=properties,
            **({"children": format_body_blocks(kg.source.detailed_content)} if kg.source.detailed_content else {}),
        )
        return res["id"]

    async def _sync_knowledge(self, kg: KnowledgeGraph) -> str:
        """Create a record in the Knowledge database."""
        db_id = settings.notion_knowledge_db_id
        title = kg.source.title or "Ingested Insights"
        
        # Format action items as a bulleted text string
        action_items_str = "\n".join(f"- {item}" for item in kg.action_items) if kg.action_items else ""

        # Predefine difficulty string
        diff_str = kg.source.difficulty.value if kg.source.difficulty else "Beginner"

        properties = {
            "Title": format_title(title),
            "Summary": format_rich_text(kg.source.summary),
            "Topics": format_multi_select(kg.topics),
            "Action Items": format_rich_text(action_items_str),
            "Tags": format_multi_select(kg.source.tags),
            "Difficulty": format_select(diff_str),
            "Source URL": format_url(kg.input_url),
            "Created At": format_date(datetime.now(timezone.utc)),
        }

        res = await self.client.request(
            self.client.client.pages.create,
            parent={"database_id": db_id},
            properties=properties,
            **({"children": format_body_blocks(kg.source.detailed_content)} if kg.source.detailed_content else {}),
        )
        return res["id"]

    async def _sync_resources(self, kg: KnowledgeGraph) -> None:
        """Sync and deduplicate all Resources to the Resources database."""
        db_id = settings.notion_resources_db_id
        source_title = kg.source.title or "Ingested Content"

        # 1. Fetch potential candidates for duplicate checks (scan up to 200 records to check duplicates)
        # To avoid making many separate query requests, we can list the last 200 items in the DB
        # and do fuzzy matching in-memory. This is fast and matches the deduplication agent's needs!
        candidates = []
        try:
            candidates_res = await self.client.request(
                self.client.client.databases.query,
                database_id=db_id,
                page_size=200
            )
            for page in candidates_res.get("results", []):
                p_id = page["id"]
                p_props = page.get("properties", {})
                
                # Extract Name from Title
                name_list = p_props.get("Name", {}).get("title", [])
                p_name = name_list[0]["text"]["content"] if name_list else ""
                
                # Extract URL
                p_url = p_props.get("URL", {}).get("url") or ""
                
                # Extract Description
                desc_list = p_props.get("Description", {}).get("rich_text", [])
                p_desc = desc_list[0]["text"]["content"] if desc_list else ""
                
                # Extract Tags
                tags_list = p_props.get("Tags", {}).get("multi_select", [])
                p_tags = [t["name"] for t in tags_list]
                
                candidates.append({
                    "id": p_id,
                    "name": p_name,
                    "url": p_url,
                    "description": p_desc,
                    "tags": p_tags
                })
        except Exception as exc:
            self._log.warning("sync.resources.fetch_candidates_failed", error=str(exc))

        # 2. Iterate through each resource in KnowledgeGraph, check duplicates, and sync
        from agents.deduplication import DeduplicationAgent
        dedup_agent = DeduplicationAgent(self.client)

        for res in kg.resources:
            # Skip resources without names
            if not res.name:
                continue

            # Compare against Notion candidates using DeduplicationAgent
            matched_page_id = None
            is_dup = False
            if candidates:
                res, is_dup, matched_page_id = await dedup_agent.deduplicate_against_candidates(res, candidates)

            properties = {
                "Name": format_title(res.name),
                "Type": format_select(res.resource_type.value),
                "URL": format_url(res.url),
                "Description": format_rich_text(res.description),
                "Tags": format_multi_select(res.tags),
                "Enriched": format_checkbox(res.enriched),
                "Source Title": format_rich_text(source_title),
                "Added At": format_date(datetime.now(timezone.utc)),
            }

            if is_dup and matched_page_id:
                # Update existing page
                self._log.debug("sync.resource.updating_existing", name=res.name, page_id=matched_page_id)
                await self.client.request(
                    self.client.client.pages.update,
                    page_id=matched_page_id,
                    properties=properties
                )
                res.notion_page_id = matched_page_id
                res.merged = True
            else:
                # Create new page
                self._log.debug("sync.resource.creating_new", name=res.name)
                create_res = await self.client.request(
                    self.client.client.pages.create,
                    parent={"database_id": db_id},
                    properties=properties
                )
                res.notion_page_id = create_res["id"]
