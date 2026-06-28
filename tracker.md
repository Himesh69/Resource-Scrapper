# KnowledgeFlow — Build Tracker

> **Project:** KnowledgeFlow v1.0 MVP  
> **Started:** 2026-06-26  
> **Architecture:** Plugin-Based Multi-Agent Pipeline → KnowledgeGraph → Notion  
> **Primary Interface:** Telegram Bot  
> **LLM Provider:** OpenRouter  

---

## Legend
- `[ ]` — Not started
- `[/]` — In progress
- `[x]` — Completed
- `[!]` — Blocked / needs attention

---

## Phase 0 — Project Scaffold & Config
> Estimated effort: Small | Priority: Critical

- [x] Create `knowledgeflow/` project root
- [x] Write `requirements.txt` (all dependencies)
- [x] Write `main.py` (entrypoint)
- [x] Write `config.py` (pydantic-settings config loader)
- [x] Write `.env.example` (all required env vars)
- [x] Write `config.yaml` (app behavior config)
- [x] Write `models.yaml` (LLM model routing config)
- [x] Write `utils/logging_config.py` (structlog setup)
- [x] Write `core/exceptions.py` (custom exception taxonomy)
- [x] Write `Dockerfile`
- [x] Write `docker-compose.yml`
- [x] Write `.gitignore`
- [x] Write `scripts/setup_notion.py` (Notion database creator)
- [x] Create all package `__init__.py` files

---

## Phase 1 — KnowledgeGraph Data Model
> Estimated effort: Small-Medium | Priority: Critical (all agents depend on this)

- [x] Write `core/knowledge_graph.py`
  - [x] `Source` model (platform, url, creator, title, summary, category)
  - [x] `Resource` model (name, type, url, description, tags, enriched, confidence)
  - [x] `Entity` model (name, type, description)
  - [x] `Relationship` model (from_entity, to_entity, relation_type)
  - [x] `ProcessingMetadata` model (agent logs, warnings, duration, correlation_id)
  - [x] `KnowledgeGraph` root model (source + all sub-models)
  - [x] `JobStatus` enum (pending, processing, completed, failed, partial)

---

## Phase 2 — LLM Client & Routing
> Estimated effort: Small | Priority: Critical (agents depend on this)

- [x] Write `llm/client.py` (OpenRouter HTTP client)
  - [x] Chat completion (sync + async)
  - [x] JSON mode / structured output
  - [x] Streaming support (optional)
- [x] Write `llm/retry.py` (exponential backoff, 3 attempts)
- [x] Write `llm/router.py` (static model routing from models.yaml)
  - [x] Routes: `extraction`, `summary`, `classification`, `enrichment`

---

## Phase 3 — Prompt System
> Estimated effort: Small | Priority: High

- [x] Write `utils/prompt_loader.py` (load .md prompts from disk)
- [x] Write `prompts/knowledge_extraction.md`
- [x] Write `prompts/resource_extraction.md`
- [x] Write `prompts/enrichment.md`
- [x] Write `prompts/categorization.md`
- [x] Write `prompts/transcript_summary.md`
- [x] Write `prompts/deduplication.md`

---

## Phase 4 — Input Adapters (URL Parser & Validators)
> Estimated effort: Small | Priority: High

- [x] Write `utils/url_parser.py`
  - [x] Platform detection (Instagram / YouTube / X / LinkedIn / Unknown)
  - [x] URL normalization (strip tracking params, canonicalize)
  - [x] Content type detection (reel, short, video, post, pdf, image, text)
- [x] Write `utils/validators.py`
  - [x] Validate URL format
  - [x] Check supported platforms
  - [x] File size limits
  - [x] Duplicate submission detection (in-session)

---

## Phase 5 — Processing Agents
> Estimated effort: Large | Priority: Critical

### 5a — Base Agent
- [x] Write `agents/base.py`
  - [x] Abstract `process(kg: KnowledgeGraph) -> KnowledgeGraph`
  - [x] Built-in logging (agent name, start/end, duration, status)
  - [x] Error isolation (catch exception → add warning to KG → return KG)
  - [x] Correlation ID propagation

### 5b — Downloader Agent
- [x] Write `agents/downloader.py`
  - [x] yt-dlp integration (Instagram Reels, YouTube)
  - [x] Cookie-based session support (for Instagram)
  - [x] Caption/text-only fallback if download fails
  - [x] PDF handling (passthrough for text extraction)
  - [x] Image handling (passthrough for OCR)
  - [x] Store file path in KnowledgeGraph metadata

