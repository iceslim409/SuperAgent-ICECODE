"""Curator — background skill maintenance orchestrator.

The curator is an auxiliary-model task that periodically reviews agent-created
skills and maintains the collection. It runs inactivity-triggered (no cron
daemon): when the agent is idle and the last curator run was longer than
``interval_hours`` ago, ``maybe_run_curator()`` spawns a forked AIAgent to do
the review.

Responsibilities:
  - Auto-transition lifecycle states based on derived skill activity timestamps
  - Spawn a background review agent that can pin / archive / consolidate /
    patch agent-created skills via skill_manage
  - Persist curator state (last_run_at, paused, etc.) in .curator_state

Strict invariants:
  - Only touches agent-created skills (see tools/skill_usage.is_agent_created)
  - Never auto-deletes — only archives. Archive is recoverable.
  - Pinned skills bypass all auto-transitions
  - Uses the auxiliary client; never touches the main session's prompt cache

Implementation is split across sub-modules:
  curator_state.py       — persistent state (.curator_state)
  curator_config.py      — config access + defaults
  curator_scheduler.py   — idle/interval check + auto transitions
  curator_prompt.py      — LLM review prompt strings
  curator_reports.py     — per-run JSON + Markdown reports
  curator_orchestrator.py — LLM review fork + run_curator_review
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

# Re-export everything for backward compatibility — callers do
# `from agent import curator` and then `curator.load_state()` etc.
from .curator_state import (
    load_state,
    save_state,
    set_paused,
    is_paused,
)
from .curator_config import (
    DEFAULT_INTERVAL_HOURS,
    DEFAULT_MIN_IDLE_HOURS,
    DEFAULT_STALE_AFTER_DAYS,
    DEFAULT_ARCHIVE_AFTER_DAYS,
    is_enabled,
    get_interval_hours,
    get_min_idle_hours,
    get_stale_after_days,
    get_archive_after_days,
)
from .curator_scheduler import (
    should_run_now,
    apply_automatic_transitions,
)
from .curator_prompt import (
    CURATOR_DRY_RUN_BANNER,
    CURATOR_REVIEW_PROMPT,
)
from .curator_orchestrator import (
    run_curator_review,
    _ReviewRuntimeBinding,
    _strip_aux_credential,
)

import logging
logger = logging.getLogger(__name__)


def maybe_run_curator(
    *,
    idle_for_seconds: Optional[float] = None,
    on_summary: Optional[Callable[[str], None]] = None,
) -> Optional[Dict[str, Any]]:
    """Best-effort: run a curator pass if all gates pass. Returns the result
    dict if a pass was started, else None. Never raises."""
    try:
        if not should_run_now():
            return None
        # Idle gating: only enforce when the caller provided a measurement.
        if idle_for_seconds is not None:
            min_idle_s = get_min_idle_hours() * 3600.0
            if idle_for_seconds < min_idle_s:
                return None
        return run_curator_review(on_summary=on_summary)
    except Exception as e:
        logger.debug("maybe_run_curator failed: %s", e, exc_info=True)
        return None
