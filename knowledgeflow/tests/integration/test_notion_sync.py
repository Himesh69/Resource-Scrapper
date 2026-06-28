"""
Integration tests for Notion Sync Adapter.

Mocks the Notion API client to verify that the sync logic correctly
translates KnowledgeGraph data into Notion API create/update calls.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.knowledge_graph import (
    KnowledgeGraph, Resource, ResourceType, Platform, Difficulty, JobStatus,
)
from adapters.notion.schema import (
    format_title, format_rich_text, format_url, format_select,
    format_multi_select, format_checkbox, format_date,
    format_body_blocks, map_platform, map_job_status,
)


# ── Schema Formatter Tests ───────────────────────────────────────────────────

class TestNotionSchemaFormatters:
    """Verify that the property formatters produce valid Notion payloads."""

    def test_format_title(self) -> None:
        result = format_title("Hello World")
        assert result == {"title": [{"type": "text", "text": {"content": "Hello World"}}]}

    def test_format_title_empty(self) -> None:
        result = format_title("")
        assert result["title"][0]["text"]["content"] == ""

    def test_format_rich_text_truncation(self) -> None:
        long_text = "A" * 3000
        result = format_rich_text(long_text)
        content = result["rich_text"][0]["text"]["content"]
        assert len(content) <= 1900

    def test_format_url(self) -> None:
        result = format_url("https://example.com")
        assert result == {"url": "https://example.com"}

    def test_format_url_empty(self) -> None:
        result = format_url("")
        assert result == {"url": None}

    def test_format_select(self) -> None:
        result = format_select("Instagram")
        assert result == {"select": {"name": "Instagram"}}

    def test_format_multi_select(self) -> None:
        result = format_multi_select(["python", "fastapi", ""])
        # Empty strings should be filtered
        assert result == {"multi_select": [{"name": "python"}, {"name": "fastapi"}]}

    def test_format_checkbox(self) -> None:
        assert format_checkbox(True) == {"checkbox": True}
        assert format_checkbox(False) == {"checkbox": False}

    def test_format_date_with_value(self) -> None:
        dt = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc)
        result = format_date(dt)
        assert result["date"]["start"] == dt.isoformat()

    def test_format_date_none(self) -> None:
        result = format_date(None)
        assert result == {"date": None}

    def test_format_body_blocks(self) -> None:
        text = "This is a prompt"
        result = format_body_blocks(text, heading="Prompt")
        
        assert len(result) == 2
        assert result[0]["type"] == "heading_2"
        assert result[0]["heading_2"]["rich_text"][0]["text"]["content"] == "Prompt"
        assert result[1]["type"] == "paragraph"
        assert result[1]["paragraph"]["rich_text"][0]["text"]["content"] == "This is a prompt"

    def test_format_body_blocks_long_text(self) -> None:
        text = "A" * 5000
        result = format_body_blocks(text)
        
        # 1 heading + ceil(5000 / 2000) paragraphs = 1 + 3 = 4 blocks
        assert len(result) == 4
        assert result[1]["paragraph"]["rich_text"][0]["text"]["content"] == "A" * 2000
        assert result[2]["paragraph"]["rich_text"][0]["text"]["content"] == "A" * 2000
        assert result[3]["paragraph"]["rich_text"][0]["text"]["content"] == "A" * 1000

    def test_format_body_blocks_empty(self) -> None:
        assert format_body_blocks("") == []
        assert format_body_blocks("   ") == []


# ── Enum Mapping Tests ───────────────────────────────────────────────────────

class TestEnumMappings:
    def test_map_platform(self) -> None:
        assert map_platform(Platform.INSTAGRAM) == "Instagram"
        assert map_platform(Platform.YOUTUBE) == "YouTube"
        assert map_platform(Platform.X) == "X / Twitter"
        assert map_platform(Platform.UNKNOWN) == "Other"

    def test_map_job_status(self) -> None:
        assert map_job_status(JobStatus.COMPLETED) == "Completed"
        assert map_job_status(JobStatus.PARTIAL) == "Partial"
        assert map_job_status(JobStatus.FAILED) == "Failed"
        assert map_job_status(JobStatus.PROCESSING) == "Processing"


# ── NotionSync Mock Tests ────────────────────────────────────────────────────

try:
    import notion_client  # noqa: F401
    HAS_NOTION = True
except ImportError:
    HAS_NOTION = False


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_NOTION, reason="notion-client not installed")
async def test_sync_creates_source_record() -> None:
    """Verify sync calls pages.create for the Sources database."""
    from adapters.notion.sync import NotionSync
    from adapters.notion.client import NotionClientWrapper

    # Build a KnowledgeGraph with minimal content
    kg = KnowledgeGraph.create_for_url("https://youtube.com/watch?v=test123")
    kg.source.title = "Test Video"
    kg.source.platform = Platform.YOUTUBE
    kg.source.summary = "A test summary"
    kg.source.primary_category = "Programming"
    kg.source.difficulty = Difficulty.INTERMEDIATE
    kg.source.tags = ["python", "testing"]
    kg.metadata.status = JobStatus.COMPLETED

    # Mock the wrapper
    mock_wrapper = MagicMock(spec=NotionClientWrapper)
    # Mock the underlying notion client
    mock_wrapper.client = MagicMock()
    mock_wrapper.client.databases.query = AsyncMock()
    mock_wrapper.client.pages.create = AsyncMock()

    # request() should call the passed function and return a dict with an "id"
    async def mock_request(func, *args, **kwargs):
        return {"id": "fake-page-id-123", "results": []}

    mock_wrapper.request = AsyncMock(side_effect=mock_request)

    # Patch settings to indicate Notion is configured
    with patch("adapters.notion.sync.settings") as mock_settings:
        mock_settings.notion_configured.return_value = True
        mock_settings.notion_creators_db_id = "db-creators"
        mock_settings.notion_sources_db_id = "db-sources"
        mock_settings.notion_resources_db_id = "db-resources"
        mock_settings.notion_knowledge_db_id = "db-knowledge"
        mock_settings.notion_categories_db_id = "db-categories"

        sync = NotionSync(client=mock_wrapper)
        result = await sync.sync(kg)

    # Verify the request method was called (at least for sources, knowledge, creator)
    assert mock_wrapper.request.call_count >= 3
    assert result.notion_source_page_id == "fake-page-id-123"
    assert result.notion_knowledge_page_id == "fake-page-id-123"


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_NOTION, reason="notion-client not installed")
async def test_sync_with_detailed_content() -> None:
    """Verify sync passes children blocks when detailed_content is present."""
    from adapters.notion.sync import NotionSync
    from adapters.notion.client import NotionClientWrapper

    kg = KnowledgeGraph.create_for_url("https://youtube.com/watch?v=test456")
    kg.source.title = "Test Video 2"
    kg.source.platform = Platform.YOUTUBE
    kg.source.summary = "A test summary"
    kg.source.detailed_content = "This is a detailed step-by-step guide."
    kg.metadata.status = JobStatus.COMPLETED

    mock_wrapper = MagicMock(spec=NotionClientWrapper)
    mock_wrapper.client = MagicMock()
    mock_wrapper.client.databases.query = AsyncMock()
    mock_wrapper.client.pages.create = AsyncMock()

    async def mock_request(func, *args, **kwargs):
        if func == mock_wrapper.client.pages.create:
            # We expect kwargs to contain 'children' when creating Knowledge/Sources pages
            pass
        return {"id": "fake-page-id-456", "results": []}

    mock_wrapper.request = AsyncMock(side_effect=mock_request)

    with patch("adapters.notion.sync.settings") as mock_settings:
        mock_settings.notion_configured.return_value = True
        mock_settings.notion_creators_db_id = "db-creators"
        mock_settings.notion_sources_db_id = "db-sources"
        mock_settings.notion_resources_db_id = "db-resources"
        mock_settings.notion_knowledge_db_id = "db-knowledge"
        mock_settings.notion_categories_db_id = "db-categories"

        sync = NotionSync(client=mock_wrapper)
        await sync.sync(kg)

    # Find the calls to pages.create
    create_calls = [
        call for call in mock_wrapper.request.call_args_list
        if call[0][0] == mock_wrapper.client.pages.create
    ]
    
    # We should have created a source page and a knowledge page, both should have children
    found_children = 0
    for call in create_calls:
        kwargs = call[1]
        if "children" in kwargs:
            children = kwargs["children"]
            assert isinstance(children, list)
            assert len(children) == 2  # heading + 1 paragraph
            found_children += 1

    # Should be 2 (Knowledge page and Sources page)
    assert found_children == 2
