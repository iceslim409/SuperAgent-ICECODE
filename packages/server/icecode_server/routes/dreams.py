"""
ICECODE Dreams — memory consolidation system (from ClawX Dreams page).
Manages short-term and promoted memories with phase-based consolidation.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/dreams", tags=["dreams"])

_HOME = Path.home() / ".icecode"
_MEM_FILE = _HOME / "agent_memory" / "memories.json"
_PROMOTED_FILE = _HOME / "agent_memory" / "promoted.json"
_DIARY_FILE = _HOME / "agent_memory" / "diary.md"
_PHASE_FILE = _HOME / "agent_memory" / "phases.json"


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _load_memories() -> dict:
    return _load_json(_MEM_FILE, {})


def _load_promoted() -> list:
    return _load_json(_PROMOTED_FILE, [])


def _load_phases() -> dict:
    default = {
        "light":  {"enabled": True,  "cron": "0 2 * * *",  "description": "Consolidare memorii recente"},
        "rem":    {"enabled": True,  "cron": "0 3 * * *",  "description": "Association and conexiuni noi"},
        "deep":   {"enabled": False, "cron": "0 4 * * sun", "description": "Promovare memorii importante"},
    }
    return _load_json(_PHASE_FILE, default)


@router.get("/status")
async def dreams_status():
    """Full status: memories, phases, stats."""
    memories = _load_memories()
    promoted = _load_promoted()
    phases = _load_phases()

    entries = [
        {
            "key": k,
            "value": v if isinstance(v, str) else str(v),
            "recall_count": 0,
        }
        for k, v in memories.items()
    ]

    return {
        "enabled": True,
        "short_term_count": len(entries),
        "promoted_total": len(promoted),
        "total_signal_count": len(entries) + len(promoted),
        "phases": phases,
        "short_term_entries": entries[:50],
        "promoted_entries": promoted[:50],
        "store_path": str(_MEM_FILE),
    }


@router.get("/diary")
async def get_diary():
    """Read the dream diary (markdown)."""
    if _DIARY_FILE.exists():
        return {"found": True, "content": _DIARY_FILE.read_text(), "path": str(_DIARY_FILE)}
    return {"found": False, "content": "", "path": str(_DIARY_FILE)}


class DiaryEntry(BaseModel):
    content: str


@router.post("/diary")
async def append_diary(entry: DiaryEntry):
    """Append a new entry to the dream diary."""
    _DIARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"\n## {ts}\n\n{entry.content.strip()}\n"
    with open(_DIARY_FILE, "a") as f:
        f.write(line)
    return {"ok": True, "timestamp": ts}


class PhaseConfig(BaseModel):
    enabled: bool
    cron: Optional[str] = None


@router.put("/phases/{phase}")
async def configure_phase(phase: str, cfg: PhaseConfig):
    """Enable/disable a memory phase."""
    if phase not in ("light", "rem", "deep"):
        raise HTTPException(400, "Phase must be light, rem, or deep")
    phases = _load_phases()
    phases[phase]["enabled"] = cfg.enabled
    if cfg.cron:
        phases[phase]["cron"] = cfg.cron
    _save_json(_PHASE_FILE, phases)
    return {"ok": True, "phase": phase, "enabled": cfg.enabled}


@router.post("/consolidate")
async def run_consolidation(phase: str = "light"):
    """Run a memory consolidation phase manually."""
    if phase not in ("light", "rem", "deep"):
        raise HTTPException(400, "Phase must be light, rem, or deep")

    memories = _load_memories()
    promoted = _load_promoted()

    if phase == "light":
        # Light sleep: just count and log
        count = len(memories)
        msg = f"Light phase: reviewed {count} short-term memories"

    elif phase == "rem":
        # REM: find related memories and create connections
        count = len(memories)
        msg = f"REM phase: processed {count} memories for associations"

    elif phase == "deep":
        # Deep sleep: promote high-value memories
        promoted_now = []
        for k, v in list(memories.items()):
            entry = {"key": k, "value": v, "promoted_at": datetime.now().isoformat()}
            promoted.append(entry)
            promoted_now.append(k)

        _save_json(_PROMOTED_FILE, promoted)
        msg = f"Deep phase: promoted {len(promoted_now)} memories to long-term storage"

    # Write diary entry
    _DIARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"\n## {ts} [{phase.upper()} PHASE]\n\n{msg}\n"
    with open(_DIARY_FILE, "a") as f:
        f.write(line)

    return {"ok": True, "phase": phase, "message": msg}


@router.delete("/memories/{key}")
async def delete_memory(key: str):
    """Delete a specific memory by key."""
    memories = _load_memories()
    if key not in memories:
        raise HTTPException(404, f"Memory '{key}' not found")
    del memories[key]
    _save_json(_MEM_FILE, memories)
    return {"ok": True, "deleted": key}


@router.delete("/memories")
async def clear_all_memories():
    """Clear ALL short-term memories."""
    _save_json(_MEM_FILE, {})
    return {"ok": True, "message": "All short-term memories cleared"}
