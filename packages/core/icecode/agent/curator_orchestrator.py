"""Curator orchestrator — spawns a forked AIAgent for the LLM review pass."""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, NamedTuple, Optional

from .curator_state import load_state, save_state
from .curator_config import get_min_idle_hours
from .curator_scheduler import apply_automatic_transitions
from .curator_prompt import CURATOR_DRY_RUN_BANNER, CURATOR_REVIEW_PROMPT
from .curator_reports import _write_run_report, _build_rename_summary

logger = logging.getLogger(__name__)


def _strip_aux_credential(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class _ReviewRuntimeBinding(NamedTuple):
    """Provider/model for the curator review fork plus optional per-slot overrides."""

    provider: str
    model: str
    explicit_api_key: Optional[str]
    explicit_base_url: Optional[str]


def _render_candidate_list() -> str:
    """Human/agent-readable list of agent-created skills with usage stats."""
    from icecode_tools import skill_usage
    rows = skill_usage.agent_created_report()
    if not rows:
        return "No agent-created skills to review."
    lines = [f"Agent-created skills ({len(rows)}):\n"]
    for r in rows:
        lines.append(
            f"- {r['name']}  "
            f"state={r['state']}  "
            f"pinned={'yes' if r.get('pinned') else 'no'}  "
            f"activity={r.get('activity_count', 0)}  "
            f"use={r.get('use_count', 0)}  "
            f"view={r.get('view_count', 0)}  "
            f"patches={r.get('patch_count', 0)}  "
            f"last_activity={r.get('last_activity_at') or 'never'}"
        )
    return "\n".join(lines)


def _resolve_review_runtime(cfg: Dict[str, Any]) -> _ReviewRuntimeBinding:
    """Resolve provider/model and per-slot credentials for the curator review fork.

    Same precedence as `_resolve_review_model()`. Non-empty ``api_key`` /
    ``base_url`` from the active slot are returned as explicit overrides so
    ``resolve_runtime_provider`` does not silently reuse the main chat
    credential chain for a routed auxiliary model.
    """
    _main = cfg.get("model", {}) if isinstance(cfg.get("model"), dict) else {}
    _main_provider = _main.get("provider") or "auto"
    _main_model = _main.get("default") or _main.get("model") or ""

    _aux = cfg.get("auxiliary", {}) if isinstance(cfg.get("auxiliary"), dict) else {}
    _cur_task = _aux.get("curator", {}) if isinstance(_aux.get("curator"), dict) else {}
    _task_provider = (_cur_task.get("provider") or "").strip() or None
    _task_model = (_cur_task.get("model") or "").strip() or None
    if _task_provider and _task_provider != "auto" and _task_model:
        return _ReviewRuntimeBinding(
            _task_provider,
            _task_model,
            _strip_aux_credential(_cur_task.get("api_key")),
            _strip_aux_credential(_cur_task.get("base_url")),
        )

    _cur = cfg.get("curator", {}) if isinstance(cfg.get("curator"), dict) else {}
    _legacy = _cur.get("auxiliary", {}) if isinstance(_cur.get("auxiliary"), dict) else {}
    _legacy_provider = _legacy.get("provider") or None
    _legacy_model = _legacy.get("model") or None
    if _legacy_provider and _legacy_model:
        logger.info(
            "curator: using deprecated curator.auxiliary.{provider,model} "
            "config — please migrate to auxiliary.curator.{provider,model}"
        )
        return _ReviewRuntimeBinding(
            str(_legacy_provider),
            str(_legacy_model),
            _strip_aux_credential(_legacy.get("api_key")),
            _strip_aux_credential(_legacy.get("base_url")),
        )

    return _ReviewRuntimeBinding(_main_provider, _main_model, None, None)


def _resolve_review_model(cfg: Dict[str, Any]) -> tuple[str, str]:
    """Pick (provider, model) for the curator review fork.

    Curator is a regular auxiliary task slot — ``auxiliary.curator.{provider,model}``
    — so it participates in the canonical aux-model plumbing (``hermes model`` →
    auxiliary picker, the dashboard Models tab, ``auxiliary.curator.{timeout,
    base_url,api_key,extra_body}``). ``provider: "auto"`` with an empty model
    means "use the main chat model" — same default as every other aux task.

    Legacy fallback: users who configured ``curator.auxiliary.{provider,model}``
    under the previous one-off schema still work. Precedence:
      1. ``auxiliary.curator.{provider,model}`` when both are set non-auto
      2. Legacy ``curator.auxiliary.{provider,model}`` when both are set
      3. Main ``model.{provider,default/model}`` pair
    """
    b = _resolve_review_runtime(cfg)
    return b.provider, b.model


def _run_llm_review(prompt: str) -> Dict[str, Any]:
    """Spawn an AIAgent fork to run the curator review prompt.

    Returns a dict with:
      - final: full (untruncated) final response from the reviewer
      - summary: short summary suitable for state file (240-char cap)
      - model, provider: what the fork actually ran on
      - tool_calls: list of {name, arguments} for every tool call made during
        the pass (arguments may be truncated for readability)
      - error: set if the pass failed mid-run; final/summary may still be empty

    Never raises; callers get a structured failure instead.
    """
    import contextlib
    result_meta: Dict[str, Any] = {
        "final": "",
        "summary": "",
        "model": "",
        "provider": "",
        "tool_calls": [],
        "error": None,
    }
    try:
        from run_agent import AIAgent
    except Exception as e:
        result_meta["error"] = f"AIAgent import failed: {e}"
        result_meta["summary"] = result_meta["error"]
        return result_meta

    _api_key = None
    _base_url = None
    _api_mode = None
    _resolved_provider = None
    _model_name = ""
    try:
        from icecode_cli.hermes_cli.config import load_config
        from icecode_cli.hermes_cli.runtime_provider import resolve_runtime_provider
        _cfg = load_config()
        _binding = _resolve_review_runtime(_cfg)
        _provider, _model_name = _binding.provider, _binding.model
        _rp = resolve_runtime_provider(
            requested=_provider,
            target_model=_model_name,
            explicit_api_key=_binding.explicit_api_key,
            explicit_base_url=_binding.explicit_base_url,
        )
        _api_key = _rp.get("api_key")
        _base_url = _rp.get("base_url")
        _api_mode = _rp.get("api_mode")
        _resolved_provider = _rp.get("provider") or _provider
    except Exception as e:
        logger.debug("Curator provider resolution failed: %s", e, exc_info=True)

    result_meta["model"] = _model_name
    result_meta["provider"] = _resolved_provider or ""

    review_agent = None
    try:
        review_agent = AIAgent(
            model=_model_name,
            provider=_resolved_provider,
            api_key=_api_key,
            base_url=_base_url,
            api_mode=_api_mode,
            max_iterations=9999,
            quiet_mode=True,
            platform="curator",
            skip_context_files=True,
            skip_memory=True,
        )
        review_agent._memory_nudge_interval = 0
        review_agent._skill_nudge_interval = 0

        with open(os.devnull, "w", encoding="utf-8") as _devnull, \
             contextlib.redirect_stdout(_devnull), \
             contextlib.redirect_stderr(_devnull):
            conv_result = review_agent.run_conversation(user_message=prompt)

        final = ""
        if isinstance(conv_result, dict):
            final = str(conv_result.get("final_response") or "").strip()
        result_meta["final"] = final
        result_meta["summary"] = (final[:240] + "…") if len(final) > 240 else (final or "no change")

        _calls: List[Dict[str, Any]] = []
        for msg in getattr(review_agent, "_session_messages", []) or []:
            if not isinstance(msg, dict):
                continue
            tcs = msg.get("tool_calls") or []
            for tc in tcs:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") or {}
                name = fn.get("name") or ""
                args_raw = fn.get("arguments") or ""
                if isinstance(args_raw, str) and len(args_raw) > 400:
                    args_raw = args_raw[:400] + "…"
                _calls.append({"name": name, "arguments": args_raw})
        result_meta["tool_calls"] = _calls
    except Exception as e:
        result_meta["error"] = f"error: {e}"
        result_meta["summary"] = result_meta["error"]
    finally:
        if review_agent is not None:
            try:
                review_agent.close()
            except Exception:
                pass
    return result_meta


def run_curator_review(
    on_summary: Optional[Callable[[str], None]] = None,
    synchronous: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute a single curator review pass.

    Steps:
      1. Apply automatic state transitions (pure, no LLM).
      2. If there are agent-created skills, spawn a forked AIAgent that runs
         the LLM review prompt against the current candidate list.
      3. Update .curator_state with last_run_at and a one-line summary.
      4. Invoke *on_summary* with a user-visible description.

    If *synchronous* is True, the LLM review runs in the calling thread; the
    default is to spawn a daemon thread so the caller returns immediately.

    If *dry_run* is True, the automatic stale/archive transitions are SKIPPED
    and the LLM review pass is instructed to produce a report only — no
    skill_manage mutations, no terminal archive moves. The REPORT.md still
    gets written and ``state.last_report_path`` still records it so users
    can read what the curator WOULD have done.
    """
    from icecode_tools import skill_usage
    start = datetime.now(timezone.utc)
    if dry_run:
        try:
            report = skill_usage.agent_created_report()
            counts = {
                "checked": len(report),
                "marked_stale": 0,
                "archived": 0,
                "reactivated": 0,
            }
        except Exception:
            counts = {"checked": 0, "marked_stale": 0, "archived": 0, "reactivated": 0}
    else:
        try:
            from agent import curator_backup
            snap = curator_backup.snapshot_skills(reason="pre-curator-run")
            if snap is not None and on_summary:
                try:
                    on_summary(f"curator: snapshot created ({snap.name})")
                except Exception:
                    pass
        except Exception as e:
            logger.debug("Curator pre-run snapshot failed: %s", e, exc_info=True)
        counts = apply_automatic_transitions(now=start)

    auto_summary_parts = []
    if counts["marked_stale"]:
        auto_summary_parts.append(f"{counts['marked_stale']} marked stale")
    if counts["archived"]:
        auto_summary_parts.append(f"{counts['archived']} archived")
    if counts["reactivated"]:
        auto_summary_parts.append(f"{counts['reactivated']} reactivated")
    auto_summary = ", ".join(auto_summary_parts) if auto_summary_parts else "no changes"

    state = load_state()
    if not dry_run:
        state["last_run_at"] = start.isoformat()
        state["run_count"] = int(state.get("run_count", 0)) + 1
    prefix = "dry-run auto: " if dry_run else "auto: "
    state["last_run_summary"] = f"{prefix}{auto_summary}"
    save_state(state)

    def _llm_pass():
        nonlocal auto_summary
        try:
            before_report = skill_usage.agent_created_report()
        except Exception:
            before_report = []
        before_names = {r.get("name") for r in before_report if isinstance(r, dict)}

        llm_meta: Dict[str, Any] = {}
        try:
            candidate_list = _render_candidate_list()
            if "No agent-created skills" in candidate_list:
                final_summary = f"{prefix}{auto_summary}; llm: skipped (no candidates)"
                llm_meta = {
                    "final": "",
                    "summary": "skipped (no candidates)",
                    "model": "",
                    "provider": "",
                    "tool_calls": [],
                    "error": None,
                }
            else:
                if dry_run:
                    prompt = (
                        f"{CURATOR_DRY_RUN_BANNER}\n\n"
                        f"{CURATOR_REVIEW_PROMPT}\n\n"
                        f"{candidate_list}"
                    )
                else:
                    prompt = f"{CURATOR_REVIEW_PROMPT}\n\n{candidate_list}"
                llm_meta = _run_llm_review(prompt)
                final_summary = (
                    f"{prefix}{auto_summary}; llm: {llm_meta.get('summary', 'no change')}"
                )
        except Exception as e:
            logger.debug("Curator LLM pass failed: %s", e, exc_info=True)
            final_summary = f"{prefix}{auto_summary}; llm: error ({e})"
            llm_meta = {
                "final": "",
                "summary": f"error ({e})",
                "model": "",
                "provider": "",
                "tool_calls": [],
                "error": str(e),
            }

        try:
            rename_lines = _build_rename_summary(
                before_names=before_names,
                after_report=skill_usage.agent_created_report(),
                tool_calls=llm_meta.get("tool_calls", []) or [],
                model_final=llm_meta.get("final", "") or "",
            )
            if rename_lines:
                final_summary = f"{final_summary}\n{rename_lines}"
        except Exception as e:
            logger.debug("Curator rename summary build failed: %s", e, exc_info=True)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        state2 = load_state()
        state2["last_run_duration_seconds"] = elapsed
        state2["last_run_summary"] = final_summary

        try:
            after_report = skill_usage.agent_created_report()
        except Exception:
            after_report = []
        try:
            report_path = _write_run_report(
                started_at=start,
                elapsed_seconds=elapsed,
                auto_counts=counts,
                auto_summary=auto_summary,
                before_report=before_report,
                before_names=before_names,
                after_report=after_report,
                llm_meta=llm_meta,
            )
            if report_path is not None:
                state2["last_report_path"] = str(report_path)
        except Exception as e:
            logger.debug("Curator report write failed: %s", e, exc_info=True)

        save_state(state2)

        if on_summary:
            try:
                on_summary(f"curator: {final_summary}")
            except Exception:
                pass

    if synchronous:
        _llm_pass()
    else:
        t = threading.Thread(target=_llm_pass, daemon=True, name="curator-review")
        t.start()

    return {
        "started_at": start.isoformat(),
        "auto_transitions": counts,
        "summary_so_far": auto_summary,
    }
