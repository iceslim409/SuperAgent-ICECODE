"""
ICECODE Model Router API
=========================
Exposes the intelligent model router as an HTTP API.
Unique to ICECODE — not present in Hermes, OpenCode, or ClawX.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/router", tags=["router"])

try:
    from icecode.router import get_router, ModelRouter
    _HAS_ROUTER = True
except ImportError:
    _HAS_ROUTER = False


class RouteRequest(BaseModel):
    prompt: str
    force_model: Optional[str] = None


class RouteResponse(BaseModel):
    model: str
    complexity: str
    reason: str
    fallback_model: Optional[str] = None
    estimated_tokens: int


@router.post("/decide", response_model=RouteResponse)
async def decide_model(req: RouteRequest):
    """
    Given a prompt, returns the optimal Ollama model to use.
    ICECODE automatically selects based on task complexity and available models.
    """
    if not _HAS_ROUTER:
        return RouteResponse(
            model="qwen3.5:4b",
            complexity="unknown",
            reason="Router module not available",
            estimated_tokens=2048,
        )
    r = get_router()
    decision = await r.route_async(req.prompt, req.force_model)
    return RouteResponse(
        model=decision.model,
        complexity=decision.complexity.value,
        reason=decision.reason,
        fallback_model=decision.fallback_model,
        estimated_tokens=decision.estimated_tokens,
    )


@router.get("/describe")
async def describe_router():
    """
    Returns available models grouped by tier.
    Useful for the UI to show which models are installed.
    """
    if not _HAS_ROUTER:
        return {"error": "Router module not available"}
    r = get_router()
    return r.describe()


@router.post("/assess")
async def assess_complexity(req: RouteRequest):
    """Assess task complexity without routing to a model."""
    if not _HAS_ROUTER:
        return {"complexity": "unknown"}
    complexity = ModelRouter.assess_complexity(req.prompt)
    return {
        "complexity": complexity.value,
        "description": {
            "trivial": "Quick answer, no reasoning needed",
            "simple": "Everyday task, short output",
            "moderate": "Coding or analysis, medium reasoning",
            "complex": "Architecture, multi-step reasoning, long output",
            "vision": "Image/screenshot analysis required",
        }.get(complexity.value, ""),
    }
