## **KnowledgeFlow – Product Requirements Document (PRD)** 

**Version:** 1.0.0 

**Status:** Draft – Approved for Development **Project Type:** Personal AI Knowledge Ingestion Platform **License:** MIT (Open Source) **Primary Platform:** Telegram **Primary Knowledge Store:** Notion **LLM Provider:** OpenRouter 

**Architecture:** Plugin-Based Multi-Agent System 

## **1. Document Control** 

**Field Value** Project Name KnowledgeFlow Author Project Owner Document Type Product Requirements Document Version 1.0.0 Last Updated June 2026 Development Model Iterative Architecture Style Plugin-Based Multi-Agent Deployment Local / Docker 

## **2. Executive Summary** 

KnowledgeFlow is a personal AI-powered knowledge ingestion system designed to capture educational information from modern digital content and transform it into structured, searchable knowledge. 

Instead of acting as a bookmarking tool, KnowledgeFlow functions as an intelligent knowledge pipeline. It receives content from multiple sources, extracts meaningful information using specialized AI agents, enriches discovered resources with verified metadata, organizes relationships between entities, and stores everything inside a structured Notion workspace. 

The project is designed around a central **KnowledgeGraph** object. Every processing agent contributes to this object, ensuring that no component writes directly to external systems. Persistence is delegated to output adapters, allowing future integrations without modifying the processing pipeline. 

## **3. Vision Statement** 

Create a personal AI system capable of continuously converting educational content into structured knowledge with minimal human intervention. 

The system should: 

- Minimize manual note-taking. 

- Preserve valuable educational content. 

- Extract resources automatically. 

- Build relationships between resources. 

- Organize knowledge inside Notion. 

- Be extensible through plugins. 

- Operate with zero recurring infrastructure cost for the MVP. 

## **4. Problem Statement** 

Educational content is increasingly distributed across short-form platforms such as Instagram Reels, YouTube Shorts, X posts, LinkedIn posts, PDFs, screenshots, and videos. 

Current workflows require users to: 

- Save posts manually. 

- Copy links into notes. 

- Organize bookmarks. 

- Search through saved videos repeatedly. 

- Lose context between related resources. 

These approaches create fragmented knowledge that becomes difficult to search, maintain, and reuse. 

KnowledgeFlow addresses this by transforming unstructured media into structured knowledge automatically. 

## **5. Product Goals** 

## **Primary Goals** 

- Convert educational media into structured knowledge. 

- Automatically extract resources from content. 

- Enrich extracted resources. 

- Organize information into Notion. 

- Minimize manual work. 

- Maintain high extraction accuracy. 

- Support future expansion through adapters. 

## **Secondary Goals** 

- Support multiple input sources. 

- Maintain consistent processing regardless of source. 

- Enable intelligent deduplication. 

- Produce reusable knowledge rather than isolated notes. 

## **6. Non-Goals** 

The MVP intentionally excludes: 

- Multi-user authentication. 

- SaaS deployment. 

- Billing. 

- Team collaboration. 

- Mobile application. 

- Browser extension. 

- Native desktop application. 

- Social media publishing. 

- Local SQL database. 

- Recommendation engine. 

These may be considered in future versions. 

## **7. Target User** 

## **Primary User** 

The project is designed for a single technical user who consumes educational content regularly and wants to maintain a high-quality personal knowledge base with minimal manual effort. 

## **User Characteristics** 

- Comfortable using Telegram. 

- Consumes educational videos daily. 

- Uses Notion for knowledge management. 

- Prefers automation over manual organization. 

 Values structured information. 

## **8. Product Philosophy** 

KnowledgeFlow follows several guiding principles. 

## **Knowledge First** 

The product stores knowledge, not bookmarks. 

## **Source Agnostic** 

The same processing pipeline applies regardless of whether content originates from YouTube, Instagram, PDFs, or other supported inputs. 

## **Adapter Driven** 

External platforms are isolated behind adapters. Core processing remains independent. 

