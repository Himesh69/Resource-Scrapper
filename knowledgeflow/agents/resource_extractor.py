"""
KnowledgeFlow — Resource Extractor Agent

Identifies educational resources (books, papers, GitHub repos, courses, tools, etc.) mentioned in the content.
Uses LLM resource extraction followed by a deterministic regex URL matcher fallback.

Filtering philosophy:
  - No HTTP health checks (slow, unreliable, social links reject HEAD requests)
  - LLM resources without a URL must have confidence >= 0.75 AND be Prompt/Template/Book/Paper type
  - Regex fallback only matches explicit http/https URLs and well-known short link domains
  - Never add the source platform (instagram.com, youtube.com, etc.) as a resource
"""
from __future__ import annotations

import re
from urllib.parse import urlparse
import structlog

from agents.base import BaseAgent
from core.exceptions import LLMError, AgentError
from core.knowledge_graph import KnowledgeGraph, Resource, ResourceType
from llm.client import LLMClient
from utils.prompt_loader import render_prompt
from utils.url_parser import normalize_url

log = structlog.get_logger(__name__)

# Only match explicit http/https URLs and well-known short-link / link-in-bio domains
# Does NOT match bare domains like "twitter.com" or "toolname.ai" in free text to avoid noise
_URL_RE = re.compile(
    r'(?:'
    r'https?://[^\s<>"\')\]]+|'              # Explicit http/https URLs
    r'\b(?:bit\.ly|tinyurl\.com|t\.co|'      # Common short-link domains
    r'linktr\.ee|lnk\.to|stan\.store|'       # Link-in-bio services
    r'beacons\.ai|carrd\.co|tap\.bio|'
    r'msha\.ke|hoo\.be)'
    r'/[^\s<>"\')\]]*'                        # …followed by a path
    r')',
    re.IGNORECASE
)

# Platform domains we must never add as resources
_PLATFORM_DOMAINS = frozenset({
    "instagram.com", "youtube.com", "youtu.be",
    "tiktok.com", "twitter.com", "x.com",
    "facebook.com", "fb.com", "linkedin.com",
    "threads.net", "snapchat.com", "pinterest.com",
})

# Minimum confidence for LLM-extracted resources that have no URL
_MIN_CONFIDENCE_NO_URL = 0.75


def _is_platform_url(url: str) -> bool:
    """Return True if this URL points to a content-hosting platform we should skip."""
    try:
        netloc = urlparse(url).netloc.lower().lstrip("www.")
        return any(netloc == domain or netloc.endswith("." + domain) for domain in _PLATFORM_DOMAINS)
    except Exception:
        return False


