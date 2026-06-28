"""
KnowledgeFlow — File Cache

Handles caching of intermediate pipeline files (downloads, transcripts, OCR output).
Cleans up after successful processing runs if KEEP_CACHE is False.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import aiofiles
import structlog

from config import settings, BASE_DIR
from core.exceptions import CacheError

log = structlog.get_logger(__name__)


class FileCache:
    """
    Manages filesystem-based cache.
    Paths are structured as: {cache_dir}/{job_id}/...
    """

    def __init__(self, cache_dir_name: str | None = None) -> None:
        cache_dir_str = cache_dir_name or settings.cache_dir
        # Resolve cache dir relative to project root if relative
        cache_path = Path(cache_dir_str)
        if not cache_path.is_absolute():
            self.cache_dir = BASE_DIR / cache_path
        else:
            self.cache_dir = cache_path

        self._log = log.bind(component="FileCache", cache_dir=str(self.cache_dir))
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Create the cache root directory if it doesn't exist."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self._log.exception("cache.init_failed")
            raise CacheError(f"Failed to initialize cache directory: {exc}") from exc

    def get_job_dir(self, job_id: str) -> Path:
        """Get the cache sub-directory for a specific job."""
        job_dir = self.cache_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    async def save_text(self, job_id: str, filename: str, content: str) -> Path:
        """Save a text file in the job's cache directory."""
        path = self.get_job_dir(job_id) / filename
        try:
            async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                await f.write(content)
            return path
        except Exception as exc:
            self._log.error("cache.save_text_failed", job_id=job_id, filename=filename, error=str(exc))
            raise CacheError(f"Failed to write text cache file '{filename}': {exc}") from exc

    async def read_text(self, job_id: str, filename: str) -> str:
        """Read a text file from the job's cache directory."""
        path = self.get_job_dir(job_id) / filename
        if not path.exists():
            raise FileNotFoundError(f"Cache file not found: {path}")
        try:
            async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
                return await f.read()
        except Exception as exc:
            self._log.error("cache.read_text_failed", job_id=job_id, filename=filename, error=str(exc))
            raise CacheError(f"Failed to read text cache file '{filename}': {exc}") from exc

    async def save_json(self, job_id: str, filename: str, data: Any) -> Path:
        """Save JSON-serializable data to a file."""
        return await self.save_text(job_id, filename, json.dumps(data, indent=2, ensure_ascii=False))

    async def read_json(self, job_id: str, filename: str) -> Any:
        """Read and parse JSON from a file."""
        text = await self.read_text(job_id, filename)
        try:
            return json.loads(text)
        except Exception as exc:
            self._log.error("cache.parse_json_failed", job_id=job_id, filename=filename, error=str(exc))
            raise CacheError(f"Failed to parse JSON cache file '{filename}': {exc}") from exc

    def cleanup_job(self, job_id: str) -> None:
        """Remove the job cache directory if keep_cache settings are disabled."""
        if settings.keep_cache:
            self._log.debug("cache.cleanup_skipped", job_id=job_id, reason="keep_cache is True")
            return

        job_dir = self.cache_dir / job_id
        if job_dir.exists() and job_dir.is_dir():
            try:
                shutil.rmtree(job_dir)
                self._log.debug("cache.cleanup_success", job_id=job_id)
            except Exception as exc:
                self._log.warning("cache.cleanup_failed", job_id=job_id, error=str(exc))
