"""
ICECODE Skills API
Built-in skills + user skills from ~/.icecode/skills/
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/skills", tags=["skills"])

# ── Built-in skills ───────────────────────────────────────────────────────────

BUILTIN_SKILLS = [
    {
        "id": "code_execution",
        "name": "Code Execution",
        "description": "Run Python, bash, JS code in terminal. Returns output and erori.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["run_terminal"],
        "tags": ["code", "terminal"],
    },
    {
        "id": "file_operations",
        "name": "File Operations",
        "description": "Read, write, list files and directories on disk.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["read_file", "write_file", "list_dir"],
        "tags": ["files", "storage"],
    },
    {
        "id": "web_search",
        "name": "Web Search",
        "description": "Search the web with DuckDuckGo. Returns relevant results.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["search_web", "web_fetch"],
        "tags": ["web", "search"],
    },
    {
        "id": "memory",
        "name": "Persistent Memory",
        "description": "Save and retrieve information between sessions.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["remember", "recall"],
        "tags": ["memory", "learning"],
    },
    {
        "id": "computer_control",
        "name": "Computer Control",
        "description": "Control desktop: screenshot, click, typing, open applications.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["screenshot", "click", "type_text", "hotkey", "open_app",
                  "move_mouse", "scroll", "get_screen_size"],
        "tags": ["autonomous", "desktop"],
    },
    {
        "id": "git_operations",
        "name": "Git Operations",
        "description": "Clone, commit, push, pull via terminal. Lucru cu repository-uri git.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["run_terminal"],
        "tags": ["git", "code"],
    },
    {
        "id": "api_calls",
        "name": "API Calls",
        "description": "Make HTTP requests to external APIs. Parses JSON/XML.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["web_fetch"],
        "tags": ["api", "web"],
    },
    {
        "id": "data_analysis",
        "name": "Data Analysis",
        "description": "Analyze CSV, JSON data. Generate statistics and charts with Python.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["run_terminal", "read_file", "write_file"],
        "tags": ["data", "analysis"],
    },
    {
        "id": "project_scaffold",
        "name": "Project Scaffold",
        "description": "Create project scaffolding (Python, Node.js, React, FastAPI etc.)",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["write_file", "run_terminal", "list_dir"],
        "tags": ["code", "scaffold"],
    },
    {
        "id": "self_learning",
        "name": "Self Learning",
        "description": "Agent learns from interactions and saves new knowledge.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["remember", "recall"],
        "tags": ["learning", "memory"],
    },
]


class SkillToggle(BaseModel):
    enabled: bool


def _skills_file():
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    return cfg.home_dir / "data" / "skills_config.json"


def _load_overrides() -> dict:
    """Load enable/disable overrides for skills."""
    f = _skills_file()
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return {}


def _save_overrides(overrides: dict):
    f = _skills_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(overrides, indent=2))


def _build_skill_list():
    """Return built-in skills + any user skills from ~/.icecode/skills/."""
    overrides = _load_overrides()
    result = []

    # Built-in skills with override support
    for s in BUILTIN_SKILLS:
        skill = dict(s)
        if skill["id"] in overrides:
            skill["enabled"] = overrides[skill["id"]]
        result.append(skill)

    # User-created skills from markdown files
    try:
        from icecode.config.settings import ICECodeSettings
        cfg = ICECodeSettings()
        skills_dir = cfg.home_dir / "skills"
        if skills_dir.exists():
            for md_file in sorted(skills_dir.glob("**/*.md")):
                skill_id = md_file.stem
                if any(s["id"] == skill_id for s in result):
                    continue
                result.append({
                    "id": skill_id,
                    "name": skill_id.replace("_", " ").title(),
                    "description": f"Custom skill from {md_file.name}",
                    "version": "1.0.0",
                    "enabled": overrides.get(skill_id, True),
                    "builtin": False,
                    "tools": [],
                    "tags": ["custom"],
                    "path": str(md_file),
                })
    except Exception:
        pass

    return result


@router.get("/")
@router.get("")
async def list_skills():
    return _build_skill_list()


@router.get("/stats")
async def skill_stats():
    skills = _build_skill_list()
    return {
        "total": len(skills),
        "enabled": sum(1 for s in skills if s.get("enabled")),
        "builtin": sum(1 for s in skills if s.get("builtin")),
        "custom": sum(1 for s in skills if not s.get("builtin")),
    }


@router.put("/{skill_id}/toggle")
async def toggle_skill(skill_id: str, req: SkillToggle):
    overrides = _load_overrides()
    overrides[skill_id] = req.enabled
    _save_overrides(overrides)
    return {"ok": True, "skill_id": skill_id, "enabled": req.enabled}


@router.post("/discover")
async def discover_skills():
    """Scan for skills and return the full list."""
    skills = _build_skill_list()
    return {
        "ok": True,
        "count": len(skills),
        "discovered": [s["id"] for s in skills],
        "message": f"Found {len(skills)} skills ({sum(1 for s in skills if s.get('builtin'))} built-in)",
    }


@router.post("/")
async def create_skill(body: dict):
    """Create a custom skill (saves as markdown to ~/.icecode/skills/)."""
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    skills_dir = cfg.home_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "name is required")

    skill_id = name.lower().replace(" ", "_")
    content = f"# {name}\n\n{body.get('description', '')}\n\n## Tools\n{', '.join(body.get('tools', []))}\n"
    (skills_dir / f"{skill_id}.md").write_text(content)

    return {"ok": True, "id": skill_id, "name": name}


# ── Curator ──────────────────────────────────────────────────────────────────

def _curator_file():
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    return cfg.home_dir / "data" / "skills_curator.json"


def _load_curator() -> dict:
    f = _curator_file()
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return {"pinned": [], "archived": [], "usage_counts": {}}


def _save_curator(data: dict):
    f = _curator_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2))


@router.get("/curator/status")
async def curator_status():
    """Skill curator status — usage, pinned, archived."""
    curator = _load_curator()
    skills = _build_skill_list()
    return {
        "total_skills": len(skills),
        "pinned": curator.get("pinned", []),
        "archived": curator.get("archived", []),
        "usage_counts": curator.get("usage_counts", {}),
        "enabled": True,
    }


@router.post("/curator/pin/{skill_id}")
async def pin_skill(skill_id: str):
    """Pin a skill so curator never archives it."""
    curator = _load_curator()
    if skill_id not in curator["pinned"]:
        curator["pinned"].append(skill_id)
    if skill_id in curator.get("archived", []):
        curator["archived"].remove(skill_id)
    _save_curator(curator)
    return {"ok": True, "pinned": skill_id}


@router.post("/curator/unpin/{skill_id}")
async def unpin_skill(skill_id: str):
    curator = _load_curator()
    curator["pinned"] = [s for s in curator.get("pinned", []) if s != skill_id]
    _save_curator(curator)
    return {"ok": True, "unpinned": skill_id}


@router.post("/curator/archive/{skill_id}")
async def archive_skill(skill_id: str):
    """Archive a skill (disables it and marks for review)."""
    curator = _load_curator()
    overrides = _load_overrides()

    if skill_id not in curator.get("archived", []):
        curator.setdefault("archived", []).append(skill_id)
    overrides[skill_id] = False  # disable
    _save_curator(curator)
    _save_overrides(overrides)
    return {"ok": True, "archived": skill_id}


@router.post("/curator/restore/{skill_id}")
async def restore_skill(skill_id: str):
    """Restore an archived skill."""
    curator = _load_curator()
    overrides = _load_overrides()
    curator["archived"] = [s for s in curator.get("archived", []) if s != skill_id]
    overrides[skill_id] = True
    _save_curator(curator)
    _save_overrides(overrides)
    return {"ok": True, "restored": skill_id}


@router.post("/curator/run")
async def curator_run():
    """Run curator: report usage stats and suggest which to archive."""
    curator = _load_curator()
    skills = _build_skill_list()
    pinned = set(curator.get("pinned", []))
    archived = set(curator.get("archived", []))
    usage = curator.get("usage_counts", {})

    suggestions = []
    for s in skills:
        sid = s["id"]
        if sid in pinned or sid in archived or s.get("builtin"):
            continue
        if usage.get(sid, 0) == 0:
            suggestions.append({"skill_id": sid, "reason": "never used", "action": "archive"})

    return {
        "ok": True,
        "skills_reviewed": len(skills),
        "archive_suggestions": suggestions,
        "pinned_count": len(pinned),
        "archived_count": len(archived),
    }
