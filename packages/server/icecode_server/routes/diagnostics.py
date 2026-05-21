"""ICECODE Diagnostics API"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("/")
async def diagnostics():
    return {
        "version": "1.0.0",
        "python": sys.version,
        "platform": platform.system(),
        "arch": platform.machine(),
        "packages": {
            "core": _check_import("icecode"),
            "fastapi": _check_import("fastapi"),
            "anthropic": _check_import("anthropic"),
            "openai": _check_import("openai"),
            "sqlalchemy": _check_import("sqlalchemy"),
            "loguru": _check_import("loguru"),
        }
    }


@router.get("/health")
async def health():
    return {"status": "ok"}


def _check_import(name: str) -> str:
    try:
        mod = __import__(name)
        return getattr(mod, "__version__", "installed")
    except ImportError:
        return "not installed"
