"""Curator state — persistent scheduler state stored in .curator_state."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from icecode.icecode_constants import get_hermes_home

logger = logging.getLogger(__name__)


def _state_file() -> Path:
    return get_hermes_home() / "skills" / ".curator_state"


def _default_state() -> Dict[str, Any]:
    return {
        "last_run_at": None,
        "last_run_duration_seconds": None,
        "last_run_summary": None,
        "last_run_summary_shown_at": None,
        "last_report_path": None,
        "paused": False,
        "run_count": 0,
    }


def load_state() -> Dict[str, Any]:
    path = _state_file()
    if not path.exists():
        return _default_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            base = _default_state()
            base.update({k: v for k, v in data.items() if k in base or k.startswith("_")})
            return base
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("Failed to read curator state: %s", e)
    return _default_state()


def save_state(data: Dict[str, Any]) -> None:
    path = _state_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".curator_state_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.debug("Failed to save curator state: %s", e, exc_info=True)


def set_paused(paused: bool) -> None:
    state = load_state()
    state["paused"] = bool(paused)
    save_state(state)


def is_paused() -> bool:
    return bool(load_state().get("paused"))