## **Plugin Friendly** 

New capabilities should be introduced as plugins without modifying the existing core. 

## **Deterministic Processing** 

Where possible, deterministic techniques (OCR, regex, metadata parsing) should precede LLM reasoning. 

## **AI as Enhancement** 

LLMs enrich and structure information rather than replacing deterministic extraction. 

## **9. Success Metrics** 

## **Functional** 

- Successfully process supported input sources. 

- Produce a valid KnowledgeGraph for every successful request. 

- Persist processed knowledge into Notion. 

- Extract URLs with high accuracy. 

- Categorize content consistently. 

## **Performance** 

- Complete processing within acceptable time for typical educational videos. 

- Support up to three concurrent processing jobs. 

- Retry transient failures up to three times using exponential backoff. 

## **Quality** 

- Accurate summaries. 

- Meaningful categorization. 

- Minimal duplicate resources. 

- Reliable enrichment. 

## **10. Core Principles** 

1. Plugin-Based Architecture 

2. Multi-Agent Processing 

3. KnowledgeGraph-Centric Design 

4. Telegram as an Input Adapter 

5. Notion as the Primary Knowledge Store 

6. OpenRouter as the LLM Gateway 

7. Static Model Routing 

8. External Prompt Management 

9. Configuration-Driven Behavior 

- 10.No Local Database for MVP 

## **11. High-Level Product Flow** 

User 

│ 

▼ 

Telegram Adapter 

│ 

▼ 

KnowledgeFlow Core 

│ 

▼ 

Input Processing 

│ 

▼ 

Knowledge Engine 

│ 

▼ 

KnowledgeGraph 

│ 

▼ 

Notion Adapter 

│ 

▼ 

Structured Knowledge Base 

## **12. Supported Inputs (MVP)** 

The MVP supports the following input types: 

|The MVP supports|the following i|
|---|---|
|**Input**|**Supported**|
|Instagram Reel URL Yes||
|YouTube Shorts URL Yes||
|YouTube Video URL Yes||
|Instagram Post|Yes|
|X Post|Yes|
|LinkedIn Post|Yes|
|PDF|Yes|
|Screenshot|Yes|
|Local Video|Yes|
|Plain Text|Yes|



## **13. Core Functional Requirements (Overview)** 

The system shall: 

- Accept supported inputs through Telegram. 

- Validate incoming content. 

- Download media when required. 

- Extract metadata. 

- Generate summaries. 

- Detect visible text using OCR. 

- Extract educational resources. 

- Enrich resources with official metadata. 

- Categorize content. 

- Detect duplicates. 

- Build a KnowledgeGraph. 

- Persist structured knowledge into Notion. 

- Notify the user of completion. 

## **14. Assumptions** 

- The user owns and manages the Notion workspace. 

- The user provides required API credentials. 

- Processing occurs on the user's own machine or Docker environment. 

- External services may impose rate limits or access restrictions. 

## **15. Document Status** 

This is **Part 1** of the complete PRD. Subsequent parts will expand the functional requirements, user stories, feature specifications, acceptance criteria, risks, roadmap, and appendices into a full engineering-grade document. 

## **KnowledgeFlow – Product Requirements Document (PRD)** 

## **Part 2 — Functional Requirements & Product Specification** 

Continue after Part 1 

## **16. Functional Requirements** 

This section defines every functional capability required for the MVP. 

Each requirement is mandatory unless explicitly marked as optional. 

## **FR-001 Input Acquisition** 

## **Description** 

The system shall accept multiple educational content formats and normalize them into a common internal representation. 

## **Supported Inputs** 

## **Required** 

**Input** Instagram Reel URL ✅ Instagram Post ✅ YouTube Shorts URL ✅ YouTube Video URL ✅ X/Twitter Post ✅ LinkedIn Post ✅ PDF ✅ Screenshot ✅ Local Video ✅ Plain Text ✅ 

## **Acceptance Criteria** 

The system must correctly determine 

- input type 

- platform 

