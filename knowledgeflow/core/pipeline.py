"""
KnowledgeFlow — Pipeline Orchestrator

Sequences the execution of all processing agents, passes the KnowledgeGraph
between them, handles recoverable errors, and resolves the final job status.

Pipeline modes:
  FULL PATH  — Download → OCR → Transcript → VisualResource → KnowledgeBuilder → Resource → Enrich → Categorize → Dedup
  FAST PATH  — Triggered when EarlyResourceScanAgent finds URLs in description/pinned comment.
               Skips Download, OCR, Transcript, VisualResource to save time and credits.
"""
from __future__ import annotations

from datetime import datetime, timezone
import structlog

from agents.base import BaseAgent
from agents.downloader import DownloaderAgent
from agents.metadata import MetadataAgent
from agents.ocr import OCRAgent
from agents.transcript import TranscriptAgent
from agents.knowledge_builder import KnowledgeBuilderAgent
from agents.resource_extractor import ResourceExtractorAgent
from agents.enrichment import EnrichmentAgent
from agents.categorization import CategorizationAgent
from agents.deduplication import DeduplicationAgent
from agents.visual_resource_extractor import VisualResourceExtractorAgent
from agents.early_resource_scan import EarlyResourceScanAgent

from cache.file_cache import FileCache
from core.exceptions import AgentError
from core.knowledge_graph import KnowledgeGraph, JobStatus, AgentStatus
from llm.client import LLMClient

log = structlog.get_logger(__name__)


class Pipeline:
    """
    Main pipeline orchestrator that processes a KnowledgeGraph through all agent steps.

    After MetadataAgent + EarlyResourceScanAgent, the pipeline decides:
      - FAST PATH: resources found in text → skip video processing
      - FULL PATH: no resources found → full video analysis
    """

    def __init__(self, client: LLMClient, cache: FileCache) -> None:
        self.client = client
        self.cache = cache
        self._log = log.bind(component="Pipeline")

        # ── Phase 1: Always run (lightweight, no LLM, no download) ──
        self.phase1_agents: list[BaseAgent] = [
            MetadataAgent(),
            EarlyResourceScanAgent(),
        ]

        # ── Phase 2a: FULL PATH — expensive video processing ──
        self.full_path_agents: list[BaseAgent] = [
            DownloaderAgent(self.cache),
            OCRAgent(),
            TranscriptAgent(self.client),
            VisualResourceExtractorAgent(self.client),
        ]

        # ── Phase 2b: FAST PATH — no video processing needed ──
        # (empty — we skip straight to Phase 3)

        # ── Phase 3: Always run — LLM extraction & finalization ──
        self.phase3_agents: list[BaseAgent] = [
            KnowledgeBuilderAgent(self.client),
            ResourceExtractorAgent(self.client),
            EnrichmentAgent(self.client),
            CategorizationAgent(self.client),
            DeduplicationAgent(self.client),
        ]

    async def run(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        """
        Run the pipeline over the KnowledgeGraph.
        """
        kg.metadata.status = JobStatus.PROCESSING
        self._log.info("pipeline.start", job_id=kg.metadata.job_id, url=kg.input_url)

        has_failures = False
        aborted = False

        # ── Phase 1: Metadata + Early Resource Scan ──
        for agent in self.phase1_agents:
            kg, agent_failed, agent_aborted = await self._run_agent(agent, kg)
            if agent_failed:
                has_failures = True
            if agent_aborted:
                aborted = True
                break

        if not aborted:
            # ── Decide path ──
            if kg.metadata.early_resources_found:
                self._log.info(
                    "pipeline.fast_path",
                    reason="Resources found in description/pinned comment — skipping video processing",
                )
                # FAST PATH: skip download, OCR, transcript, visual extraction
                phase2_agents = []
            else:
                self._log.info("pipeline.full_path", reason="No early resources — running full video analysis")
                phase2_agents = self.full_path_agents

            # ── Phase 2: Conditional video processing ──
            for agent in phase2_agents:
                kg, agent_failed, agent_aborted = await self._run_agent(agent, kg)
                if agent_failed:
                    has_failures = True
                if agent_aborted:
                    aborted = True
                    break

        if not aborted:
            # ── Phase 3: LLM extraction & finalization ──
            for agent in self.phase3_agents:
                kg, agent_failed, agent_aborted = await self._run_agent(agent, kg)
                if agent_failed:
                    has_failures = True
                if agent_aborted:
                    aborted = True
                    break

        # ── Resolve final status ──
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

        self._log.info(
            "pipeline.finished",
            job_id=kg.metadata.job_id,
            status=kg.metadata.status.value,
            warnings_count=len(kg.metadata.warnings),
        )
        return kg

    async def _run_agent(
        self, agent: BaseAgent, kg: KnowledgeGraph
    ) -> tuple[KnowledgeGraph, bool, bool]:
        """
        Run a single agent, returning (updated_kg, had_failure, was_aborted).
        """
        self._log.debug("pipeline.executing_agent", agent=agent.name)
        failed = False
        aborted = False

        try:
            kg = await agent.process(kg)
            log_entry = next(
                (l for l in kg.metadata.agent_logs if l.agent_name == agent.name), None
            )
            if log_entry and log_entry.status in (AgentStatus.FAILED, AgentStatus.ERROR):
                failed = True
        except AgentError as exc:
            failed = True
            if not exc.recoverable:
                self._log.error("pipeline.aborted.agent_error", agent=agent.name, error=str(exc))
                aborted = True
        except Exception as exc:
            failed = True
            self._log.exception("pipeline.aborted.unexpected_error", agent=agent.name, error=str(exc))
            aborted = True

        return kg, failed, aborted
