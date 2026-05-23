"""Stub for plugins.web.firecrawl."""
async def scrape(url: str, **kw) -> dict: return {"content": "", "url": url}
async def search(query: str, **kw) -> list: return []
