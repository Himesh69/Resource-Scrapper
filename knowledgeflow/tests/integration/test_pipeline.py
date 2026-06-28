"""
Integration tests for the Pipeline Orchestrator.

Uses mock agents to verify the pipeline's sequencing, error handling,
and final status resolution without actually calling external APIs.
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from core.exceptions import AgentError
from core.knowledge_graph import KnowledgeGraph, JobStatus, AgentStatus
from agents.base import BaseAgent


# ── Stub Agents ──────────────────────────────────────────────────────────────

class SuccessAgent(BaseAgent):
    """Agent that always succeeds and adds a topic."""
    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        kg.topics.append(f"topic_from_{self.name}")
        return kg


class RecoverableFailAgent(BaseAgent):
    """Agent that raises a recoverable error."""
    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        raise AgentError(self.name, "Recoverable test failure", recoverable=True)


class FatalFailAgent(BaseAgent):
    """Agent that raises a non-recoverable error."""
    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        raise AgentError(self.name, "Fatal test failure", recoverable=False)


# ── Minimal Pipeline Runner ─────────────────────────────────────────────────

async def _run_agents(agents: list[BaseAgent], kg: KnowledgeGraph) -> KnowledgeGraph:
    """
    Simplified pipeline runner that mirrors core/pipeline.py logic
    but uses injected agents so we don't need LLMClient / FileCache.
    """
    from datetime import datetime, timezone

    kg.metadata.status = JobStatus.PROCESSING
    has_failures = False
    aborted = False

    for agent in agents:
        try:
            kg = await agent.process(kg)
            log_entry = next(
                (l for l in kg.metadata.agent_logs if l.agent_name == agent.name), None
            )
            if log_entry and log_entry.status in (AgentStatus.FAILED, AgentStatus.ERROR):
                has_failures = True
        except AgentError as exc:
            has_failures = True
            if not exc.recoverable:
                aborted = True
                break
        except Exception:
            has_failures = True
            aborted = True
            break

    kg.metadata.finished_at = datetime.now(timezone.utc)

    if aborted:
        kg.metadata.status = JobStatus.FAILED
    elif has_failures:
        if kg.has_useful_content():
            kg.metadata.status = JobStatus.PARTIAL
        else:
            kg.metadata.status = JobStatus.FAILED
    else:
        kg.metadata.status = JobStatus.COMPLETED

    return kg


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_all_success() -> None:
    """All agents succeed → status should be COMPLETED."""
    agents = [
        SuccessAgent(name="AgentA"),
        SuccessAgent(name="AgentB"),
        SuccessAgent(name="AgentC"),
    ]
    kg = KnowledgeGraph.create_for_url("https://youtube.com/watch?v=test")
    result = await _run_agents(agents, kg)

    assert result.metadata.status == JobStatus.COMPLETED
    assert "topic_from_AgentA" in result.topics
    assert "topic_from_AgentB" in result.topics
    assert "topic_from_AgentC" in result.topics
    assert len(result.metadata.agent_logs) == 3
    assert all(l.status == AgentStatus.SUCCESS for l in result.metadata.agent_logs)


@pytest.mark.asyncio
async def test_pipeline_recoverable_failure_with_content() -> None:
    """
    A recoverable agent failure in the middle → pipeline continues.
    Because we set title + SuccessAgent adds topics, final status should be PARTIAL.
    """
    agents = [
        SuccessAgent(name="AgentA"),
        RecoverableFailAgent(name="AgentB"),
        SuccessAgent(name="AgentC"),
    ]
    kg = KnowledgeGraph.create_for_url("https://youtube.com/watch?v=test")
    kg.source.title = "Test Video"  # ensure has_useful_content() is True
    result = await _run_agents(agents, kg)

    assert result.metadata.status == JobStatus.PARTIAL
    # AgentA and AgentC should have run, AgentB logged a failure
    assert "topic_from_AgentA" in result.topics
    assert "topic_from_AgentC" in result.topics
    assert len(result.metadata.warnings) >= 1


@pytest.mark.asyncio
async def test_pipeline_fatal_failure_aborts() -> None:
    """
    A non-recoverable agent failure should abort the pipeline.
    AgentC should never execute.
    """
    agents = [
        SuccessAgent(name="AgentA"),
        FatalFailAgent(name="AgentB"),
        SuccessAgent(name="AgentC"),
    ]
    kg = KnowledgeGraph.create_for_url("https://youtube.com/watch?v=test")
    result = await _run_agents(agents, kg)

    assert result.metadata.status == JobStatus.FAILED
    assert "topic_from_AgentA" in result.topics
    assert "topic_from_AgentC" not in result.topics


@pytest.mark.asyncio
async def test_pipeline_all_fail_no_content() -> None:
    """All agents fail and no useful content → status should be FAILED."""
    agents = [
        RecoverableFailAgent(name="AgentA"),
        RecoverableFailAgent(name="AgentB"),
    ]
    kg = KnowledgeGraph.create_for_url("https://youtube.com/watch?v=test")
    result = await _run_agents(agents, kg)

    assert result.metadata.status == JobStatus.FAILED
    assert not result.has_useful_content()
