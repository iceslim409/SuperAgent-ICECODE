"""ICECODE Knowledge Base API — local RAG with manual + automatic indexing."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parents[4] / "core"))

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

_UPLOAD_DIR = Path.home() / ".icecode" / "data" / "knowledge" / "uploads"
_AUTO_CFG   = Path.home() / ".icecode" / "data" / "knowledge" / "auto_config.json"

# ── Auto-index config helpers ──────────────────────────────────────────────

_DEFAULT_AUTO_CFG = {
    "enabled": False,
    "path": "",
    "interval_minutes": 60,
    "last_indexed": None,
    "last_chunks": 0,
    "status": "idle",
}

def _load_auto_cfg() -> dict:
    try:
        if _AUTO_CFG.exists():
            return {**_DEFAULT_AUTO_CFG, **json.loads(_AUTO_CFG.read_text())}
    except Exception:
        pass
    return dict(_DEFAULT_AUTO_CFG)

def _save_auto_cfg(cfg: dict) -> None:
    _AUTO_CFG.parent.mkdir(parents=True, exist_ok=True)
    _AUTO_CFG.write_text(json.dumps(cfg, indent=2, default=str))

# ── Background auto-index loop ─────────────────────────────────────────────

async def start_auto_index_task():
    """Long-running background task — re-indexes on schedule when enabled."""
    while True:
        cfg = _load_auto_cfg()
        if cfg.get("enabled") and cfg.get("path"):
            path = Path(cfg["path"]).expanduser()
            if path.exists():
                cfg["status"] = "indexing"
                _save_auto_cfg(cfg)
                try:
                    from icecode.knowledge.manager import KnowledgeManager
                    result = KnowledgeManager.instance().index_directory(
                        str(path), recursive=True
                    )
                    cfg.update({
                        "status": "idle",
                        "last_indexed": datetime.now(timezone.utc).isoformat(),
                        "last_chunks": result.get("indexed", 0),
                    })
                except Exception as e:
                    cfg["status"] = f"error: {e}"
                _save_auto_cfg(cfg)
            interval = max(1, cfg.get("interval_minutes", 60))
        else:
            interval = 5  # poll config every 5 min while disabled

        await asyncio.sleep(interval * 60)

# ── Pydantic models ────────────────────────────────────────────────────────

class IndexPathRequest(BaseModel):
    path: str
    recursive: bool = True

class SearchRequest(BaseModel):
    query: str
    k: int = 5

class AutoIndexConfig(BaseModel):
    enabled: bool
    path: str = ""
    interval_minutes: int = 60

# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/stats")
async def knowledge_stats():
    """Knowledge base statistics."""
    try:
        from icecode.knowledge.manager import KnowledgeManager
        return KnowledgeManager.instance().stats()
    except Exception as e:
        return {"rag_available": False, "error": str(e)}


@router.get("/auto-index")
async def get_auto_index_config():
    """Get auto-index configuration and last-run status."""
    return _load_auto_cfg()


@router.post("/auto-index")
async def set_auto_index_config(req: AutoIndexConfig):
    """Enable/disable auto-index and configure path + interval."""
    if req.enabled and not req.path:
        raise HTTPException(400, "path is required when enabling auto-index")
    cfg = _load_auto_cfg()
    cfg.update({
        "enabled": req.enabled,
        "path": req.path,
        "interval_minutes": max(1, req.interval_minutes),
    })
    _save_auto_cfg(cfg)
    return cfg


@router.post("/auto-index/run")
async def trigger_auto_index_now():
    """Trigger an immediate re-index of the configured auto-index path."""
    cfg = _load_auto_cfg()
    path_str = cfg.get("path", "")
    if not path_str:
        raise HTTPException(400, "No auto-index path configured. Set it via POST /api/knowledge/auto-index")
    path = Path(path_str).expanduser()
    if not path.exists():
        raise HTTPException(404, f"Path not found: {path_str}")
    try:
        from icecode.knowledge.manager import KnowledgeManager
        result = KnowledgeManager.instance().index_directory(str(path), recursive=True)
        cfg.update({
            "last_indexed": datetime.now(timezone.utc).isoformat(),
            "last_chunks": result.get("indexed", 0),
            "status": "idle",
        })
        _save_auto_cfg(cfg)
        return {**result, "auto_config": cfg}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/index")
async def index_path(req: IndexPathRequest):
    """Manually index a file or directory into the knowledge base."""
    try:
        from icecode.knowledge.manager import KnowledgeManager
        km = KnowledgeManager.instance()
        p = Path(req.path).expanduser()
        if p.is_dir():
            result = km.index_directory(str(p), recursive=req.recursive)
        elif p.is_file():
            result = km.index_file(str(p))
        else:
            raise HTTPException(404, f"Path not found: {req.path}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/upload")
async def upload_and_index(file: UploadFile = File(...)):
    """Upload a file and index it into the knowledge base."""
    try:
        from icecode.knowledge.manager import KnowledgeManager
        _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest = _UPLOAD_DIR / file.filename
        content = await file.read()
        dest.write_bytes(content)
        km = KnowledgeManager.instance()
        result = km.index_file(str(dest))
        return {**result, "filename": file.filename}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/search")
async def search_knowledge(q: str, k: int = 5):
    """Semantic search in the knowledge base."""
    try:
        from icecode.knowledge.manager import KnowledgeManager
        results = KnowledgeManager.instance().search(q, k=k)
        return {"query": q, "results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/search")
async def search_knowledge_post(req: SearchRequest):
    """Semantic search (POST version for larger queries)."""
    try:
        from icecode.knowledge.manager import KnowledgeManager
        results = KnowledgeManager.instance().search(req.query, k=req.k)
        return {"query": req.query, "results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/sources")
async def list_sources():
    """List all indexed sources."""
    try:
        from icecode.knowledge.manager import KnowledgeManager
        sources = KnowledgeManager.instance().list_sources()
        return {"sources": sources, "count": len(sources)}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/sources")
async def delete_source(path: str):
    """Remove a source from the knowledge base."""
    try:
        from icecode.knowledge.manager import KnowledgeManager
        removed = KnowledgeManager.instance().delete_source(path)
        return {"deleted": path, "chunks_removed": removed}
    except Exception as e:
        raise HTTPException(500, str(e))
