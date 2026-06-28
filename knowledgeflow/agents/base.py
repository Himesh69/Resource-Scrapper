"""
KnowledgeFlow — Base Agent Abstract Class

All processing agents subclass BaseAgent.
Provides built-in timing, structured logging, exception capturing, and warnings propagation.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import structlog

from core.exceptions import AgentError
from core.knowledge_graph import KnowledgeGraph, AgentStatus

log = structlog.get_logger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all processing agents.
    
    Subclasses must implement:
        _process_impl(kg: KnowledgeGraph) -> KnowledgeGraph
    """

    def __init__(self, name: str | None = None) -> None:
        self.name = name or self.__class__.__name__
        self._log = log.bind(agent=self.name)

    async def process(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        """
        Run the agent's processing logic.
        Wraps execution with telemetry, logging, and error boundaries.
        """
        started_at = datetime.now(timezone.utc)
        kg.update_agent_log(
            agent_name=self.name,
            status=AgentStatus.RUNNING,
            started_at=started_at
        )
        self._log.info("agent.started")

        try:
            kg = await self._process_impl(kg)
            finished_at = datetime.now(timezone.utc)
            kg.update_agent_log(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                finished_at=finished_at
            )
            self._log.info("agent.success")
        except AgentError as exc:
            # Caught agent errors (recoverable by default)
            finished_at = datetime.now(timezone.utc)
            status = AgentStatus.FAILED if exc.recoverable else AgentStatus.ERROR
            error_msg = str(exc)
            
            kg.update_agent_log(
                agent_name=self.name,
                status=status,
                error=error_msg,
                finished_at=finished_at
            )
            kg.add_warning(f"Agent {self.name} failed: {error_msg}")
            self._log.error("agent.failed", error=error_msg, recoverable=exc.recoverable)
            
            if not exc.recoverable:
                raise exc
        except Exception as exc:
            # Unhandled errors (treated as non-recoverable agent errors)
            finished_at = datetime.now(timezone.utc)
            error_msg = f"Unexpected error: {str(exc)}"
            
            kg.update_agent_log(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                error=error_msg,
                finished_at=finished_at
            )
            kg.add_warning(f"Agent {self.name} encountered unexpected error: {error_msg}")
            self._log.exception("agent.exception", error=error_msg)
            
            # Re-raise as AgentError to terminate the pipeline if unexpected
            raise AgentError(self.name, error_msg, recoverable=False) from exc

        return kg

    @abstractmethod
    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        """Subclasses implement this method with their core business logic."""
        pass