- processing strategy 

without user intervention. 

## **FR-002 Input Validation** 

Every submitted input must be validated before processing begins. 

Validation includes 

- malformed URLs 

- unsupported domains 

- inaccessible files 

- unsupported media types 

- file size limits 

- duplicate submissions 

If validation fails 

the system must stop immediately and notify the user. 

## **FR-003 Download Pipeline** 

For downloadable media 

the system shall retrieve 

- media file 

- metadata 

- title 

- description 

- author 

- publication information 

The downloader must abstract away platform-specific logic. 

Future platforms should require only a new adapter. 

## **FR-004 Metadata Extraction** 

Metadata extraction must occur before AI processing. 

Examples include 

Platform 

Instagram 

Creator 

Username 

Publication Date 

Video Length 

Caption 

Hashtags 

Description 

Thumbnail URL 

Original Source URL 

Metadata should be deterministic. 

No LLM involvement. 

## **FR-005 OCR Processing** 

KnowledgeFlow shall detect textual information embedded inside visual media. 

OCR should process 

- scene changes 

- periodic frames 

to maximize accuracy while minimizing cost. 

Detected text should include 

URLs 

Books 

Framework names 

Repositories 

Tool names 

Email addresses 

Codes 

Commands 

Prompts 

Version numbers 

## **FR-006 Speech Processing** 

Audio shall be transcribed. 

The transcript is **not stored directly** . 

Instead 

an AI-generated summary is produced. 

Reasons 

- lower storage 

- easier search 

- cleaner Notion pages 

## **FR-007 Knowledge Extraction** 

This is the primary intelligence stage. 

## Inputs 

Transcript Summary OCR Output Metadata Caption Description ↓ Outputs Topics Resources People Companies Products Books Repositories Frameworks APIs Courses Action Items Tags Relationships 

## **FR-008 Resource Detection** 

The system shall identify every educational resource mentioned. 

Including Official websites GitHub repositories Documentation Books 

Research Papers 

Products 

Courses 

AI Tools 

Frameworks Libraries Templates Newsletters 

Discord Communities Podcasts YouTube Channels Prompts APIs 

## **FR-009 Resource Enrichment** 

Every detected resource should be enriched whenever possible. 

Example 

Input 

Cursor 

Output 

Name 

Cursor 

Website Official URL Description AI-first code editor 

Category AI IDE 

Tags Coding 

LLM 

Developer Tools Only official sources should be used for enrichment. 

## **FR-010 Categorization** 

Every source shall receive 

Primary Category 

Subcategory 

Tags 

Difficulty 

Example 

Programming 

↓ 

Python 

↓ 

AI Agents 

↓ 

LangGraph 

## **FR-011 Duplicate Detection** 

Duplicate resources should never create unnecessary records. 

Matching should use 

Normalized URL 

↓ 

Resource Name 

↓ 

Fuzzy Matching 

If duplicate found 

merge intelligently. 

Never discard previously collected information. 

## **FR-012 KnowledgeGraph Construction** 

Every processing stage updates a shared KnowledgeGraph. 

No component writes directly to Notion. 

Advantages 

- portability 

- testing 

- extensibility 

- easier debugging 

KnowledgeGraph becomes the canonical data model. 

## **FR-013 Notion Synchronization** 

After processing 

KnowledgeGraph 

↓ 

Notion Adapter 

↓ 

Relational Databases 

The adapter is responsible for 

creating 

updating 

linking 

deduplicating 

records. 

## **FR-014 Telegram Feedback** 

Telegram acts purely as an adapter. 

Responsibilities 

Receive user requests 

Show progress 

Display summary 

Ask for approval (optional) 

Notify completion 

Telegram never performs business logic. 

## **FR-015 Approval Workflow** 

The system supports two modes. 

Automatic 

↓ 

Immediately save 

Manual 

↓ 

Preview 

↓ 

Approve ↓ 

Save 

Users may switch modes through settings. 

## **FR-016 Retry Strategy** 

