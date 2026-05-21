"""
ICECODE Profiles — multi-profile config management (from Hermes profiles system).
Switch between different model/provider/system_prompt configurations.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/profiles", tags=["profiles"])

_HOME = Path.home() / ".icecode"
_PROFILES_FILE = _HOME / "data" / "profiles.json"

DEFAULT_PROFILES = [
    {
        "id": "default",
        "name": "Default",
        "description": "Default profile — general model, all tools active",
        "model": "qwen2.5:7b",
        "provider": "ollama",
        "system_prompt": "",
        "max_iterations": 10,
        "tools": ["read_file", "write_file", "list_dir", "run_terminal", "web_fetch", "search_web", "remember", "recall"],
        "active": True,
        "builtin": True,
    },
    {
        "id": "coding",
        "name": "Coding",
        "description": "Optimized for coding — coder model, terminal + files",
        "model": "qwen2.5:7b",
        "provider": "ollama",
        "system_prompt": "You are a programming expert. Write clean, efficient and well-documented code. Explain technical decisions.",
        "max_iterations": 15,
        "tools": ["read_file", "write_file", "list_dir", "run_terminal"],
        "active": False,
        "builtin": True,
    },
    {
        "id": "research",
        "name": "Research",
        "description": "Web research + memory — no terminal",
        "model": "qwen2.5:7b",
        "provider": "ollama",
        "system_prompt": "You are a research agent. You find information from multiple sources, verify facts and create clear reports.",
        "max_iterations": 10,
        "tools": ["web_fetch", "search_web", "remember", "recall", "write_file"],
        "active": False,
        "builtin": True,
    },
    {
        "id": "autonomous",
        "name": "Autonomous",
        "description": "Full desktop control — all tools + computer control",
        "model": "qwen2.5:7b",
        "provider": "ollama",
        "system_prompt": "You are an autonomous agent that can control the computer. Complete tasks without human intervention.",
        "max_iterations": 20,
        "tools": ["read_file", "write_file", "list_dir", "run_terminal", "web_fetch", "search_web",
                  "remember", "recall", "screenshot", "click", "type_text", "hotkey", "open_app"],
        "active": False,
        "builtin": True,
        "enable_computer": True,
    },
    {
        "id": "fast",
        "name": "Fast",
        "description": "Fast responses — small model, no tools",
        "model": "qwen2.5:0.5b-instruct",
        "provider": "ollama",
        "system_prompt": "Answer concisely and directly. Be as brief as possible.",
        "max_iterations": 3,
        "tools": [],
        "active": False,
        "builtin": True,
    },
]


def _load() -> list:
    if _PROFILES_FILE.exists():
        try:
            return json.loads(_PROFILES_FILE.read_text())
        except Exception:
            pass
    _save(DEFAULT_PROFILES)
    return DEFAULT_PROFILES


def _save(profiles: list):
    _PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PROFILES_FILE.write_text(json.dumps(profiles, indent=2, ensure_ascii=False))


class ProfileCreate(BaseModel):
    name: str
    description: Optional[str] = None
    model: str = "qwen2.5:7b"
    provider: str = "ollama"
    system_prompt: str = ""
    max_iterations: int = 10
    tools: List[str] = []
    enable_computer: bool = False


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    system_prompt: Optional[str] = None
    max_iterations: Optional[int] = None
    tools: Optional[List[str]] = None
    enable_computer: Optional[bool] = None


@router.get("/")
@router.get("")
async def list_profiles():
    return _load()


@router.get("/active")
async def get_active_profile():
    profiles = _load()
    for p in profiles:
        if p.get("active"):
            return p
    return profiles[0] if profiles else {}


@router.post("/{profile_id}/activate")
async def activate_profile(profile_id: str):
    profiles = _load()
    found = False
    for p in profiles:
        p["active"] = (p["id"] == profile_id)
        if p["id"] == profile_id:
            found = True
    if not found:
        raise HTTPException(404, f"Profile '{profile_id}' not found")
    _save(profiles)
    return {"ok": True, "active": profile_id}


@router.post("/")
async def create_profile(req: ProfileCreate):
    profiles = _load()
    import uuid as _uuid
    profile = {
        "id": f"profile_{_uuid.uuid4().hex[:8]}",
        "name": req.name,
        "description": req.description or "",
        "model": req.model,
        "provider": req.provider,
        "system_prompt": req.system_prompt,
        "max_iterations": req.max_iterations,
        "tools": req.tools,
        "enable_computer": req.enable_computer,
        "active": False,
        "builtin": False,
    }
    profiles.append(profile)
    _save(profiles)
    return profile


@router.patch("/{profile_id}")
async def update_profile(profile_id: str, req: ProfileUpdate):
    profiles = _load()
    for p in profiles:
        if p["id"] == profile_id:
            if req.name is not None: p["name"] = req.name
            if req.description is not None: p["description"] = req.description
            if req.model is not None: p["model"] = req.model
            if req.provider is not None: p["provider"] = req.provider
            if req.system_prompt is not None: p["system_prompt"] = req.system_prompt
            if req.max_iterations is not None: p["max_iterations"] = req.max_iterations
            if req.tools is not None: p["tools"] = req.tools
            if req.enable_computer is not None: p["enable_computer"] = req.enable_computer
            _save(profiles)
            return p
    raise HTTPException(404, f"Profile '{profile_id}' not found")


@router.delete("/{profile_id}")
async def delete_profile(profile_id: str):
    profiles = _load()
    before = len(profiles)
    profiles = [p for p in profiles if not (p["id"] == profile_id and not p.get("builtin"))]
    if len(profiles) == before:
        raise HTTPException(400, "Cannot delete built-in profile or profile not found")
    _save(profiles)
    return {"ok": True, "deleted": profile_id}
