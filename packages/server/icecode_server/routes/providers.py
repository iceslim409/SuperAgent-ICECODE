"""
ICECODE Providers API
Manage LLM provider accounts — cloud + local.
Auto-detects available models after API key is saved.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, List

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/providers", tags=["providers"])

# ── Provider catalog ──────────────────────────────────────────────────────────

PROVIDERS_CATALOG = [
    {
        "id": "ollama",
        "name": "Ollama (Local)",
        "description": "Local models — runs fully offline, no costs",
        "requires_key": False,
        "base_url": "http://localhost:11434/v1",
        "models_endpoint": "http://localhost:11434/api/tags",
        "docs_url": "https://ollama.com",
        "color": "#3fb950",
        "icon": "🦙",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "description": "GPT-4o, GPT-4-turbo, GPT-3.5 — the most popular cloud models",
        "requires_key": True,
        "base_url": "https://api.openai.com/v1",
        "models_endpoint": "https://api.openai.com/v1/models",
        "key_header": "Authorization",
        "key_prefix": "Bearer ",
        "docs_url": "https://platform.openai.com",
        "color": "#10a37f",
        "icon": "🤖",
    },
    {
        "id": "anthropic",
        "name": "Anthropic (Claude)",
        "description": "Claude 3.5 Sonnet, Claude 3 Opus — AI with advanced reasoning",
        "requires_key": True,
        "base_url": "https://api.anthropic.com/v1",
        "models_endpoint": "https://api.anthropic.com/v1/models",
        "key_header": "x-api-key",
        "key_prefix": "",
        "extra_headers": {"anthropic-version": "2023-06-01"},
        "docs_url": "https://docs.anthropic.com",
        "color": "#cc785c",
        "icon": "🧠",
        "static_models": [
            "claude-opus-4-5", "claude-opus-4-0",
            "claude-sonnet-4-5", "claude-sonnet-4-0",
            "claude-haiku-4-5",
            "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229", "claude-3-haiku-20240307",
        ],
    },
    {
        "id": "groq",
        "name": "Groq",
        "description": "Ultra-fast LPU inference — Llama, Mistral, Gemma at extreme speeds",
        "requires_key": True,
        "base_url": "https://api.groq.com/openai/v1",
        "models_endpoint": "https://api.groq.com/openai/v1/models",
        "key_header": "Authorization",
        "key_prefix": "Bearer ",
        "docs_url": "https://console.groq.com",
        "color": "#f97316",
        "icon": "⚡",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "description": "Gateway for 200+ models — unified access to all providers",
        "requires_key": True,
        "base_url": "https://openrouter.ai/api/v1",
        "models_endpoint": "https://openrouter.ai/api/v1/models",
        "key_header": "Authorization",
        "key_prefix": "Bearer ",
        "extra_headers": {"HTTP-Referer": "https://icecode.app"},
        "docs_url": "https://openrouter.ai",
        "color": "#8b5cf6",
        "icon": "🌐",
    },
    {
        "id": "together",
        "name": "Together AI",
        "description": "Open-source models at low cost — Llama, Mistral, Mixtral",
        "requires_key": True,
        "base_url": "https://api.together.xyz/v1",
        "models_endpoint": "https://api.together.xyz/v1/models",
        "key_header": "Authorization",
        "key_prefix": "Bearer ",
        "docs_url": "https://api.together.ai",
        "color": "#06b6d4",
        "icon": "🤝",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "description": "DeepSeek-V3, DeepSeek-R1 — high-performance Chinese models",
        "requires_key": True,
        "base_url": "https://api.deepseek.com/v1",
        "models_endpoint": "https://api.deepseek.com/v1/models",
        "key_header": "Authorization",
        "key_prefix": "Bearer ",
        "docs_url": "https://platform.deepseek.com",
        "color": "#3b82f6",
        "icon": "🔬",
        "static_models": ["deepseek-chat", "deepseek-reasoner", "deepseek-coder"],
    },
    {
        "id": "google",
        "name": "Google (Gemini)",
        "description": "Gemini 2.5 Pro, Gemini 2.0 Flash — Google multimodal models",
        "requires_key": True,
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models_endpoint": "https://generativelanguage.googleapis.com/v1beta/models",
        "key_param": "key",
        "docs_url": "https://ai.google.dev",
        "color": "#4285f4",
        "icon": "💎",
        "static_models": [
            "gemini-2.5-pro", "gemini-2.5-flash",
            "gemini-2.0-flash", "gemini-2.0-flash-lite",
            "gemini-1.5-pro", "gemini-1.5-flash",
        ],
    },
    {
        "id": "custom",
        "name": "Custom (OpenAI-compatible)",
        "description": "Any OpenAI-compatible local server (LM Studio, llama.cpp, vLLM, etc.)",
        "requires_key": False,
        "base_url": "",
        "docs_url": "",
        "color": "#6e7681",
        "icon": "⚙️",
    },
]

_CATALOG_BY_ID = {p["id"]: p for p in PROVIDERS_CATALOG}


def _providers_file() -> Path:
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    return cfg.home_dir / "data" / "providers.json"


def _load_providers() -> list:
    f = _providers_file()
    return json.loads(f.read_text()) if f.exists() else []


def _save_providers(providers: list):
    f = _providers_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(providers, indent=2))


# ── Models detection ──────────────────────────────────────────────────────────

async def _detect_models(provider_id: str, api_key: str, base_url: str = "") -> List[str]:
    """Fetch available models from a provider using their API key."""
    catalog = _CATALOG_BY_ID.get(provider_id)
    if not catalog:
        return []

    # Static model list only as fallback when no API key provided
    if catalog.get("static_models") and not api_key:
        return catalog["static_models"]

    if provider_id == "ollama":
        try:
            r = httpx.get("http://localhost:11434/api/tags", timeout=3)
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    endpoint = catalog.get("models_endpoint", "")
    if not endpoint:
        return []

    headers = {}
    key_header = catalog.get("key_header", "")
    if key_header and api_key:
        headers[key_header] = catalog.get("key_prefix", "") + api_key
    for k, v in catalog.get("extra_headers", {}).items():
        headers[k] = v

    params = {}
    if catalog.get("key_param") and api_key:
        params[catalog["key_param"]] = api_key

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(endpoint, headers=headers, params=params)
        if r.status_code != 200:
            return []
        data = r.json()

        # Different providers return models in different shapes
        if provider_id == "openrouter":
            return [m["id"] for m in data.get("data", [])][:100]
        elif provider_id == "together":
            items = data if isinstance(data, list) else data.get("result", data.get("data", []))
            return [m.get("id", m.get("name", "")) for m in items if m.get("id") or m.get("name")][:100]
        elif provider_id == "google":
            # Filter to only text generation models, strip "models/" prefix
            models = []
            for m in data.get("models", []):
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods or "streamGenerateContent" in methods:
                    name = m["name"].replace("models/", "")
                    if name not in models:
                        models.append(name)
            return models
        elif provider_id == "anthropic":
            # Anthropic returns OpenAI-compatible list sorted newest first
            items = data.get("data", [])
            return [m["id"] for m in items if m.get("id")]
        else:
            # OpenAI-compatible (openai, groq, deepseek, mistral, custom)
            items = data.get("data", data.get("models", []))
            ids = [m["id"] for m in items if m.get("id")]
            return sorted(ids, key=lambda x: (0 if any(k in x for k in ("gpt-4","o1","o3","claude")) else 1, x))
    except Exception:
        return []


# ── Routes ────────────────────────────────────────────────────────────────────

class ProviderCreate(BaseModel):
    provider_id: str
    api_key: str = ""
    base_url: Optional[str] = None
    default_model: Optional[str] = None


@router.get("/catalog")
async def get_catalog():
    """Full provider catalog with metadata."""
    providers = _load_providers()
    configured_ids = {p["id"] for p in providers}
    result = []
    for p in PROVIDERS_CATALOG:
        entry = dict(p)
        entry["configured"] = p["id"] in configured_ids
        result.append(entry)
    return {"providers": result}


@router.get("/")
async def list_configured():
    """List configured providers (API keys redacted)."""
    providers = _load_providers()
    result = []
    for p in providers:
        entry = dict(p)
        if entry.get("api_key"):
            entry["api_key"] = "***"
        # Enrich with catalog metadata
        meta = _CATALOG_BY_ID.get(p["id"], {})
        entry["name"] = meta.get("name", p["id"])
        entry["icon"] = meta.get("icon", "🔌")
        entry["color"] = meta.get("color", "#6e7681")
        result.append(entry)
    return result


@router.post("/")
async def add_provider(req: ProviderCreate):
    """Save provider config and auto-detect available models."""
    providers = _load_providers()
    providers = [p for p in providers if p["id"] != req.provider_id]

    models = await _detect_models(req.provider_id, req.api_key, req.base_url or "")

    provider = {
        "id": req.provider_id,
        "api_key": req.api_key,
        "base_url": req.base_url,
        "default_model": req.default_model or (models[0] if models else ""),
        "models": models,
        "enabled": True,
    }
    providers.append(provider)
    _save_providers(providers)

    provider["api_key"] = "***"
    return {**provider, "models_found": len(models)}


@router.post("/{provider_id}/detect-models")
async def detect_models(provider_id: str):
    """Re-detect available models for a configured provider."""
    providers = _load_providers()
    found = next((p for p in providers if p["id"] == provider_id), None)
    if not found:
        raise HTTPException(404, f"Provider '{provider_id}' not configured")

    models = await _detect_models(provider_id, found.get("api_key", ""), found.get("base_url", "") or "")

    # Update stored models list
    for p in providers:
        if p["id"] == provider_id:
            p["models"] = models
            if not p.get("default_model") and models:
                p["default_model"] = models[0]
    _save_providers(providers)

    return {"provider_id": provider_id, "models": models, "count": len(models)}


@router.get("/{provider_id}/models")
async def get_provider_models(provider_id: str):
    """Get cached models list for a provider."""
    providers = _load_providers()
    found = next((p for p in providers if p["id"] == provider_id), None)
    if not found:
        # For Ollama, always fetch live
        if provider_id == "ollama":
            models = await _detect_models("ollama", "", "")
            return {"provider_id": "ollama", "models": models}
        raise HTTPException(404, f"Provider '{provider_id}' not configured")
    return {"provider_id": provider_id, "models": found.get("models", [])}


@router.delete("/{provider_id}")
async def remove_provider(provider_id: str):
    providers = _load_providers()
    providers = [p for p in providers if p["id"] != provider_id]
    _save_providers(providers)
    return {"ok": True}
