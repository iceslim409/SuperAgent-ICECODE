"""
ICECODE Batch Processing — run the same prompt across multiple files or
a list of prompts in parallel, with SSE streaming per item.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/batch", tags=["batch"])


class BatchRequest(BaseModel):
    prompt: str                        # base prompt (may contain {file}, {content})
    files: Optional[List[str]] = None  # file paths — prompt runs on each
    prompts: Optional[List[str]] = None  # OR: list of distinct prompts
    model: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 2048
    concurrency: int = 3               # max parallel jobs


async def _run_item(idx: int, item_label: str, full_prompt: str,
                    model: str, provider: str, base_url: Optional[str],
                    max_tokens: int) -> dict:
    """Run agent on a single item."""
    start = time.time()
    result = {
        "idx": idx,
        "label": item_label,
        "text": "",
        "elapsed_ms": 0,
        "tokens": 0,
        "error": None,
    }
    try:
        _core = str(Path(__file__).parents[3] / "core")
        if _core not in sys.path:
            sys.path.insert(0, _core)

        import httpx

        actual_base = base_url or os.getenv("ICECODE_BASE_URL", "http://localhost:11434/v1")
        api_key = (
            os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY") or
            os.getenv("GROQ_API_KEY") or "local"
        )

        messages = [{"role": "user", "content": full_prompt}]
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{actual_base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "max_tokens": max_tokens},
            )
            data = resp.json()
            if "error" in data:
                result["error"] = str(data["error"])
            else:
                choice = data.get("choices", [{}])[0]
                result["text"] = choice.get("message", {}).get("content", "")
                usage = data.get("usage", {})
                result["tokens"] = usage.get("total_tokens", 0)
    except Exception as e:
        result["error"] = str(e)

    result["elapsed_ms"] = int((time.time() - start) * 1000)
    return result


def _build_prompt(template: str, file_path: str = "", content: str = "", idx: int = 0) -> str:
    return (template
            .replace("{file}", file_path)
            .replace("{filename}", Path(file_path).name if file_path else str(idx + 1))
            .replace("{content}", content))


@router.post("/run")
async def run_batch(req: BatchRequest):
    """Run batch job, streaming results as SSE."""

    model = req.model or os.getenv("ICECODE_MODEL", "qwen2.5:7b")
    provider = req.provider or os.getenv("ICECODE_PROVIDER", "ollama")

    # Build items list
    items: List[tuple] = []  # (label, full_prompt)
    if req.files:
        for i, fpath in enumerate(req.files):
            try:
                content = Path(fpath).read_text(encoding="utf-8", errors="replace")[:8000]
            except Exception as e:
                content = f"[Error reading file: {e}]"
            full_prompt = _build_prompt(req.prompt, fpath, content, i)
            items.append((Path(fpath).name, full_prompt))
    elif req.prompts:
        for i, p in enumerate(req.prompts):
            items.append((f"Prompt {i + 1}", p))
    else:
        return StreamingResponse(
            iter([f"data: {json.dumps({'event': 'error', 'message': 'Provide files or prompts'})}\n\n"]),
            media_type="text/event-stream",
        )

    async def generate():
        yield f"data: {json.dumps({'event': 'start', 'total': len(items), 'model': model})}\n\n"

        sem = asyncio.Semaphore(req.concurrency)

        async def bounded(idx, label, prompt):
            async with sem:
                yield_data = await _run_item(idx, label, prompt, model, provider, req.base_url, req.max_tokens)
                return yield_data

        tasks = [bounded(i, label, prompt) for i, (label, prompt) in enumerate(items)]

        completed = 0
        for coro in asyncio.as_completed(tasks):
            result = await coro
            completed += 1
            yield f"data: {json.dumps({'event': 'item_done', 'completed': completed, 'total': len(items), **result})}\n\n"

        yield f"data: {json.dumps({'event': 'done', 'total': len(items)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/templates")
async def get_templates():
    """Pre-built batch prompt templates."""
    return [
        {
            "id": "code_review",
            "name": "Code Review",
            "prompt": "Analyze this code file and identify: potential bugs, security issues, and improvement suggestions.\n\nFile: {filename}\n\nContent:\n```\n{content}\n```",
            "icon": "🔍",
        },
        {
            "id": "summarize",
            "name": "Summarize Files",
            "prompt": "Summarize the content of this file in 3-5 sentences. File: {filename}\n\n{content}",
            "icon": "📝",
        },
        {
            "id": "translate",
            "name": "Translate to English",
            "prompt": "Translate the following text to English. File: {filename}\n\n{content}",
            "icon": "🌐",
        },
        {
            "id": "find_todos",
            "name": "Find TODOs & FIXMEs",
            "prompt": "List all TODO, FIXME, HACK, and XXX comments in this file with their line context.\n\n{filename}:\n```\n{content}\n```",
            "icon": "✅",
        },
        {
            "id": "docstring",
            "name": "Generate Docstrings",
            "prompt": "Add proper docstrings to all functions and classes in this Python file that are missing them. Return the complete updated file.\n\n{filename}:\n```python\n{content}\n```",
            "icon": "📚",
        },
    ]
