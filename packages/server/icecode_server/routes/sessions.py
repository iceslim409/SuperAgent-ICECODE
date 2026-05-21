"""ICECODE Sessions API"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/")
async def list_sessions():
    try:
        from icecode.config.settings import ICECodeSettings
        from icecode.state import ICECodeState
        cfg = ICECodeSettings()
        state = ICECodeState(str(cfg.db_path))
        return await state.list_sessions()
    except Exception as e:
        return []


@router.get("/{session_id}")
async def get_session(session_id: str):
    try:
        from icecode.config.settings import ICECodeSettings
        from icecode.state import ICECodeState
        cfg = ICECodeSettings()
        state = ICECodeState(str(cfg.db_path))
        return await state.get_session(session_id)
    except Exception as e:
        raise HTTPException(404, str(e))


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    try:
        from icecode.config.settings import ICECodeSettings
        from icecode.state import ICECodeState
        cfg = ICECodeSettings()
        state = ICECodeState(str(cfg.db_path))
        await state.delete_session(session_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/search")
async def search_sessions(q: str = ""):
    """FTS5 full-text search across all sessions."""
    try:
        from icecode.config.settings import ICECodeSettings
        from icecode.state import ICECodeState
        cfg = ICECodeSettings()
        state = ICECodeState(str(cfg.db_path))
        return await state.search_sessions(q)
    except Exception as e:
        return []
