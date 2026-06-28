"""
Unit tests for the updated KnowledgeGraph data model.

Covers:
- New fields: detailed_content, pinned_comment, saved_frame_paths
- Existing helpers still work after model changes
"""
from __future__ import annotations

import pytest
from core.knowledge_graph import (
    KnowledgeGraph, Resource, ResourceType, Platform,
    JobStatus, AgentStatus, Source, ProcessingMetadata,
)


def test_knowledge_graph_creation() -> None:
    """Test factory method and initial states."""
    url = "https://instagram.com/reel/abc"
    kg = KnowledgeGraph.create_for_url(url=url, telegram_user_id=123, telegram_message_id=456)

    assert kg.input_url == url
    assert kg.metadata.telegram_user_id == 123
    assert kg.metadata.telegram_message_id == 456
    assert kg.metadata.status == JobStatus.PENDING
    assert len(kg.resources) == 0
    assert len(kg.metadata.warnings) == 0


def test_new_source_fields_default_to_empty() -> None:
    """New fields detailed_content and pinned_comment default to empty strings."""
    kg = KnowledgeGraph.create_for_url("https://instagram.com/reel/abc")
    assert kg.source.detailed_content == ""
    assert kg.source.pinned_comment == ""


def test_new_metadata_fields_default_to_empty_list() -> None:
    """New field saved_frame_paths defaults to empty list."""
    kg = KnowledgeGraph.create_for_url("https://instagram.com/reel/abc")
    assert kg.metadata.saved_frame_paths == []


def test_detailed_content_can_store_long_prompt() -> None:
    """detailed_content can store large verbatim prompt text (no size limit on model)."""
    kg = KnowledgeGraph.create_for_url("https://instagram.com/reel/abc")
    long_prompt = "You are an expert AI assistant. " * 500  # ~16 000 chars
    kg.source.detailed_content = long_prompt
    assert kg.source.detailed_content == long_prompt
    assert len(kg.source.detailed_content) > 10_000


def test_pinned_comment_stored_and_retrieved() -> None:
    """pinned_comment is stored and retrievable."""
    kg = KnowledgeGraph.create_for_url("https://instagram.com/reel/abc")
    comment = "🔗 Full prompt in bio → https://example.com/prompt\n#ai #chatgpt"
    kg.source.pinned_comment = comment
    assert kg.source.pinned_comment == comment


def test_saved_frame_paths_stored_and_retrieved() -> None:
    """saved_frame_paths stores a list of file paths."""
    kg = KnowledgeGraph.create_for_url("https://instagram.com/reel/abc")
    paths = ["/tmp/frames/frame_000.jpg", "/tmp/frames/frame_001.jpg"]
    kg.metadata.saved_frame_paths = paths
    assert kg.metadata.saved_frame_paths == paths
    assert len(kg.metadata.saved_frame_paths) == 2


def test_add_warnings() -> None:
    """Test warning accumulation."""
    kg = KnowledgeGraph.create_for_url("https://youtube.com/watch?v=123")
    kg.add_warning("Test warning 1")
    kg.add_warning("Test warning 2")

    assert len(kg.metadata.warnings) == 2
    assert kg.metadata.warnings[0] == "Test warning 1"
    assert kg.metadata.warnings[1] == "Test warning 2"


def test_add_resource_deduplication() -> None:
    """Test that resources are not added if they have duplicate URLs."""
    kg = KnowledgeGraph.create_for_url("https://youtube.com/watch?v=123")

    res1 = Resource(name="Pydantic", resource_type=ResourceType.LIBRARY, url="https://pydantic.dev")
    res2 = Resource(name="Pydantic Docs", resource_type=ResourceType.DOCUMENTATION, url="https://pydantic.dev")
    res3 = Resource(name="FastAPI", resource_type=ResourceType.FRAMEWORK, url="https://fastapi.tiangolo.com")

    kg.add_resource(res1)
    kg.add_resource(res2)  # Duplicate URL, should be ignored
    kg.add_resource(res3)

    assert len(kg.resources) == 2
    assert kg.resources[0].name == "Pydantic"
    assert kg.resources[1].name == "FastAPI"


def test_update_agent_log() -> None:
    """Test agent execution telemetry logging."""
    kg = KnowledgeGraph.create_for_url("https://youtube.com/watch?v=123")

    kg.update_agent_log("TestAgent", AgentStatus.RUNNING)
    assert len(kg.metadata.agent_logs) == 1
    assert kg.metadata.agent_logs[0].agent_name == "TestAgent"
    assert kg.metadata.agent_logs[0].status == AgentStatus.RUNNING

    kg.update_agent_log("TestAgent", AgentStatus.SUCCESS, warning="Done quickly")
    assert kg.metadata.agent_logs[0].status == AgentStatus.SUCCESS
    assert kg.metadata.agent_logs[0].warning == "Done quickly"


def test_has_useful_content_with_detailed_content() -> None:
    """has_useful_content returns True when there's a summary (detailed_content is extra)."""
    kg = KnowledgeGraph.create_for_url("https://instagram.com/reel/abc")
    assert not kg.has_useful_content()

    kg.source.detailed_content = "Step 1: Do this. Step 2: Do that."
    # detailed_content alone doesn't satisfy has_useful_content (needs title/summary/resources/topics)
    assert not kg.has_useful_content()

    kg.source.summary = "A guide about something"
    assert kg.has_useful_content()


def test_add_resource_no_url_always_added() -> None:
    """Resources without URLs are always added (no URL to deduplicate on)."""
    kg = KnowledgeGraph.create_for_url("https://instagram.com/reel/abc")
    res1 = Resource(name="Book A", resource_type=ResourceType.BOOK, url="")
    res2 = Resource(name="Book B", resource_type=ResourceType.BOOK, url="")

    kg.add_resource(res1)
    kg.add_resource(res2)

    assert len(kg.resources) == 2
