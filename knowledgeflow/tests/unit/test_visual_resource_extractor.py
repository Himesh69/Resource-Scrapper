"""
Unit tests for the VisualResourceExtractorAgent.

Mocks the LLM vision calls and YouTube searches to verify that the agent
correctly detects YouTube thumbnails and adds them as resources.
"""
from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import Response

from agents.visual_resource_extractor import VisualResourceExtractorAgent
from core.knowledge_graph import KnowledgeGraph, JobStatus, ResourceType


@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    return client


@pytest.fixture
def mock_frames(tmp_path):
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    frame_paths = []
    
    # Create 3 dummy image files
    for i in range(3):
        path = frames_dir / f"frame_{i:03d}.jpg"
        path.write_bytes(b"dummy_image_data")
        frame_paths.append(str(path))
        
    return frame_paths


@pytest.mark.asyncio
async def test_skip_if_no_frames(mock_llm_client) -> None:
    """Agent should do nothing if no frames were saved."""
    kg = KnowledgeGraph.create_for_url("https://instagram.com/reel/abc")
    kg.metadata.saved_frame_paths = []

    agent = VisualResourceExtractorAgent(mock_llm_client)
    result = await agent.process(kg)

    assert len(result.resources) == 0
    assert mock_llm_client.complete_json.call_count == 0


@pytest.mark.asyncio
async def test_vision_detects_youtube_and_searches(mock_llm_client, mock_frames) -> None:
    """Vision detects a YouTube video, then searches for it and adds it."""
    kg = KnowledgeGraph.create_for_url("https://instagram.com/reel/abc")
    kg.metadata.saved_frame_paths = mock_frames

    # Mock the LLM to say it found a YouTube video on the first frame, and nothing on others
    async def mock_complete_json(*args, **kwargs):
        # We can just return the same result for all frames since unique_refs will deduplicate it
        return {
            "is_youtube": True,
            "title": "Learn FastAPI in 10 Minutes",
            "channel": "Tech Channel",
            "url": ""
        }

    mock_llm_client.complete_json = AsyncMock(side_effect=mock_complete_json)

    # Mock httpx.AsyncClient.get to simulate YouTube search results
    html = 'Some HTML... /watch?v=dQw4w9WgXcQ ... more html'
    
    # We patch httpx.AsyncClient so when it's used as a context manager, it returns our mock
    mock_response = AsyncMock(spec=Response)
    mock_response.status_code = 200
    mock_response.text = html

    mock_httpx_client = AsyncMock()
    mock_httpx_client.get.return_value = mock_response

    class MockAsyncClientContextManager:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return mock_httpx_client
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    agent = VisualResourceExtractorAgent(mock_llm_client)

    with patch("httpx.AsyncClient", MockAsyncClientContextManager):
        result = await agent.process(kg)

    # It should have called the LLM for the frames
    assert mock_llm_client.complete_json.call_count > 0

    # It should have added the resource
    assert len(result.resources) == 1
    res = result.resources[0]
    
    assert res.name == "Learn FastAPI in 10 Minutes"
    assert res.resource_type == ResourceType.WEBSITE
    assert res.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert res.description == "YouTube video by Tech Channel"
    assert "youtube" in res.tags


@pytest.mark.asyncio
async def test_vision_detects_youtube_with_url(mock_llm_client, mock_frames) -> None:
    """Vision detects a YouTube video and extracts the URL directly."""
    kg = KnowledgeGraph.create_for_url("https://instagram.com/reel/abc")
    kg.metadata.saved_frame_paths = mock_frames

    async def mock_complete_json(*args, **kwargs):
        return {
            "is_youtube": True,
            "title": "Direct URL Video",
            "channel": "Awesome Creator",
            "url": "https://youtu.be/12345678901"
        }

    mock_llm_client.complete_json = AsyncMock(side_effect=mock_complete_json)

    agent = VisualResourceExtractorAgent(mock_llm_client)
    result = await agent.process(kg)

    assert len(result.resources) == 1
    res = result.resources[0]
    
    assert res.name == "Direct URL Video"
    assert res.resource_type == ResourceType.WEBSITE
    assert res.url == "https://youtu.be/12345678901"


@pytest.mark.asyncio
async def test_vision_no_youtube_detected(mock_llm_client, mock_frames) -> None:
    """Vision analyzes frames but doesn't find any YouTube content."""
    kg = KnowledgeGraph.create_for_url("https://instagram.com/reel/abc")
    kg.metadata.saved_frame_paths = mock_frames

    async def mock_complete_json(*args, **kwargs):
        return {
            "is_youtube": False,
            "title": "",
            "channel": "",
            "url": ""
        }

    mock_llm_client.complete_json = AsyncMock(side_effect=mock_complete_json)

    agent = VisualResourceExtractorAgent(mock_llm_client)
    result = await agent.process(kg)

    assert len(result.resources) == 0
