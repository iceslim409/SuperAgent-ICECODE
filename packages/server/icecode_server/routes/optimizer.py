"""ICECODE Cost Optimizer API — cost router + context compressor stats."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/optimizer", tags=["optimizer"])


def _router():
    from icecode.optimizer import get_cost_router
    return get_cost_router()


class RouteRequest(BaseModel):
    prompt: str
    preferred_models: Optional[list[str]] = None


@router.post("/route")
async def route_prompt(req: RouteRequest):
    """Score a prompt and return the recommended cheapest model."""
    r = _router()
    if req.preferred_models:
        r.preferred_models = req.preferred_models
    decision = r.route(req.prompt)
    return {
        "model": decision.model,
        "complexity_score": decision.score,
        "tier": decision.tier,
        "cost_per_1k_input_usd": decision.cost_per_1k_input,
        "cost_per_1k_output_usd": decision.cost_per_1k_output,
        "estimated_cost_usd": decision.estimated_cost_usd,
        "reason": decision.reason,
        "is_local": decision.is_local,
    }


@router.get("/stats")
async def optimizer_stats():
    return _router().stats()


@router.get("/cost-table")
async def cost_table():
    from icecode.optimizer.cost_router import COST_TABLE
    return {
        model: {**info}
        for model, info in COST_TABLE.items()
        if model != "__local__"
    }


class CompressRequest(BaseModel):
    messages: list[dict]


@router.post("/compress")
async def compress_context(req: CompressRequest):
    from icecode.optimizer.context_compressor import compress
    compressed, saved = compress(req.messages)
    return {
        "original_count": len(req.messages),
        "compressed_count": len(compressed),
        "tokens_saved": saved,
        "messages": compressed,
    }