Failures caused by 

network 

OpenRouter 

temporary APIs 

should retry 

three times 

using exponential backoff. 

Permanent failures 

should immediately terminate the affected stage. 

## **FR-017 Partial Failures** 

Pipeline stages should fail independently whenever possible. 

Example 

OCR fails 

↓ 

Transcript succeeds 

↓ 

Extraction continues 

↓ 

Notion entry created 

↓ 

OCR warning attached 

The system should maximize successful knowledge extraction. 

## **FR-018 Logging** 

Every agent must emit structured JSON logs. 

Each log should contain 

Timestamp 

Agent 

Action 

Duration 

Status 

Error 

Correlation ID 

Logs should simplify debugging. 

## **FR-019 Caching** 

Intermediate artifacts should be cached. 

Examples 

Downloaded media 

OCR output 

Transcript 

Metadata 

Cache is automatically removed 

unless 

--keep-cache 

is enabled. 

## **FR-020 Concurrency** 

The pipeline supports 

up to three 

parallel processing jobs. 

Concurrency should be configurable. 

## **17 User Stories** 

## **Story 1** 

As a learner 

I want to send an Instagram Reel 

so that 

KnowledgeFlow automatically saves useful information into Notion. 

## **Story 2** 

As a developer 

I want GitHub repositories extracted 

without manual searching. 

## **Story 3** 

As a researcher 

I want books 

papers 

and documentation 

organized automatically. 

## **Story 4** 

As a knowledge worker 

I want duplicate resources merged 

so that 

my knowledge base remains clean. 

## **Story 5** 

As the project owner 

I want Telegram to notify me 

when processing completes. 

## **18 Feature Specifications** 

MVP Features 

- ✅ Telegram Adapter 

- ✅ Downloader 

- ✅ OCR 

- ✅ Transcript Summary 

- ✅ Resource Extraction 

- ✅ Resource Enrichment 

- ✅ Categorization 

- ✅ Duplicate Detection 

- ✅ KnowledgeGraph 

- ✅ Notion Adapter 

Future 

Semantic Search 

MCP 

Web Dashboard 

Browser Extension 

Multi-user 

Vector Search 

AI Chat 

## **19 Acceptance Criteria** 

The MVP is considered complete when 

- ✓ Telegram receives URLs 

- ✓ Supported content is processed 

- ✓ Resources are extracted 

- ✓ Official metadata is enriched 

- ✓ Categories assigned 

- ✓ Duplicate resources merged 

- ✓ KnowledgeGraph constructed 

- ✓ Data stored inside Notion 

- ✓ User notified 

- ✓ All automated tests pass 

## **20 Non-Functional Requirements** 

Performance 

Reliable 

Maintainable 

Plugin-based 

Strong typing 

Testable 

Observable 

Configurable 

Open-source friendly 

Platform independent 

Docker compatible 

Zero recurring infrastructure cost 

## **End of Part 2** 

The next part will define: 

- Detailed system constraints 

- Business rules 

- Edge cases 

- Security model 

- Privacy requirements 

- Product roadmap 

- Risks 

- Release milestones 

- Complete appendices 

## **Part 3 — Business Rules, Constraints, Security & Roadmap** 

Continue after Part 2 

## **21. Business Rules** 

Business rules define invariant behavior across the system. These rules must be enforced regardless of the input source or implementation details. 

## **BR-001 — KnowledgeGraph is the Single Source of Truth** 

Every processing agent must operate exclusively on the shared KnowledgeGraph object. 

Agents **must not** : 

- Write directly to Notion. 

- Send Telegram messages. 

- Access unrelated adapters. 

- Modify external systems. 

All external communication is handled by adapters after the KnowledgeGraph reaches a valid state. 

## **BR-002 — Adapters Are Stateless** 

Adapters translate between external platforms and the internal system. 

Responsibilities: 

- Accept input. 

- Validate payloads. 

- Convert to internal request models. 

- Return results to users. 

Adapters must not: 

