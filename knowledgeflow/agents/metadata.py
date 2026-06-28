"""
KnowledgeFlow — Metadata Agent

Deterministically extracts metadata for various platforms (YouTube, Instagram, PDFs, etc.).
No LLM calls — uses yt-dlp for video platforms and simple file readers for local files.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import structlog
import yt_dlp

from agents.base import BaseAgent
from core.exceptions import AgentError
from core.knowledge_graph import KnowledgeGraph, Platform, ContentType, Source

log = structlog.get_logger(__name__)


class MetadataAgent(BaseAgent):
    """
    Agent responsible for extracting platform-specific metadata (title, author, date, etc.).
    """

    def __init__(self) -> None:
        super().__init__(name="MetadataAgent")

    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        platform = kg.source.platform
        url = kg.input_url
        self._log.info("metadata.extract", url=url, platform=platform)

        # Assign inputs to metadata if not already done
        if not kg.source.url:
            kg.source.url = url
        if kg.source.platform == Platform.UNKNOWN:
            # We import and run detection if it wasn't populated
            from utils.url_parser import detect_platform, detect_content_type
            kg.source.platform = detect_platform(url)
            kg.source.content_type = detect_content_type(url)

        try:
            if platform in (Platform.YOUTUBE, Platform.INSTAGRAM):
                kg = await self._extract_video_metadata(kg)
            elif platform == Platform.PDF:
                kg = await self._extract_pdf_metadata(kg)
            elif platform == Platform.IMAGE:
                kg = await self._extract_image_metadata(kg)
            elif platform == Platform.TEXT:
                # Text input has no external url metadata, but we can set default title
                if not kg.source.title:
                    kg.source.title = "Text Snippet"
                kg.source.description = kg.input_url
            else:
                self._log.info("metadata.skipped", reason=f"Unsupported platform {platform}")
        except Exception as exc:
            # Metadata failures are recoverable. Add a warning and continue.
            self._log.warning("metadata.failed", error=str(exc))
            kg.add_warning(f"MetadataAgent failed: {exc}")

        return kg

    async def _extract_video_metadata(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        """Extract metadata for YouTube / Instagram using yt-dlp."""
        url = kg.input_url
        
        def _get_info():
            from config import app_config
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "getcomments": True,  # Fetch comments to capture pinned/top comment
            }
            
            cookie_file = app_config.get("ytdlp", {}).get("cookies_file", "")
            browser = app_config.get("ytdlp", {}).get("cookies_from_browser", "")
            
            if cookie_file and Path(cookie_file).exists():
                ydl_opts["cookiefile"] = cookie_file
            elif browser:
                ydl_opts["cookiesfrombrowser"] = (browser,)
                
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            info = await asyncio.to_thread(_get_info)
            if not info:
                return kg

            kg.source.title = info.get("title") or info.get("description", "")[:60] or "Video Content"
            kg.source.description = info.get("description") or ""
            kg.source.creator_name = info.get("uploader") or info.get("channel") or ""
            kg.source.creator_username = info.get("uploader_id") or ""
            kg.source.duration_seconds = info.get("duration")
            kg.source.thumbnail_url = info.get("thumbnail") or ""

            # Try parsing upload date
            upload_date_str = info.get("upload_date")  # YYYYMMDD
            if upload_date_str:
                try:
                    dt = datetime.strptime(upload_date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
                    kg.source.published_at = dt
                except ValueError:
                    pass

            # Extract pinned comment or top creator comment
            comments = info.get("comments") or []
            uploader_id = info.get("uploader_id") or ""
            pinned_comment = ""
            creator_comment = ""
            first_comment = ""

            for comment in comments:
                text = (comment.get("text") or "").strip()
                if not text:
                    continue

                if not first_comment:
                    first_comment = text

                # Prioritize pinned comments
                if comment.get("is_pinned"):
                    pinned_comment = text
                    break

                # Track first comment by the creator
                if not creator_comment:
                    comment_author = comment.get("author_id") or comment.get("author") or ""
                    if uploader_id and comment_author and comment_author == uploader_id:
                        creator_comment = text

            # Priority: pinned > creator's own comment > first comment
            kg.source.pinned_comment = pinned_comment or creator_comment or first_comment

            if kg.source.pinned_comment:
                self._log.info(
                    "metadata.pinned_comment_extracted",
                    char_count=len(kg.source.pinned_comment),
                )

            self._log.info(
                "metadata.extracted_video",
                title=kg.source.title,
                uploader=kg.source.creator_name,
            )
        except Exception as exc:
            raise AgentError(
                self.name,
                f"Failed to extract video metadata via yt-dlp: {exc}",
                recoverable=True
            ) from exc

        return kg

    async def _extract_pdf_metadata(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        """Extract metadata from PDF file."""
        media_path = kg.metadata.media_file_path
        if not media_path or not Path(media_path).exists():
            self._log.debug("metadata.pdf.no_file")
            return kg

        path = Path(media_path)
        kg.source.title = path.stem.replace("_", " ").replace("-", " ").title()
        
        # We can extract pages if pypdf is installed, otherwise default to 1 page
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            num_pages = len(reader.pages)
            kg.source.description = f"PDF Document: {path.name} ({num_pages} pages)"
            self._log.info("metadata.extracted_pdf", title=kg.source.title, pages=num_pages)
        except ImportError:
            self._log.debug("metadata.pdf.pypdf_missing")
            kg.source.description = f"PDF Document: {path.name}"
        except Exception as exc:
            self._log.warning("metadata.pdf.parse_error", error=str(exc))
            kg.source.description = f"PDF Document: {path.name}"

        return kg

    async def _extract_image_metadata(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        """Extract metadata from image file."""
        media_path = kg.metadata.media_file_path
        if not media_path or not Path(media_path).exists():
            return kg

        path = Path(media_path)
        kg.source.title = path.stem.replace("_", " ").replace("-", " ").title()
        kg.source.description = f"Image File: {path.name}"
        self._log.info("metadata.extracted_image", title=kg.source.title)
        return kg
