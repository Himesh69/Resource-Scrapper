"""
KnowledgeFlow — Media Downloader Agent

Downloads media (Instagram Reels, YouTube Videos, PDFs, Images) via URL.
Integrates yt-dlp for video platforms and httpx for direct file downloads.
Provides a caption/text-only fallback if the download fails.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import structlog
import yt_dlp

from agents.base import BaseAgent
from cache.file_cache import FileCache
from core.exceptions import DownloadError, PrivateContentError
from core.knowledge_graph import KnowledgeGraph, Platform, ContentType

log = structlog.get_logger(__name__)


class DownloaderAgent(BaseAgent):
    """
    Agent responsible for downloading content from the provided URL.
    Saves media files to the file cache directory.
    """

    def __init__(self, cache: FileCache) -> None:
        super().__init__(name="DownloaderAgent")
        self.cache = cache

    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        url = kg.input_url
        platform = kg.source.platform
        job_id = kg.metadata.job_id

        self._log.info("download.start", url=url, platform=platform)

        # 1. Skip if platform is TEXT or UNKNOWN
        if platform in (Platform.TEXT, Platform.UNKNOWN):
            self._log.info("download.skipped", reason=f"Platform is {platform}")
            return kg

        # 2. Determine target filename
        extension = self._get_extension(platform, url)
        filename = f"media.{extension}"
        job_dir = self.cache.get_job_dir(job_id)
        output_path = job_dir / filename

        try:
            if platform in (Platform.YOUTUBE, Platform.INSTAGRAM):
                # Download video/audio via yt-dlp
                await self._download_video(url, output_path)
            else:
                # Direct download via HTTP (PDF, Image, etc.)
                await self._download_file(url, output_path)

            kg.metadata.media_file_path = str(output_path)
            self._log.info("download.success", path=str(output_path))
        except Exception as exc:
            self._log.warning("download.failed", error=str(exc))
            kg.add_warning(
                f"Downloader failed: {exc}. "
                f"Pipeline will proceed with caption/text-only fallback mode."
            )
            # Do not raise an exception; allow processing to continue as a fallback
            kg.metadata.media_file_path = ""

        return kg

    def _get_extension(self, platform: Platform, url: str) -> str:
        """Resolve expected file extension based on platform/URL."""
        if platform == Platform.PDF:
            return "pdf"
        elif platform == Platform.IMAGE:
            # Try to guess extension from URL
            path_lower = url.lower()
            for ext in ("png", "jpg", "jpeg", "webp", "gif"):
                if f".{ext}" in path_lower:
                    return ext
            return "png"
        else:
            # Default to mp4 for video/audio downloads
            return "mp4"

    async def _download_video(self, url: str, output_path: Path) -> None:
        """Download video/audio using yt-dlp in a background thread."""
        from config import app_config
        # yt-dlp configurations
        ydl_opts = {
            # Low resolution capped at 360p or 480p is fast and perfectly fine for OCR + transcription
            "format": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best",
            "outtmpl": f"{output_path.with_suffix('')}.%(ext)s",  # Ensure yt-dlp appends the extension properly
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
        }
        
        cookie_file = app_config.get("ytdlp", {}).get("cookies_file", "")
        browser = app_config.get("ytdlp", {}).get("cookies_from_browser", "")
        
        if cookie_file and Path(cookie_file).exists():
            ydl_opts["cookiefile"] = cookie_file
        elif browser:
            ydl_opts["cookiesfrombrowser"] = (browser,)

        # Run yt-dlp in a separate thread to prevent event loop blocking
        def _run_ytdl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        try:
            await asyncio.to_thread(_run_ytdl)
            # Find the downloaded file (it starts with the stem and has an extension)
            # yt-dlp might download as .mkv, .webm, or .mp4 depending on format
            downloaded_files = list(output_path.parent.glob(f"{output_path.stem}.*"))
            for f in downloaded_files:
                if f != output_path and not f.name.endswith(".part"):
                    f.rename(output_path)
        except Exception as exc:
            # Check for common private/auth errors
            exc_str = str(exc).lower()
            if "private" in exc_str or "login" in exc_str or "sign in" in exc_str or "confirm your age" in exc_str:
                raise PrivateContentError(url) from exc
            raise DownloadError(f"yt-dlp download failed: {exc}") from exc

    async def _download_file(self, url: str, output_path: Path) -> None:
        """Download standard files asynchronously using HTTPX."""
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Write to cached file asynchronously
                import aiofiles
                async with aiofiles.open(output_path, "wb") as f:
                    await f.write(response.content)
        except Exception as exc:
            raise DownloadError(f"Direct file download failed: {exc}") from exc
