"""ICECODE Usage API — token usage and cost tracking across all sessions."""
from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/usage", tags=["usage"])

_USAGE_FILE = Path.home() / ".icecode" / "data" / "usage.json"

# Cost per 1M tokens (input/output) in USD — approximate 2025 prices
_COST_TABLE = {
    "gpt-4o":                    (2.50, 10.00),
    "gpt-4o-mini":               (0.15,  0.60),
    "gpt-4-turbo":               (10.0, 30.00),
    "gpt-3.5-turbo":             (0.50,  1.50),
    "claude-opus-4":             (15.0, 75.00),
    "claude-sonnet-4":           (3.00, 15.00),
    "claude-haiku-4":            (0.80,  4.00),
    "claude-3-5-sonnet":         (3.00, 15.00),
    "claude-3-5-haiku":          (0.80,  4.00),
    "claude-3-opus":             (15.0, 75.00),
    "deepseek-chat":             (0.07,  0.28),
    "deepseek-reasoner":         (0.55,  2.19),
    "gemini-2.5-pro":            (1.25,  5.00),
    "gemini-2.0-flash":          (0.075, 0.30),
    "gemini-1.5-pro":            (1.25,  5.00),
    "ollama":                    (0.0,   0.0),   # free — local
}


def _cost_for_model(model: str, prompt_t: int, completion_t: int) -> float:
    """Estimate USD cost for a given model + token counts."""
    model_lower = (model or "").lower()
    for key, (in_rate, out_rate) in _COST_TABLE.items():
        if key in model_lower:
            return (prompt_t / 1_000_000) * in_rate + (completion_t / 1_000_000) * out_rate
    return 0.0  # local/unknown model = free


def _load() -> dict:
    if _USAGE_FILE.exists():
        try:
            return json.loads(_USAGE_FILE.read_text())
        except Exception:
            pass
    return {
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "total_sessions": 0,
        "total_tool_calls": 0,
        "by_model": {},
        "by_day": {},
        "sessions": [],
    }


def _save(data: dict):
    _USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USAGE_FILE.write_text(json.dumps(data, indent=2))


class UsageRecord(BaseModel):
    session_id: str
    model: str = ""
    provider: str = "ollama"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_calls: int = 0
    iterations: int = 0
    elapsed_seconds: float = 0.0


@router.post("/record")
async def record_usage(rec: UsageRecord):
    """Called after each chat session to persist token usage."""
    data = _load()
    total = rec.prompt_tokens + rec.completion_tokens
    cost = _cost_for_model(rec.model, rec.prompt_tokens, rec.completion_tokens)
    today = date.today().isoformat()

    # Totals
    data["total_prompt_tokens"]     += rec.prompt_tokens
    data["total_completion_tokens"] += rec.completion_tokens
    data["total_tokens"]            += total
    data["total_cost_usd"]          = round(data["total_cost_usd"] + cost, 6)
    data["total_sessions"]          += 1
    data["total_tool_calls"]        += rec.tool_calls

    # Per-model
    bm = data.setdefault("by_model", {})
    bm.setdefault(rec.model, {"prompt": 0, "completion": 0, "total": 0, "cost": 0.0, "sessions": 0})
    bm[rec.model]["prompt"]     += rec.prompt_tokens
    bm[rec.model]["completion"] += rec.completion_tokens
    bm[rec.model]["total"]      += total
    bm[rec.model]["cost"]        = round(bm[rec.model]["cost"] + cost, 6)
    bm[rec.model]["sessions"]   += 1

    # Per-day
    bd = data.setdefault("by_day", {})
    bd.setdefault(today, {"tokens": 0, "cost": 0.0, "sessions": 0})
    bd[today]["tokens"]   += total
    bd[today]["cost"]      = round(bd[today]["cost"] + cost, 6)
    bd[today]["sessions"] += 1

    # Session log (keep last 200)
    sessions = data.setdefault("sessions", [])
    sessions.append({
        "session_id":  rec.session_id,
        "model":       rec.model,
        "provider":    rec.provider,
        "prompt_t":    rec.prompt_tokens,
        "completion_t": rec.completion_tokens,
        "total_t":     total,
        "tool_calls":  rec.tool_calls,
        "iterations":  rec.iterations,
        "cost_usd":    round(cost, 6),
        "elapsed_s":   rec.elapsed_seconds,
        "at":          datetime.now().isoformat(),
    })
    data["sessions"] = sessions[-200:]

    _save(data)
    return {"ok": True, "tokens": total, "cost_usd": cost}


@router.get("/")
async def get_usage():
    """Full usage stats."""
    data = _load()
    return {
        "total_tokens":      data["total_tokens"],
        "total_prompt":      data["total_prompt_tokens"],
        "total_completion":  data["total_completion_tokens"],
        "total_cost_usd":    round(data["total_cost_usd"], 4),
        "total_sessions":    data["total_sessions"],
        "total_tool_calls":  data.get("total_tool_calls", 0),
        "by_model":          data.get("by_model", {}),
        "today":             data.get("by_day", {}).get(date.today().isoformat(), {}),
        "last_7_days":       _last_n_days(data.get("by_day", {}), 7),
    }


@router.get("/sessions")
async def get_session_usage(limit: int = 50):
    """Recent session usage records."""
    data = _load()
    sessions = data.get("sessions", [])
    return {"sessions": list(reversed(sessions))[:limit]}


@router.delete("/")
async def reset_usage():
    """Reset all usage stats."""
    _save({
        "total_prompt_tokens": 0, "total_completion_tokens": 0,
        "total_tokens": 0, "total_cost_usd": 0.0,
        "total_sessions": 0, "total_tool_calls": 0,
        "by_model": {}, "by_day": {}, "sessions": [],
    })
    return {"ok": True}


def _last_n_days(by_day: dict, n: int) -> list:
    from datetime import timedelta
    result = []
    today = date.today()
    for i in range(n - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        result.append({"date": d, **by_day.get(d, {"tokens": 0, "cost": 0.0, "sessions": 0})})
    return result
