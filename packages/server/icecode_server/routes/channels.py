"""
ICECODE Channels API
Manage messaging platform channels — Telegram, Discord, Slack, etc.
"""
from __future__ import annotations

import uuid
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/channels", tags=["channels"])

SUPPORTED_PLATFORMS = [
    "telegram", "discord", "whatsapp", "signal", "matrix", "mattermost",
    "slack", "email", "sms", "dingtalk", "wecom", "feishu", "qqbot",
    "yuanbao", "bluebubbles", "google_chat", "irc", "line", "teams",
    "homeassistant", "webhook", "api_server",
]


class ChannelCreate(BaseModel):
    platform: str
    name: str
    config: Dict[str, Any] = {}


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


def _load_channels():
    import json
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    f = cfg.home_dir / "data" / "channels.json"
    if f.exists():
        return json.loads(f.read_text())
    return []


def _save_channels(channels):
    import json
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    f = cfg.home_dir / "data" / "channels.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(channels, indent=2))


@router.get("/")
async def list_channels():
    return _load_channels()


@router.get("/platforms")
async def list_platforms():
    return {"platforms": SUPPORTED_PLATFORMS}


@router.post("/")
async def create_channel(req: ChannelCreate):
    if req.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(400, f"Unsupported platform. Supported: {SUPPORTED_PLATFORMS}")
    channels = _load_channels()
    channel = {
        "id": f"ch_{uuid.uuid4().hex[:8]}",
        "platform": req.platform,
        "name": req.name,
        "config": req.config,
        "enabled": True,
        "status": "disconnected",
    }
    channels.append(channel)
    _save_channels(channels)
    return channel


@router.put("/{channel_id}")
async def update_channel(channel_id: str, req: ChannelUpdate):
    channels = _load_channels()
    for ch in channels:
        if ch["id"] == channel_id:
            if req.name is not None:
                ch["name"] = req.name
            if req.config is not None:
                ch["config"].update(req.config)
            if req.enabled is not None:
                ch["enabled"] = req.enabled
            _save_channels(channels)
            return ch
    raise HTTPException(404, "Channel not found")


@router.delete("/{channel_id}")
async def delete_channel(channel_id: str):
    channels = _load_channels()
    channels = [c for c in channels if c["id"] != channel_id]
    _save_channels(channels)
    return {"ok": True}


@router.post("/{channel_id}/connect")
async def connect_channel(channel_id: str):
    """Attempt to connect a channel via the Gateway."""
    channels = _load_channels()
    for ch in channels:
        if ch["id"] == channel_id:
            ch["status"] = "connecting"
            _save_channels(channels)
            # TODO: trigger gateway platform start
            return {"ok": True, "status": "connecting"}
    raise HTTPException(404, "Channel not found")
