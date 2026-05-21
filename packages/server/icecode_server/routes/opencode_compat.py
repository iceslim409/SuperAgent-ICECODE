"""
OpenCode-compatible API layer — expune rutele pe care SDK-ul TypeScript le aşteaptă.

Formatul: /session, /session/{id}/message, /provider, /config, /global/event
Acestea mapează la engine-ul Python existent.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parents[4] / "core"))

router = APIRouter(tags=["opencode-compat"])


# ── Models ──────────────────────────────────────────────────────────────────

class SessionCreateBody(BaseModel):
    parentID: Optional[str] = None
    title: Optional[str] = None


class MessagePromptBody(BaseModel):
    messageID: Optional[str] = None
    model: Optional[Dict[str, str]] = None
    agent: Optional[str] = None
    noReply: bool = False
    system: Optional[str] = None
    parts: List[Dict[str, Any]] = []


# ── Helper ───────────────────────────────────────────────────────────────────

def _make_session(session_id: str, title: Optional[str] = None) -> Dict:
    return {
        "id": session_id,
        "projectID": "default",
        "directory": str(Path.cwd()),
        "title": title or f"Session {session_id[:8]}",
        "time": {"created": int(datetime.now().timestamp() * 1000), "updated": int(datetime.now().timestamp() * 1000)},
        "version": "2.0.0",
    }


def _parts_to_text(parts: List[Dict[str, Any]]) -> str:
    texts = []
    for p in parts:
        if p.get("type") == "text":
            texts.append(p.get("text", ""))
    return " ".join(texts)


async def _sse_compat_stream(session_id: str, message: str, model_info: Optional[Dict] = None):
    """Rulează agentul Python şi emite events în formatul OpenCode."""
    from icecode.agent.core import ICECodeAgent, get_session_store

    store = get_session_store()
    existing = store.load(session_id)
    history = existing["messages"] if existing else []

    model = None
    provider = None
    if model_info:
        model = model_info.get("modelID")
        provider = model_info.get("providerID")

    agent = ICECodeAgent(
        model=model,
        provider=provider,
        session_id=session_id,
    )

    msg_id = f"msg_{uuid.uuid4().hex[:8]}"
    assistant_msg_id = f"msg_{uuid.uuid4().hex[:8]}"

    # Confirmăm că mesajul a fost primit
    yield f"data: {json.dumps({'type': 'session.updated', 'properties': {'id': session_id}})}\n\n"

    full_text = ""
    try:
        async for event in agent.run_stream(message, history=history):
            etype = event.get("type", "")

            if etype == "text":
                chunk = event.get("text", "")
                full_text += chunk
                payload = {
                    "type": "message.part.updated",
                    "properties": {
                        "sessionID": session_id,
                        "messageID": assistant_msg_id,
                        "part": {
                            "type": "text",
                            "text": chunk,
                            "time": {"start": int(datetime.now().timestamp() * 1000)},
                        }
                    }
                }
                yield f"data: {json.dumps(payload)}\n\n"

            elif etype == "tool_call":
                payload = {
                    "type": "message.part.updated",
                    "properties": {
                        "sessionID": session_id,
                        "messageID": assistant_msg_id,
                        "part": {
                            "type": "tool-invocation",
                            "toolInvocation": {
                                "state": "call",
                                "toolCallId": event.get("id", uuid.uuid4().hex[:8]),
                                "toolName": event.get("name", ""),
                                "args": event.get("input", {}),
                            }
                        }
                    }
                }
                yield f"data: {json.dumps(payload)}\n\n"

            elif etype == "tool_result":
                payload = {
                    "type": "message.part.updated",
                    "properties": {
                        "sessionID": session_id,
                        "messageID": assistant_msg_id,
                        "part": {
                            "type": "tool-invocation",
                            "toolInvocation": {
                                "state": "result",
                                "toolCallId": event.get("id", uuid.uuid4().hex[:8]),
                                "toolName": event.get("name", ""),
                                "result": event.get("content", ""),
                            }
                        }
                    }
                }
                yield f"data: {json.dumps(payload)}\n\n"

            elif etype == "usage":
                payload = {
                    "type": "message.updated",
                    "properties": {
                        "sessionID": session_id,
                        "message": {
                            "id": assistant_msg_id,
                            "role": "assistant",
                            "tokens": {
                                "input": event.get("input_tokens", 0),
                                "output": event.get("output_tokens", 0),
                                "cache": {"read": 0, "write": 0},
                            }
                        }
                    }
                }
                yield f"data: {json.dumps(payload)}\n\n"

            elif etype in ("done", "error"):
                break

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'properties': {'message': str(e)}})}\n\n"

    # Mesaj final
    yield f"data: {json.dumps({'type': 'message.updated', 'properties': {'sessionID': session_id, 'message': {'id': assistant_msg_id, 'role': 'assistant', 'finishReason': 'stop'}}})}\n\n"
    yield "data: [DONE]\n\n"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/session")
async def list_sessions():
    """Listează toate sesiunile."""
    from icecode.agent.core import get_session_store
    store = get_session_store()
    sessions = store.list() if hasattr(store, "list") else []
    result = []
    for s in sessions:
        result.append(_make_session(s.get("id", uuid.uuid4().hex[:8]), s.get("title")))
    return result


@router.post("/session")
async def create_session(body: SessionCreateBody = None):
    """Creează o sesiune nouă."""
    session_id = f"ses_{uuid.uuid4().hex[:8]}"
    return _make_session(session_id, body.title if body else None)


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Returnează o sesiune după ID."""
    from icecode.agent.core import get_session_store
    store = get_session_store()
    existing = store.load(session_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Session not found")
    return _make_session(session_id, existing.get("title"))


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Şterge o sesiune."""
    from icecode.agent.core import get_session_store
    store = get_session_store()
    store.delete(session_id)
    return {"ok": True}


@router.get("/session/{session_id}/message")
async def list_messages(session_id: str):
    """Listează mesajele unei sesiuni."""
    from icecode.agent.core import get_session_store
    store = get_session_store()
    existing = store.load(session_id)
    messages = existing.get("messages", []) if existing else []
    result = []
    for i, m in enumerate(messages):
        result.append({
            "id": m.get("id", f"msg_{i}"),
            "sessionID": session_id,
            "role": m.get("role", "user"),
            "parts": [{"type": "text", "text": m.get("content", "")}],
            "time": {"created": int(datetime.now().timestamp() * 1000)},
        })
    return result


@router.post("/session/{session_id}/message")
async def send_message(session_id: str, body: MessagePromptBody, request: Request):
    """Trimite un mesaj şi streamează răspunsul (SSE)."""
    text = _parts_to_text(body.parts)
    if not text:
        raise HTTPException(status_code=400, detail="No text content in parts")

    model_info = body.model

    return StreamingResponse(
        _sse_compat_stream(session_id, text, model_info),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/session/{session_id}/abort")
async def abort_session(session_id: str):
    """Opreşte generarea curentă."""
    return {"ok": True}


@router.get("/session/{session_id}/revert")
async def revert_session(session_id: str):
    return {"ok": True}


@router.get("/provider")
async def list_providers():
    """Listează providerii disponibili."""
    providers = []
    provider_list = [
        ("anthropic", "Anthropic", ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"]),
        ("openai", "OpenAI", ["gpt-4o", "gpt-4o-mini", "o1", "o3-mini"]),
        ("google", "Google", ["gemini-2.0-flash", "gemini-1.5-pro"]),
        ("ollama", "Ollama (local)", ["llama3", "mistral", "phi3"]),
        ("groq", "Groq", ["llama-3.1-70b-versatile", "mixtral-8x7b-32768"]),
    ]
    for pid, name, models in provider_list:
        providers.append({
            "id": pid,
            "name": name,
            "enabled": True,
            "models": [
                {"id": m, "name": m, "attachment": False, "reasoning": False, "temperature": True}
                for m in models
            ],
        })
    return providers


@router.get("/provider/auth")
async def list_provider_auth():
    return []


@router.get("/config")
async def get_config():
    """Returnează configuraţia curentă."""
    return {
        "version": "2.0.0",
        "theme": "dark",
        "autoshare": False,
        "keybinds": {},
        "providers": {},
        "models": {},
        "mcp": {},
    }


@router.post("/config")
async def update_config(body: Dict[str, Any]):
    return body


@router.get("/config/providers")
async def get_config_providers():
    return {}


@router.get("/global/event")
async def global_event_stream():
    """SSE stream pentru evenimente globale."""
    async def gen():
        yield f"data: {json.dumps({'type': 'server.ready', 'properties': {'version': '2.0.0'}})}\n\n"
        while True:
            await asyncio.sleep(30)
            yield f"data: {json.dumps({'type': 'ping'})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/agent")
async def list_agents():
    return [{"id": "icecode", "name": "ICECODE Agent", "description": "Default ICECODE agent"}]


@router.get("/path")
async def get_path(request: Request):
    directory = request.query_params.get("directory", str(Path.cwd()))
    return {"path": directory}


@router.get("/project")
async def list_projects():
    return []


@router.get("/project/current")
async def current_project(request: Request):
    directory = request.query_params.get("directory", str(Path.cwd()))
    return {"id": "default", "directory": directory, "path": directory}


@router.get("/log")
async def get_log():
    return []


@router.get("/find")
async def find(request: Request):
    return {"files": [], "symbols": []}


@router.get("/find/file")
async def find_file(request: Request):
    return []


@router.get("/find/symbol")
async def find_symbol(request: Request):
    return []
