"""ICECODE Sessions API"""
from __future__ import annotations
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

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


@router.get("/{session_id}/export")
async def export_session(session_id: str, format: str = "json"):
    """Export a session as JSON or Markdown."""
    try:
        from icecode.config.settings import ICECodeSettings
        from icecode.state import ICECodeState
        cfg = ICECodeSettings()
        state = ICECodeState(str(cfg.db_path))
        session = await state.get_session(session_id)
        if not session:
            raise HTTPException(404, "Session not found")

        messages = session.get("messages", [])
        title = session.get("title") or session_id[:16]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        if format == "markdown":
            lines = [f"# {title}\n", f"*Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n---\n"]
            for m in messages:
                role = m.get("role", "unknown").capitalize()
                content = m.get("content", "")
                lines.append(f"**{role}**\n\n{content}\n\n---\n")
            body = "\n".join(lines)
            return Response(
                content=body,
                media_type="text/markdown",
                headers={"Content-Disposition": f'attachment; filename="session_{ts}.md"'},
            )
        else:
            body = json.dumps(session, ensure_ascii=False, indent=2)
            return Response(
                content=body,
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="session_{ts}.json"'},
            )
    except HTTPException:
        raise
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
