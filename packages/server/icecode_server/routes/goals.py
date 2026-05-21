"""
ICECODE Goals — persistent agent goals (from Hermes /goal + /subgoal).
Standing goals are injected into every agent prompt automatically.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/goals", tags=["goals"])

_FILE = Path.home() / ".icecode" / "data" / "goals.json"


def _load() -> list:
    if _FILE.exists():
        try:
            return json.loads(_FILE.read_text())
        except Exception:
            pass
    return []


def _save(goals: list):
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(goals, indent=2, ensure_ascii=False))


class GoalCreate(BaseModel):
    text: str
    priority: str = "medium"
    subgoals: List[str] = []


class SubgoalAdd(BaseModel):
    text: str


@router.get("/")
@router.get("")
async def list_goals():
    return _load()


@router.get("/active-prompt")
async def active_prompt():
    """Returns goals formatted as a system prompt injection."""
    goals = [g for g in _load() if not g.get("completed")]
    if not goals:
        return {"prompt": ""}
    lines = ["STANDING GOALS (always keep in mind):"]
    for g in goals:
        prefix = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(g.get("priority", "medium"), "•")
        lines.append(f"  {prefix} {g['text']}")
        for sub in g.get("subgoals", []):
            if not sub.get("completed"):
                lines.append(f"    → {sub['text']}")
    return {"prompt": "\n".join(lines)}


@router.post("/")
@router.post("")
async def create_goal(req: GoalCreate):
    goals = _load()
    goal = {
        "id": f"goal_{uuid.uuid4().hex[:8]}",
        "text": req.text,
        "priority": req.priority,
        "completed": False,
        "subgoals": [
            {"id": f"sg_{uuid.uuid4().hex[:6]}", "text": s, "completed": False}
            for s in req.subgoals
        ],
        "created_at": datetime.now().isoformat(),
    }
    goals.append(goal)
    _save(goals)
    return goal


@router.post("/{goal_id}/subgoal")
async def add_subgoal(goal_id: str, req: SubgoalAdd):
    goals = _load()
    for g in goals:
        if g["id"] == goal_id:
            g.setdefault("subgoals", []).append({
                "id": f"sg_{uuid.uuid4().hex[:6]}",
                "text": req.text,
                "completed": False,
            })
            _save(goals)
            return g
    raise HTTPException(404, f"Goal {goal_id} not found")


@router.post("/{goal_id}/complete")
async def complete_goal(goal_id: str):
    goals = _load()
    for g in goals:
        if g["id"] == goal_id:
            g["completed"] = True
            g["completed_at"] = datetime.now().isoformat()
            _save(goals)
            return g
    raise HTTPException(404, f"Goal {goal_id} not found")


@router.delete("/{goal_id}")
async def delete_goal(goal_id: str):
    goals = _load()
    goals = [g for g in goals if g["id"] != goal_id]
    _save(goals)
    return {"ok": True}


@router.delete("/")
async def clear_completed():
    goals = [g for g in _load() if not g.get("completed")]
    _save(goals)
    return {"ok": True, "remaining": len(goals)}
