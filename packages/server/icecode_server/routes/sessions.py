"""ICECODE Sessions API"""
from __future__ import annotations
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _store():
    from icecode.agent.core import get_session_store
    return get_session_store()


@router.get("/")
async def list_sessions():
    try:
        return _store().list_sessions()
    except Exception:
        return []


@router.get("/search")
async def search_sessions(q: str = ""):
    """Text search across session titles and previews."""
    try:
        sessions = _store().list_sessions()
        if not q:
            return sessions
        q_lower = q.lower()
        return [
            s for s in sessions
            if q_lower in s.get("title", "").lower()
            or q_lower in s.get("preview", "").lower()
        ]
    except Exception:
        return []


@router.get("/{session_id}")
async def get_session(session_id: str):
    try:
        data = _store().load(session_id)
        if not data:
            raise HTTPException(404, "Session not found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(404, str(e))


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    try:
        store = _store()
        path = store.session_dir / f"{session_id}.json"
        if path.exists():
            path.unlink()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{session_id}/export")
async def export_session(session_id: str, format: str = "json"):
    """Export a session as JSON or Markdown."""
    try:
        session = _store().load(session_id)
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
                if isinstance(content, list):
                    content = " ".join(
                        p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
                    )
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
