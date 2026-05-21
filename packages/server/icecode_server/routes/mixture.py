"""
ICECODE Mixture of Agents — send prompt to multiple Ollama models, synthesize best response.
Ported from Hermes mixture_of_agents_tool.
"""
from __future__ import annotations

import asyncio
import json
from typing import List, Optional

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/mixture", tags=["mixture"])

_SYNTHESIS_PROMPT = """You are a synthesis agent. You received responses from multiple AI models for the same prompt.
Your job: extract the BEST parts from each response, combine insights, and produce a single superior answer.
Be concise. Keep code/commands exact. If responses contradict, pick the most accurate one.

ORIGINAL PROMPT: {prompt}

MODEL RESPONSES:
{responses}

SYNTHESIZED RESPONSE:"""


async def _query_model(model: str, prompt: str, timeout: int = 60) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False,
                      "options": {"num_ctx": 4096, "num_predict": 1024}},
            )
            if r.status_code == 200:
                data = r.json()
                return {"model": model, "response": data.get("response", ""), "ok": True}
            return {"model": model, "response": "", "ok": False, "error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"model": model, "response": "", "ok": False, "error": str(e)}


class MixtureRequest(BaseModel):
    prompt: str
    models: Optional[List[str]] = None
    synthesizer_model: Optional[str] = None
    timeout: int = 60


@router.post("/query")
async def mixture_query(req: MixtureRequest):
    """Query multiple models in parallel and return all responses."""
    # Auto-detect models if not provided
    if not req.models:
        try:
            r = httpx.get("http://localhost:11434/api/tags", timeout=3)
            installed = [m["name"] for m in r.json().get("models", [])]
            # Pick 3 diverse models for mixture
            prefs = ["qwen2.5:7b", "mistral:7b-instruct", "phi4-mini:latest",
                     "qwen3.5:4b", "granite4.1:3b", "qwen2.5:3b"]
            models = []
            for p in prefs:
                for m in installed:
                    if m == p or m.startswith(p.split(":")[0]+":"):
                        if m not in models:
                            models.append(m)
                            break
                if len(models) >= 3:
                    break
            req.models = models or installed[:3]
        except Exception:
            req.models = ["qwen2.5:7b"]

    # Query all models in parallel
    tasks = [_query_model(m, req.prompt, req.timeout) for m in req.models]
    results = await asyncio.gather(*tasks)

    successful = [r for r in results if r["ok"] and r["response"]]
    failed = [r for r in results if not r["ok"]]

    return {
        "models_queried": req.models,
        "successful": len(successful),
        "failed": len(failed),
        "responses": results,
    }


@router.post("/synthesize")
async def mixture_synthesize(req: MixtureRequest):
    """Query multiple models AND synthesize into single best response."""
    # Get responses from all models
    query_result = await mixture_query(req)
    successful = [r for r in query_result["responses"] if r["ok"] and r["response"]]

    if not successful:
        return {"error": "No successful model responses", "responses": query_result["responses"]}

    if len(successful) == 1:
        # Only one model responded — return directly
        return {
            "synthesized": successful[0]["response"],
            "model_used": successful[0]["model"],
            "individual_responses": successful,
        }

    # Format responses for synthesis
    resp_text = "\n\n".join([
        f"--- Response from {r['model']} ---\n{r['response']}"
        for r in successful
    ])

    synthesis_prompt = _SYNTHESIS_PROMPT.format(
        prompt=req.prompt,
        responses=resp_text,
    )

    synthesizer = req.synthesizer_model or successful[0]["model"]
    synth_result = await _query_model(synthesizer, synthesis_prompt, timeout=90)

    return {
        "synthesized": synth_result.get("response", "") if synth_result["ok"] else resp_text,
        "synthesizer_model": synthesizer,
        "models_used": [r["model"] for r in successful],
        "individual_responses": successful,
    }


@router.get("/models")
async def available_models():
    """List models available for mixture."""
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        return {"models": models, "count": len(models)}
    except Exception as e:
        return {"models": [], "error": str(e)}
