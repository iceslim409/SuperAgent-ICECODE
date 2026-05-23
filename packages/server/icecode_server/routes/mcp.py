"""ICECODE MCP API — manage and connect to MCP servers"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class MCPServerCreate(BaseModel):
    name: str
    transport: str = "stdio"  # stdio | sse | http
    command: Optional[str] = None
    args: List[str] = []
    url: Optional[str] = None
    env: Dict[str, str] = {}


def _load() -> list:
    import json
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    f = cfg.home_dir / "data" / "mcp_servers.json"
    return json.loads(f.read_text()) if f.exists() else []


def _save(servers: list):
    import json
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    f = cfg.home_dir / "data" / "mcp_servers.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(servers, indent=2))


async def _connect_stdio(server: dict) -> list:
    """Connect to a stdio MCP server and return its tools."""
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        raise RuntimeError("mcp package not installed — run: pip install mcp")

    import shutil
    cmd = server.get("command", "")
    if not shutil.which(cmd):
        raise RuntimeError(f"Command not found: '{cmd}'. Install it first (e.g. npm install -g @modelcontextprotocol/server-filesystem)")

    params = StdioServerParameters(
        command=cmd,
        args=server.get("args") or [],
        env=server.get("env") or None,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return [{"name": t.name, "description": t.description or ""} for t in result.tools]


async def _connect_sse(server: dict) -> list:
    """Connect to a SSE/HTTP MCP server and return its tools."""
    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client
    except ImportError:
        raise RuntimeError("mcp package not installed — run: pip install mcp")

    url = server.get("url", "")
    if not url:
        raise RuntimeError("URL is required for SSE/HTTP transport")

    async with sse_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return [{"name": t.name, "description": t.description or ""} for t in result.tools]


@router.get("/")
async def list_servers():
    return _load()


@router.post("/")
async def add_server(req: MCPServerCreate):
    servers = _load()
    server = {
        "id": f"mcp_{uuid.uuid4().hex[:8]}",
        "name": req.name,
        "transport": req.transport,
        "command": req.command,
        "args": req.args,
        "url": req.url,
        "env": req.env,
        "enabled": True,
        "status": "disconnected",
        "tools": [],
        "tools_count": 0,
        "error": None,
    }
    servers.append(server)
    _save(servers)
    return server


@router.delete("/{server_id}")
async def remove_server(server_id: str):
    servers = [s for s in _load() if s["id"] != server_id]
    _save(servers)
    return {"ok": True}


@router.post("/{server_id}/connect")
async def connect_server(server_id: str):
    """Connect to MCP server, discover tools, update status."""
    servers = _load()
    server = next((s for s in servers if s["id"] == server_id), None)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    server["status"] = "connecting"
    server["error"] = None
    _save(servers)

    try:
        transport = server.get("transport", "stdio")
        if transport == "stdio":
            tools = await asyncio.wait_for(_connect_stdio(server), timeout=15.0)
        elif transport in ("sse", "http"):
            tools = await asyncio.wait_for(_connect_sse(server), timeout=10.0)
        else:
            raise ValueError(f"Unknown transport: {transport}")

        server["status"] = "connected"
        server["tools"] = tools
        server["tools_count"] = len(tools)
        server["error"] = None

    except asyncio.TimeoutError:
        server["status"] = "error"
        server["error"] = "Connection timed out (15s)"
        server["tools"] = []
        server["tools_count"] = 0
    except Exception as e:
        server["status"] = "error"
        server["error"] = str(e)
        server["tools"] = []
        server["tools_count"] = 0

    _save(servers)
    return {
        "ok": server["status"] == "connected",
        "status": server["status"],
        "tools_count": server["tools_count"],
        "tools": server["tools"],
        "error": server.get("error"),
    }


@router.post("/{server_id}/disconnect")
async def disconnect_server(server_id: str):
    servers = _load()
    server = next((s for s in servers if s["id"] == server_id), None)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    server["status"] = "disconnected"
    server["tools"] = []
    server["tools_count"] = 0
    _save(servers)
    return {"ok": True}
