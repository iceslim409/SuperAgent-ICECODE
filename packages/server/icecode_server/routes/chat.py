"""
ICECODE Chat API — real-time SSE streaming with full agent tool loop.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

sys.path.insert(0, str(Path(__file__).parents[4] / "core"))

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Cache configured providers for 30s to avoid reading providers.json on every request
_providers_cache: list = []
_providers_cache_ts: float = 0.0
_PROVIDERS_TTL = 30.0

# Cache Ollama model list for 60s (avoids blocking httpx.get on every request)
_ollama_cache: str = ""
_ollama_cache_ts: float = 0.0
_OLLAMA_TTL = 60.0


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
    autopilot: bool = False
    active_skills: List[str] = []    # skill slugs/ids to inject into system prompt
    auto_skills: bool = False         # auto-detect relevant skills from message


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

    # ── Semantic Cache check ──────────────────────────────────────────────────
    try:
        from icecode.cache import get_cache as _get_cache
        _cache = _get_cache()
        cached = _cache.get(request.message, model=request.model or "")
        if cached:
            yield f"data: {json.dumps({'type': 'cache_hit', 'message': 'Response from cache (0 tokens consumed)'})}\n\n"
            yield f"data: {json.dumps({'type': 'text', 'content': cached})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'usage': {'total_tokens': 0, 'cached': True}})}\n\n"
            return
    except Exception:
        _cache = None

    # ── Context Compression ───────────────────────────────────────────────────
    compression_info = None
    if history:
        try:
            from icecode.optimizer.context_compressor import compress as _compress
            compressed_history, tokens_saved = _compress(history)
            if tokens_saved > 0:
                history = compressed_history
                compression_info = {"tokens_saved": tokens_saved}
        except Exception:
            pass

    # ── Model selection: explicit > configured default (no blind auto-routing) ──
    if request.model:
        actual_model = request.model
        router_info = None
    else:
        # Always use the configured default — avoids routing to unconfigured cloud models
        actual_model = _default_model()
        router_info = None

    # Build system_extra from active skills
    system_extra = ""
    all_skill_slugs = list(request.active_skills)

    # Auto-detect additional relevant skills from message
    auto_detected: List[str] = []
    if request.auto_skills:
        try:
            from icecode_server.routes.skills import auto_detect_skills
            auto_detected = auto_detect_skills(request.message, limit=4)
            # merge without duplicates
            for s in auto_detected:
                if s not in all_skill_slugs:
                    all_skill_slugs.append(s)
        except Exception as e:
            logger.warning(f"Auto-detect skills failed: {e}")

    if all_skill_slugs:
        try:
            from icecode_server.routes.skills import load_skill_content
            injected = []
            for sid in all_skill_slugs[:8]:
                content = load_skill_content(sid)
                if content:
                    label = f"{sid} [auto]" if sid in auto_detected else sid
                    injected.append(f"### SKILL: {label}\n{content[:3000]}")
            if injected:
                system_extra = "\n\n=== ACTIVE SKILLS ===\n" + "\n\n---\n\n".join(injected)
                if auto_detected:
                    system_extra = f"\n\n[Auto-detected skills: {', '.join(auto_detected)}]" + system_extra
        except Exception as e:
            logger.warning(f"Could not load skills: {e}")

    agent = ICECodeAgent(
        model=actual_model,
        provider=request.provider or _default_provider(),
        base_url=request.base_url,
        max_iterations=request.max_iterations,
        session_id=session_id,
        enable_computer=request.enable_computer,
        autopilot=request.autopilot,
        system_extra=system_extra,
    )
    agent.history = history

    # Emit router decision as first chunk if auto-routing was used
    if router_info:
        yield f"data: {json.dumps({'type': 'router', **router_info})}\n\n"

    # Emit compression info if context was trimmed
    if compression_info:
        yield f"data: {json.dumps({'type': 'compression', **compression_info})}\n\n"

    # Emit auto-detected skills so UI can display them
    if auto_detected:
        yield f"data: {json.dumps({'type': 'skills_detected', 'skills': auto_detected})}\n\n"

    full_response = []
    async for chunk in agent.stream(request.message):
        if chunk.get("type") == "text":
            full_response.append(chunk.get("content", ""))
        yield f"data: {json.dumps(chunk)}\n\n"

    # Store response in semantic cache
    if _cache is not None and full_response:
        try:
            u = agent.usage.to_dict()
            tokens = u.get("prompt_tokens", 0) + u.get("completion_tokens", 0)
            info = {}
            try:
                from icecode.optimizer.cost_router import COST_TABLE
                info = COST_TABLE.get(actual_model, COST_TABLE.get("__local__", {}))
            except Exception:
                pass
            cost = (
                u.get("prompt_tokens", 0) * info.get("input", 0) +
                u.get("completion_tokens", 0) * info.get("output", 0)
            ) / 1000
            _cache.set(request.message, "".join(full_response),
                       model=actual_model, tokens_used=tokens, cost_usd=cost)
        except Exception:
            pass

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


def _get_configured_providers() -> list:
    """Load enabled providers from providers.json that have an API key and models (cached 30s)."""
    global _providers_cache, _providers_cache_ts
    now = time.monotonic()
    if now - _providers_cache_ts < _PROVIDERS_TTL:
        return _providers_cache
    try:
        from icecode_server.routes.providers import _load_providers
        _providers_cache = [
            p for p in _load_providers()
            if p.get("enabled", True) and p.get("api_key") and p.get("models")
        ]
    except Exception:
        _providers_cache = []
    _providers_cache_ts = now
    return _providers_cache


def _default_provider() -> str:
    """Return first fully configured provider (has key + models), fallback to ollama."""
    providers = _get_configured_providers()
    if providers:
        return providers[0]["id"]
    return "ollama"


def _best_ollama_model() -> str:
    """Return best installed Ollama model (cached 60s). Never blocks the event loop."""
    global _ollama_cache, _ollama_cache_ts
    now = time.monotonic()
    if _ollama_cache and now - _ollama_cache_ts < _OLLAMA_TTL:
        return _ollama_cache
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
                        _ollama_cache = m
                        _ollama_cache_ts = now
                        return m
            if installed:
                _ollama_cache = installed[0]
                _ollama_cache_ts = now
                return installed[0]
    except Exception:
        pass
    return "qwen2.5:7b"


def _default_model() -> str:
    """Return default model from first fully configured provider, fallback to best Ollama."""
    providers = _get_configured_providers()
    if providers:
        p = providers[0]
        model = p.get("default_model") or (p.get("models") or [None])[0]
        if model:
            return model
    return _best_ollama_model()


@router.get("/available-models")
async def available_models():
    """Combined list of all available models (local + cloud providers)."""
    result = {"local": {}, "cloud": [], "default_provider": _default_provider(), "default_model": _default_model()}

    # Ollama local models
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code == 200:
            result["local"]["ollama"] = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass

    # Configured cloud providers (already filtered for key+models in _get_configured_providers)
    for p in _get_configured_providers():
        result["cloud"].append({
            "id": p["id"],
            "name": p.get("name", p["id"]),
            "models": p["models"],
            "default_model": p.get("default_model", ""),
        })

    return result


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
        except (WebSocketDisconnect, Exception):
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

            ws_alive = True
            try:
                async for chunk in agent.stream(message):
                    if cancel_event.is_set():
                        try:
                            await websocket.send_json({"type": "cancelled"})
                        except (WebSocketDisconnect, RuntimeError):
                            ws_alive = False
                        break
                    try:
                        await websocket.send_json(chunk)
                    except (WebSocketDisconnect, RuntimeError):
                        ws_alive = False
                        break
            except WebSocketDisconnect:
                ws_alive = False
            except Exception as e:
                try:
                    await websocket.send_json({"type": "error", "content": str(e)})
                except (WebSocketDisconnect, RuntimeError):
                    ws_alive = False

            # Persist session regardless of connection state
            try:
                store.save(session_id, agent.history, {
                    "model": actual_model,
                    "provider": msg_data.get("provider"),
                    "usage": agent.usage.to_dict(),
                })
            except Exception:
                pass

            if not ws_alive:
                break
            try:
                await websocket.send_json({"type": "done", "session_id": session_id})
            except (WebSocketDisconnect, RuntimeError):
                break

    except WebSocketDisconnect:
        pass
    finally:
        receiver.cancel()
        try:
            await receiver
        except asyncio.CancelledError:
            pass
