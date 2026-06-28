"""
KnowledgeFlow — Visual Resource Extractor Agent

Analyzes saved video frames to detect YouTube video thumbnails and other
visual references. Uses LLM vision to identify YouTube content, then
searches for the actual video URL via YouTube search.

Pipeline position: runs after OCR (which saves frames) and before ResourceExtractor.
"""
from __future__ import annotations

import base64
import asyncio
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from agents.base import BaseAgent
from core.exceptions import AgentError
from core.knowledge_graph import KnowledgeGraph, Resource, ResourceType
from llm.client import LLMClient
from config import app_config

log = structlog.get_logger(__name__)

# Maximum number of frames to analyze with vision LLM (cost control)
_MAX_VISION_FRAMES = 5


class VisualResourceExtractorAgent(BaseAgent):
    """
    Agent that uses LLM vision to detect YouTube thumbnails and other
    visual resource references in video frames.
    """

    def __init__(self, client: LLMClient) -> None:
        super().__init__(name="VisualResourceExtractorAgent")
        self.client = client

    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        frame_paths = kg.metadata.saved_frame_paths
        if not frame_paths:
            self._log.info("visual_resource.skipped", reason="No saved frames available")
            return kg

        self._log.info("visual_resource.start", total_frames=len(frame_paths))

        # Select evenly-spaced subset of frames to analyze (cost control)
        selected = self._select_frames(frame_paths, _MAX_VISION_FRAMES)
        self._log.info("visual_resource.frames_selected", count=len(selected))

        # Analyze frames sequentially with a delay to respect rate limits
        results = []
        for path in selected:
            try:
                res = await self._analyze_frame(path)
                results.append(res)
            except Exception as exc:
                results.append(exc)
            # Short sleep between frames to stay well under Google AI Studio's RPM limits
            await asyncio.sleep(1.2)

        youtube_refs: list[dict] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._log.warning(
                    "visual_resource.frame_analysis_failed",
                    frame=selected[i],
                    error=str(result),
                )
                continue
            if result and result.get("is_youtube") and result.get("videos"):
                youtube_refs.extend(result.get("videos"))

        if not youtube_refs:
            self._log.info("visual_resource.no_youtube_detected")
            return kg

        self._log.info("visual_resource.youtube_detected", count=len(youtube_refs))

        # Deduplicate by title (multiple frames may show the same video)
        seen_titles: set[str] = set()
        unique_refs: list[dict] = []
        for ref in youtube_refs:
            title_key = (ref.get("title") or "").strip().lower()
            if title_key and title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_refs.append(ref)

        # Search for YouTube URLs for each unique reference
        search_tasks = [self._find_youtube_url(ref) for ref in unique_refs]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        added = 0
        for ref, url_result in zip(unique_refs, search_results):
            if isinstance(url_result, Exception):
                self._log.warning(
                    "visual_resource.search_failed",
                    title=ref.get("title"),
                    error=str(url_result),
                )
                continue

            title = ref.get("title", "YouTube Video").strip()
            channel = ref.get("channel", "").strip()
            url = url_result or ""

            resource = Resource(
                name=title,
                resource_type=ResourceType.YOUTUBE_CHANNEL if not url else ResourceType.WEBSITE,
                url=url,
                description=f"YouTube video by {channel}" if channel else "YouTube video detected in reel frame",
                tags=["youtube", "visual-discovery"],
                confidence=0.75 if url else 0.5,
            )
            kg.add_resource(resource)
            added += 1

        self._log.info("visual_resource.success", resources_added=added)
        return kg

    def _select_frames(self, paths: list[str], max_count: int) -> list[str]:
        """Select evenly-spaced frames from the list."""
        if len(paths) <= max_count:
            return paths
        step = len(paths) / max_count
        return [paths[int(i * step)] for i in range(max_count)]

    async def _analyze_frame(self, frame_path: str) -> dict | None:
        """Use vision LLM to check if a frame contains a YouTube thumbnail."""
        path = Path(frame_path)
        if not path.exists():
            return None

        # Read and encode the image
        img_bytes = path.read_bytes()
        img_b64 = base64.b64encode(img_bytes).decode()

        # Determine MIME type
        suffix = path.suffix.lower()
        mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

        messages = [
            {
                "role": "system",
                "content": (
                    "You analyze screenshots to detect YouTube video references. "
                    "Output strict JSON only."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Does this image show a YouTube video thumbnail, screenshot, or recommendation? "
                            "Look for the YouTube play button, red YouTube UI, video titles, channel names, "
                            "or any visual indication of a YouTube video being displayed.\n\n"
                            "Return JSON: "
                            '{\"is_youtube\": bool, \"videos\": [{\"title\": \"video title if visible\", '
                            '\"channel\": \"channel name if visible\", \"url\": \"URL if visible else empty\"}]}'
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{img_b64}"},
                    },
                ],
            },
        ]

        try:
            result = await self.client.complete_json(
                task="extraction",
                messages=messages,
                agent_name=self.name,
            )
            return result
        except Exception as exc:
            self._log.debug("visual_resource.vision_call_failed", error=str(exc))
            return None

    async def _find_youtube_url(self, ref: dict) -> str | None:
        """Search for a YouTube video URL using title and channel name.

        Strategy:
        1. If the vision LLM already found a direct YouTube URL, return it.
        2. Try to scrape the first video ID from the YouTube search results page.
        3. If scraping fails (YouTube renders via JS), fall back to returning a
           YouTube search URL so the user can find the video manually.
        """
        title = ref.get("title", "").strip()
        channel = ref.get("channel", "").strip()
        direct_url = ref.get("url", "").strip()

        # Fix: parentheses required — without them `or "youtu.be" in direct_url`
        # is always True because a non-empty string is truthy.
        if direct_url and ("youtube.com" in direct_url or "youtu.be" in direct_url):
            return direct_url

        if not title:
            return None

        # Build search query
        query_parts = [title]
        if channel:
            query_parts.append(channel)
        query = " ".join(query_parts)

        search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                response = await client.get(search_url, headers=headers)
                if response.status_code == 200:
                    import re
                    html = response.text
                    # YouTube embeds video IDs in initial page JSON/HTML
                    video_ids = re.findall(r'/watch\?v=([a-zA-Z0-9_-]{11})', html)
                    if video_ids:
                        first_id = video_ids[0]
                        self._log.debug("visual_resource.youtube_id_found", video_id=first_id)
                        return f"https://www.youtube.com/watch?v={first_id}"

        except Exception as exc:
            self._log.debug(
                "visual_resource.youtube_scrape_failed",
                query=query,
                error=str(exc),
            )

        # Fallback: return the search URL itself so the user can click and find the video
        self._log.debug("visual_resource.youtube_search_url_fallback", query=query)
        return search_url
