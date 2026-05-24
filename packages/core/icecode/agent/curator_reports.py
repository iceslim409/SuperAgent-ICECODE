"""Curator reports — per-run JSON + Markdown report generation."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from icecode.icecode_constants import get_hermes_home

logger = logging.getLogger(__name__)


def _reports_root() -> Path:
    """Directory where curator run reports are written.

    Lives under the profile-aware logs dir (``~/.icecode/logs/curator/``)
    alongside ``agent.log`` and ``gateway.log`` so it's found by anyone
    looking for operational telemetry, not mixed in with the user's
    authored skill data in ``~/.icecode/skills/``.

    ``ensure_hermes_home()`` pre-creates this dir on every CLI launch and
    the v22→v23 migration backfills it for existing profiles, but we
    still mkdir here as a belt-and-suspenders so the curator works even
    from an odd entry path (e.g. gateway-only install, bare library use)
    that bypasses both.
    """
    root = get_hermes_home() / "logs" / "curator"
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.debug("Curator reports dir create failed: %s", e)
    return root


def _needle_in_path_component(needle: str, path: str) -> bool:
    """Check if *needle* is a complete filename stem or directory name in *path*.

    Unlike simple substring matching, this avoids false positives where short
    skill names are embedded in longer filenames (e.g. "api" matching
    "references/api-design.md").  Hyphens and underscores are normalised so
    "open-webui-setup" matches "open_webui_setup.md".
    """
    norm_needle = needle.replace("-", "_")
    for part in path.replace("\\", "/").split("/"):
        if not part:
            continue
        stem = part.rsplit(".", 1)[0] if "." in part else part
        if stem.replace("-", "_") == norm_needle:
            return True
    return False


def _classify_removed_skills(
    removed: List[str],
    added: List[str],
    after_names: Set[str],
    tool_calls: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Split ``removed`` into consolidated vs pruned.

    A removed skill is "consolidated" when the curator absorbed its content
    into another skill (an umbrella) during this run — the content still
    lives, just under a different name. A removed skill is "pruned" when the
    curator archived it for staleness/irrelevance without preserving its
    content elsewhere.

    Heuristic: scan this run's ``skill_manage`` tool calls and look for
    ``write_file``/``patch``/``create``/``edit`` actions whose target skill
    (the ``name`` argument) is NOT the removed skill and whose
    ``file_path`` / ``file_content`` / ``content`` arguments reference the
    removed skill's name. That's the textbook "absorbed into umbrella"
    signal. Ties are broken by first-match (earliest tool call wins).

    Returns ``{"consolidated": [{"name", "into", "evidence"}, ...],
               "pruned":       [{"name"}, ...]}``.
    """
    consolidated: List[Dict[str, Any]] = []
    pruned: List[Dict[str, Any]] = []

    parsed_calls: List[Dict[str, Any]] = []
    for tc in tool_calls or []:
        if not isinstance(tc, dict):
            continue
        if tc.get("name") != "skill_manage":
            continue
        raw = tc.get("arguments") or ""
        args: Dict[str, Any] = {}
        if isinstance(raw, dict):
            args = raw
        elif isinstance(raw, str):
            try:
                args = json.loads(raw)
            except Exception:
                args = {"_raw": raw}
        if not isinstance(args, dict):
            continue
        parsed_calls.append(args)

    destinations = set(after_names) | set(added or [])

    for name in removed:
        if not name:
            continue
        into: Optional[str] = None
        evidence: Optional[str] = None

        needles = {name, name.replace("-", "_"), name.replace("_", "-")}

        for args in parsed_calls:
            target = args.get("name")
            if not isinstance(target, str) or not target:
                continue
            if target == name:
                continue
            if target not in destinations:
                continue

            haystacks: List[tuple[str, str]] = []
            for key in ("file_path", "file_content", "content", "new_string", "_raw"):
                v = args.get(key)
                if isinstance(v, str):
                    haystacks.append((key, v))
            hit = False
            for key, hay in haystacks:
                for needle in needles:
                    if not needle:
                        continue
                    if key == "file_path":
                        matched = _needle_in_path_component(needle, hay)
                    else:
                        matched = bool(
                            re.search(rf'\b{re.escape(needle)}\b', hay)
                        )
                    if matched:
                        hit = True
                        evidence = (
                            f"skill_manage action={args.get('action', '?')} "
                            f"on '{target}' referenced '{name}' "
                            f"in {hay[:80]}"
                        )
                        break
                if hit:
                    break
            if hit:
                into = target
                break

        if into:
            consolidated.append({"name": name, "into": into, "evidence": evidence})
        else:
            pruned.append({"name": name})

    return {"consolidated": consolidated, "pruned": pruned}