- Contain business logic. 

- Perform AI processing. 

- Manage state. 

- Call other adapters directly. 

## **BR-003 — AI Enhances, Not Replaces Deterministic Processing** 

The system should always prefer deterministic extraction before invoking an LLM. 

Order of preference: 

1. Metadata extraction 

2. URL parsing 

3. OCR 

4. Transcript generation 

5. Regex-based extraction 

6. LLM reasoning 

This minimizes cost and reduces hallucinations. 

## **BR-004 — Official Sources Take Priority** 

When enriching a detected resource: 

Priority order: 

1. Official website 

2. Official GitHub repository 

3. Official documentation 

4. Verified project metadata 

Community blogs or unofficial mirrors should not be treated as canonical. 

## **BR-005 — Preserve Existing Knowledge** 

When duplicate resources are detected: 

- Do not overwrite existing data blindly. 

- Merge new information where appropriate. 

- Preserve existing relationships. 

- Append new source references. 

**BR-006 — Fail Gracefully** 

A single component failure should not terminate the entire pipeline if meaningful output can still be produced. 

Example: 

- OCR fails 

- Transcript succeeds 

- Resource extraction proceeds 

- Notion entry is created with an OCR warning 

## **22. System Constraints** 

## **Cost Constraint** 

## MVP must have **zero recurring infrastructure cost** . 

Allowed: 

- Local execution 

- Docker 

- Free OpenRouter models 

- Notion free plan 

- Telegram Bot API 

Not allowed: 

- Paid cloud databases 

- Managed orchestration platforms 

- Paid vector databases 

## **Deployment Constraint** 

Primary deployment targets: 

- Local machine 

- Docker Compose 

Future: 

- VPS 

- Kubernetes 

- Cloud deployment 

## **Performance Constraint** 

The system should remain responsive while processing up to **three concurrent jobs** . 

Long-running tasks should provide progress updates through Telegram. 

## **Configuration Constraint** 

No secrets may be hardcoded. 

Configuration sources: 

- .env 

- config.yaml 

- models.yaml 

- Markdown prompt files 

## **Extensibility Constraint** 

Adding a new input source should require only: 

- A new adapter. 

- Configuration updates. 

Core processing should remain unchanged. 

## **23. Edge Cases** 

The system must explicitly handle the following scenarios. 

## **Invalid URL** 

Input: 

https://example.invalid 

Expected: 

- Reject request. 

- Notify user. 

- Do not start pipeline. 

## **Private Content** 

If a resource cannot legally or technically be accessed: 

- Stop processing. 

- Explain the limitation. 

- Preserve audit logs. 

## **Unsupported Platform** 

If a user submits an unsupported platform: 

- Reject gracefully. 

- Suggest supported sources. 

## **Empty Transcript** 

If transcription produces no usable output: 

Continue with: 

- OCR 

- Metadata 

- Caption 

Do not fail immediately. 

## **OCR Failure** 

If OCR cannot detect text: 

Continue processing. 

Record warning. 

## **OpenRouter Timeout** 

Retry three times. 

If still unsuccessful: 

- Mark stage as failed. 

- Continue where possible. 

- Notify user. 

## **Duplicate Resource** 

Do not create a second record. 

Merge intelligently. 

Update relationships. 

## **Missing Official Website** 

If enrichment fails: 

Store resource with available information. 

Mark enrichment status as incomplete. 

## **Multiple Resources With Similar Names** 

Example: 

Next.js 

Next Auth 

Next UI 

The enrichment stage must distinguish them correctly. 

## **Broken Media** 

If downloaded media cannot be processed: 

Delete temporary files. 

Record error. 

Notify user. 

## **24. Security & Privacy** 

## **Security Principles** 

KnowledgeFlow is a personal application. 

Despite this, security should be treated as a first-class concern. 

## **Secrets Management** 

Secrets include: 

- OpenRouter API Key 

- Telegram Bot Token 

 Notion Integration Token 

## Rules: 

- Never commit secrets. 

