"""
ICECODE Model Benchmark — sends the same prompt to multiple models simultaneously,
displays responses side-by-side with time, tokens and cost.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


class BenchmarkModel(BaseModel):
    provider: str = "ollama"
    model: str
    base_url: Optional[str] = None


class BenchmarkRequest(BaseModel):
    prompt: str
    models: List[BenchmarkModel]
    max_tokens: int = 1024
    system: Optional[str] = None


async def _run_one(idx: int, bm: BenchmarkModel, prompt: str, system: str, max_tokens: int) -> Dict[str, Any]:
    """Run a single model and return result with timing."""
    start = time.time()
    result: Dict[str, Any] = {
        "idx": idx,
        "provider": bm.provider,
        "model": bm.model,
        "text": "",
        "input_tokens": 0,
        "output_tokens": 0,
        "elapsed_ms": 0,
        "error": None,
    }
    try:
        import sys
        from pathlib import Path
        _core = str(Path(__file__).parents[3] / "core")
        if _core not in sys.path:
            sys.path.insert(0, _core)

        import os
        import httpx

        base_url = bm.base_url or os.getenv("ICECODE_BASE_URL", "http://localhost:11434/v1")
        api_key = (
            os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY") or
            os.getenv("GROQ_API_KEY") or "local"
        )

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": bm.model, "messages": messages, "max_tokens": max_tokens},
            )
            data = resp.json()
            if "error" in data:
                result["error"] = str(data["error"])
            else:
                choice = data.get("choices", [{}])[0]
                result["text"] = choice.get("message", {}).get("content", "")
                usage = data.get("usage", {})
                result["input_tokens"] = usage.get("prompt_tokens", 0)
                result["output_tokens"] = usage.get("completion_tokens", 0)
    except Exception as e:
        result["error"] = str(e)

    result["elapsed_ms"] = int((time.time() - start) * 1000)
    return result


@router.post("/run")
async def run_benchmark(req: BenchmarkRequest):
    """Run prompt on all models in parallel, stream results as SSE."""

    async def generate():
        yield f"data: {json.dumps({'event': 'start', 'count': len(req.models)})}\n\n"

        tasks = [
            _run_one(i, bm, req.prompt, req.system or "", req.max_tokens)
            for i, bm in enumerate(req.models)
        ]

        for coro in asyncio.as_completed(tasks):
            result = await coro
            yield f"data: {json.dumps({'event': 'result', **result})}\n\n"

        yield f"data: {json.dumps({'event': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/presets")
async def get_presets():
    """Return model presets for quick benchmark setup."""
    import os
    return [
        {"label": "Ollama Local", "provider": "ollama", "model": "llama3.2:latest",
         "base_url": os.getenv("ICECODE_BASE_URL", "http://localhost:11434/v1")},
        {"label": "GPT-4o Mini", "provider": "openai", "model": "gpt-4o-mini",
         "base_url": "https://api.openai.com/v1"},
        {"label": "Claude Haiku", "provider": "anthropic", "model": "claude-haiku-4-5-20251001",
         "base_url": "https://api.anthropic.com/v1"},
        {"label": "Gemma 2 9B", "provider": "ollama", "model": "gemma2:9b",
         "base_url": os.getenv("ICECODE_BASE_URL", "http://localhost:11434/v1")},
        {"label": "Qwen 2.5 7B", "provider": "ollama", "model": "qwen2.5:7b",
         "base_url": os.getenv("ICECODE_BASE_URL", "http://localhost:11434/v1")},
    ]
