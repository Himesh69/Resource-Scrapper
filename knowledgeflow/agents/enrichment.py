"""
KnowledgeFlow — Enrichment Agent

Enriches extracted resources with official metadata.
- GitHub repos: fetches star count, description, and primary language from GitHub API.
- Websites: fetches HTML title and OpenGraph description.
- Fallback: uses LLM enrichment if HTTP fetches fail or if a resource has no URL.
"""
from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse
import structlog
from bs4 import BeautifulSoup
import httpx

from agents.base import BaseAgent
from core.exceptions import LLMError
from core.knowledge_graph import KnowledgeGraph, Resource
from llm.client import LLMClient
from utils.prompt_loader import render_prompt

log = structlog.get_logger(__name__)

# Pattern to identify GitHub repository URLs
_GITHUB_REPO_RE = re.compile(r'github\.com/([^/]+)/([^/]+?)(?:/|\.git|$)')


class EnrichmentAgent(BaseAgent):
    """
    Agent responsible for enriching Resource objects using HTTP requests and LLM fallbacks.
    """

    def __init__(self, client: LLMClient) -> None:
        super().__init__(name="EnrichmentAgent")
        self.client = client

    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        if not kg.resources:
            self._log.info("enrichment.skipped", reason="No resources to enrich")
            return kg

        self._log.info("enrichment.start", count=len(kg.resources))

        # Process all resources in parallel to save time
        tasks = [self._enrich_resource(res, kg.source.summary + " " + kg.source.description) for res in kg.resources]
        enriched_resources = await asyncio.gather(*tasks)

        kg.resources = list(enriched_resources)
        self._log.info("enrichment.success", enriched_count=sum(1 for r in kg.resources if r.enriched))
        return kg

    async def _enrich_resource(self, res: Resource, context: str) -> Resource:
        """Enrich a single resource. First tries HTTP/API, then falls back to LLM."""
        log_ctx = self._log.bind(resource_name=res.name, url=res.url)

        if not res.url:
            # If there is no URL, we must use LLM to describe it
            log_ctx.debug("enrich.llm_fallback_only", reason="No URL provided")
            return await self._enrich_via_llm(res, context)

        # Parse URL to see if it's GitHub
        parsed = urlparse(res.url)
        github_match = _GITHUB_REPO_RE.search(parsed.netloc + parsed.path)

        success = False
        if github_match:
            owner, repo = github_match.groups()
            success = await self._enrich_github(res, owner, repo)
        
        if not success:
            # Try regular website metadata extraction
            success = await self._enrich_website(res)

        if success:
            res.enriched = True
            log_ctx.debug("enrich.http_success")
        else:
            # Fallback to LLM enrichment if HTTP failed
            log_ctx.debug("enrich.http_failed", reason="Enriching via LLM")
            res = await self._enrich_via_llm(res, context)

        return res

    async def _enrich_github(self, res: Resource, owner: str, repo: str) -> bool:
        """Fetch repository details from the official GitHub API."""
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {"User-Agent": "KnowledgeFlow-App"}
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(api_url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    stars = data.get("stargazers_count", 0)
                    lang = data.get("language")
                    desc = data.get("description") or ""
                    
                    res.name = data.get("full_name", res.name)
                    res.description = desc.strip()
                    
                    # Add stats to tags / description for visibility
                    if lang and lang.lower() not in [t.lower() for t in res.tags]:
                        res.tags.append(lang.lower())
                    if stars > 0:
                        res.tags.append(f"★ {stars}")
                    
                    return True
        except Exception as exc:
            self._log.debug("enrich.github.failed", error=str(exc))
        return False

    async def _enrich_website(self, res: Resource) -> bool:
        """Fetch title and description from general website HTML."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                response = await client.get(res.url, headers=headers)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    # 1. Title extraction
                    title_tag = soup.find("title")
                    title = title_tag.text.strip() if title_tag else ""
                    
                    # Check OpenGraph title
                    og_title = soup.find("meta", property="og:title")
                    if og_title and og_title.get("content"):
                        title = og_title.get("content").strip()
                        
                    # 2. Description extraction
                    desc = ""
                    og_desc = soup.find("meta", property="og:description")
                    if og_desc and og_desc.get("content"):
                        desc = og_desc.get("content").strip()
                    else:
                        meta_desc = soup.find("meta", attrs={"name": "description"})
                        if meta_desc and meta_desc.get("content"):
                            desc = meta_desc.get("content").strip()

                    # Apply extracted metadata
                    if title:
                        # Only overwrite name if it was just a raw domain fallback
                        if res.name.lower() in res.url.lower():
                            res.name = title[:60]
                    if desc:
                        res.description = desc
                        return True
        except Exception as exc:
            self._log.debug("enrich.website.failed", error=str(exc))
        return False

    async def _enrich_via_llm(self, res: Resource, context: str) -> Resource:
        """Fallback to LLM for description and tags generation."""
        try:
            prompt = render_prompt(
                "enrichment",
                name=res.name,
                resource_type=res.resource_type.value,
                url=res.url or "N/A",
                context=context,
            )
        except FileNotFoundError:
            self._log.warning("enrich.prompt_missing")
            return res

        messages = [
            {"role": "system", "content": "You are a Resource Enrichment assistant that outputs strict JSON."},
            {"role": "user", "content": prompt}
        ]

        try:
            res_dict = await self.client.complete_json(
                task="enrichment",
                messages=messages,
                agent_name=self.name
            )

            res.name = res_dict.get("name", res.name).strip()
            res.description = res_dict.get("description", res.description).strip()
            
            tags = res_dict.get("tags", [])
            for t in tags:
                if t.strip() and t.strip().lower() not in [tag.lower() for tag in res.tags]:
                    res.tags.append(t.strip())

            res.enriched = True
        except Exception as exc:
            self._log.warning("enrich.llm_fallback.failed", error=str(exc))
        
        return res