- Load from environment. 

- Validate during startup. 

## **Temporary Files** 

Downloaded media is temporary. 

Policy: 

- Cache during processing. 

- Delete after success. 

- Retain only when --keep-cache is enabled. 

## **Logging** 

Logs must never include: 

- API keys 

- Tokens 

- Credentials 

- Authorization headers 

## **User Privacy** 

KnowledgeFlow should only process content explicitly submitted by the user. 

No background monitoring. 

No automatic scraping of accounts. 

No telemetry. 

No analytics. 

## **Data Ownership** 

All processed knowledge belongs to the user. 

KnowledgeFlow does not retain external copies. 

## **25. Risks** 

## **Platform Changes** 

Instagram, YouTube, X, and LinkedIn may change APIs or restrict automated access. Mitigation: 

- Adapter abstraction. 

- Independent downloader modules. 

## **AI Hallucination** 

LLMs may invent entities or relationships. 

Mitigation: 

- Deterministic extraction first. 

- Structured prompts. 

- Schema validation. 

- Confidence scoring. 

## **OCR Accuracy** 

Poor video quality may reduce OCR performance. 

Mitigation: 

- Adaptive frame selection. 

- Confidence thresholds. 

- User warnings. 

## **Duplicate Detection** 

Different spellings may refer to the same resource. 

Mitigation: 

- Normalized URLs. 

- Fuzzy matching. 

- Manual review (future). 

## **Third-Party Availability** 

External APIs may be unavailable. 

Mitigation: 

- Retry strategy. 

- Graceful degradation. 

- Partial processing. 

## **26. Release Milestones** 

## **Version 0.1** 

Foundation 

- Repository 

- Documentation 

- Configuration 

- KnowledgeGraph 

- Telegram Adapter 

## **Version 0.2** 

## Processing 

- Downloader 

- OCR 

- Transcript 

- Metadata 

## **Version 0.3** 

Knowledge Engine 

- Resource Extraction 

- Categorization 

- Enrichment 

- Deduplication 

## **Version 0.4** 

Persistence 

- Notion Adapter 

- Settings 

- Progress Tracking 

## **Version 1.0** 

Stable MVP 

- Complete pipeline 

- Automated testing 

- Docker support 

- Open-source release 

## **27. Future Roadmap** 

Potential future enhancements: 

## **Integrations** 

- Discord 

- Slack 

- Email 

- Obsidian 

- Google Docs 

## **AI Features** 

- Semantic search 

- Retrieval-Augmented Generation (RAG) 

- AI chat over saved knowledge 

- Daily knowledge digest 

## **Platform Expansion** 

- Browser extension 

- Web dashboard 

- Desktop application 

- Mobile companion 

## **Advanced Knowledge Management** 

- Automatic relationship discovery 

- Knowledge graph visualization 

- Resource recommendation 

- Learning paths 

## **28. Product Principles** 

Every future feature should satisfy the following principles: 

1. Keep the KnowledgeGraph as the canonical model. 

2. Prefer deterministic extraction before AI. 

3. Treat adapters as replaceable plugins. 

4. Design for extensibility. 

5. Preserve user ownership of data. 

6. Minimize operational cost. 

7. Maintain clear separation of concerns. 

8. Keep the MVP focused and maintainable. 

## **29. Appendix A — Terminology** 

## **Term Definition** 

KnowledgeGraph Central in-memory representation of extracted knowledge. 

Adapter Component that interfaces with an external system. Agent Independent processing unit responsible for a single task. Resource Any extracted educational asset (tool, book, URL, API, etc.). Enrichment Adding verified metadata to an extracted resource. Deduplication Merging resources representing the same entity. 

## **30. PRD Completion Criteria** 

This PRD is considered complete when: 

- All functional requirements are implemented. 

- All acceptance criteria are satisfied. 

- Every feature maps to an implementation task. 

- All architectural decisions are documented. 

- The project can be built without undocumented assumptions. 

**End of Part 3** 

