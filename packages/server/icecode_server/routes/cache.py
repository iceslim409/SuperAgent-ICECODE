"""ICECODE Semantic Cache API."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/cache", tags=["cache"])


def _get_cache():
    from icecode.cache import get_cache
    return get_cache()


@router.get("/stats")
async def cache_stats():
    return _get_cache().stats()


@router.delete("/clear")
async def cache_clear():
    n = _get_cache().clear()
    return {"cleared": n, "message": f"{n} entries removed from semantic cache"}


class CacheTestRequest(BaseModel):
    prompt: str


@router.post("/test")
async def cache_test(req: CacheTestRequest):
    """Check if a prompt would hit the cache (without recording a miss)."""
    cache = _get_cache()
    result = cache.get(req.prompt)
    if result:
        return {"hit": True, "response_preview": result[:200]}
    return {"hit": False}
