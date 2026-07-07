"""
KnowledgeFlow — Transcript Agent

Extracts audio from video files using ffmpeg.
Transcribes audio using Gemini multimodal API.
Summarizes the transcript (or fallback context) using the prompt system.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import structlog

from agents.base import BaseAgent
from core.exceptions import TranscriptionError, LLMError
from core.knowledge_graph import KnowledgeGraph, Platform
from llm.client import LLMClient
from utils.prompt_loader import render_prompt

log = structlog.get_logger(__name__)


class TranscriptAgent(BaseAgent):
    """
    Agent responsible for extracting audio, transcribing it, and generating content summaries.
    """

    def __init__(self, client: LLMClient) -> None:
        super().__init__(name="TranscriptAgent")
        self.client = client

    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        media_path_str = kg.metadata.media_file_path
        platform = kg.source.platform
        job_id = kg.metadata.job_id

        # 1. Determine if we should attempt transcription
        # Transcription is only relevant for video/audio platforms (YouTube, Instagram)
        has_media = bool(media_path_str and Path(media_path_str).exists())
        is_video = platform in (Platform.YOUTUBE, Platform.INSTAGRAM)

        if is_video and has_media:
            media_path = Path(media_path_str)
            audio_path = media_path.with_name("audio.mp3")

            try:
                # Extract audio from video
                audio_extracted = await self._extract_audio(media_path, audio_path)
                if audio_extracted and audio_path.exists() and audio_path.stat().st_size > 0:
                    # Transcribe audio using Gemini multimodal API
                    self._log.info("transcript.transcribing", path=str(audio_path))
                    raw_transcript = await self.client.transcribe(audio_path, agent_name=self.name)
                    kg.metadata.raw_transcript = raw_transcript.strip()
                    self._log.info("transcript.success", char_count=len(kg.metadata.raw_transcript))
                else:
                    self._log.warning("transcript.audio_extraction.empty")
            except Exception as exc:
                self._log.warning("transcript.failed", error=str(exc))
                kg.add_warning(f"Audio transcription failed: {exc}. Summary will rely on title/caption only.")
        else:
            self._log.info("transcript.skipped", reason=f"Platform is {platform} or no media file cached")

        # 2. Generate summary using LLM (run for all platforms, using whatever text is available)
        kg = await self._generate_summary(kg)

        return kg

    async def _extract_audio(self, video_path: Path, audio_path: Path) -> bool:
        """Extract audio stream from video using ffmpeg subprocess."""
        self._log.info("transcript.ffmpeg.start", video=str(video_path), audio=str(audio_path))
        
        # Build command: extract audio to mp3 with medium quality
        cmd = [
            "ffmpeg",
            "-y",               # Overwrite output
            "-i", str(video_path),
            "-vn",              # Disable video
            "-acodec", "libmp3lame",
            "-q:a", "4",        # VBR quality 4 (around 160kbps)
            str(audio_path)
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                err_str = stderr.decode(errors="replace")
                self._log.warning("transcript.ffmpeg.error", code=process.returncode, stderr=err_str)
                return False

            return True
        except FileNotFoundError:
            self._log.warning("transcript.ffmpeg.not_found", reason="ffmpeg executable not found on system path")
            return False
        except Exception as exc:
            self._log.error("transcript.ffmpeg.failed", error=str(exc))
            return False

    async def _generate_summary(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        """Call LLM to summarize the transcript, captions, or OCR text."""
        self._log.info("transcript.summary.start")
        
        # Load and render prompt template
        try:
            prompt = render_prompt(
                "transcript_summary",
                title=kg.source.title or "Untitled Input",
                platform=kg.source.platform.value,
                creator=kg.source.creator_name or "Unknown Creator",
                caption=f"Caption: {kg.source.description or 'None'}\nOCR Text: {kg.metadata.ocr_text or 'None'}",
                pinned_comment=kg.source.pinned_comment or "No pinned comment.",
                transcript=kg.metadata.raw_transcript or "No transcription available.",
            )
        except FileNotFoundError as exc:
            raise TranscriptionError(f"Prompt template missing: {exc}")

        messages = [
            {"role": "system", "content": "You are a helpful assistant that outputs strict JSON."},
            {"role": "user", "content": prompt}
        ]

        try:
            res_dict = await self.client.complete_json(
                task="summary",
                messages=messages,
                agent_name=self.name
            )

            # Update KnowledgeGraph
            kg.source.summary = res_dict.get("summary", "").strip()
            
            # If original title was empty/missing, set it to the LLM-normalized title
            if not kg.source.title or kg.source.title.startswith("Untitled"):
                kg.source.title = res_dict.get("title", "").strip()

            # Save key points as key concepts if relevant
            key_points = res_dict.get("key_points", [])
            for kp in key_points:
                if kp.strip() and kp.strip() not in kg.key_concepts:
                    kg.key_concepts.append(kp.strip())

            # Store detailed content (full prompts, step-by-step guides)
            detailed = res_dict.get("detailed_content", "").strip()
            if detailed:
                kg.source.detailed_content = detailed
                content_type = res_dict.get("content_type", "general")
                self._log.info(
                    "transcript.detailed_content.extracted",
                    content_type=content_type,
                    char_count=len(detailed),
                )

            self._log.info("transcript.summary.success", title=kg.source.title)
        except LLMError as exc:
            # Re-raise so BaseAgent wraps it or errors out depending on recoverability
            raise
        except Exception as exc:
            raise TranscriptionError(f"Failed to generate and parse content summary: {exc}") from exc

        return kg