class ResourceExtractorAgent(BaseAgent):
    """
    Agent responsible for extracting resources (links, repositories, tools, books).
    """

    def __init__(self, client: LLMClient) -> None:
        super().__init__(name="ResourceExtractorAgent")
        self.client = client

    async def _process_impl(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        self._log.info("resource_extractor.start")

        # 1. Load and render prompt template
        try:
            prompt = render_prompt(
                "resource_extraction",
                caption=f"Caption: {kg.source.description or 'None'}\nOCR Text: {kg.metadata.ocr_text or 'None'}",
                pinned_comment=kg.source.pinned_comment or "No pinned comment.",
                summary=kg.source.summary or "No summary available.",
                ocr_text=kg.metadata.ocr_text or "No OCR text extracted.",
            )
        except FileNotFoundError as exc:
            raise AgentError(self.name, f"Prompt template missing: {exc}", recoverable=False)

        messages = [
            {"role": "system", "content": "You are a Resource Extraction assistant that outputs strict JSON."},
            {"role": "user", "content": prompt}
        ]

        # 2. Extract resources via LLM
        llm_resources: list[Resource] = []
        try:
            res_dict = await self.client.complete_json(
                task="extraction",
                messages=messages,
                agent_name=self.name
            )

            raw_resources = res_dict.get("resources", [])
            for r_data in raw_resources:
                try:
                    # Clean up resource type
                    r_type_str = r_data.get("resource_type")
                    r_type = ResourceType.OTHER
                    for val in ResourceType:
                        if r_type_str and val.value.lower() == r_type_str.lower():
                            r_type = val
                            break
                    r_data["resource_type"] = r_type

                    # Skip resources with no name
                    if not r_data.get("name"):
                        continue

                    url = r_data.get("url", "").strip() or None

                    # Skip if the URL points to the source platform itself
                    if url and _is_platform_url(url):
                        self._log.debug("resource_extractor.skipped_platform_url", url=url)
                        continue

                    # Resources without a URL are kept if they are not explicitly Websites
                    # AND the LLM is confident enough.
                    if not url:
                        confidence = float(r_data.get("confidence", 0))
                        if r_type == ResourceType.WEBSITE or confidence < _MIN_CONFIDENCE_NO_URL:
                            self._log.debug(
                                "resource_extractor.skipped_no_url",
                                name=r_data.get("name"),
                                type=r_type,
                                confidence=confidence,
                            )
                            continue

                    resource = Resource.model_validate(r_data)
                    llm_resources.append(resource)

                except Exception as val_exc:
                    self._log.warning("resource_extractor.validation_failed", data=r_data, error=str(val_exc))

        except LLMError:
            raise
        except Exception as exc:
            self._log.error("resource_extractor.llm_failed", error=str(exc))
            kg.add_warning(f"ResourceExtractor LLM failed: {exc}. Relying on regex fallback only.")

        # 3. Post-extraction anti-hallucination: validate URLs against source text
        # Collect all raw text where URLs could legitimately appear
        raw_source_texts = "\n".join(filter(None, [
            kg.source.description,
            kg.source.pinned_comment,
            kg.metadata.ocr_text,
        ])).lower()

        validated_resources: list[Resource] = []
        for r in llm_resources:
            if r.url:
                # Check if the URL (or a meaningful fragment) appears in the raw text
                url_lower = r.url.lower().strip()
                # Strip protocol for matching — source text may have "github.com/x" without "https://"
                url_bare = url_lower.replace("https://", "").replace("http://", "").rstrip("/")

                if url_lower in raw_source_texts or url_bare in raw_source_texts:
                    validated_resources.append(r)
                else:
                    # Check if at least the domain+first-path-segment appears
                    try:
                        parsed = urlparse(r.url)
                        domain_path = parsed.netloc.lower().lstrip("www.")
                        if parsed.path and parsed.path != "/":
                            first_segment = parsed.path.strip("/").split("/")[0]
                            domain_path += "/" + first_segment
                        if domain_path in raw_source_texts:
                            validated_resources.append(r)
                        else:
                            self._log.info(
                                "resource_extractor.hallucinated_url_dropped",
                                name=r.name,
                                url=r.url,
                            )
                    except Exception:
                        self._log.info("resource_extractor.hallucinated_url_dropped", name=r.name, url=r.url)
            else:
                # URL-less resources (prompts, books) — already filtered above, keep them
                validated_resources.append(r)

        # 4. Append validated LLM resources
        for r in validated_resources:
            kg.add_resource(r)

        # 5. Regex Fallback — only explicit http/https URLs and short-link services
        # Scans: caption, pinned comment, OCR text (NOT the LLM summary to avoid double-counting)
        raw_text_sources = [
            kg.source.description,
            kg.source.pinned_comment,
            kg.metadata.ocr_text,
        ]

        extracted_urls: set[str] = set()
        for text in raw_text_sources:
            if text:
                for match in _URL_RE.findall(text):
                    url = match.strip().rstrip(".,;!)?]}")
                    # Ensure it has a scheme
                    if not url.startswith("http"):
                        url = "https://" + url
                    try:
                        parsed = urlparse(url)
                        if parsed.netloc:
                            normalized = normalize_url(url)
                            extracted_urls.add(normalized)
                    except Exception:
                        pass

        # 6. Add any regex URLs not already covered by LLM extraction
        existing_urls = {normalize_url(r.url) for r in kg.resources if r.url}
        source_url = normalize_url(kg.input_url) if kg.input_url else None

        fallback_count = 0
        for url in extracted_urls:
            # Skip if already covered or is the source itself
            if url in existing_urls or url == source_url:
                continue
            # Skip platform URLs
            if _is_platform_url(url):
                continue

            # Derive a clean display name from the domain/path
            try:
                parsed = urlparse(url)
                name = parsed.netloc.lstrip("www.").split(".")[0].capitalize()
                # Use path segment as hint if domain is a short-link service
                short_link_domains = {"bit.ly", "tinyurl.com", "t.co", "linktr.ee", "lnk.to"}
                if parsed.netloc.lstrip("www.") in short_link_domains:
                    name = f"Link ({parsed.netloc})"
            except Exception:
                name = "Reference Link"

            fallback_res = Resource(
                name=name,
                resource_type=ResourceType.WEBSITE,
                url=url,
                description="Extracted directly from source text.",
                confidence=0.8,
            )
            kg.add_resource(fallback_res)
            existing_urls.add(url)
            fallback_count += 1

        self._log.info(
            "resource_extractor.success",
            total_extracted=len(kg.resources),
            regex_fallback_added=fallback_count,
        )
        return kg
