"""Stub for plugins.web.firecrawl.provider — full API surface."""
from typing import Any, Dict, List, Optional

_FIRECRAWL_CLS_CACHE: Dict = {}
_firecrawl_backend_help_suffix: str = ""

class Firecrawl:
    def __init__(self, api_key: str = ""): self.api_key = api_key
    async def scrape_url(self, url: str, **kw) -> dict: return {"markdown": ""}
    async def search(self, query: str, **kw) -> list: return []

class _FirecrawlProxy:
    async def scrape(self, url: str, **kw) -> dict: return {"content": ""}
    async def search(self, query: str, **kw) -> list: return []

def _get_firecrawl_client(**kw): return _FirecrawlProxy()
def _get_firecrawl_gateway_url() -> str: return ""
def _get_direct_firecrawl_config(**kw) -> dict: return {}
def _extract_scrape_payload(resp: Any) -> str: return str(resp)
def _extract_web_search_results(resp: Any) -> list: return []
def _has_direct_firecrawl_config() -> bool: return False
def _is_tool_gateway_ready() -> bool: return False
def _load_firecrawl_cls(): return Firecrawl
def _normalize_result_list(results: Any) -> list: return list(results) if results else []
def _raise_web_backend_configuration_error(msg: str = "") -> None:
    raise RuntimeError(msg or "Web backend not configured")
def _to_plain_object(obj: Any) -> Any: return obj
def check_firecrawl_api_key() -> bool: return False

class FirecrawlProvider:
    async def scrape(self, url: str, **kw) -> dict: return {"content": ""}
    async def search(self, query: str, **kw) -> list: return []

def get_provider(): return FirecrawlProvider()
