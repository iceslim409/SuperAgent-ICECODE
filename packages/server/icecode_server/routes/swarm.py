"""ICECODE Swarm API — multi-agent orchestration endpoints."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parents[4] / "core"))

router = APIRouter(prefix="/api/swarm", tags=["swarm"])


class SwarmAgentConfig(BaseModel):
    role: str
    task: str = "{input}"
    model: str = ""
    provider: str = "ollama"
    base_url: Optional[str] = None
    system_extra: str = ""
    max_iterations: int = 8


class SwarmRunRequest(BaseModel):
    input: str
    mode: str = "pipeline"          # "pipeline" | "parallel"
    agents: List[SwarmAgentConfig] = []
    template: Optional[str] = None  # use a built-in template
    model: str = ""                  # default model for all agents
    provider: str = "ollama"
    base_url: Optional[str] = None


async def _sse_swarm(req: SwarmRunRequest):
    from icecode.swarm.coordinator import SwarmCoordinator, TEMPLATES

    if req.template:
        async for chunk in SwarmCoordinator.run_template(
            req.template,
            req.input,
            model=req.model,
            provider=req.provider,
            base_url=req.base_url,
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
        return

    agents_cfg = [a.model_dump() for a in req.agents]
    coord = SwarmCoordinator(
        mode=req.mode,
        model=req.model,
        provider=req.provider,
        base_url=req.base_url,
    )
    async for chunk in coord.run(req.input, agents_cfg):
        yield f"data: {json.dumps(chunk)}\n\n"


@router.post("/run")
async def run_swarm(req: SwarmRunRequest):
    """Start a swarm execution — streams SSE events."""
    return StreamingResponse(
        _sse_swarm(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/templates")
async def list_templates():
    """List built-in swarm templates."""
    from icecode.swarm.coordinator import TEMPLATES
    return {
        "templates": [
            {
                "id": k,
                "name": v["name"],
                "description": v["description"],
                "mode": v["mode"],
                "num_agents": len(v.get("stages", v.get("agents", []))),
            }
            for k, v in TEMPLATES.items()
        ]
    }


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    """Get full template config including agent stages."""
    from icecode.swarm.coordinator import TEMPLATES
    tpl = TEMPLATES.get(template_id)
    if not tpl:
        from fastapi import HTTPException
        raise HTTPException(404, f"Template '{template_id}' not found")
    return {"id": template_id, **tpl}
