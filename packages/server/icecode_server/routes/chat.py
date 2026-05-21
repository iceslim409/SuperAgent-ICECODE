"""
ICECODE Chat API — real-time SSE streaming with full agent tool loop.
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

sys.path.insert(0, str(Path(__file__).parents[4] / "core"))

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None   # custom Ollama/LM Studio endpoint
    stream: bool = True
    max_iterations: int = 10
    enable_computer: bool = False


class SessionMessage(BaseModel):
    role: str
    content: str


async def _sse_stream(request: ChatRequest):
    """Yield SSE events from ICECodeAgent."""
    from icecode.agent.core import ICECodeAgent, get_session_store

    store = get_session_store()
    session_id = request.session_id or f"s_{uuid.uuid4().hex[:8]}"

    # Restore session history if continuing
    existing = store.load(session_id)
    history = existing["messages"] if existing else []

    # ICECODE Intelligent Model Router: auto-select model if none specified
    if request.model:
        actual_model = request.model
        router_info = None
    else:
        try:
            from icecode.router import get_router
            _r = get_router()
            decision = _r.route(request.message)
            actual_model = decision.model
            router_info = {"model": actual_model, "complexity": decision.complexity.value, "reason": decision.reason}
        except Exception:
            actual_model = _default_model()
            router_info = None

    agent = ICECodeAgent(
        model=actual_model,
        provider=request.provider or _default_provider(),
        base_url=request.base_url,
        max_iterations=request.max_iterations,
        session_id=session_id,
        enable_computer=request.enable_computer,
    )
    agent.history = history

    # Emit router decision as first chunk if auto-routing was used
    if router_info:
        yield f"data: {json.dumps({'type': 'router', **router_info})}\n\n"

    async for chunk in agent.stream(request.message):
        yield f"data: {json.dumps(chunk)}\n\n"

    # Persist session
    try:
        store.save(session_id, agent.history, {
            "model": actual_model,
            "provider": request.provider,
            "usage": agent.usage.to_dict(),
        })
    except Exception as e:
        logger.warning(f"Session save error: {e}")

    # Record token usage
    try:
        u = agent.usage.to_dict()
        import httpx as _hx
        _hx.post("http://localhost:13210/api/usage/record", json={
            "session_id":       session_id,
            "model":            actual_model,
            "provider":         request.provider or "ollama",
            "prompt_tokens":    u.get("prompt_tokens", 0),
            "completion_tokens": u.get("completion_tokens", 0),
            "tool_calls":       u.get("tool_calls", 0),
            "iterations":       u.get("iterations", 0),
            "elapsed_seconds":  u.get("elapsed_seconds", 0.0),
        }, timeout=2)
    except Exception:
        pass


def _default_provider() -> str:
    return "ollama"


def _default_model() -> str:
    """Pick best available Ollama model for chat."""
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code == 200:
            installed = [m["name"] for m in r.json().get("models", [])]
            prefs = ["qwen2.5:7b", "qwen3.5:4b", "mistral:7b-instruct",
                     "phi4-mini:latest", "granite4.1:3b", "qwen2.5:3b",
                     "qwen3.5:2b", "qwen2.5:1.5b", "llama3.2:1b",
                     "qwen2.5-coder:7b"]
            for p in prefs:
                for m in installed:
                    if m == p or m.startswith(p.split(":")[0] + ":" + p.split(":")[1]):
                        return m
            return installed[0] if installed else "qwen2.5:7b"
    except Exception:
        pass
    return "qwen2.5:7b"


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Stream agent response as SSE (text/event-stream)."""
    return StreamingResponse(
        _sse_stream(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/")
async def chat(request: ChatRequest):
    """Non-streaming chat — returns full response."""
    from icecode.agent.core import ICECodeAgent, get_session_store

    store = get_session_store()
    session_id = request.session_id or f"s_{uuid.uuid4().hex[:8]}"
    existing = store.load(session_id)

    agent = ICECodeAgent(
        model=request.model,
        provider=request.provider or _default_provider(),
        base_url=request.base_url,
        max_iterations=request.max_iterations,
        session_id=session_id,
    )
    if existing:
        agent.history = existing["messages"]

    chunks = []
    tool_calls = []
    async for chunk in agent.stream(request.message):
        if chunk.get("type") == "text":
            chunks.append(chunk["content"])
        elif chunk.get("type") == "tool_call":
            tool_calls.append(chunk["name"])

    actual_model = request.model or _default_model()
    try:
        store.save(session_id, agent.history, {
            "model": actual_model,
            "provider": request.provider,
            "usage": agent.usage.to_dict(),
        })
    except Exception:
        pass

    # Persist token usage asynchronously
    try:
        u = agent.usage.to_dict()
        import httpx as _hx
        _hx.post("http://localhost:13210/api/usage/record", json={
            "session_id":       session_id,
            "model":            actual_model,
            "provider":         request.provider or "ollama",
            "prompt_tokens":    u.get("prompt_tokens", 0),
            "completion_tokens": u.get("completion_tokens", 0),
            "tool_calls":       u.get("tool_calls", 0),
            "iterations":       u.get("iterations", 0),
            "elapsed_seconds":  u.get("elapsed_seconds", 0.0),
        }, timeout=2)
    except Exception:
        pass

    return {
        "session_id": session_id,
        "response": "".join(chunks),
        "tool_calls": tool_calls,
        "usage": agent.usage.to_dict(),
    }


@router.get("/sessions")
async def list_sessions():
    """List all chat sessions."""
    from icecode.agent.core import get_session_store
    return get_session_store().list_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session message history."""
    from icecode.agent.core import get_session_store
    data = get_session_store().load(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    return data


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    from pathlib import Path
    f = Path.home() / ".icecode" / "sessions" / f"{session_id}.json"
    if f.exists():
        f.unlink()
        return {"deleted": session_id}
    raise HTTPException(status_code=404, detail="Session not found")


@router.get("/memories")
async def list_memories():
    """List all agent memories."""
    import json as _json
    f = Path.home() / ".icecode" / "agent_memory" / "memories.json"
    if f.exists():
        return _json.loads(f.read_text())
    return {}


@router.websocket("/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """
    Bidirectional WebSocket endpoint for real-time chat.

    Client sends JSON: {"message": "...", "model": "...", "provider": "..."}
    Server streams JSON chunks: {"type": "text"|"tool_call"|"done"|"error", ...}
    Client can send {"type": "cancel"} to abort current generation.
    """
    from icecode.agent.core import ICECodeAgent, get_session_store

    await websocket.accept()
    store = get_session_store()
    cancel_event = asyncio.Event()

    async def receive_loop():
        """Listen for incoming messages from client."""
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "cancel":
                    cancel_event.set()
                elif data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                else:
                    await message_queue.put(data)
        except WebSocketDisconnect:
            await message_queue.put(None)

    message_queue: asyncio.Queue = asyncio.Queue()
    receiver = asyncio.create_task(receive_loop())

    try:
        while True:
            msg_data = await message_queue.get()
            if msg_data is None:
                break

            cancel_event.clear()
            message = msg_data.get("message", "")
            if not message:
                continue

            existing = store.load(session_id)
            history = existing["messages"] if existing else []
            actual_model = msg_data.get("model") or _default_model()

            agent = ICECodeAgent(
                model=actual_model,
                provider=msg_data.get("provider") or _default_provider(),
                base_url=msg_data.get("base_url"),
                max_iterations=msg_data.get("max_iterations", 10),
                session_id=session_id,
                enable_computer=msg_data.get("enable_computer", False),
            )
            agent.history = history

            try:
                async for chunk in agent.stream(message):
                    if cancel_event.is_set():
                        await websocket.send_json({"type": "cancelled"})
                        break
                    await websocket.send_json(chunk)
            except Exception as e:
                await websocket.send_json({"type": "error", "content": str(e)})

            # Persist session
            try:
                store.save(session_id, agent.history, {
                    "model": actual_model,
                    "provider": msg_data.get("provider"),
                    "usage": agent.usage.to_dict(),
                })
            except Exception:
                pass

            await websocket.send_json({"type": "done", "session_id": session_id})

    except WebSocketDisconnect:
        pass
    finally:
        receiver.cancel()
        try:
            await receiver
        except asyncio.CancelledError:
            pass
