"""ICECODE Files API — sandboxed file access"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/files", tags=["files"])

ALLOWED_ROOTS = [Path.home() / ".icecode", Path.cwd()]


def _safe_path(p: str) -> Path:
    path = Path(p).resolve()
    for root in ALLOWED_ROOTS:
        try:
            path.relative_to(root.resolve())
            return path
        except ValueError:
            continue
    raise HTTPException(403, f"Path not allowed: {p}")


@router.get("/read")
async def read_file(path: str):
    p = _safe_path(path)
    if not p.exists():
        raise HTTPException(404, "File not found")
    if p.is_dir():
        return {"type": "dir", "entries": [str(e.name) for e in p.iterdir()]}
    return {"type": "file", "content": p.read_text(errors="replace"), "size": p.stat().st_size}


class WriteRequest(BaseModel):
    path: str
    content: str


@router.post("/write")
async def write_file(req: WriteRequest):
    p = _safe_path(req.path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(req.content)
    return {"ok": True, "path": str(p)}
