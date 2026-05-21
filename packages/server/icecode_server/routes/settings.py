"""ICECODE Settings API"""
from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    data: Dict[str, Any]


def _load():
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    f = cfg.home_dir / "settings.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _save(data):
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    f = cfg.home_dir / "settings.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2))


@router.get("/")
async def get_settings():
    return _load()


@router.patch("/")
async def update_settings(req: SettingsUpdate):
    current = _load()
    current.update(req.data)
    _save(current)
    return current
