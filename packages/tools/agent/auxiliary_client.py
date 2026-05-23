"""Stub for agent.auxiliary_client."""
from __future__ import annotations
import os
from typing import Any, Dict, List, Optional


def _read_main_provider() -> str: return os.getenv("ICECODE_PROVIDER", "ollama")
def _read_main_model() -> str: return os.getenv("ICECODE_MODEL", "llava:latest")


async def async_call_llm(messages: List[Dict], model: str = "", max_tokens: int = 2048, **kw) -> Any:
    import httpx, json
    base_url = os.getenv("ICECODE_BASE_URL", "http://localhost:11434/v1")
    api_key = os.getenv("OPENAI_API_KEY") or "local"
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model or _read_main_model(), "messages": messages, "max_tokens": max_tokens})
        return r.json()

def call_llm(messages: List[Dict], model: str = "", max_tokens: int = 2048, **kw) -> Any:
    import httpx, json
    base_url = os.getenv("ICECODE_BASE_URL", "http://localhost:11434/v1")
    api_key = os.getenv("OPENAI_API_KEY") or "local"
    r = httpx.post(f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model or _read_main_model(), "messages": messages, "max_tokens": max_tokens},
        timeout=60)
    return r.json()

def extract_content_or_reasoning(response: Any) -> str:
    try:
        if isinstance(response, dict):
            choices = response.get("choices", [])
            if choices: return choices[0].get("message", {}).get("content", "")
    except Exception: pass
    return str(response)

def get_auxiliary_extra_body(**kw) -> Dict: return {}

async def resolve_provider_client(provider: str = "", model: str = ""):
    import openai
    base_url = os.getenv("ICECODE_BASE_URL", "http://localhost:11434/v1")
    client = openai.AsyncOpenAI(base_url=base_url, api_key=os.getenv("OPENAI_API_KEY") or "local")
    return client, model or _read_main_model()

async def resolve_vision_provider_client(provider: str = "", model: str = ""):
    return await resolve_provider_client(provider, model)

async def get_async_text_auxiliary_client(**kw):
    import openai, os
    base_url = os.getenv("ICECODE_BASE_URL", "http://localhost:11434/v1")
    client = openai.AsyncOpenAI(base_url=base_url, api_key=os.getenv("OPENAI_API_KEY") or "local")
    return client