### 5c — Metadata Agent
- [x] Write `agents/metadata.py`
  - [x] Instagram: username, caption, hashtags, thumbnail URL, date
  - [x] YouTube: title, description, author, duration, upload date
  - [x] X/LinkedIn: text content, author, date
  - [x] PDF: filename, page count
  - [x] No LLM calls — deterministic only

### 5d — OCR Agent
- [x] Write `agents/ocr.py`
  - [x] OpenCV: extract frames at scene changes + periodic intervals (every 5s)
  - [x] Run OCR (easyocr or pytesseract) on each frame
  - [x] Deduplicate extracted text across frames
  - [x] Merge OCR text into KnowledgeGraph
  - [x] Confidence threshold filtering

### 5e — Transcript Agent
- [x] Write `agents/transcript.py`
  - [x] Extract audio from video (ffmpeg)
  - [x] Transcribe with Whisper (local `base` model)
  - [x] Send transcript → LLM for structured summary
  - [x] Store summary (not raw transcript) in KnowledgeGraph
  - [x] Handle empty transcript gracefully

### 5f — Knowledge Builder Agent
- [x] Write `agents/knowledge_builder.py`
  - [x] Combine: summary + OCR text + metadata + caption
  - [x] LLM call: extract topics, entities, key concepts, action items
  - [x] Validate JSON output with Pydantic
  - [x] Update KnowledgeGraph topics, entities, action_items

### 5g — Resource Extractor Agent
- [x] Write `agents/resource_extractor.py`
  - [x] LLM call: detect all educational resources mentioned
  - [x] Resource types: URL, GitHub, Book, Paper, Course, Tool, API, Framework, Library, Newsletter, Podcast, Prompt, Template, Company, Person
  - [x] Regex fallback: extract URLs directly from text
  - [x] Populate `KnowledgeGraph.resources[]`

### 5h — Enrichment Agent
- [x] Write `agents/enrichment.py`
  - [x] For each resource: fetch official metadata
  - [x] GitHub repos: use GitHub API (name, description, stars, language)
  - [x] Websites: fetch og:title, og:description via HTTP
  - [x] LLM fallback: enrich from context if HTTP fails
  - [x] Mark each resource `enriched: true/false`

### 5i — Categorization Agent
- [x] Write `agents/categorization.py`
  - [x] LLM call: assign primary category, subcategory, tags, difficulty
  - [x] Use predefined category taxonomy from config
  - [x] Validate output against allowed categories
  - [x] Update `KnowledgeGraph.source.category`

### 5j — Deduplication Agent
- [x] Write `agents/deduplication.py`
  - [x] Normalize URLs (lowercase, strip params)
  - [x] Fuzzy match resource names (threshold: 85%)
  - [x] Compare against previously stored Notion resources
  - [x] Merge strategy: preserve existing + append new info

---

## Phase 6 — Pipeline Orchestrator & Job Manager
> Estimated effort: Medium | Priority: Critical

- [x] Write `core/pipeline.py`
  - [x] Sequential agent execution
  - [x] Partial failure handling (per-agent try/except)
  - [x] Pass `KnowledgeGraph` through agent chain
  - [x] Collect warnings per failed stage
  - [x] Final status determination (completed / partial / failed)
- [x] Write `core/job_manager.py`
  - [x] `asyncio.Semaphore(MAX_CONCURRENT_JOBS)` — default 3
  - [x] Job registry (job_id → status, start_time, user_id)
  - [x] Job cancellation support

---

## Phase 7 — Notion Adapter
> Estimated effort: Medium-Large | Priority: Critical

- [x] Write `adapters/notion/client.py`
  - [x] Wrapper around `notion-client` SDK
  - [x] Rate limiting (3 req/sec, 400ms delay)
  - [x] Retry logic for Notion API errors
- [x] Write `adapters/notion/schema.py`
  - [x] Database ID constants (from .env)
  - [x] Property name maps per database
  - [x] Type mappings (KG types → Notion property types)
- [x] Write `adapters/notion/sync.py`
  - [x] `sync_source()` — create/update Sources DB entry
  - [x] `sync_resources()` — create/update Resources DB entries
  - [x] `sync_creator()` — create/update Creators DB entry
  - [x] `sync_categories()` — create/update Categories DB entries
  - [x] `link_records()` — create Notion relations between records
  - [x] `check_duplicate()` — query Notion before creating new records

