"""
KnowledgeFlow — KnowledgeGraph Data Model

This is the single canonical data structure that flows through the
entire processing pipeline. Every agent READS from and WRITES TO this
object. No agent writes to external systems (Notion, Telegram) directly.

Architecture rule:
    Input → KnowledgeGraph → Agents → KnowledgeGraph → Output Adapters

The KnowledgeGraph is constructed at the start of each job and persisted
to Notion only after all agents have finished (or partially failed).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ── Enumerations ─────────────────────────────────────────────────────────────

class Platform(str, Enum):
    """Supported input platforms."""
    INSTAGRAM = "instagram"
    YOUTUBE   = "youtube"
    X         = "x"
    LINKEDIN  = "linkedin"
    PDF       = "pdf"
    IMAGE     = "image"
    TEXT      = "text"
    UNKNOWN   = "unknown"


class ContentType(str, Enum):
    """More specific content type within a platform."""
    REEL         = "reel"
    SHORT        = "short"
    VIDEO        = "video"
    POST         = "post"
    ARTICLE      = "article"
    PDF          = "pdf"
    SCREENSHOT   = "screenshot"
    LOCAL_VIDEO  = "local_video"
    PLAIN_TEXT   = "plain_text"
    UNKNOWN      = "unknown"


class ResourceType(str, Enum):
    """Categories of educational resources that can be extracted."""
    WEBSITE          = "Website"
    GITHUB_REPO      = "GitHub Repository"
    DOCUMENTATION    = "Documentation"
    BOOK             = "Book"
    RESEARCH_PAPER   = "Research Paper"
    COURSE           = "Course"
    AI_TOOL          = "AI Tool"
    FRAMEWORK        = "Framework"
    LIBRARY          = "Library"
    API              = "API"
    COMPANY          = "Company"
    PERSON           = "Person"
    NEWSLETTER       = "Newsletter"
    PODCAST          = "Podcast"
    YOUTUBE_CHANNEL  = "YouTube Channel"
    DISCORD          = "Discord Community"
    PROMPT           = "Prompt"
    TEMPLATE         = "Template"
    OTHER            = "Other"


class Difficulty(str, Enum):
    """Content difficulty level."""
    BEGINNER     = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED     = "Advanced"
    EXPERT       = "Expert"


class JobStatus(str, Enum):
    """Overall pipeline job status."""
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    PARTIAL    = "partial"    # Some agents failed but output was produced
    FAILED     = "failed"     # Critical failure, no useful output


class AgentStatus(str, Enum):
    """Per-agent execution status."""
    PENDING  = "pending"
    RUNNING  = "running"
    SUCCESS  = "success"
    SKIPPED  = "skipped"   # Agent determined it had nothing to do
    FAILED   = "failed"    # Agent failed but pipeline continued (recoverable)
    ERROR    = "error"     # Non-recoverable failure


# ── Sub-models ────────────────────────────────────────────────────────────────

class Source(BaseModel):
    """
    Information about the original content being processed.
    Populated by: MetadataAgent, CategorizationAgent.
    """
    title: str = ""
    url: str = ""
    platform: Platform = Platform.UNKNOWN
    content_type: ContentType = ContentType.UNKNOWN
    creator_name: str = ""
    creator_username: str = ""
    creator_profile_url: str = ""
    description: str = ""          # Original caption / description
    summary: str = ""              # AI-generated summary
    detailed_content: str = ""     # Full extracted content (prompts, steps, guides)
    pinned_comment: str = ""       # Pinned/top comment text from the platform
    primary_category: str = ""
    subcategory: str = ""
    tags: list[str] = Field(default_factory=list)
    difficulty: Optional[Difficulty] = None
    published_at: Optional[datetime] = None
    thumbnail_url: str = ""
    duration_seconds: Optional[int] = None   # For videos


class Resource(BaseModel):
    """
    An educational resource extracted from the content.
    Populated by: ResourceExtractorAgent, EnrichmentAgent, DeduplicationAgent.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    resource_type: ResourceType = ResourceType.OTHER
    url: str = ""
    description: str = ""
    prompts: str = ""
    tags: list[str] = Field(default_factory=list)
    enriched: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    # Set to the Notion page ID if this resource already exists in Notion
    notion_page_id: Optional[str] = None
    # True if this resource was merged into an existing Notion record
    merged: bool = False

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Resource name cannot be empty")
        return v.strip()


class Entity(BaseModel):
    """
    A named entity extracted from the content
    (person, company, technology, concept, etc.).
    Populated by: KnowledgeBuilderAgent.
    """
    name: str
    entity_type: str    # e.g. "person", "company", "technology", "concept"
    description: str = ""


class Relationship(BaseModel):
    """
    A relationship between two entities or resources.
    Populated by: KnowledgeBuilderAgent.
    """
    from_entity: str
    to_entity: str
    relation: str       # e.g. "uses", "created_by", "part_of", "competes_with"


