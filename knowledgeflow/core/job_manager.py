"""
KnowledgeFlow — Job Manager

Manages job submission, concurrent execution limits (using asyncio.Semaphore),
tracking active jobs, and handling job cancellations.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, Optional

import structlog

from config import settings
from core.knowledge_graph import KnowledgeGraph, JobStatus

log = structlog.get_logger(__name__)


class JobEntry:
    """Represents a job in the manager's registry."""

    def __init__(
        self,
        job_id: str,
        url: str,
        telegram_user_id: Optional[int],
        task: asyncio.Task[Any]
    ) -> None:
        self.job_id = job_id
        self.url = url
        self.telegram_user_id = telegram_user_id
        self.task = task
        self.submitted_at = datetime.now(timezone.utc)
        self.status = JobStatus.PENDING


class JobManager:
    """
    Registry and queue coordinator for managing processing jobs with cancellation and concurrency limits.
    """

    def __init__(self, max_concurrent: int | None = None) -> None:
        limit = max_concurrent or settings.max_concurrent_jobs
        self._semaphore = asyncio.Semaphore(limit)
        self._registry: Dict[str, JobEntry] = {}
        self._log = log.bind(component="JobManager", max_concurrent=limit)

    async def run_job_with_semaphore(
        self,
        job_id: str,
        coro: Coroutine[Any, Any, KnowledgeGraph],
        on_complete: Callable[[KnowledgeGraph], Coroutine[Any, Any, None]]
    ) -> None:
        """Run a job coroutine under the semaphore lock."""
        entry = self._registry.get(job_id)
        if not entry:
            self._log.warning("job.run.missing_entry", job_id=job_id)
            return

        self._log.debug("job.queue.waiting", job_id=job_id, url=entry.url)
        async with self._semaphore:
            entry.status = JobStatus.PROCESSING
            self._log.info("job.started", job_id=job_id, url=entry.url)
            
            kg = None
            try:
                kg = await coro
                entry.status = kg.metadata.status
            except asyncio.CancelledError:
                self._log.info("job.cancelled_mid_execution", job_id=job_id)
                entry.status = JobStatus.FAILED
                raise
            except Exception as exc:
                self._log.error("job.execution_failed", job_id=job_id, error=str(exc))
                entry.status = JobStatus.FAILED
            finally:
                # Always run completion callback if we got a KG
                if kg:
                    try:
                        await on_complete(kg)
                    except Exception as callback_exc:
                        self._log.exception("job.callback_failed", job_id=job_id, error=str(callback_exc))
                
                # Cleanup registry
                if job_id in self._registry:
                    del self._registry[job_id]
                self._log.info("job.finished_and_cleared", job_id=job_id, status=entry.status.value)

    def submit(
        self,
        job_id: str,
        url: str,
        telegram_user_id: Optional[int],
        job_coro: Coroutine[Any, Any, KnowledgeGraph],
        on_complete: Callable[[KnowledgeGraph], Coroutine[Any, Any, None]]
    ) -> str:
        """
        Submit a new job to the manager. Creates an asyncio.Task and starts queueing.
        """
        # Create wrap task
        loop = asyncio.get_running_loop()
        task = loop.create_task(
            self.run_job_with_semaphore(job_id, job_coro, on_complete)
        )

        entry = JobEntry(
            job_id=job_id,
            url=url,
            telegram_user_id=telegram_user_id,
            task=task
        )
        self._registry[job_id] = entry
        self._log.info("job.submitted", job_id=job_id, url=url, user_id=telegram_user_id)
        return job_id

    def cancel(self, job_id: str) -> bool:
        """
        Cancel a running or pending job by its ID.
        Returns True if the job was successfully cancelled, False otherwise.
        """
        entry = self._registry.get(job_id)
        if not entry:
            self._log.warning("job.cancel.not_found", job_id=job_id)
            return False

        self._log.info("job.cancelling", job_id=job_id, url=entry.url)
        entry.task.cancel()
        
        # Remove from registry
        if job_id in self._registry:
            del self._registry[job_id]
        return True

    def get_active_jobs(self) -> list[dict[str, Any]]:
        """Return a list of all active/pending job info."""
        return [
            {
                "job_id": entry.job_id,
                "url": entry.url,
                "user_id": entry.telegram_user_id,
                "status": entry.status.value,
                "duration_seconds": int((datetime.now(timezone.utc) - entry.submitted_at).total_seconds())
            }
            for entry in self._registry.values()
        ]