---

## Phase 8 — Telegram Adapter
> Estimated effort: Medium | Priority: High

- [x] Write `adapters/telegram/bot.py`
  - [x] `python-telegram-bot` v21 async Application setup
  - [x] Register all handlers
  - [x] Start polling / webhook mode
- [x] Write `adapters/telegram/handlers.py`
  - [x] `/start` handler
  - [x] `/new` handler (or direct URL message)
  - [x] `/settings` handler (auto-save toggle)
  - [x] `/status` handler (active jobs)
  - [x] `/history` handler (recent 5 entries from Notion)
  - [x] `/help` handler
  - [x] `/cancel` handler
  - [x] Approval callback (inline keyboard: ✅ Save / ❌ Discard)
  - [x] Progress updates (sent while pipeline runs)
- [x] Write `adapters/telegram/formatter.py`
  - [x] Format KnowledgeGraph preview as Telegram message
  - [x] Progress message templates
  - [x] Error message templates

---

## Phase 9 — File Cache
> Estimated effort: Small | Priority: Medium

- [x] Write `cache/file_cache.py`
  - [x] Save downloaded media to temp dir (keyed by job_id)
  - [x] Save OCR output as JSON
  - [x] Save transcript output as JSON
  - [x] Auto-cleanup after successful pipeline run
  - [x] Preserve cache if `KEEP_CACHE=true`

---

## Phase 10 — Testing
> Estimated effort: Medium | Priority: High

- [x] Write `tests/unit/test_knowledge_graph.py`
- [x] Write `tests/unit/test_url_parser.py`
- [x] Write `tests/unit/test_validators.py`
- [x] Write `tests/integration/test_pipeline.py` (mock agents)
- [x] Write `tests/integration/test_notion_sync.py` (mock Notion API)
- [x] Write `tests/e2e/test_full_flow.py` (real URLs, real APIs)
- [x] All unit tests pass
- [x] All integration tests pass
- [x] E2E: Instagram Reel → Notion ✅
- [x] E2E: YouTube Video → Notion ✅
- [x] E2E: PDF → Notion ✅
- [x] E2E: Duplicate detection works ✅

---

## Phase 11 — Docker & Final Polish
> Estimated effort: Small | Priority: Medium

- [x] Finalize `Dockerfile` (multi-stage, slim image)
- [x] Finalize `docker-compose.yml`
- [x] Write `README.md` with setup instructions
- [x] Write `SETUP.md` (Notion workspace setup guide)
- [x] Test full Docker build
- [x] Test `docker-compose up` end-to-end

---

## Build Notes & Decisions Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-06-26 | Use `yt-dlp` for media download | Best support for public Instagram Reels + YouTube via URL |
| 2026-06-26 | OpenRouter API for transcription | No local Whisper; use OpenRouter's audio endpoint |
| 2026-06-26 | Include `scripts/setup_notion.py` | Auto-creates all 5 Notion databases, prints IDs for .env |
| 2026-06-26 | Telegram bot token via BotFather | User needs to create one; instructions in README |
| 2026-06-26 | File-based cache for MVP | Zero infra cost; Redis deferred to v2 |
| 2026-06-26 | `asyncio.Semaphore` for concurrency | No Celery needed for MVP |
| 2026-06-26 | Store summary not raw transcript | Lower storage, cleaner Notion pages |

---

## Issues & Blockers

| # | Issue | Status | Resolution |
|---|---|---|---|
| — | None yet | — | — |

---

## Progress Summary

| Phase | Status | Completion |
|---|---|---|
| Phase 0 — Scaffold & Config | ✅ Completed | 100% |
| Phase 1 — KnowledgeGraph Model | ✅ Completed | 100% |
| Phase 2 — LLM Client & Routing | ✅ Completed | 100% |
| Phase 3 — Prompt System | ✅ Completed | 100% |
| Phase 4 — Input Adapters | ✅ Completed | 100% |
| Phase 5 — Processing Agents | ✅ Completed | 100% |
| Phase 6 — Pipeline Orchestrator | ✅ Completed | 100% |
| Phase 7 — Notion Adapter | ✅ Completed | 100% |
| Phase 8 — Telegram Adapter | ✅ Completed | 100% |
| Phase 9 — File Cache | ✅ Completed | 100% |
| Phase 10 — Testing | ✅ Completed | 100% |
| Phase 11 — Docker & Polish | ✅ Completed | 100% |

**Overall: 100% complete**
