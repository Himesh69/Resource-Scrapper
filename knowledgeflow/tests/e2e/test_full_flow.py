"""
End-to-end test skeleton for the full KnowledgeFlow pipeline.

These tests require real credentials (OPENROUTER_API_KEY, NOTION_TOKEN, etc.)
and network access. They are excluded from CI and meant for manual verification.

Run with:
    TELEGRAM_BOT_TOKEN=xxx OPENROUTER_API_KEY=xxx NOTION_TOKEN=xxx \\
    pytest tests/e2e/test_full_flow.py -v -s
"""
from __future__ import annotations

import os

import pytest

# Skip all tests in this module if the required env vars are missing
pytestmark = pytest.mark.skipif(
    not all([
        os.getenv("OPENROUTER_API_KEY"),
        os.getenv("NOTION_TOKEN"),
    ]),
    reason="E2E tests require OPENROUTER_API_KEY and NOTION_TOKEN env vars"
)


@pytest.mark.asyncio
async def test_youtube_url_full_pipeline() -> None:
    """
    Full pipeline run: YouTube URL → Pipeline → KnowledgeGraph check.
    Does NOT sync to Notion (to avoid polluting your workspace during testing).
    """
    from cache.file_cache import FileCache
    from core.knowledge_graph import KnowledgeGraph, JobStatus
    from core.pipeline import Pipeline
    from llm.client import LLMClient

    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # famous short video for testing

    cache = FileCache()
    client = LLMClient()
    pipeline = Pipeline(client, cache)

    kg = KnowledgeGraph.create_for_url(url)
    result = await pipeline.run(kg)

    # The pipeline should either complete or partially succeed
    assert result.metadata.status in (JobStatus.COMPLETED, JobStatus.PARTIAL)
    # Should have extracted a title from metadata
    assert result.source.title
    # Should have a summary
    assert result.source.summary
    # Should have at least one topic
    assert len(result.topics) >= 1

    # Cleanup
    cache.cleanup_job(result.metadata.job_id)


@pytest.mark.asyncio
async def test_instagram_reel_full_pipeline() -> None:
    """
    Full pipeline run with an Instagram Reel URL.
    This may fail if the reel is private or geo-restricted.
    """
    from cache.file_cache import FileCache
    from core.knowledge_graph import KnowledgeGraph, JobStatus
    from core.pipeline import Pipeline
    from llm.client import LLMClient

    url = "https://www.instagram.com/reel/C1234example/"  # replace with a real public reel URL

    cache = FileCache()
    client = LLMClient()
    pipeline = Pipeline(client, cache)

    kg = KnowledgeGraph.create_for_url(url)
    result = await pipeline.run(kg)

    # Even if download fails, the pipeline should handle it gracefully
    assert result.metadata.status in (JobStatus.COMPLETED, JobStatus.PARTIAL, JobStatus.FAILED)
    # If it failed, check that warnings were logged
    if result.metadata.status == JobStatus.FAILED:
        assert len(result.metadata.warnings) >= 1

    cache.cleanup_job(result.metadata.job_id)
