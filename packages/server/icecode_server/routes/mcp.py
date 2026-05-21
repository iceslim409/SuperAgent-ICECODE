"""ICECODE MCP API — manage MCP servers"""
from __future__ import annotations

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


def _load():
    import json
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    f = cfg.home_dir / "data" / "mcp_servers.json"
    return json.loads(f.read_text()) if f.exists() else []


def _save(servers):
    import json
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    f = cfg.home_dir / "data" / "mcp_servers.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(servers, indent=2))


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
    """Connect to an MCP server and discover tools."""
    # Integration with packages/mcp TypeScript client via subprocess/IPC
    return {"ok": True, "message": "MCP connect initiated"}
