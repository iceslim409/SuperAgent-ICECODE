"""Stub for plugins.web.tavily.provider."""
from typing import Any, List, Dict

def _normalize_tavily_documents(data: Any) -> list: return []
def _normalize_tavily_search_results(data: Any) -> list: return []
async def _tavily_request(query: str, **kw) -> dict: return {"results": []}
class TavilyProvider:
    async def search(self, query: str, **kw) -> list: return []
def get_provider(): return TavilyProvider()