class AgentLog(BaseModel):
    """
    Execution record for a single agent run.
    Attached to ProcessingMetadata by the pipeline orchestrator.
    """
    agent_name: str
    status: AgentStatus = AgentStatus.PENDING
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: str = ""
    warning: str = ""


class ProcessingMetadata(BaseModel):
    """
    Technical metadata about the processing run itself.
    Populated by: the pipeline orchestrator and individual agents.
    """
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    status: JobStatus = JobStatus.PENDING
    # Per-agent execution logs (ordered by execution sequence)
    agent_logs: list[AgentLog] = Field(default_factory=list)
    # Non-fatal warnings accumulated during processing
    warnings: list[str] = Field(default_factory=list)
    # Path to cached media on disk (cleared after success unless --keep-cache)
    media_file_path: str = ""
    # Raw OCR text (merged from all frames)
    ocr_text: str = ""
    # Paths to saved video frames for visual resource analysis
    saved_frame_paths: list[str] = Field(default_factory=list)
    # Raw transcript (before summarization — not stored in Notion)
    raw_transcript: str = ""
    # Flag: True when early scan found URLs in description/pinned comment.
    # When set, the pipeline skips expensive video processing (download, OCR, transcription).
    early_resources_found: bool = False
    # Telegram user ID who submitted this job
    telegram_user_id: Optional[int] = None
    # Telegram message ID for progress updates
    telegram_message_id: Optional[int] = None


# ── Root KnowledgeGraph ───────────────────────────────────────────────────────

class KnowledgeGraph(BaseModel):
    """
    The central data model shared across the entire pipeline.

    Design rules:
      - Every agent receives this object and returns an updated copy.
      - Agents NEVER write to Notion or Telegram directly.
      - Only output adapters (NotionAdapter, TelegramAdapter) read
        the final KnowledgeGraph and persist it externally.
      - The 'metadata' field tracks the technical run; all other
        fields contain the extracted knowledge.
    """

    # ── Submitted input ──────────────────────────────────────
    # The raw URL or file path submitted by the user
    input_url: str = ""
    input_type: ContentType = ContentType.UNKNOWN

    # ── Extracted knowledge ───────────────────────────────────
    source: Source = Field(default_factory=Source)
    resources: list[Resource] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    key_concepts: list[str] = Field(default_factory=list)

    # ── Technical metadata ────────────────────────────────────
    metadata: ProcessingMetadata = Field(default_factory=ProcessingMetadata)

    # ── Notion output references ──────────────────────────────
    # Set after successful Notion sync
    notion_source_page_id: Optional[str] = None
    notion_knowledge_page_id: Optional[str] = None

    # ── Convenience helpers ───────────────────────────────────

    def add_warning(self, message: str) -> None:
        """Record a non-fatal warning during processing."""
        self.metadata.warnings.append(message)

    def add_resource(self, resource: Resource) -> None:
        """Append a resource if not already present (by URL or name)."""
        for existing in self.resources:
            if existing.url and existing.url == resource.url:
                return
        self.resources.append(resource)

    def update_agent_log(
        self,
        agent_name: str,
        status: AgentStatus,
        error: str = "",
        warning: str = "",
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
    ) -> None:
        """Create or update the AgentLog for a given agent."""
        for log in self.metadata.agent_logs:
            if log.agent_name == agent_name:
                log.status = status
                log.error_message = error
                log.warning = warning
                if started_at:
                    log.started_at = started_at
                if finished_at:
                    log.finished_at = finished_at
                    if log.started_at:
                        delta = finished_at - log.started_at
                        log.duration_ms = int(delta.total_seconds() * 1000)
                return
        # Not found — create new entry
        self.metadata.agent_logs.append(
            AgentLog(
                agent_name=agent_name,
                status=status,
                started_at=started_at,
                finished_at=finished_at,
                error_message=error,
                warning=warning,
            )
        )

    def is_successful(self) -> bool:
        """True if the job completed with at least partial results."""
        return self.metadata.status in (JobStatus.COMPLETED, JobStatus.PARTIAL)

    def has_useful_content(self) -> bool:
        """True if there is enough content to create a Notion entry."""
        return bool(
            self.source.title
            or self.source.summary
            or self.resources
            or self.topics
        )

    @classmethod
    def create_for_url(
        cls,
        url: str,
        telegram_user_id: Optional[int] = None,
        telegram_message_id: Optional[int] = None,
    ) -> "KnowledgeGraph":
        """Factory: create a fresh KnowledgeGraph for a new URL job."""
        from utils.url_parser import detect_platform, detect_content_type
        
        kg = cls(input_url=url)
        kg.source.platform = detect_platform(url)
        kg.source.content_type = detect_content_type(url)
        
        kg.metadata.telegram_user_id = telegram_user_id
        kg.metadata.telegram_message_id = telegram_message_id
        kg.metadata.status = JobStatus.PENDING
        return kg
