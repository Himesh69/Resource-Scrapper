## 12-API_SPEC.md 

## API Specification 

**Project:** Instagram AI Research & Content Intelligence Platform 

**Version:** 1.0 

**Status:** Production Design 

## Document Overview 

## Purpose 

This document defines the REST API specification for the Instagram AI Research & Content Intelligence Platform. The API acts as the communication layer between the frontend, AI agents, databases, and external services. It follows RESTful principles, supports asynchronous workflows, and provides consistent request/response formats. 

## Objectives 

The API is designed to: 

- Expose all platform functionality through REST endpoints 

- Support authentication and authorization 

- Provide consistent request and response schemas 

- Enable AI workflow orchestration 

- Support asynchronous job execution 

- Ensure scalability and maintainability 

- Simplify frontend integration 

## Base URL 

Production: https://api.instagram-ai.com/v1 

Development: http://localhost:8000/api/v1 

## API Architecture 

text id="g2wq4n" Frontend           API Gateway           FastAPI Backend       │ ▼ │ ▼ │ ┌──┼───────────────┐▼▼                    Database        AI Agents                                    ▼ │ │▼ ▼ Redis        Vector Store 

## Authentication 

The API uses JWT-based authentication. 

## Headers 

Authorization: Bearer <access_token> Content-Type: application/json 

## Standard Response Format 

## Success 

json id="r1h3zt" {   "success": true,   "message": "Operation completed successfully.", "data": {},   "timestamp": "2026-06-26T12:00:00Z" } 

## Error 

json id="cx8d7m" {   "success": false,   "error": {     "code": "VALIDATION_ERROR", "message": "Invalid request payload."   },   "timestamp": "2026-06-26T12:00:00Z" } 

## Authentication Endpoints 

## Register User 

POST /auth/register 

Request 

json id="f8m2lp" {   "name": "John Doe",   "email": "john@example.com",   "password": "********" } 

## Login 

POST /auth/login 

## Response 

json id="n5q7yu" {   "access_token": "",   "refresh_token": "",   "expires_in": 3600 } 

Refresh Token 

POST /auth/refresh 

## Logout 

POST /auth/logout 

## User Endpoints 

Get Current User 

GET /users/me 

## Update Profile 

PUT /users/me 

Delete Account 

DELETE /users/me 

## Research API 

## Create Research Job 

POST /research 

## Request 

json id="r4s6bk" {   "username": "creator_name",   "platform": "instagram", "analysis_type": "full" } 

## Get Research Report 

GET /research/{research_id} 

## List Research Reports 

GET /research 

## Delete Research 

DELETE /research/{research_id} 

## Creator API 

## Get Creator 

GET /creators/{username} 

## Search Creators 

GET /creators/search 

Query Parameters: 

- keyword 

- category 

- country 

- followers_min 

 followers_max 

## Competitor API 

## Analyze Competitors 

POST /competitors/analyze 

## List Competitors 

GET /competitors 

## Trend API 

## Get Trending Topics 

GET /trends 

## Analyze Trend 

POST /trends/analyze 

## Content Generation API 

## Generate Caption 

POST /content/caption 

Request 

json id="y7l0ne" {   "topic": "AI Tools",   "tone": "Professional",   "length": "Medium" } 

Generate Reel Script 

POST /content/reel 

## Generate Carousel 

POST /content/carousel 

## Generate Content Calendar 

POST /content/calendar 

## Prompt API 

List Prompts 

GET /prompts 

## Create Prompt 

POST /prompts 

Update Prompt 

PUT /prompts/{prompt_id} 

Delete Prompt 

DELETE /prompts/{prompt_id} 

## AI Agent API 

Execute Agent 

POST /agents/run 

Request 

json id="v6p9fd" {   "agent": "research",   "input": {     "username": "creator_name"   } } 

## Get Agent Status 

GET /agents/{job_id} 

## Cancel Agent Job 

DELETE /agents/{job_id} 

## Knowledge Graph API 

## Search Entities 

GET /knowledge/search 

## Get Entity 

GET /knowledge/entity/{id} 

## Create Relationship 

POST /knowledge/relationship 

## Analytics API 

## Dashboard Metrics 

GET /analytics/dashboard 

## Usage Statistics 

GET /analytics/usage 

## AI Metrics 

GET /analytics/ai 

## Reports API 

## Generate Report 

POST /reports 

## Download Report 

GET /reports/{id}/download 

## List Reports 

GET /reports 

## Notifications API 

## Get Notifications 

GET /notifications 

## Mark as Read 

PUT /notifications/{id}/read 

## Webhooks 

## Workflow Completed 

POST /webhooks/workflow-completed 

## Research Finished 

POST /webhooks/research-completed 

## AI Generation Completed 

POST /webhooks/ai-finished 

## Pagination 

Standard query parameters: 

?page=1 &limit=20 &sort=created_at &order=desc 

## Filtering 

Supported parameters: 

- category 

- status 

- date_from 

- date_to 

- keyword 

- platform 

- user_id 

## HTTP Status Codes 

|Code|Meaning|
|---|---|
|200|Success|
|201|Created|
|202|Accepted|
|204|No Content|
|400|Bad Request|
|401|Unauthorized|
|403|Forbidden|



|Code|Meaning|
|---|---|
|404|Not Found|
|409|Confict|
|422|Validation Error|
|429|Too Many Requests|
|500|Internal Server Error|



## Rate Limiting 

Default limits: 

|Default limits:||
|---|---|
|Endpoint|Limit|
|Authentication|10 requests/minute|
|AI Generation|20 requests/minute|
|Research|30 requests/minute|
|Analytics|60 requests/minute|
|General API|100 requests/minute|



## API Versioning 

The platform follows URI versioning. 

/api/v1/ /api/v2/ 

Backward compatibility is maintained within major versions. 

## Security 

The API implements: 

- JWT authentication 

- HTTPS only 

- CORS protection 

- Input validation 

- Rate limiting 

- SQL injection prevention 

- XSS protection 

- CSRF mitigation (where applicable) 

- Audit logging 

## Error Handling 

Every error response includes: 

- Error code 

- Human-readable message 

- Timestamp 

- Request ID 

- Optional validation details 

## API Documentation 

Interactive documentation is automatically generated using OpenAPI. 

Available endpoints: 

/swagger /redoc /openapi.json 

## Future Enhancements 

- GraphQL endpoint 

- WebSocket support for real-time updates 

- Batch API operations 

- API key authentication 

- Multi-tenant support 

- SDKs for JavaScript and Python 

- Streaming AI responses 

## Summary 

The API specification provides a consistent, secure, and scalable interface for all platform components. By standardizing endpoint design, authentication, request/response formats, and error handling, the API enables seamless integration between the frontend, AI agents, databases, and external services while remaining extensible for future platform growth. 

