# KnowledgeFlow PRD (Skeleton)

> Version: v0.1-draft Status: Approved for implementation

# 1. Vision

KnowledgeFlow is a personal AI-powered knowledge ingestion platform that
transforms educational content (short-form videos, documents, posts,
screenshots, and text) into structured knowledge stored in Notion.

## Goals

-   Extract knowledge from educational content.
-   Extract and enrich resources.
-   Organize knowledge in Notion.
-   Zero recurring cost for MVP.
-   Open-source and extensible.

# 2. Product Scope

## Inputs

-   Instagram Reel URL
-   YouTube Shorts URL
-   YouTube Video URL
-   Instagram Posts
-   X Posts
-   LinkedIn Posts
-   PDF
-   Screenshot
-   Local Video
-   Plain Text

## Primary Output

-   Structured Notion Knowledge Base

## Future

-   Telegram Bot (primary adapter)
-   Additional adapters (Markdown, MCP, etc.)

# 3. High-Level Architecture

    Input Layer
    ------------
    Telegram Adapter
    URL Adapter
    PDF Adapter
    Image Adapter
    Video Adapter

    ↓

    Processing Layer
    ----------------
    Downloader Agent
    Metadata Agent
    OCR Agent
    Transcript Agent
    Vision Agent

    ↓

    Knowledge Layer
    ---------------
    Knowledge Graph Builder
    Resource Extractor
    Entity Extractor
    Category Agent
    Relationship Builder
    Deduplication Agent

    ↓

    Output Layer
    ------------
    Notion Adapter
    Telegram Adapter
    Future Adapters

# 4. Core Principles

-   Plugin-based architecture
-   OpenRouter-only LLM provider
-   Multiple models with static routing
-   External Markdown prompts
-   Config-driven behavior
-   No database (Notion is source of truth)
-   Intermediate cache deleted after success unless `--keep-cache`
-   Up to 3 concurrent jobs
-   Retry with exponential backoff (3 attempts)

# 5. Agent Pipeline

1.  Downloader
2.  Metadata
3.  OCR (adaptive)
4.  Transcript
5.  Knowledge Graph Builder
6.  Resource Extraction
7.  Enrichment
8.  Categorization
9.  Deduplication
10. Notion Output
11. Telegram Notification

# 6. Knowledge Graph

The pipeline produces a single KnowledgeGraph object.

## Source

-   Title
-   URL
-   Platform
-   Creator
-   Summary
-   Category

## Resources

-   URLs
-   GitHub repositories
-   Documentation
-   Books
-   Research papers
-   Courses
-   Products
-   AI tools
-   APIs
-   Companies
-   People
-   Prompts
-   Templates
-   Newsletters
-   Discord communities
-   YouTube channels
-   Podcasts
-   Frameworks
-   Libraries

## Metadata

-   Tags
-   Relationships
-   Action items

# 7. Telegram UX

Commands

-   /start
-   /new
-   /settings
-   /status
-   /history
-   /help
-   /cancel

Settings

-   Auto-save
-   Approval before save
-   Model selection (future)

# 8. Notion Design

Separate databases:

-   Sources
-   Resources
-   Categories
-   Creators
-   Knowledge

Resources are linked to Sources.

Duplicate resources are merged intelligently.

# 9. LLM Strategy

Static routing.

Suggested:

-   Extraction Model
-   Summary Model
-   Classification Model

Prompts stored as Markdown files.

# 10. Testing

-   Unit Tests
-   Integration Tests
-   End-to-End Tests

# 11. Roadmap

## v0.1

-   Telegram adapter
-   Notion integration
-   Instagram & YouTube support

## v0.2

-   Resource enrichment
-   Better duplicate detection

## v0.3

-   Additional input adapters

## v1.0

-   Stable open-source release

# 12. Open Questions

To be finalized in the full specification:

-   Detailed KnowledgeGraph schema
-   Prompt specifications
-   Folder structure
-   API contracts
-   Plugin interface
-   Error taxonomy
-   Security considerations
-   Configuration schema
-   Deployment guide
-   Contributor guidelines

------------------------------------------------------------------------

This document serves as the initial engineering PRD. A subsequent
version will expand this into a comprehensive implementation
specification covering architecture, interfaces, prompts, schemas,
workflows, and testing in depth.