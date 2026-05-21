"""
ICECODE Kanban — task tracking for agents and users.
Ported from Hermes kanban system.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/kanban", tags=["kanban"])

_HOME = Path.home() / ".icecode"
_DB_FILE = _HOME / "data" / "kanban.json"

STATUSES = ("todo", "in_progress", "done", "blocked", "cancelled")
PRIORITIES = ("low", "medium", "high", "urgent")


def _load() -> dict:
    if _DB_FILE.exists():
        try:
            return json.loads(_DB_FILE.read_text())
        except Exception:
            pass
    return {"boards": {"default": {"tasks": []}}}


def _save(data: dict):
    _DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DB_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _get_board(data: dict, board: str) -> dict:
    if board not in data["boards"]:
        data["boards"][board] = {"tasks": []}
    return data["boards"][board]


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "todo"
    priority: str = "medium"
    agent_id: Optional[str] = None
    board: str = "default"
    tags: List[str] = []
    due_date: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    agent_id: Optional[str] = None
    tags: Optional[List[str]] = None
    due_date: Optional[str] = None


@router.get("/boards")
async def list_boards():
    data = _load()
    result = []
    for bname, bdata in data["boards"].items():
        tasks = bdata.get("tasks", [])
        result.append({
            "name": bname,
            "task_count": len(tasks),
            "todo": sum(1 for t in tasks if t.get("status") == "todo"),
            "in_progress": sum(1 for t in tasks if t.get("status") == "in_progress"),
            "done": sum(1 for t in tasks if t.get("status") == "done"),
        })
    return result


@router.get("/tasks")
async def list_tasks(board: str = "default", status: Optional[str] = None):
    data = _load()
    tasks = _get_board(data, board).get("tasks", [])
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    return sorted(tasks, key=lambda t: {"urgent": 0, "high": 1, "medium": 2, "low": 3}.get(t.get("priority", "medium"), 2))


@router.post("/tasks")
async def create_task(req: TaskCreate):
    if req.status not in STATUSES:
        raise HTTPException(400, f"status must be one of: {STATUSES}")
    if req.priority not in PRIORITIES:
        raise HTTPException(400, f"priority must be one of: {PRIORITIES}")

    data = _load()
    board = _get_board(data, req.board)

    task = {
        "id": f"task_{uuid.uuid4().hex[:8]}",
        "title": req.title,
        "description": req.description or "",
        "status": req.status,
        "priority": req.priority,
        "agent_id": req.agent_id,
        "board": req.board,
        "tags": req.tags,
        "due_date": req.due_date,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    board["tasks"].append(task)
    _save(data)
    return task


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    data = _load()
    for bdata in data["boards"].values():
        for t in bdata.get("tasks", []):
            if t["id"] == task_id:
                return t
    raise HTTPException(404, f"Task {task_id} not found")


@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, req: TaskUpdate):
    data = _load()
    for bdata in data["boards"].values():
        for t in bdata.get("tasks", []):
            if t["id"] == task_id:
                if req.title is not None: t["title"] = req.title
                if req.description is not None: t["description"] = req.description
                if req.status is not None:
                    if req.status not in STATUSES:
                        raise HTTPException(400, f"status must be one of: {STATUSES}")
                    t["status"] = req.status
                if req.priority is not None: t["priority"] = req.priority
                if req.agent_id is not None: t["agent_id"] = req.agent_id
                if req.tags is not None: t["tags"] = req.tags
                if req.due_date is not None: t["due_date"] = req.due_date
                t["updated_at"] = datetime.now().isoformat()
                _save(data)
                return t
    raise HTTPException(404, f"Task {task_id} not found")


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    data = _load()
    for bdata in data["boards"].values():
        for i, t in enumerate(bdata.get("tasks", [])):
            if t["id"] == task_id:
                bdata["tasks"].pop(i)
                _save(data)
                return {"ok": True, "deleted": task_id}
    raise HTTPException(404, f"Task {task_id} not found")


@router.get("/stats")
async def kanban_stats():
    data = _load()
    all_tasks = []
    for bdata in data["boards"].values():
        all_tasks.extend(bdata.get("tasks", []))
    return {
        "total": len(all_tasks),
        "by_status": {s: sum(1 for t in all_tasks if t.get("status") == s) for s in STATUSES},
        "by_priority": {p: sum(1 for t in all_tasks if t.get("priority") == p) for p in PRIORITIES},
        "boards": len(data["boards"]),
    }