def _parse_structured_summary(
    llm_final: str,
) -> Dict[str, List[Dict[str, str]]]:
    """Extract the structured YAML block from the curator's final response.

    The curator prompt requires a fenced ```yaml block under
    ``## Structured summary (required)`` with ``consolidations:`` and
    ``prunings:`` lists. This parses it tolerantly:

    - Missing block → returns empty lists (we'll fall back to heuristic).
    - Malformed YAML → returns empty lists and we rely on heuristic.
    - Partial block (e.g. only consolidations) → returns what we could parse.

    Returns ``{"consolidations": [{"from", "into", "reason"}, ...],
               "prunings":       [{"name", "reason"}, ...]}``.
    """
    empty = {"consolidations": [], "prunings": []}
    if not llm_final or not isinstance(llm_final, str):
        return empty

    match = re.search(
        r"```ya?ml\s*\n(.*?)\n```",
        llm_final,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return empty

    body = match.group(1)

    try:
        import yaml  # type: ignore
        data = yaml.safe_load(body)
    except Exception:
        return empty

    if not isinstance(data, dict):
        return empty

    out: Dict[str, List[Dict[str, str]]] = {"consolidations": [], "prunings": []}
    cons_raw = data.get("consolidations") or []
    prun_raw = data.get("prunings") or []

    if isinstance(cons_raw, list):
        for entry in cons_raw:
            if not isinstance(entry, dict):
                continue
            frm = entry.get("from")
            into = entry.get("into")
            if not (isinstance(frm, str) and frm.strip()
                    and isinstance(into, str) and into.strip()):
                continue
            reason = entry.get("reason")
            out["consolidations"].append({
                "from": frm.strip(),
                "into": into.strip(),
                "reason": (reason or "").strip() if isinstance(reason, str) else "",
            })

    if isinstance(prun_raw, list):
        for entry in prun_raw:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not (isinstance(name, str) and name.strip()):
                continue
            reason = entry.get("reason")
            out["prunings"].append({
                "name": name.strip(),
                "reason": (reason or "").strip() if isinstance(reason, str) else "",
            })

    return out


def _extract_absorbed_into_declarations(
    tool_calls: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Walk this run's tool calls and extract model-declared absorption targets.

    The curator prompt requires every ``skill_manage(action='delete')`` call
    to pass ``absorbed_into=<umbrella>`` when consolidating, or
    ``absorbed_into=""`` when truly pruning. This is the single authoritative
    signal for classification — the model's own declaration at the moment of
    deletion, which beats both post-hoc YAML summary parsing and substring
    heuristics on other tool calls.

    Returns ``{skill_name: {"into": "<umbrella>" | "", "declared": True}}``.
    Entries with ``into == ""`` are explicit prunings.
    Skills without a ``skill_manage(delete)`` call, or with one that omitted
    ``absorbed_into``, are not in the returned dict — caller falls back to
    the existing heuristic/YAML logic for those (backward compat with older
    curator runs and any callers that don't populate the arg).
    """
    out: Dict[str, Dict[str, Any]] = {}
    for tc in tool_calls or []:
        if not isinstance(tc, dict):
            continue
        if tc.get("name") != "skill_manage":
            continue
        raw = tc.get("arguments") or ""
        args: Dict[str, Any] = {}
        if isinstance(raw, dict):
            args = raw
        elif isinstance(raw, str):
            try:
                args = json.loads(raw)
            except Exception:
                continue
        if not isinstance(args, dict):
            continue
        if args.get("action") != "delete":
            continue
        name = args.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        if "absorbed_into" not in args:
            continue
        target = args.get("absorbed_into")
        if target is None:
            continue
        if not isinstance(target, str):
            continue
        out[name.strip()] = {"into": target.strip(), "declared": True}
    return out


def _reconcile_classification(
    removed: List[str],
    heuristic: Dict[str, List[Dict[str, Any]]],
    model_block: Dict[str, List[Dict[str, str]]],
    destinations: Set[str],
    absorbed_declarations: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Merge heuristic (tool-call evidence) with the model's structured block.

    Rules (evaluated in order; first match wins):
    - **Model-declared `absorbed_into` at delete time is authoritative.** Any
      entry in ``absorbed_declarations`` beats every other signal. This is
      the model telling us directly, at the moment of deletion, what it did.
      ``into != ""`` and target exists → consolidated. ``into == ""`` →
      pruned. ``into != ""`` but target doesn't exist → hallucination; fall
      through to the usual signals.
    - Model-declared consolidation wins when its ``into`` target exists
      in ``destinations`` (survived or newly-created). This gives the
      model authority over intent + rationale.
    - Model-declared consolidation whose ``into`` target does NOT exist is
      downgraded: the model hallucinated an umbrella. We prefer the
      heuristic's finding for that skill, or fall back to pruned.
    - Heuristic-only finding (model didn't mention it, tool calls confirm)
      is preserved as a consolidation, marked ``source="tool-call audit"``.
    - Model-declared pruning is accepted unless the heuristic has
      tool-call evidence that contradicts it (rare — the heuristic would
      have flagged consolidation). In that case we log both.

    Every removed skill is placed in exactly one bucket.
    """
    heur_cons = {e["name"]: e for e in heuristic.get("consolidated", [])}
    heur_pruned = {e["name"] for e in heuristic.get("pruned", [])}

    model_cons = {e["from"]: e for e in model_block.get("consolidations", [])}
    model_pruned = {e["name"]: e for e in model_block.get("prunings", [])}

    declared = absorbed_declarations or {}

    consolidated: List[Dict[str, Any]] = []
    pruned: List[Dict[str, Any]] = []

    for name in removed:
        mc = model_cons.get(name)
        mp = model_pruned.get(name)
        hc = heur_cons.get(name)
        dec = declared.get(name)

        if dec is not None:
            into_claim = dec.get("into", "")
            if into_claim and into_claim in destinations:
                entry: Dict[str, Any] = {
                    "name": name,
                    "into": into_claim,
                    "source": "absorbed_into (model-declared at delete)",
                    "reason": (mc.get("reason") or "") if mc else "",
                }
                if hc and hc.get("evidence"):
                    entry["evidence"] = hc["evidence"]
                consolidated.append(entry)
                continue
            if into_claim == "":
                pruned.append({
                    "name": name,
                    "source": "absorbed_into=\"\" (model-declared prune)",
                    "reason": (mp.get("reason") or "") if mp else "",
                })
                continue

        if mc and mc.get("into") in destinations:
            entry: Dict[str, Any] = {
                "name": name,
                "into": mc["into"],
                "source": "model" + ("+audit" if hc else ""),
                "reason": mc.get("reason") or "",
            }
            if hc and hc.get("evidence"):
                entry["evidence"] = hc["evidence"]
            consolidated.append(entry)
            continue

        if mc and mc.get("into") not in destinations:
            if hc:
                consolidated.append({
                    "name": name,
                    "into": hc["into"],
                    "source": "tool-call audit (model named missing umbrella)",
                    "reason": "",
                    "evidence": hc.get("evidence", ""),
                    "model_claimed_into": mc["into"],
                })
            else:
                pruned.append({
                    "name": name,
                    "source": "fallback (model named missing umbrella, no tool-call evidence)",
                    "reason": "",
                })
            continue

        if hc:
            consolidated.append({
                "name": name,
                "into": hc["into"],
                "source": "tool-call audit (model omitted from structured block)",
                "reason": "",
                "evidence": hc.get("evidence", ""),
            })
            continue

        reason = mp.get("reason", "") if mp else ""
        pruned.append({
            "name": name,
            "source": "model" if mp else "no-evidence fallback",
            "reason": reason,
        })

    return {"consolidated": consolidated, "pruned": pruned}


def _build_rename_summary(
    *,
    before_names: Set[str],
    after_report: List[Dict[str, Any]],
    tool_calls: List[Dict[str, Any]],
    model_final: str,
) -> str:
    """Format the user-visible rename map for a curator run.

    Renders the "where did my skills go?" lines that get appended to the
    `final_summary` string fed to gateway/CLI receivers. Empty string when
    nothing was archived this run — most ticks are no-op and shouldn't add
    extra log noise.

    Format::

        archived 4 skill(s):
          • pdf-extraction → document-tools
          • docx-extraction → document-tools
          • flaky-thing — pruned (stale)
          • old-utility → spreadsheet-ops
        full report: hermes curator status
        keep an umbrella stable: hermes curator pin document-tools

    Cap is 10 entries so a 50-skill consolidation doesn't blow up
    agent.log; the full list is always in REPORT.md. The pin hint only
    appears when at least one consolidation produced an umbrella worth
    pinning (pruned-only runs skip it).
    """
    after_by_name = {r.get("name"): r for r in after_report if isinstance(r, dict)}
    after_names = set(after_by_name.keys())
    removed = sorted(before_names - after_names)
    added = sorted(after_names - before_names)
    if not removed:
        return ""

    heuristic = _classify_removed_skills(
        removed=removed,
        added=added,
        after_names=after_names,
        tool_calls=tool_calls,
    )
    model_block = _parse_structured_summary(model_final)
    destinations = set(after_names) | set(added)
    absorbed_declarations = _extract_absorbed_into_declarations(tool_calls)
    classification = _reconcile_classification(
        removed=removed,
        heuristic=heuristic,
        model_block=model_block,
        destinations=destinations,
        absorbed_declarations=absorbed_declarations,
    )
    consolidated = classification["consolidated"]
    pruned = classification["pruned"]

    SHOW = 10
    lines: List[str] = []
    total = len(consolidated) + len(pruned)
    lines.append(f"archived {total} skill(s):")
    shown = 0
    for entry in consolidated:
        if shown >= SHOW:
            break
        name = entry.get("name", "?")
        into = entry.get("into", "?")
        lines.append(f"  • {name} → {into}")
        shown += 1
    for entry in pruned:
        if shown >= SHOW:
            break
        name = entry.get("name", "?") if isinstance(entry, dict) else str(entry)
        lines.append(f"  • {name} — pruned (stale)")
        shown += 1
    if total > SHOW:
        lines.append(f"  … and {total - SHOW} more")
    lines.append("full report: hermes curator status")
    if consolidated:
        umbrellas = sorted({e.get("into") for e in consolidated if e.get("into")})
        if umbrellas:
            example = umbrellas[0]
            lines.append(
                f"keep an umbrella stable: hermes curator pin {example}"
            )
    return "\n".join(lines)


def _write_run_report(
    *,
    started_at: datetime,
    elapsed_seconds: float,
    auto_counts: Dict[str, int],
    auto_summary: str,
    before_report: List[Dict[str, Any]],
    before_names: Set[str],
    after_report: List[Dict[str, Any]],
    llm_meta: Dict[str, Any],
) -> Optional[Path]:
    """Write run.json + REPORT.md under logs/curator/{YYYYMMDD-HHMMSS}/.

    Returns the report directory path on success, None if the write
    couldn't happen (caller logs and continues — reporting is best-effort).
    """
    root = _reports_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.debug("Curator report dir create failed: %s", e)
        return None

    stamp = started_at.strftime("%Y%m%d-%H%M%S")
    run_dir = root / stamp
    suffix = 1
    while run_dir.exists():
        suffix += 1
        run_dir = root / f"{stamp}-{suffix}"
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except Exception as e:
        logger.debug("Curator run dir create failed: %s", e)
        return None

    after_by_name = {r.get("name"): r for r in after_report if isinstance(r, dict)}
    after_names = set(after_by_name.keys())
    removed = sorted(before_names - after_names)
    added = sorted(after_names - before_names)
    before_by_name = {r.get("name"): r for r in before_report if isinstance(r, dict)}

    transitions: List[Dict[str, str]] = []
    for name in sorted(after_names & before_names):
        s_before = (before_by_name.get(name) or {}).get("state")
        s_after = (after_by_name.get(name) or {}).get("state")
        if s_before and s_after and s_before != s_after:
            transitions.append({"name": name, "from": s_before, "to": s_after})

    tc_counts: Dict[str, int] = {}
    for tc in llm_meta.get("tool_calls", []) or []:
        name = tc.get("name", "unknown")
        tc_counts[name] = tc_counts.get(name, 0) + 1

    heuristic = _classify_removed_skills(
        removed=removed,
        added=added,
        after_names=after_names,
        tool_calls=llm_meta.get("tool_calls", []) or [],
    )
    model_block = _parse_structured_summary(llm_meta.get("final", "") or "")
    destinations = set(after_names) | set(added or [])
    absorbed_declarations = _extract_absorbed_into_declarations(
        llm_meta.get("tool_calls", []) or []
    )
    classification = _reconcile_classification(
        removed=removed,
        heuristic=heuristic,
        model_block=model_block,
        destinations=destinations,
        absorbed_declarations=absorbed_declarations,
    )
    consolidated = classification["consolidated"]
    pruned = classification["pruned"]

    cron_rewrites: Dict[str, Any] = {"rewrites": [], "jobs_updated": 0, "jobs_scanned": 0}
    try:
        consolidated_map = {
            e["name"]: e["into"]
            for e in consolidated
            if isinstance(e, dict) and e.get("name") and e.get("into")
        }
        pruned_names = [
            e["name"] for e in pruned
            if isinstance(e, dict) and e.get("name")
        ]
        if consolidated_map or pruned_names:
            from cron.jobs import rewrite_skill_refs as _rewrite_cron_refs
            cron_rewrites = _rewrite_cron_refs(
                consolidated=consolidated_map,
                pruned=pruned_names,
            )
    except Exception as e:
        logger.debug("Curator cron skill rewrite failed: %s", e, exc_info=True)
        cron_rewrites = {
            "rewrites": [],
            "jobs_updated": 0,
            "jobs_scanned": 0,
            "error": str(e),
        }

    payload = {
        "started_at": started_at.isoformat(),
        "duration_seconds": round(elapsed_seconds, 2),
        "model": llm_meta.get("model", ""),
        "provider": llm_meta.get("provider", ""),
        "auto_transitions": auto_counts,
        "counts": {
            "before": len(before_names),
            "after": len(after_names),
            "delta": len(after_names) - len(before_names),
            "archived_this_run": len(removed),
            "added_this_run": len(added),
            "consolidated_this_run": len(consolidated),
            "pruned_this_run": len(pruned),
            "state_transitions": len(transitions),
            "cron_jobs_rewritten": int(cron_rewrites.get("jobs_updated", 0)),
            "tool_calls_total": sum(tc_counts.values()),
        },
        "tool_call_counts": tc_counts,
        "archived": removed,
        "consolidated": consolidated,
        "pruned": pruned,
        "pruned_names": [p["name"] for p in pruned],
        "added": added,
        "state_transitions": transitions,
        "cron_rewrites": cron_rewrites,
        "llm_final": llm_meta.get("final", ""),
        "llm_summary": llm_meta.get("summary", ""),
        "llm_error": llm_meta.get("error"),
        "tool_calls": llm_meta.get("tool_calls", []),
    }

    try:
        (run_dir / "run.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as e:
        logger.debug("Curator run.json write failed: %s", e)

    try:
        md = _render_report_markdown(payload)
        (run_dir / "REPORT.md").write_text(md, encoding="utf-8")
    except Exception as e:
        logger.debug("Curator REPORT.md write failed: %s", e)

    try:
        if int(cron_rewrites.get("jobs_updated", 0)) > 0:
            (run_dir / "cron_rewrites.json").write_text(
                json.dumps(cron_rewrites, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
    except Exception as e:
        logger.debug("Curator cron_rewrites.json write failed: %s", e)

    return run_dir


def _render_report_markdown(p: Dict[str, Any]) -> str:
    """Render the human-readable report."""
    lines: List[str] = []
    started = p.get("started_at", "")
    duration = p.get("duration_seconds", 0) or 0
    mins, secs = divmod(int(duration), 60)
    dur_label = f"{mins}m {secs}s" if mins else f"{secs}s"

    lines.append(f"# Curator run — {started}\n")
    model = p.get("model") or "(not resolved)"
    prov = p.get("provider") or "(not resolved)"
    counts = p.get("counts") or {}
    lines.append(
        f"Model: `{model}` via `{prov}`  ·  Duration: {dur_label}  ·  "
        f"Agent-created skills: {counts.get('before', 0)} → {counts.get('after', 0)} "
        f"({counts.get('delta', 0):+d})\n"
    )

    error = p.get("llm_error")
    if error:
        lines.append(f"> ⚠ LLM pass error: `{error}`\n")

    auto = p.get("auto_transitions") or {}
    lines.append("## Auto-transitions (pure, no LLM)\n")
    lines.append(f"- checked: {auto.get('checked', 0)}")
    lines.append(f"- marked stale: {auto.get('marked_stale', 0)}")
    lines.append(f"- archived (no LLM, pure time-based staleness): {auto.get('archived', 0)}")
    lines.append(f"- reactivated: {auto.get('reactivated', 0)}")
    lines.append("")

    tc_counts = p.get("tool_call_counts") or {}
    lines.append("## LLM consolidation pass\n")
    lines.append(f"- tool calls: **{counts.get('tool_calls_total', 0)}** "
                 f"(by name: {', '.join(f'{k}={v}' for k, v in sorted(tc_counts.items())) or 'none'})")
    lines.append(f"- consolidated into umbrellas: **{counts.get('consolidated_this_run', 0)}**")
    lines.append(f"- pruned (archived for staleness): **{counts.get('pruned_this_run', 0)}**")
    lines.append(f"- new skills this run: **{counts.get('added_this_run', 0)}**")
    lines.append(f"- state transitions (active ↔ stale ↔ archived): "
                 f"**{counts.get('state_transitions', 0)}**")
    lines.append("")

    consolidated = p.get("consolidated") or []
    if consolidated:
        lines.append(f"### Consolidated into umbrella skills ({len(consolidated)})\n")
        lines.append(
            "_These skills were **absorbed into another skill** during this run — "
            "their content still lives, just under a different name. "
            "The original directory was moved to `~/.icecode/skills/.archive/` for "
            "safety and can be restored via `hermes curator restore <name>` if the "
            "consolidation was wrong._\n"
        )
        SHOW = 50
        for entry in consolidated[:SHOW]:
            name = entry.get("name", "?")
            into = entry.get("into", "?")
            reason = (entry.get("reason") or "").strip()
            source = entry.get("source", "")
            line = f"- `{name}` → merged into `{into}`"
            if reason:
                line += f" — {reason}"
            if source and source.startswith("tool-call audit"):
                line += f"  _(detected via {source})_"
            lines.append(line)
            if entry.get("model_claimed_into"):
                lines.append(
                    f"  ⚠ The curator's summary named `{entry['model_claimed_into']}` "
                    "as the umbrella but that skill doesn't exist post-run; "
                    "showing the tool-call audit's finding instead."
                )
        if len(consolidated) > SHOW:
            lines.append(f"- … and {len(consolidated) - SHOW} more (see `run.json`)")
        lines.append("")

    pruned = p.get("pruned") or []
    if pruned:
        lines.append(f"### Pruned — archived for staleness ({len(pruned)})\n")
        lines.append(
            "_These skills were archived without being merged into an umbrella "
            "(e.g. stale, unused, or judged irrelevant). "
            "Directories live under `~/.icecode/skills/.archive/`. "
            "Restore any via `hermes curator restore <name>`._\n"
        )
        SHOW = 50
        for entry in pruned[:SHOW]:
            if isinstance(entry, dict):
                name = entry.get("name", "?")
                reason = (entry.get("reason") or "").strip()
                line = f"- `{name}`"
                if reason:
                    line += f" — {reason}"
                lines.append(line)
            else:
                lines.append(f"- `{entry}`")
        if len(pruned) > SHOW:
            lines.append(f"- … and {len(pruned) - SHOW} more (see `run.json`)")
        lines.append("")

    added = p.get("added") or []
    if added:
        lines.append(f"### New skills this run ({len(added)})\n")
        lines.append("_Usually these are new class-level umbrellas created via `skill_manage action=create`._\n")
        for n in added:
            lines.append(f"- `{n}`")
        lines.append("")

    trans = p.get("state_transitions") or []
    if trans:
        lines.append(f"### State transitions ({len(trans)})\n")
        for t in trans:
            lines.append(f"- `{t.get('name')}`: {t.get('from')} → {t.get('to')}")
        lines.append("")

    cron_rw = p.get("cron_rewrites") or {}
    cron_rewrites_list = cron_rw.get("rewrites") or []
    if cron_rewrites_list:
        lines.append(f"### Cron job skill references rewritten ({len(cron_rewrites_list)})\n")
        lines.append(
            "_Cron jobs that referenced a consolidated or pruned skill were "
            "updated in-place so they keep loading the right instructions "
            "on their next run. See `cron_rewrites.json` for the full record._\n"
        )
        SHOW = 25
        for entry in cron_rewrites_list[:SHOW]:
            job_name = entry.get("job_name") or entry.get("job_id") or "?"
            before = entry.get("before") or []
            after = entry.get("after") or []
            mapped = entry.get("mapped") or {}
            dropped = entry.get("dropped") or []
            lines.append(
                f"- `{job_name}`: `{', '.join(before)}` → `{', '.join(after) or '(none)'}`"
            )
            for old, new in mapped.items():
                lines.append(f"    - `{old}` → `{new}` (consolidated)")
            for name in dropped:
                lines.append(f"    - `{name}` dropped (pruned)")
        if len(cron_rewrites_list) > SHOW:
            lines.append(
                f"- … and {len(cron_rewrites_list) - SHOW} more "
                "(see `cron_rewrites.json`)"
            )
        lines.append("")

    final = (p.get("llm_final") or "").strip()
    if final:
        lines.append("## LLM final summary\n")
        lines.append(final)
        lines.append("")
    elif not error:
        llm_sum = p.get("llm_summary") or ""
        if llm_sum:
            lines.append("## LLM summary\n")
            lines.append(llm_sum)
            lines.append("")

    lines.append("## Recovery\n")
    lines.append("- Restore an archived skill: `hermes curator restore <name>`")
    lines.append("- All archives live under `~/.icecode/skills/.archive/` and are recoverable by `mv`")
    lines.append("- See `run.json` in this directory for the full machine-readable record.")
    lines.append("")

    return "\n".join(lines)
