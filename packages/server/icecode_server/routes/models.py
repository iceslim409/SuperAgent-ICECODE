"""ICECODE Models API — list models per provider"""
from fastapi import APIRouter
router = APIRouter(prefix="/api/models", tags=["models"])

import httpx

def _get_ollama_models():
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return []

MODELS = {
    "ollama": "*",
}

@router.get("/")
async def list_models():
    ollama_models = _get_ollama_models()
    return {"models": {"ollama": ollama_models}}

@router.get("/{provider}")
async def models_for_provider(provider: str):
    if provider == "ollama":
        return {"provider": "ollama", "models": _get_ollama_models()}
    return {"provider": provider, "models": []}
