"""
core/search_providers.py
=====================
Multi-provider Web Search for Nexus Core.

Supports:
- Tavily (cloud, AI-optimized search)
- Firecrawl (cloud, markdown extraction)
- SerpAPI (cloud, Google search results)
- DuckDuckGo (free, no API key)

Common interface:
    search(query: str) -> dict  # Returns results dict
"""

from __future__ import annotations

import logging
import os
from core.api_keys import get_api_key
from typing import Optional

logger = logging.getLogger("SearchProviders")


class SearchProvider:
    """Base class for search providers."""

    name: str = "base"
    available: bool = False
    init_error: Optional[str] = None

    def search(self, query: str) -> dict:
        raise NotImplementedError


# ══════════════════════════════════════════════════════════════════════════════
# Tavily Search
# ══════════════════════════════════════════════════════════════════════════════


class TavilyProvider(SearchProvider):
    name = "tavily"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = get_api_key("tavily_api_key", "TAVILY_API_KEY", api_key)
        self._available = bool(self.api_key)
        self._init_error: Optional[str] = None
        if not self.api_key:
            self._init_error = "TAVILY_API_KEY not set"

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def search(self, query: str) -> dict:
        if not self._available:
            return {"error": self._init_error or "Tavily not configured", "results": []}
        try:
            import requests
            resp = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": True,
                    "include_images": False,
                    "include_raw_content": False,
                    "max_results": 5,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "answer": data.get("answer", ""),
                    "results": data.get("results", []),
                    "provider": "tavily",
                }
            logger.error(f"Tavily error {resp.status_code}: {resp.text[:200]}")
            return {"error": f"HTTP {resp.status_code}", "results": []}
        except Exception as exc:
            logger.error(f"Tavily search error: {exc}")
            return {"error": str(exc), "results": []}


# ══════════════════════════════════════════════════════════════════════════════
# Firecrawl Search
# ══════════════════════════════════════════════════════════════════════════════


class FirecrawlProvider(SearchProvider):
    name = "firecrawl"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = get_api_key("firecrawl_api_key", "FIRECRAWL_API_KEY", api_key)
        self._available = bool(self.api_key)
        self._init_error: Optional[str] = None
        if not self.api_key:
            self._init_error = "FIRECRAWL_API_KEY not set"

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def search(self, query: str) -> dict:
        if not self._available:
            return {"error": self._init_error or "Firecrawl not configured", "results": []}
        try:
            import requests
            resp = requests.post(
                "https://api.firecrawl.dev/v0/search",
                json={
                    "apiKey": self.api_key,
                    "query": query,
                    "limit": 5,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "answer": data.get("data", {}).get("answer", ""),
                    "results": data.get("data", {}).get("web", []),
                    "provider": "firecrawl",
                }
            logger.error(f"Firecrawl error {resp.status_code}: {resp.text[:200]}")
            return {"error": f"HTTP {resp.status_code}", "results": []}
        except Exception as exc:
            logger.error(f"Firecrawl search error: {exc}")
            return {"error": str(exc), "results": []}


# ══════════════════════════════════════════════════════════════════════════════
# SerpAPI Search
# ══════════════════════════════════════════════════════════════════════════════


class SerpAPIProvider(SearchProvider):
    name = "serpapi"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = get_api_key("serpapi_api_key", "SERPAPI_API_KEY", api_key)
        self._available = bool(self.api_key)
        self._init_error: Optional[str] = None
        if not self.api_key:
            self._init_error = "SERPAPI_API_KEY not set"

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def search(self, query: str) -> dict:
        if not self._available:
            return {"error": self._init_error or "SerpAPI not configured", "results": []}
        try:
            import requests
            resp = requests.get(
                "https://serpapi.com/search",
                params={
                    "api_key": self.api_key,
                    "q": query,
                    "engine": "google",
                    "num": 5,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "answer": data.get("answer_box", {}).get("answer", ""),
                    "results": data.get("organic_results", []),
                    "provider": "serpapi",
                }
            logger.error(f"SerpAPI error {resp.status_code}: {resp.text[:200]}")
            return {"error": f"HTTP {resp.status_code}", "results": []}
        except Exception as exc:
            logger.error(f"SerpAPI search error: {exc}")
            return {"error": str(exc), "results": []}


# ══════════════════════════════════════════════════════════════════════════════
# DuckDuckGo Search (Free, no API key)
# ══════════════════════════════════════════════════════════════════════════════


class DuckDuckGoProvider(SearchProvider):
    name = "duckduckgo"

    def __init__(self, **kwargs):
        self._available = True
        self._init_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def search(self, query: str) -> dict:
        try:
            import requests
            resp = requests.post(
                "https://api.duckduckgo.com/",
                data={
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "no_redirect": 1,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for r in data.get("RelatedTopics", [])[:5]:
                    results.append({
                        "title": r.get("Title", ""),
                        "url": r.get("FirstURL", ""),
                        "content": r.get("Abstract", ""),
                    })
                return {
                    "answer": data.get("AbstractText", ""),
                    "results": results,
                    "provider": "duckduckgo",
                }
            return {"error": f"HTTP {resp.status_code}", "results": []}
        except Exception as exc:
            logger.error(f"DuckDuckGo search error: {exc}")
            return {"error": str(exc), "results": []}


# ══════════════════════════════════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════════════════════════════════


_PROVIDER_REGISTRY: dict[str, type[SearchProvider]] = {
    "tavily": TavilyProvider,
    "firecrawl": FirecrawlProvider,
    "serpapi": SerpAPIProvider,
    "duckduckgo": DuckDuckGoProvider,
}


def get_search_provider(provider_id: str, **kwargs) -> Optional[SearchProvider]:
    """Instantiate a search provider by ID."""
    cls = _PROVIDER_REGISTRY.get(provider_id)
    if cls is None:
        logger.error(f"Unknown search provider: {provider_id}")
        return None
    try:
        return cls(**kwargs)
    except Exception as exc:
        logger.error(f"Failed to instantiate search {provider_id}: {exc}")
        return None


def get_available_search_providers() -> list[dict]:
    """Return list of search providers with availability status."""
    providers = []
    for pid, cls in _PROVIDER_REGISTRY.items():
        try:
            instance = cls()
            providers.append({
                "id": pid,
                "name": cls.name,
                "available": instance.available,
                "init_error": instance.init_error,
            })
        except Exception as exc:
            providers.append({
                "id": pid,
                "name": cls.name,
                "available": False,
                "init_error": str(exc),
            })
    return providers


# Default instance manager
_default_provider: Optional[SearchProvider] = None


def get_default_search() -> Optional[SearchProvider]:
    """Get the default search provider (Tavily preferred, then Firecrawl, then DuckDuckGo)."""
    global _default_provider
    if _default_provider is None:
        for pid in ("tavily", "firecrawl", "serpapi", "duckduckgo"):
            provider = get_search_provider(pid)
            if provider and provider.available:
                _default_provider = provider
                break
    return _default_provider
