## 09-PROMPTS.md 

## Prompt Engineering Specification 

**Project:** Instagram AI Research & Content Intelligence Platform 

**Version:** 1.0 

**Status:** Production Design 

## Document Overview 

## Purpose 

This document defines the prompt engineering framework used throughout the Instagram AI Research & Content Intelligence Platform. 

Every AI-powered feature—research, trend analysis, caption generation, semantic search, workflow orchestration, and reporting—is driven by standardized prompt templates. This document establishes a consistent prompt architecture that produces reliable, structured, and repeatable outputs across different Large Language Models (LLMs). 

## Objectives 

The prompt system is designed to: 

- Standardize AI interactions 

- Produce deterministic outputs 

- Minimize hallucinations 

- Improve response quality 

- Support multiple LLM providers 

- Enable reusable prompt templates 

- Reduce token usage 

- Simplify prompt maintenance 

- Ensure structured JSON responses 

- Support version-controlled prompt evolution 

## Prompt Engineering Principles 

Every prompt follows these core principles: 

Context First 

Provide sufficient domain context before asking the model to perform a task. 

## Explicit Instructions 

State exactly what the model should do, avoiding ambiguous language. 

## Structured Outputs 

Prefer JSON or Markdown with predefined sections over free-form text. 

## Role Assignment 

Assign a clear role (e.g., Instagram strategist, data analyst, content creator) to improve consistency. 

## Constraint Definition 

Specify limits such as tone, word count, format, and prohibited content. 

## Output Validation 

Require the model to follow a predefined schema for easier parsing. 

## Prompt Architecture 

Each prompt is composed of multiple layers. 

System Prompt │ ▼ Context Injection │ ▼ Knowledge Retrieval │ ▼ User Input │ ▼ 

Prompt Template │ ▼ LLM Response │ ▼ Output Validation 

## Prompt Components 

|Component|Purpose|
|---|---|
|System Prompt|Defnes the AI’s role and behavior|
|Context|Injects relevant research and|
||retrieved knowledge|
|User Request|Specifes the user’s task|
|Constraints|Defnes formatting and behavioral|
||rules|
|Examples|Provides few-shot guidance if|
||needed|
|Output Schema|Specifes the required response|
||format|



## System Prompt Template 

You are an AI assistant specializing in Instagram growth, content strategy, competitor analysis, audience research, and social media intelligence. 

Your objectives: 

- Produce accurate and actionable insights. 

- Use structured reasoning. 

- Avoid unsupported claims. 

- Respond in Markdown or JSON when requested. 

- Maintain a professional tone. 

- Base recommendations on the provided context. 

## Research Prompt 

## Purpose 

Generate detailed research reports for Instagram creators, brands, or niches. 

## Input 

- Username 

- Niche 

- Competitor data 

- Audience information 

## Prompt Template 

Analyze the following Instagram profile. 

Include: 

1. Profile overview 

2. Content strategy 

3. Posting frequency 

4. Engagement patterns 

5. Audience insights 

6. Competitor comparison 

7. Growth opportunities 

8. Actionable recommendations 

Return the output in Markdown. 

## Competitor Analysis Prompt 

Compare the following Instagram accounts. 

Evaluate: 

- Content quality 

- Engagement 

- Hashtag strategy 

- Posting consistency 

- Branding 

- Audience targeting 

Highlight strengths, weaknesses, and opportunities. 

## Caption Generation Prompt 

Create an Instagram caption using the following information. 

Requirements: 

- Strong hook 

- Storytelling 

- Call-to-action 

- SEO-friendly keywords 

- Relevant emojis 

- Maximum 180 words 

## Hashtag Recommendation Prompt 

Generate 30 hashtags. 

Group them into: 

- High competition 

- Medium competition 

- Low competition 

- Niche-specific 

Return as a Markdown table. 

## Trend Analysis Prompt 

Analyze recent Instagram content. 

Identify: 

- Emerging topics 

- Viral formats 

- Trending hashtags 

- Posting patterns 

- Audience interests 

Provide a confidence score for each trend. 

## Content Calendar Prompt 

Generate a 30-day Instagram content calendar. 

Include: 

- Posting date 

- Content type 

- Caption idea 

- CTA 

- Recommended hashtags 

- Suggested posting time 

## Reel Script Prompt 

Generate a 60-second Instagram Reel script. 

Structure: 

Hook 

↓ 

Problem 

↓ 

Solution 

↓ 

Call-to-Action 

Tone: Conversational and engaging. 

## Audience Persona Prompt 

Create a detailed audience persona. 

Include: 

- Age 

- Interests 

- Pain points 

- Goals 

- Preferred content 

- Buying behavior 

- Online activity 

## Knowledge Graph Extraction Prompt 

Extract all entities and relationships. 

Entities: 

- Creator 

- Brand 

- Topic 

- Hashtag 

- Product 

- Campaign 

Relationships: 

Creator → Posts 

Posts → Topics 

Topics → Hashtags 

Output JSON only. 

## JSON Output Template 

{ "summary": "", "insights": [], "recommendations": [], "confidence": 0.95, "metadata": { "model": "", "timestamp": "", "tokens_used": 0 } } 

## Prompt Versioning 

Each prompt is version-controlled. 

|Version|Description|
|---|---|
|v1|Initial implementation|
|v2|Improved formatting|
|v3|Added JSON schema|
|v4|Added validation rules|
|v5|Optimized token usage|



## Prompt Repository Structure 

prompts/ │ ├── system/ │├── research.md │├── trend.md │├── caption.md │├── report.md │└── planner.md │ ├── templates/ 

- │├── creator_analysis.md 

- │├── competitor.md 

│├── audience.md │└── content_calendar.md │ ├── validation/ │├── json_schema.md │├── output_checks.md │└── safety.md │ └── versions/ ├── v1/ ├── v2/ └── v3/ 

## Prompt Validation 

Before accepting an AI response, validate: 

- Required fields are present 

- JSON is syntactically correct 

- Word limits are respected 

- No unsupported claims are made 

- Formatting rules are followed 

## Prompt Optimization Techniques 

- Context compression 

- Retrieval-Augmented Generation (RAG) 

- Few-shot examples 

- Role prompting 

- Chain-of-thought (internal use) 

- Self-consistency checks 

- Structured output schemas 

- Token budgeting 

## Error Handling 

If the model cannot complete a task: 

1. Retry with a simplified prompt. 

2. Reduce context size. 

3. Use fallback templates. 

4. Log the failure. 

5. Return a user-friendly message. 

## Security Considerations 

- Sanitize user inputs before prompt construction. 

- Prevent prompt injection through validation. 

- Restrict sensitive system instructions. 

- Avoid exposing internal prompts to end users. 

- Log prompt executions for auditing. 

## Monitoring Metrics 

Track: 

- Prompt latency 

- Token usage 

- Success rate 

- Retry count 

- Validation failures 

- Model cost 

- User satisfaction 

## Future Improvements 

- Automatic prompt optimization 

- A/B testing of prompt variants 

- Adaptive prompt selection 

- Multi-model routing 

- Prompt analytics dashboard 

- Reinforcement learning from user feedback 

## Summary 

The prompt engineering framework provides a standardized, reusable, and secure foundation for all AI interactions within the platform. By combining structured templates, context injection, validation, and version control, the system delivers consistent, highquality outputs while remaining flexible enough to support future AI models and evolving business requirements. 

