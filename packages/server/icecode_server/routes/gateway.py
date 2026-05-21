"""ICECODE Gateway API — start/stop/status gateway process"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from loguru import logger

router = APIRouter(prefix="/api/gateway", tags=["gateway"])

_gateway_process: subprocess.Popen = None


@router.get("/status")
async def gateway_status():
    global _gateway_process
    if _gateway_process and _gateway_process.poll() is None:
        return {"state": "running", "pid": _gateway_process.pid}
    return {"state": "stopped"}


@router.post("/start")
async def start_gateway():
    global _gateway_process
    if _gateway_process and _gateway_process.poll() is None:
        return {"ok": True, "state": "already_running", "pid": _gateway_process.pid}

    hermes_root = Path(__file__).parents[5] / "icecode-agent-main"
    gateway_run = hermes_root / "gateway" / "run.py"

    if not gateway_run.exists():
        return {"ok": False, "error": "Gateway not found"}

    try:
        _gateway_process = subprocess.Popen(
            [sys.executable, str(gateway_run)],
            cwd=str(hermes_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        await asyncio.sleep(1)
        if _gateway_process.poll() is None:
            return {"ok": True, "state": "running", "pid": _gateway_process.pid}
        return {"ok": False, "error": "Process exited immediately"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/stop")
async def stop_gateway():
    global _gateway_process
    if _gateway_process and _gateway_process.poll() is None:
        _gateway_process.terminate()
        try:
            _gateway_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _gateway_process.kill()
        _gateway_process = None
        return {"ok": True, "state": "stopped"}
    return {"ok": True, "state": "already_stopped"}


@router.post("/restart")
async def restart_gateway():
    await stop_gateway()
    await asyncio.sleep(1)
    return await start_gateway()
