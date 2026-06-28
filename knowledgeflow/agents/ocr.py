"""
KnowledgeFlow — OCR Agent

Extracts text from images and videos using easyocr and OpenCV.
For videos: extracts frames periodically and performs OCR on each.
For PDFs: extracts text using pypdf.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import structlog

from agents.base import BaseAgent
from core.exceptions import OCRError
from core.knowledge_graph import KnowledgeGraph, Platform
from config import app_config

log = structlog.get_logger(__name__)


class OCRAgent(BaseAgent):
    """
    Agent responsible for running OCR on images/video frames and extracting PDF text.
    """

    def __init__(self) -> None:
        super().__init__(name="OCRAgent")
        self._reader = None  # Lazily initialized easyocr Reader

    def _get_reader(self):
        """Lazy load easyocr reader to save startup time and memory."""
        if self._reader is None:
            import easyocr
            # Load English reader. Disable GPU by default for compatibility,
            # but allow it if CUDA is available.
            self._reader = easyocr.Reader(["en"], gpu=False)
        return self._reader

    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        media_path_str = kg.metadata.media_file_path
        platform = kg.source.platform

        if not media_path_str:
            self._log.info("ocr.skipped", reason="No media file path found in metadata")
            return kg

        media_path = Path(media_path_str)
        if not media_path.exists():
            self._log.warning("ocr.file_not_found", path=str(media_path))
            return kg

        self._log.info("ocr.start", path=str(media_path), platform=platform)

        try:
            if platform == Platform.PDF:
                kg = await self._process_pdf(kg, media_path)
            elif platform == Platform.IMAGE:
                kg = await self._process_image(kg, media_path)
            elif platform in (Platform.YOUTUBE, Platform.INSTAGRAM):
                kg = await self._process_video(kg, media_path)
            else:
                self._log.debug("ocr.skipped", reason=f"OCR not supported for platform {platform}")
        except Exception as exc:
            # Wrap as recoverable OCRError
            raise OCRError(f"OCR processing failed: {exc}") from exc

        return kg

    async def _process_pdf(self, kg: KnowledgeGraph, path: Path) -> KnowledgeGraph:
        """Extract text from PDF using pypdf."""
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            text_parts = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            extracted_text = "\n\n".join(text_parts).strip()
            if extracted_text:
                kg.metadata.ocr_text = extracted_text
                self._log.info("ocr.pdf.success", char_count=len(extracted_text))
            else:
                self._log.warning("ocr.pdf.empty_text", reason="No text extracted from PDF pages")
        except ImportError:
            self._log.warning("ocr.pdf.failed", reason="pypdf is not installed")
            kg.add_warning("pypdf is not installed, PDF text extraction was skipped.")
        except Exception as exc:
            self._log.error("ocr.pdf.failed", error=str(exc))
            kg.add_warning(f"Failed to extract PDF text: {exc}")

        return kg

    async def _process_image(self, kg: KnowledgeGraph, path: Path) -> KnowledgeGraph:
        """Run OCR on a single image file."""
        reader = self._get_reader()
        # easyocr can read from path directly
        results = reader.readtext(str(path))
        
        # Filter by confidence threshold
        conf_thresh = app_config.get("ocr", {}).get("confidence_threshold", 0.6)
        text_lines = []
        for bbox, text, conf in results:
            if conf >= conf_thresh:
                text_lines.append(text)

        extracted_text = "\n".join(text_lines).strip()
        kg.metadata.ocr_text = extracted_text
        self._log.info("ocr.image.success", line_count=len(text_lines), char_count=len(extracted_text))
        return kg

    async def _process_video(self, kg: KnowledgeGraph, path: Path) -> KnowledgeGraph:
        """Extract frames from video and run OCR on them, deduplicating text."""
        # Read parameters from config
        ocr_cfg = app_config.get("ocr", {})
        interval = ocr_cfg.get("frame_interval_seconds", 5)
        max_frames = ocr_cfg.get("max_frames", 30)
        conf_thresh = ocr_cfg.get("confidence_threshold", 0.6)

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            self._log.error("ocr.video.open_failed", path=str(path))
            return kg

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        self._log.info("ocr.video.info", fps=fps, total_frames=total_frames, duration_seconds=duration)

        frame_step = int(fps * interval) if fps > 0 else 150
        if frame_step <= 0:
            frame_step = 150

        frames_processed = 0
        current_frame = 0
        reader = self._get_reader()
        seen_texts: set[str] = set()
        accumulated_text = []
        saved_frame_paths: list[str] = []

        # Determine the directory to save frames (same as the media file's directory)
        frames_dir = path.parent / "frames"
        frames_dir.mkdir(exist_ok=True)

        while current_frame < total_frames and frames_processed < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
            ret, frame = cap.read()
            if not ret:
                break

            # Save frame to disk for visual resource analysis
            frame_path = frames_dir / f"frame_{frames_processed:03d}.jpg"
            cv2.imwrite(str(frame_path), frame)
            saved_frame_paths.append(str(frame_path))

            # Convert BGR (OpenCV default) to RGB (easyocr expects RGB numpy array or file path)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Run OCR on frame
            results = reader.readtext(frame_rgb)
            frame_lines = []
            for bbox, text, conf in results:
                cleaned_text = text.strip()
                if conf >= conf_thresh and len(cleaned_text) > 2:
                    # Basic inline deduplication
                    if cleaned_text.lower() not in seen_texts:
                        seen_texts.add(cleaned_text.lower())
                        frame_lines.append(cleaned_text)

            if frame_lines:
                accumulated_text.extend(frame_lines)

            frames_processed += 1
            current_frame += frame_step

        cap.release()

        final_ocr_text = "\n".join(accumulated_text).strip()
        kg.metadata.ocr_text = final_ocr_text
        kg.metadata.saved_frame_paths = saved_frame_paths
        self._log.info(
            "ocr.video.success",
            frames_processed=frames_processed,
            frames_saved=len(saved_frame_paths),
            char_count=len(final_ocr_text),
        )
        return kg
