"""engine_session_mixin — session persistence, background tasks, interrupt, and memory.

Extracted from engine.py: background review tasks, session/trajectory saving,
file mutation tracking, interrupt/steer handling, memory management, and
the close/release lifecycle.
Composed into AIAgent via mixin inheritance.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from icecode.icecode_constants import get_hermes_home
    from icecode.agent.engine_multimodal import (
        _is_multimodal_tool_result,
        _multimodal_text_summary,
        _trajectory_normalize_msg,
        _extract_error_preview,
    )
except (ImportError, AttributeError):
    def get_hermes_home():
        from pathlib import Path
        return Path.home() / ".icecode"
    def _is_multimodal_tool_result(*a, **kw): return False
    def _multimodal_text_summary(*a, **kw): return str(a[0]) if a else ""
    def _trajectory_normalize_msg(*a, **kw): return a[0] if a else {}
    def _extract_error_preview(*a, **kw): return ""

logger = logging.getLogger(__name__)


class _SessionMixin:
    """Session persistence, background tasks, interrupt/steer, and memory management."""

    def _cleanup_task_resources(self, task_id: str) -> None:
        """Clean up VM and browser resources for a given task.

        Skips ``cleanup_vm`` when the active terminal environment is marked
        persistent (``persistent_filesystem=True``) so that long-lived sandbox
        containers survive between turns. The idle reaper in
        ``terminal_tool._cleanup_inactive_envs`` still tears them down once
        ``terminal.lifetime_seconds`` is exceeded. Non-persistent backends are
        torn down per-turn as before to prevent resource leakage (the original
        intent of this hook for the Morph backend, see commit fbd3a2fd).
        """
        try:
            if is_persistent_env(task_id):
                if self.verbose_logging:
                    logging.debug(
                        f"Skipping per-turn cleanup_vm for persistent env {task_id}; "
                        f"idle reaper will handle it."
                    )
            else:
                cleanup_vm(task_id)
        except Exception as e:
            if self.verbose_logging:
                logging.warning(f"Failed to cleanup VM for task {task_id}: {e}")
        try:
            cleanup_browser(task_id)
        except Exception as e:
            if self.verbose_logging:
                logging.warning(f"Failed to cleanup browser for task {task_id}: {e}")

    # ------------------------------------------------------------------
    # Background memory/skill review
    # ------------------------------------------------------------------

    _MEMORY_REVIEW_PROMPT = (
        "Review the conversation above and consider saving to memory if appropriate.\n\n"
        "Focus on:\n"
        "1. Has the user revealed things about themselves — their persona, desires, "
        "preferences, or personal details worth remembering?\n"
        "2. Has the user expressed expectations about how you should behave, their work "
        "style, or ways they want you to operate?\n\n"
        "If something stands out, save it using the memory tool. "
        "If nothing is worth saving, just say 'Nothing to save.' and stop."
    )

    _SKILL_REVIEW_PROMPT = (
        "Review the conversation above and update the skill library. Be "
        "ACTIVE — most sessions produce at least one skill update, even if "
        "small. A pass that does nothing is a missed learning opportunity, "
        "not a neutral outcome.\n\n"
        "Target shape of the library: CLASS-LEVEL skills, each with a rich "
        "SKILL.md and a `references/` directory for session-specific detail. "
        "Not a long flat list of narrow one-session-one-skill entries. This "
        "shapes HOW you update, not WHETHER you update.\n\n"
        "Signals to look for (any one of these warrants action):\n"
        "  • User corrected your style, tone, format, legibility, or "
        "verbosity. Frustration signals like 'stop doing X', 'this is too "
        "verbose', 'don't format like this', 'why are you explaining', "
        "'just give me the answer', 'you always do Y and I hate it', or an "
        "explicit 'remember this' are FIRST-CLASS skill signals, not just "
        "memory signals. Update the relevant skill(s) to embed the "
        "preference so the next session starts already knowing.\n"
        "  • User corrected your workflow, approach, or sequence of steps. "
        "Encode the correction as a pitfall or explicit step in the skill "
        "that governs that class of task.\n"
        "  • Non-trivial technique, fix, workaround, debugging path, or "
        "tool-usage pattern emerged that a future session would benefit "
        "from. Capture it.\n"
        "  • A skill that got loaded or consulted this session turned out "
        "to be wrong, missing a step, or outdated. Patch it NOW.\n\n"
        "Preference order — prefer the earliest action that fits, but do "
        "pick one when a signal above fired:\n"
        "  1. UPDATE A CURRENTLY-LOADED SKILL. Look back through the "
        "conversation for skills the user loaded via /skill-name or you "
        "read via skill_view. If any of them covers the territory of the "
        "new learning, PATCH that one first. It is the skill that was in "
        "play, so it's the right one to extend.\n"
        "  2. UPDATE AN EXISTING UMBRELLA (via skills_list + skill_view). "
        "If no loaded skill fits but an existing class-level skill does, "
        "patch it. Add a subsection, a pitfall, or broaden a trigger.\n"
        "  3. ADD A SUPPORT FILE under an existing umbrella. Skills can be "
        "packaged with three kinds of support files — use the right "
        "directory per kind:\n"
        "     • `references/<topic>.md` — session-specific detail (error "
        "transcripts, reproduction recipes, provider quirks) AND "
        "condensed knowledge banks: quoted research, API docs, external "
        "authoritative excerpts, or domain notes you found while working "
        "on the problem. Write it concise and for the value of the task, "
        "not as a full mirror of upstream docs.\n"
        "     • `templates/<name>.<ext>` — starter files meant to be "
        "copied and modified (boilerplate configs, scaffolding, a "
        "known-good example the agent can `reproduce with modifications`).\n"
        "     • `scripts/<name>.<ext>` — statically re-runnable actions "
        "the skill can invoke directly (verification scripts, fixture "
        "generators, deterministic probes, anything the agent should run "
        "rather than hand-type each time).\n"
        "     Add support files via skill_manage action=write_file with "
        "file_path starting 'references/', 'templates/', or 'scripts/'. "
        "The umbrella's SKILL.md should gain a one-line pointer to any "
        "new support file so future agents know it exists.\n"
        "  4. CREATE A NEW CLASS-LEVEL UMBRELLA SKILL when no existing "
        "skill covers the class. The name MUST be at the class level. "
        "The name MUST NOT be a specific PR number, error string, feature "
        "codename, library-alone name, or 'fix-X / debug-Y / audit-Z-today' "
        "session artifact. If the proposed name only makes sense for "
        "today's task, it's wrong — fall back to (1), (2), or (3).\n\n"
        "User-preference embedding (important): when the user expressed a "
        "style/format/workflow preference, the update belongs in the "
        "SKILL.md body, not just in memory. Memory captures 'who the user "
        "is and what the current situation and state of your operations "
        "are'; skills capture 'how to do this class of task for this "
        "user'. When they complain about how you handled a task, the "
        "skill that governs that task needs to carry the lesson.\n\n"
        "If you notice two existing skills that overlap, note it in your "
        "reply — the background curator handles consolidation at scale.\n\n"
        "Do NOT capture (these become persistent self-imposed constraints "
        "that bite you later when the environment changes):\n"
        "  • Environment-dependent failures: missing binaries, fresh-install "
        "errors, post-migration path mismatches, 'command not found', "
        "unconfigured credentials, uninstalled packages. The user can fix "
        "these — they are not durable rules.\n"
        "  • Negative claims about tools or features ('browser tools do not "
        "work', 'X tool is broken', 'cannot use Y from execute_code'). These "
        "harden into refusals the agent cites against itself for months "
        "after the actual problem was fixed.\n"
        "  • Session-specific transient errors that resolved before the "
        "conversation ended. If retrying worked, the lesson is the retry "
        "pattern, not the original failure.\n"
        "  • One-off task narratives. A user asking 'summarize today's "
        "market' or 'analyze this PR' is not a class of work that warrants "
        "a skill.\n\n"
        "If a tool failed because of setup state, capture the FIX (install "
        "command, config step, env var to set) under an existing setup or "
        "troubleshooting skill — never 'this tool does not work' as a "
        "standalone constraint.\n\n"
        "'Nothing to save.' is a real option but should NOT be the "
        "default. If the session ran smoothly with no corrections and "
        "produced no new technique, just say 'Nothing to save.' and stop. "
        "Otherwise, act."
    )

    _COMBINED_REVIEW_PROMPT = (
        "Review the conversation above and update two things:\n\n"
        "**Memory**: who the user is. Did the user reveal persona, "
        "desires, preferences, personal details, or expectations about "
        "how you should behave? Save facts about the user and durable "
        "preferences with the memory tool.\n\n"
        "**Skills**: how to do this class of task. Be ACTIVE — most "
        "sessions produce at least one skill update. A pass that does "
        "nothing is a missed learning opportunity, not a neutral outcome.\n\n"
        "Target shape of the skill library: CLASS-LEVEL skills with a rich "
        "SKILL.md and a `references/` directory for session-specific detail. "
        "Not a long flat list of narrow one-session-one-skill entries.\n\n"
        "Signals that warrant a skill update (any one is enough):\n"
        "  • User corrected your style, tone, format, legibility, "
        "verbosity, or approach. Frustration is a FIRST-CLASS skill "
        "signal, not just a memory signal. 'stop doing X', 'don't format "
        "like this', 'I hate when you Y' — embed the lesson in the skill "
        "that governs that task so the next session starts fixed.\n"
        "  • Non-trivial technique, fix, workaround, or debugging path "
        "emerged.\n"
        "  • A skill that was loaded or consulted turned out wrong, "
        "missing, or outdated — patch it now.\n\n"
        "Preference order for skills — pick the earliest that fits:\n"
        "  1. UPDATE A CURRENTLY-LOADED SKILL. Check what skills were "
        "loaded via /skill-name or skill_view in the conversation. If one "
        "of them covers the learning, PATCH it first. It was in play; "
        "it's the right place.\n"
        "  2. UPDATE AN EXISTING UMBRELLA (skills_list + skill_view to "
        "find the right one). Patch it.\n"
        "  3. ADD A SUPPORT FILE under an existing umbrella via "
        "skill_manage action=write_file. Three kinds: "
        "`references/<topic>.md` for session-specific detail OR condensed "
        "knowledge banks (quoted research, API docs excerpts, domain "
        "notes) written concise and task-focused; `templates/<name>.<ext>` "
        "for starter files meant to be copied and modified; "
        "`scripts/<name>.<ext>` for statically re-runnable actions "
        "(verification, fixture generators, probes). Add a one-line "
        "pointer in SKILL.md so future agents find them.\n"
        "  4. CREATE A NEW CLASS-LEVEL UMBRELLA when nothing exists. "
        "Name at the class level — NOT a PR number, error string, "
        "codename, library-alone name, or 'fix-X / debug-Y' session "
        "artifact. If the name only fits today's task, fall back to (1), "
        "(2), or (3).\n\n"
        "User-preference embedding: when the user complains about how "
        "you handled a task, update the skill that governs that task — "
        "memory alone isn't enough. Memory says 'who the user is and "
        "what the current situation and state of your operations are'; "
        "skills say 'how to do this class of task for this user'. Both "
        "should carry user-preference lessons when relevant.\n\n"
        "If you notice overlapping existing skills, mention it — the "
        "background curator handles consolidation.\n\n"
        "Do NOT capture as skills (these become persistent self-imposed "
        "constraints that bite you later when the environment changes):\n"
        "  • Environment-dependent failures: missing binaries, fresh-install "
        "errors, post-migration path mismatches, 'command not found', "
        "unconfigured credentials, uninstalled packages. The user can fix "
        "these — they are not durable rules.\n"
        "  • Negative claims about tools or features ('browser tools do not "
        "work', 'X tool is broken', 'cannot use Y from execute_code'). These "
        "harden into refusals the agent cites against itself for months "
        "after the actual problem was fixed.\n"
        "  • Session-specific transient errors that resolved before the "
        "conversation ended. If retrying worked, the lesson is the retry "
        "pattern, not the original failure.\n"
        "  • One-off task narratives. A user asking 'summarize today's "
        "market' or 'analyze this PR' is not a class of work that warrants "
        "a skill.\n\n"
        "If a tool failed because of setup state, capture the FIX (install "
        "command, config step, env var to set) under an existing setup or "
        "troubleshooting skill — never 'this tool does not work' as a "
        "standalone constraint.\n\n"
        "Act on whichever of the two dimensions has real signal. If "
        "genuinely nothing stands out on either, say 'Nothing to save.' "
        "and stop — but don't reach for that conclusion as a default."
    )

    @staticmethod
    def _summarize_background_review_actions(
        review_messages: List[Dict],
        prior_snapshot: List[Dict],
    ) -> List[str]:
        """Build the human-facing action summary for a background review pass.

        Walks the review agent's session messages and collects "successful tool
        action" descriptions to surface to the user (e.g. "Memory updated").
        Tool messages already present in ``prior_snapshot`` are skipped so we
        don't re-surface stale results from the prior conversation that the
        review agent inherited via ``conversation_history`` (issue #14944).

        Matching is by ``tool_call_id`` when available, with a content-equality
        fallback for tool messages that lack one.
        """
        existing_tool_call_ids = set()
        existing_tool_contents = set()
        for prior in prior_snapshot or []:
            if not isinstance(prior, dict) or prior.get("role") != "tool":
                continue
            tcid = prior.get("tool_call_id")
            if tcid:
                existing_tool_call_ids.add(tcid)
            else:
                content = prior.get("content")
                if isinstance(content, str):
                    existing_tool_contents.add(content)

        actions: List[str] = []
        for msg in review_messages or []:
            if not isinstance(msg, dict) or msg.get("role") != "tool":
                continue
            tcid = msg.get("tool_call_id")
            if tcid and tcid in existing_tool_call_ids:
                continue
            if not tcid:
                content_str = msg.get("content")
                if isinstance(content_str, str) and content_str in existing_tool_contents:
                    continue
            try:
                data = json.loads(msg.get("content", "{}"))
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(data, dict) or not data.get("success"):
                continue
            message = data.get("message", "")
            target = data.get("target", "")
            if "created" in message.lower():
                actions.append(message)
            elif "updated" in message.lower():
                actions.append(message)
            elif "added" in message.lower() or (target and "add" in message.lower()):
                label = "Memory" if target == "memory" else "User profile" if target == "user" else target
                actions.append(f"{label} updated")
            elif "Entry added" in message:
                label = "Memory" if target == "memory" else "User profile" if target == "user" else target
                actions.append(f"{label} updated")
            elif "removed" in message.lower() or "replaced" in message.lower():
                label = "Memory" if target == "memory" else "User profile" if target == "user" else target
                actions.append(f"{label} updated")
        return actions

    def _spawn_background_review(
        self,
        messages_snapshot: List[Dict],
        review_memory: bool = False,
        review_skills: bool = False,
    ) -> None:
        """Spawn a background thread to review the conversation for memory/skill saves.

        Creates a full AIAgent fork with the same model, tools, and context as the
        main session. The review prompt is appended as the next user turn in the
        forked conversation. Writes directly to the shared memory/skill stores.
        Never modifies the main conversation history or produces user-visible output.
        """
        import threading

        # Pick the right prompt based on which triggers fired
        if review_memory and review_skills:
            prompt = self._COMBINED_REVIEW_PROMPT
        elif review_memory:
            prompt = self._MEMORY_REVIEW_PROMPT
        else:
            prompt = self._SKILL_REVIEW_PROMPT

        def _run_review():
            import contextlib
            # Install a non-interactive approval callback on this worker
            # thread so any dangerous-command guard the review agent trips
            # resolves to "deny" instead of falling back to input() -- which
            # deadlocks against the parent's prompt_toolkit TUI (#15216).
            # Same pattern as _subagent_auto_deny in tools/delegate_tool.py.
            def _bg_review_auto_deny(command, description, **kwargs):
                logger.warning(
                    "Background review auto-denied dangerous command: %s (%s)",
                    command, description,
                )
                return "deny"
            try:
                _set_approval_callback(_bg_review_auto_deny)
            except Exception:
                pass
            review_agent = None
            try:
                with open(os.devnull, "w", encoding="utf-8") as _devnull, \
                     contextlib.redirect_stdout(_devnull), \
                     contextlib.redirect_stderr(_devnull):
                    # Inherit the parent agent's live runtime (provider, model,
                    # base_url, api_key, api_mode) so the fork uses the exact
                    # same credentials the main turn is using.  Without this,
                    # AIAgent.__init__ re-runs auto-resolution from env vars,
                    # which fails for OAuth-only providers, session-scoped
                    # creds, or credential-pool setups where the resolver can't
                    # reconstruct auth from scratch -- producing the spurious
                    # "No LLM provider configured" warning at end of turn.
                    _parent_runtime = self._current_main_runtime()
                    _parent_api_mode = _parent_runtime.get("api_mode") or None
                    # The review fork needs to call agent-loop tools (memory,
                    # ICECODE' own dispatch,
                    # which the codex_app_server runtime bypasses entirely
                    # (it runs the turn inside codex's subprocess). So when
                    # the parent is on codex_app_server, downgrade the review
                    # fork to codex_responses — same auth/credentials, but
                    # ICECODE
                    # owns the loop and the agent-loop tools dispatch.
                    if _parent_api_mode == "codex_app_server":
                        _parent_api_mode = "codex_responses"
                    review_agent = AIAgent(
                        model=self.model,
                        max_iterations=16,
                        quiet_mode=True,
                        platform=self.platform,
                        provider=self.provider,
                        api_mode=_parent_api_mode,
                        base_url=_parent_runtime.get("base_url") or None,
                        api_key=_parent_runtime.get("api_key") or None,
                        credential_pool=getattr(self, "_credential_pool", None),
                        parent_session_id=self.session_id,
                    )
                    review_agent._memory_write_origin = "background_review"
                    review_agent._memory_write_context = "background_review"
                    review_agent._memory_store = self._memory_store
                    review_agent._memory_enabled = self._memory_enabled
                    review_agent._user_profile_enabled = self._user_profile_enabled
                    review_agent._memory_nudge_interval = 0
                    review_agent._skill_nudge_interval = 0
                    # Suppress all status/warning emits from the fork so the
                    # user only sees the final successful-action summary.
                    # Without this, mid-review "Iteration budget exhausted",
                    # rate-limit retries, compression warnings, and other
                    # lifecycle messages bubble up through _emit_status ->
                    # _vprint and leak past the stdout redirect (they go via
                    # _print_fn/status_callback, which bypass sys.stdout).
                    review_agent.suppress_status_output = True
                    # Inherit the parent's cached system prompt verbatim so
                    # the review fork's outbound HTTP request hits the same
                    # Anthropic/OpenRouter prefix cache the parent warmed.
                    # Without this, the fork rebuilds the system prompt from
                    # scratch (fresh _hermes_now() timestamp, fresh
                    # session_id, narrower toolset → different skills_prompt)
                    # and the byte-exact prefix-cache key misses. See
                    # issue #25322 and PR #17276 for the full analysis +
                    # measured impact (~26% end-to-end cost reduction on
                    # Sonnet 4.5).
                    review_agent._cached_system_prompt = self._cached_system_prompt
                    # Defensive: pin session_start + session_id to the
                    # parent's so any code path that re-renders parts of
                    # the system prompt (compression, plugin hooks) still
                    # produces byte-identical output. The cached-prompt
                    # assignment above already short-circuits the normal
                    # rebuild path, but these pins guarantee parity even
                    # if a future code path bypasses the cache.
                    review_agent.session_start = self.session_start
                    review_agent.session_id = self.session_id

                    from model_tools import get_tool_definitions
                    from icecode_cli.hermes_cli.plugins import (
                        set_thread_tool_whitelist,
                        clear_thread_tool_whitelist,
                    )

                    review_whitelist = {
                        t["function"]["name"]
                        for t in get_tool_definitions(
                            enabled_toolsets=["memory", "skills"],
                            quiet_mode=True,
                        )
                    }
                    set_thread_tool_whitelist(
                        review_whitelist,
                        deny_msg_fmt=(
                            "Background review denied non-whitelisted tool: "
                            "{tool_name}. Only memory/skill tools are allowed."
                        ),
                    )
                    try:
                        review_agent.run_conversation(
                            user_message=(
                                prompt
                                + "\n\nYou can only call memory and skill "
                                "management tools. Other tools will be denied "
                                "at runtime — do not attempt them."
                            ),
                            conversation_history=messages_snapshot,
                        )
                    finally:
                        clear_thread_tool_whitelist()

                    # Tear down memory providers while stdout is still
                    # redirected so background thread teardown (Honcho flush,
                    # Hindsight sync, etc.) stays silent.  The finally block
                    # below is a safety net for the exception path.
                    try:
                        review_agent.shutdown_memory_provider()
                    except Exception:
                        pass
                    try:
                        review_agent.close()
                    except Exception:
                        pass
                    review_agent = None

                # Scan the review agent's messages for successful tool actions
                # and surface a compact summary to the user. Tool messages
                # already present in messages_snapshot must be skipped, since
                # the review agent inherits that history and would otherwise
                # re-surface stale "created"/"updated" messages from the prior
                # conversation as if they just happened (issue #14944).
                actions = self._summarize_background_review_actions(
                    getattr(review_agent, "_session_messages", []),
                    messages_snapshot,
                )

                if actions:
                    summary = " · ".join(dict.fromkeys(actions))
                    self._safe_print(
                        f"  💾 Self-improvement review: {summary}"
                    )
                    _bg_cb = self.background_review_callback
                    if _bg_cb:
                        try:
                            _bg_cb(
                                f"💾 Self-improvement review: {summary}"
                            )
                        except Exception:
                            pass

            except Exception as e:
                logger.warning("Background memory/skill review failed: %s", e)
                self._emit_auxiliary_failure("background review", e)
            finally:
                # Safety-net cleanup for the exception path.  Normal
                # completion already shut down inside redirect_stdout above.
                # Re-open devnull here so any teardown output (Honcho flush,
                # Hindsight sync, background thread joins) stays silent even
                # on the exception path where redirect_stdout already exited.
                if review_agent is not None:
                    try:
                        with open(os.devnull, "w", encoding="utf-8") as _fn, \
                             contextlib.redirect_stdout(_fn), \
                             contextlib.redirect_stderr(_fn):
                            try:
                                review_agent.shutdown_memory_provider()
                            except Exception:
                                pass
                            try:
                                review_agent.close()
                            except Exception:
                                pass
                    except Exception:
                        pass
                # Clear the approval callback on this bg-review thread so a
                # recycled thread-id doesn't inherit a stale reference.
                try:
                    _set_approval_callback(None)
                except Exception:
                    pass

        t = threading.Thread(target=_run_review, daemon=True, name="bg-review")
        t.start()

    def _build_memory_write_metadata(
        self,
        *,
        write_origin: Optional[str] = None,
        execution_context: Optional[str] = None,
        task_id: Optional[str] = None,
        tool_call_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build provenance metadata for external memory-provider mirrors."""
        metadata: Dict[str, Any] = {
            "write_origin": write_origin or getattr(self, "_memory_write_origin", "assistant_tool"),
            "execution_context": (
                execution_context
                or getattr(self, "_memory_write_context", "foreground")
            ),
            "session_id": self.session_id or "",
            "parent_session_id": self._parent_session_id or "",
            "platform": self.platform or os.environ.get("ICECODE_SESSION_SOURCE", "cli"),
            "tool_name": "memory",
        }
        if task_id:
            metadata["task_id"] = task_id
        if tool_call_id:
            metadata["tool_call_id"] = tool_call_id
        return {k: v for k, v in metadata.items() if v not in {None, ""}}

    def _apply_persist_user_message_override(self, messages: List[Dict]) -> None:
        """Rewrite the current-turn user message before persistence/return.

        Some call paths need an API-only user-message variant without letting
        that synthetic text leak into persisted transcripts or resumed session
        history. When an override is configured for the active turn, mutate the
        in-memory messages list in place so both persistence and returned
        history stay clean.
        """
        idx = getattr(self, "_persist_user_message_idx", None)
        override = getattr(self, "_persist_user_message_override", None)
        if override is None or idx is None:
            return
        if 0 <= idx < len(messages):
            msg = messages[idx]
            if isinstance(msg, dict) and msg.get("role") == "user":
                msg["content"] = override

    def _persist_session(self, messages: List[Dict], conversation_history: List[Dict] = None):
        """Save session state to both JSON log and SQLite on any exit path.

        Ensures conversations are never lost, even on errors or early returns.
        """
        self._drop_trailing_empty_response_scaffolding(messages)
        self._apply_persist_user_message_override(messages)
        self._session_messages = messages
        self._save_session_log(messages)
        self._flush_messages_to_session_db(messages, conversation_history)

    def _drop_trailing_empty_response_scaffolding(self, messages: List[Dict]) -> None:
        """Remove private empty-response retry/failure scaffolding from transcript tails.

        Also rewinds past any trailing tool-result / assistant(tool_calls) pair
        that the failed iteration left hanging. Without this, the tail ends at
        a raw ``tool`` message and the next user turn lands as
        ``...tool, user, user`` — a protocol-invalid sequence that most
        providers silently reject (returns empty content), causing the
        empty-retry loop to fire forever. See #<TBD>.
        """
        # Pass 1: strip the flagged scaffolding messages themselves.
        dropped_scaffolding = False
        while (
            messages
            and isinstance(messages[-1], dict)
            and (
                messages[-1].get("_empty_recovery_synthetic")
                or messages[-1].get("_empty_terminal_sentinel")
            )
        ):
            messages.pop()
            dropped_scaffolding = True

        # Pass 2: if we stripped scaffolding, rewind through any trailing
        # tool-result messages plus the assistant(tool_calls) message that
        # produced them. This preserves role alternation so the next user
        # message follows a user or assistant message, not an orphan tool
        # result. Only runs when scaffolding was actually present — normal
        # conversation tails (real tool loops mid-progress) are untouched.
        if not dropped_scaffolding:
            return

        # Drop any trailing tool-result messages
        while (
            messages
            and isinstance(messages[-1], dict)
            and messages[-1].get("role") == "tool"
        ):
            messages.pop()

        # Drop the assistant message that issued the tool calls, if the tail
        # now ends in an assistant-with-tool_calls (the pair that owned the
        # just-popped tool results). Without this, the tail is
        # ``assistant(tool_calls=...)`` with no tool answers, which some
        # providers also reject.
        if (
            messages
            and isinstance(messages[-1], dict)
            and messages[-1].get("role") == "assistant"
            and messages[-1].get("tool_calls")
        ):
            messages.pop()

    def _repair_message_sequence(self, messages: List[Dict]) -> int:
        """Collapse malformed role-alternation left in the live history.

        Providers (OpenAI, OpenRouter, Anthropic) expect strict alternation:
        after the system message, user/tool alternates with assistant, with
        no two consecutive user messages and no tool-result that doesn't
        follow an assistant-with-tool_calls. Violations cause silent empty
        responses on most providers, which triggers the empty-retry loop.

        This runs right before the API call as a defensive belt — by the
        time it fires, the scaffolding strip should already have prevented
        most shapes, but external callers (gateway multi-queue replay,
        session resume, cron, explicit conversation_history passed in by
        host code) can feed in already-broken histories.

        Repairs applied:
          1. Stray ``tool`` messages whose ``tool_call_id`` doesn't match
             any preceding assistant tool_call — dropped.
          2. Consecutive ``user`` messages — merged with newline separator
             so no user input is lost.

        Deliberately does NOT rewind orphan ``assistant(tool_calls)+tool``
        pairs that precede a user message — that pattern IS valid when the
        previous turn completed normally and the user jumped in to redirect
        before the model got a continuation turn (the ongoing dialog
        pattern). The empty-response scaffolding stripper handles the
        genuinely-broken variant via its flag-gated rewind.

        Returns the number of repairs made (for logging/telemetry).
        """
        if not messages:
            return 0

        repairs = 0

        # Pass 1: drop stray tool messages that don't follow a known
        # assistant tool_call_id. Uses a rolling set of known ids refreshed
        # on each assistant message.
        known_tool_ids: set = set()
        filtered: List[Dict] = []
        for msg in messages:
            if not isinstance(msg, dict):
                filtered.append(msg)
                continue
            role = msg.get("role")
            if role == "assistant":
                known_tool_ids = set()
                for tc in (msg.get("tool_calls") or []):
                    tc_id = tc.get("id") if isinstance(tc, dict) else None
                    if tc_id:
                        known_tool_ids.add(tc_id)
                filtered.append(msg)
            elif role == "tool":
                tc_id = msg.get("tool_call_id")
                if tc_id and tc_id in known_tool_ids:
                    filtered.append(msg)
                else:
                    repairs += 1
            else:
                if role == "user":
                    # A user turn closes the tool-result run; subsequent
                    # tool messages without a fresh assistant tool_call
                    # are orphans.
                    known_tool_ids = set()
                filtered.append(msg)

        # Pass 2: merge consecutive user messages. Preserves all user input
        # so nothing the user typed is lost.
        merged: List[Dict] = []
        for msg in filtered:
            if (
                merged
                and isinstance(msg, dict)
                and msg.get("role") == "user"
                and isinstance(merged[-1], dict)
                and merged[-1].get("role") == "user"
            ):
                prev = merged[-1]
                prev_content = prev.get("content", "")
                new_content = msg.get("content", "")
                # Only merge plain-text content; leave multimodal (list)
                # content alone — collapsing image/audio blocks risks
                # mangling the attachment structure.
                if isinstance(prev_content, str) and isinstance(new_content, str):
                    prev["content"] = (
                        (prev_content + "\n\n" + new_content)
                        if prev_content and new_content
                        else (prev_content or new_content)
                    )
                    repairs += 1
                    continue
            merged.append(msg)

        if repairs > 0:
            # Rewrite in place so downstream paths (persistence, return
            # value, session DB flush) see the repaired sequence.
            messages[:] = merged

        return repairs

    def _flush_messages_to_session_db(self, messages: List[Dict], conversation_history: List[Dict] = None):
        """Persist any un-flushed messages to the SQLite session store.

        Uses _last_flushed_db_idx to track which messages have already been
        written, so repeated calls (from multiple exit paths) only write
        truly new messages — preventing the duplicate-write bug (#860).
        """
        if not self._session_db:
            return
        self._apply_persist_user_message_override(messages)
        try:
            # Retry row creation if the earlier attempt failed transiently.
            if not self._session_db_created:
                self._ensure_db_session()
            start_idx = len(conversation_history) if conversation_history else 0
            flush_from = max(start_idx, self._last_flushed_db_idx)
            for msg in messages[flush_from:]:
                role = msg.get("role", "unknown")
                content = msg.get("content")
                # Persist multimodal tool results as their text summary only —
                # base64 images would bloat the session DB and aren't useful
                # for cross-session replay.
                if _is_multimodal_tool_result(content):
                    content = _multimodal_text_summary(content)
                elif isinstance(content, list):
                    # List of OpenAI-style content parts: strip images, keep text.
                    _txt = []
                    for p in content:
                        if isinstance(p, dict) and p.get("type") == "text":
                            _txt.append(str(p.get("text", "")))
                        elif isinstance(p, dict) and p.get("type") in {"image", "image_url", "input_image"}:
                            _txt.append("[screenshot]")
                    content = "\n".join(_txt) if _txt else None
                tool_calls_data = None
                if hasattr(msg, "tool_calls") and isinstance(msg.tool_calls, list) and msg.tool_calls:
                    tool_calls_data = [
                        {"name": tc.function.name, "arguments": tc.function.arguments}
                        for tc in msg.tool_calls
                    ]
                elif isinstance(msg.get("tool_calls"), list):
                    tool_calls_data = msg["tool_calls"]
                self._session_db.append_message(
                    session_id=self.session_id,
                    role=role,
                    content=content,
                    tool_name=msg.get("tool_name"),
                    tool_calls=tool_calls_data,
                    tool_call_id=msg.get("tool_call_id"),
                    finish_reason=msg.get("finish_reason"),
                    reasoning=msg.get("reasoning") if role == "assistant" else None,
                    reasoning_content=msg.get("reasoning_content") if role == "assistant" else None,
                    reasoning_details=msg.get("reasoning_details") if role == "assistant" else None,
                    codex_reasoning_items=msg.get("codex_reasoning_items") if role == "assistant" else None,
                    codex_message_items=msg.get("codex_message_items") if role == "assistant" else None,
                )
            self._last_flushed_db_idx = len(messages)
        except Exception as e:
            logger.warning("Session DB append_message failed: %s", e)

    def _get_messages_up_to_last_assistant(self, messages: List[Dict]) -> List[Dict]:
        """
        Get messages up to (but not including) the last assistant turn.
        
        This is used when we need to "roll back" to the last successful point
        in the conversation, typically when the final assistant message is
        incomplete or malformed.
        
        Args:
            messages: Full message list
            
        Returns:
            Messages up to the last complete assistant turn (ending with user/tool message)
        """
        if not messages:
            return []
        
        # Find the index of the last assistant message
        last_assistant_idx = None
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "assistant":
                last_assistant_idx = i
                break
        
        if last_assistant_idx is None:
            # No assistant message found, return all messages
            return messages.copy()
        
        # Return everything up to (not including) the last assistant message
        return messages[:last_assistant_idx]

    def _format_tools_for_system_message(self) -> str:
        """
        Format tool definitions for the system message in the trajectory format.
        
        Returns:
            str: JSON string representation of tool definitions
        """
        if not self.tools:
            return "[]"
        
        # Convert tool definitions to the format expected in trajectories
        formatted_tools = []
        for tool in self.tools:
            func = tool["function"]
            formatted_tool = {
                "name": func["name"],
                "description": func.get("description", ""),
                "parameters": func.get("parameters", {}),
                "required": None  # Match the format in the example
            }
            formatted_tools.append(formatted_tool)
        
        return json.dumps(formatted_tools, ensure_ascii=False)

    def _convert_to_trajectory_format(self, messages: List[Dict[str, Any]], user_query: str, completed: bool) -> List[Dict[str, Any]]:
        """
        Convert internal message format to trajectory format for saving.
        
        Args:
            messages (List[Dict]): Internal message history
            user_query (str): Original user query
            completed (bool): Whether the conversation completed successfully
            
        Returns:
            List[Dict]: Messages in trajectory format
        """
        # Normalize multimodal tool results — trajectories are text-only, so
        # replace image-bearing tool messages with their text_summary to avoid
        # embedding ~1MB base64 blobs into every saved trajectory.
        messages = [_trajectory_normalize_msg(m) for m in messages]
        trajectory = []
        
        # Add system message with tool definitions
        system_msg = (
            "You are a function calling AI model. You are provided with function signatures within <tools> </tools> XML tags. "
            "You may call one or more functions to assist with the user query. If available tools are not relevant in assisting "
            "with user query, just respond in natural conversational language. Don't make assumptions about what values to plug "
            "into functions. After calling & executing the functions, you will be provided with function results within "
            "<tool_response> </tool_response> XML tags. Here are the available tools:\n"
            f"<tools>\n{self._format_tools_for_system_message()}\n</tools>\n"
            "For each function call return a JSON object, with the following pydantic model json schema for each:\n"
            "{'title': 'FunctionCall', 'type': 'object', 'properties': {'name': {'title': 'Name', 'type': 'string'}, "
            "'arguments': {'title': 'Arguments', 'type': 'object'}}, 'required': ['name', 'arguments']}\n"
            "Each function call should be enclosed within <tool_call> </tool_call> XML tags.\n"
            "Example:\n<tool_call>\n{'name': <function-name>,'arguments': <args-dict>}\n</tool_call>"
        )
        
        trajectory.append({
            "from": "system",
            "value": system_msg
        })
        
        # Add the actual user prompt (from the dataset) as the first human message
        trajectory.append({
            "from": "human",
            "value": user_query
        })
        
        # Skip the first message (the user query) since we already added it above.
        # Prefill messages are injected at API-call time only (not in the messages
        # list), so no offset adjustment is needed here.
        i = 1
        
        while i < len(messages):
            msg = messages[i]
            
            if msg["role"] == "assistant":
                # Check if this message has tool calls
                if "tool_calls" in msg and msg["tool_calls"]:
                    # Format assistant message with tool calls
                    # Add <think> tags around reasoning for trajectory storage
                    content = ""
                    
                    # Prepend reasoning in <think> tags if available (native thinking tokens)
                    if msg.get("reasoning") and msg["reasoning"].strip():
                        content = f"<think>\n{msg['reasoning']}\n</think>\n"
                    
                    if msg.get("content") and msg["content"].strip():
                        # Convert any <REASONING_SCRATCHPAD> tags to <think> tags
                        # (used when native thinking is disabled and model reasons via XML)
                        content += convert_scratchpad_to_think(msg["content"]) + "\n"
                    
                    # Add tool calls wrapped in XML tags
                    for tool_call in msg["tool_calls"]:
                        if not tool_call or not isinstance(tool_call, dict): continue
                        # Parse arguments - should always succeed since we validate during conversation
                        # but keep try-except as safety net
                        try:
                            arguments = json.loads(tool_call["function"]["arguments"]) if isinstance(tool_call["function"]["arguments"], str) else tool_call["function"]["arguments"]
                        except json.JSONDecodeError:
                            # This shouldn't happen since we validate and retry during conversation,
                            # but if it does, log warning and use empty dict
                            logging.warning(f"Unexpected invalid JSON in trajectory conversion: {tool_call['function']['arguments'][:100]}")
                            arguments = {}
                        
                        tool_call_json = {
                            "name": tool_call["function"]["name"],
                            "arguments": arguments
                        }
                        content += f"<tool_call>\n{json.dumps(tool_call_json, ensure_ascii=False)}\n</tool_call>\n"
                    
                    # Ensure every gpt turn has a <think> block (empty if no reasoning)
                    # so the format is consistent for training data
                    if "<think>" not in content:
                        content = "<think>\n</think>\n" + content
                    
                    trajectory.append({
                        "from": "gpt",
                        "value": content.rstrip()
                    })
                    
                    # Collect all subsequent tool responses
                    tool_responses = []
                    j = i + 1
                    while j < len(messages) and messages[j]["role"] == "tool":
                        tool_msg = messages[j]
                        # Format tool response with XML tags
                        tool_response = "<tool_response>\n"
                        
                        # Try to parse tool content as JSON if it looks like JSON
                        tool_content = tool_msg["content"]
                        try:
                            if tool_content.strip().startswith(("{", "[")):
                                tool_content = json.loads(tool_content)
                        except (json.JSONDecodeError, AttributeError):
                            pass  # Keep as string if not valid JSON
                        
                        tool_index = len(tool_responses)
                        tool_name = (
                            msg["tool_calls"][tool_index]["function"]["name"]
                            if tool_index < len(msg["tool_calls"])
                            else "unknown"
                        )
                        tool_response += json.dumps({
                            "tool_call_id": tool_msg.get("tool_call_id", ""),
                            "name": tool_name,
                            "content": tool_content
                        }, ensure_ascii=False)
                        tool_response += "\n</tool_response>"
                        tool_responses.append(tool_response)
                        j += 1
                    
                    # Add all tool responses as a single message
                    if tool_responses:
                        trajectory.append({
                            "from": "tool",
                            "value": "\n".join(tool_responses)
                        })
                        i = j - 1  # Skip the tool messages we just processed
                
                else:
                    # Regular assistant message without tool calls
                    # Add <think> tags around reasoning for trajectory storage
                    content = ""
                    
                    # Prepend reasoning in <think> tags if available (native thinking tokens)
                    if msg.get("reasoning") and msg["reasoning"].strip():
                        content = f"<think>\n{msg['reasoning']}\n</think>\n"
                    
                    # Convert any <REASONING_SCRATCHPAD> tags to <think> tags
                    # (used when native thinking is disabled and model reasons via XML)
                    raw_content = msg["content"] or ""
                    content += convert_scratchpad_to_think(raw_content)
                    
                    # Ensure every gpt turn has a <think> block (empty if no reasoning)
                    if "<think>" not in content:
                        content = "<think>\n</think>\n" + content
                    
                    trajectory.append({
                        "from": "gpt",
                        "value": content.strip()
                    })
            
            elif msg["role"] == "user":
                trajectory.append({
                    "from": "human",
                    "value": msg["content"]
                })
            
            i += 1
        
        return trajectory

    def _save_trajectory(self, messages: List[Dict[str, Any]], user_query: str, completed: bool):
        """
        Save conversation trajectory to JSONL file.
        
        Args:
            messages (List[Dict]): Complete message history
            user_query (str): Original user query
            completed (bool): Whether the conversation completed successfully
        """
        if not self.save_trajectories:
            return
        
        trajectory = self._convert_to_trajectory_format(messages, user_query, completed)
        _save_trajectory_to_file(trajectory, self.model, completed)

    @staticmethod
    def _summarize_api_error(error: Exception) -> str:
        """Extract a human-readable one-liner from an API error.

        Handles Cloudflare HTML error pages (502, 503, etc.) by pulling the
        <title> tag instead of dumping raw HTML.  Falls back to a truncated
        str(error) for everything else.
        """
        raw = str(error)

        # Cloudflare / proxy HTML pages: grab the <title> for a clean summary
        if "<!DOCTYPE" in raw or "<html" in raw:
            m = re.search(r"<title[^>]*>([^<]+)</title>", raw, re.IGNORECASE)
            title = m.group(1).strip() if m else "HTML error page (title not found)"
            # Also grab Cloudflare Ray ID if present
            ray = re.search(r"Cloudflare Ray ID:\s*<strong[^>]*>([^<]+)</strong>", raw)
            ray_id = ray.group(1).strip() if ray else None
            status_code = getattr(error, "status_code", None)
            parts = []
            if status_code:
                parts.append(f"HTTP {status_code}")
            parts.append(title)
            if ray_id:
                parts.append(f"Ray {ray_id}")
            return " — ".join(parts)

        # JSON body errors from OpenAI/Anthropic SDKs
        body = getattr(error, "body", None)
        if isinstance(body, dict):
            msg = body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else body.get("message")
            if msg:
                status_code = getattr(error, "status_code", None)
                prefix = f"HTTP {status_code}: " if status_code else ""
                return f"{prefix}{msg[:300]}"

        # Fallback: truncate the raw string but give more room than 200 chars
        status_code = getattr(error, "status_code", None)
        prefix = f"HTTP {status_code}: " if status_code else ""
        return f"{prefix}{raw[:500]}"

    def _mask_api_key_for_logs(self, key: Optional[str]) -> Optional[str]:
        if not key:
            return None
        if len(key) <= 12:
            return "***"
        return f"{key[:8]}...{key[-4:]}"

    def _clean_error_message(self, error_msg: str) -> str:
        """
        Clean up error messages for user display, removing HTML content and truncating.
        
        Args:
            error_msg: Raw error message from API or exception
            
        Returns:
            Clean, user-friendly error message
        """
        if not error_msg:
            return "Unknown error"
            
        # Remove HTML content (common with CloudFlare and gateway error pages)
        if error_msg.strip().startswith('<!DOCTYPE html') or '<html' in error_msg:
            return "Service temporarily unavailable (HTML error page returned)"
            
        # Remove newlines and excessive whitespace
        cleaned = ' '.join(error_msg.split())
        
        # Truncate if too long
        if len(cleaned) > 150:
            cleaned = cleaned[:150] + "..."
            
        return cleaned

    @staticmethod
    def _extract_api_error_context(error: Exception) -> Dict[str, Any]:
        """Extract structured rate-limit details from provider errors."""
        context: Dict[str, Any] = {}

        body = getattr(error, "body", None)
        payload = None
        if isinstance(body, dict):
            payload = body.get("error") if isinstance(body.get("error"), dict) else body
        if isinstance(payload, dict):
            reason = payload.get("code") or payload.get("error")
            if isinstance(reason, str) and reason.strip():
                context["reason"] = reason.strip()
            message = payload.get("message") or payload.get("error_description")
            if isinstance(message, str) and message.strip():
                context["message"] = message.strip()
            for key in ("resets_at", "reset_at"):
                value = payload.get(key)
                if value not in {None, ""}:
                    context["reset_at"] = value
                    break
            retry_after = payload.get("retry_after")
            if retry_after not in {None, ""} and "reset_at" not in context:
                try:
                    context["reset_at"] = time.time() + float(retry_after)
                except (TypeError, ValueError):
                    pass

        response = getattr(error, "response", None)
        headers = getattr(response, "headers", None)
        if headers:
            retry_after = headers.get("retry-after") or headers.get("Retry-After")
            if retry_after and "reset_at" not in context:
                try:
                    context["reset_at"] = time.time() + float(retry_after)
                except (TypeError, ValueError):
                    pass
            ratelimit_reset = headers.get("x-ratelimit-reset")
            if ratelimit_reset and "reset_at" not in context:
                context["reset_at"] = ratelimit_reset

        if "message" not in context:
            raw_message = str(error).strip()
            if raw_message:
                context["message"] = raw_message[:500]

        if "reset_at" not in context:
            message = context.get("message") or ""
            if isinstance(message, str):
                delay_match = re.search(r"quotaResetDelay[:\s\"]+(\\d+(?:\\.\\d+)?)(ms|s)", message, re.IGNORECASE)
                if delay_match:
                    value = float(delay_match.group(1))
                    seconds = value / 1000.0 if delay_match.group(2).lower() == "ms" else value
                    context["reset_at"] = time.time() + seconds
                else:
                    sec_match = re.search(
                        r"retry\s+(?:after\s+)?(\d+(?:\.\d+)?)\s*(?:sec|secs|seconds|s\b)",
                        message,
                        re.IGNORECASE,
                    )
                    if sec_match:
                        context["reset_at"] = time.time() + float(sec_match.group(1))

        return context

    def _usage_summary_for_api_request_hook(self, response: Any) -> Optional[Dict[str, Any]]:
        """Token buckets for ``post_api_request`` plugins (no raw ``response`` object)."""
        if response is None:
            return None
        raw_usage = getattr(response, "usage", None)
        if not raw_usage:
            return None
        from dataclasses import asdict

        cu = normalize_usage(raw_usage, provider=self.provider, api_mode=self.api_mode)
        summary = asdict(cu)
        summary.pop("raw_usage", None)
        summary["prompt_tokens"] = cu.prompt_tokens
        summary["total_tokens"] = cu.total_tokens
        return summary

    def _dump_api_request_debug(
        self,
        api_kwargs: Dict[str, Any],
        *,
        reason: str,
        error: Optional[Exception] = None,
    ) -> Optional[Path]:
        """
        Dump a debug-friendly HTTP request record for the active inference API.

        Captures the request body from api_kwargs (excluding transport-only keys
        like timeout). Intended for debugging provider-side 4xx failures where
        retries are not useful.
        """
        try:
            body = copy.deepcopy(api_kwargs)
            body.pop("timeout", None)
            body = {k: v for k, v in body.items() if v is not None}

            api_key = None
            try:
                api_key = getattr(self.client, "api_key", None)
            except Exception as e:
                logger.debug("Could not extract API key for debug dump: %s", e)

            dump_payload: Dict[str, Any] = {
                "timestamp": datetime.now().isoformat(),
                "session_id": self.session_id,
                "reason": reason,
                "request": {
                    "method": "POST",
                    "url": f"{self.base_url.rstrip('/')}{'/responses' if self.api_mode == 'codex_responses' else '/chat/completions'}",
                    "headers": {
                        "Authorization": f"Bearer {self._mask_api_key_for_logs(api_key)}",
                        "Content-Type": "application/json",
                    },
                    "body": body,
                },
            }

            if error is not None:
                error_info: Dict[str, Any] = {
                    "type": type(error).__name__,
                    "message": str(error),
                }
                for attr_name in ("status_code", "request_id", "code", "param", "type"):
                    attr_value = getattr(error, attr_name, None)
                    if attr_value is not None:
                        error_info[attr_name] = attr_value

                body_attr = getattr(error, "body", None)
                if body_attr is not None:
                    error_info["body"] = body_attr

                response_obj = getattr(error, "response", None)
                if response_obj is not None:
                    try:
                        error_info["response_status"] = getattr(response_obj, "status_code", None)
                        error_info["response_text"] = response_obj.text
                    except Exception as e:
                        logger.debug("Could not extract error response details: %s", e)

                dump_payload["error"] = error_info

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            dump_file = self.logs_dir / f"request_dump_{self.session_id}_{timestamp}.json"
            dump_file.write_text(
                json.dumps(dump_payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )

            self._vprint(f"{self.log_prefix}🧾 Request debug dump written to: {dump_file}")

            if env_var_enabled("ICECODE_DUMP_REQUEST_STDOUT"):
                print(json.dumps(dump_payload, ensure_ascii=False, indent=2, default=str))

            return dump_file
        except Exception as dump_error:
            if self.verbose_logging:
                logging.warning(f"Failed to dump API request debug payload: {dump_error}")
            return None

    @staticmethod
    def _clean_session_content(content: str) -> str:
        """Convert REASONING_SCRATCHPAD to think tags and clean up whitespace."""
        if not content:
            return content
        content = convert_scratchpad_to_think(content)
        content = re.sub(r'\n+(<think>)', r'\n\1', content)
        content = re.sub(r'(</think>)\n+', r'\1\n', content)
        return content.strip()

    def _save_session_log(self, messages: List[Dict[str, Any]] = None):
        """
        Save the full raw session to a JSON file.

        Stores every message exactly as the agent sees it: user messages,
        assistant messages (with reasoning, finish_reason, tool_calls),
        tool responses (with tool_call_id, tool_name), and injected system
        messages (compression summaries, todo snapshots, etc.).

        REASONING_SCRATCHPAD tags are converted to <think> blocks for consistency.
        Overwritten after each turn so it always reflects the latest state.
        """
        messages = messages or self._session_messages
        if not messages:
            return

        try:
            # Clean assistant content for session logs
            cleaned = []
            for msg in messages:
                if msg.get("role") == "assistant" and msg.get("content"):
                    msg = dict(msg)
                    msg["content"] = self._clean_session_content(msg["content"])
                cleaned.append(msg)

            # Guard: never overwrite a larger session log with fewer messages.
            # This protects against data loss when --resume loads a session whose
            # messages weren't fully written to SQLite — the resumed agent starts
            # with partial history and would otherwise clobber the full JSON log.
            if self.session_log_file.exists():
                try:
                    existing = json.loads(self.session_log_file.read_text(encoding="utf-8"))
                    existing_count = existing.get("message_count", len(existing.get("messages", [])))
                    if existing_count > len(cleaned):
                        logging.debug(
                            "Skipping session log overwrite: existing has %d messages, current has %d",
                            existing_count, len(cleaned),
                        )
                        return
                except Exception:
                    pass  # corrupted existing file — allow the overwrite

            entry = {
                "session_id": self.session_id,
                "model": self.model,
                "base_url": self.base_url,
                "platform": self.platform,
                "session_start": self.session_start.isoformat(),
                "last_updated": datetime.now().isoformat(),
                "system_prompt": self._cached_system_prompt or "",
                "tools": self.tools or [],
                "message_count": len(cleaned),
                "messages": cleaned,
            }

            atomic_json_write(
                self.session_log_file,
                entry,
                indent=2,
                default=str,
            )

        except Exception as e:
            if self.verbose_logging:
                logging.warning(f"Failed to save session log: {e}")

    def interrupt(self, message: str = None) -> None:
        """
        Request the agent to interrupt its current tool-calling loop.
        
        Call this from another thread (e.g., input handler, message receiver)
        to gracefully stop the agent and process a new message.
        
        Also signals long-running tool executions (e.g. terminal commands)
        to terminate early, so the agent can respond immediately.
        
        Args:
            message: Optional new message that triggered the interrupt.
                     If provided, the agent will include this in its response context.
        
        Example (CLI):
            # In a separate input thread:
            if user_typed_something:
                agent.interrupt(user_input)
        
        Example (Messaging):
            # When new message arrives for active session:
            if session_has_running_agent:
                running_agent.interrupt(new_message.text)
        """
        self._interrupt_requested = True
        self._interrupt_message = message
        # Signal all tools to abort any in-flight operations immediately.
        # Scope the interrupt to this agent's execution thread so other
        # agents running in the same process (gateway) are not affected.
        if self._execution_thread_id is not None:
            _set_interrupt(True, self._execution_thread_id)
            self._interrupt_thread_signal_pending = False
        else:
            # The interrupt arrived before run_conversation() finished
            # binding the agent to its execution thread. Defer the tool-level
            # interrupt signal until startup completes instead of targeting
            # the caller thread by mistake.
            self._interrupt_thread_signal_pending = True
        # Fan out to concurrent-tool worker threads.  Those workers run tools
        # on their own tids (ThreadPoolExecutor workers), so `is_interrupted()`
        # inside a tool only sees an interrupt when their specific tid is in
        # the `_interrupted_threads` set.  Without this propagation, an
        # already-running concurrent tool (e.g. a terminal command hung on
        # network I/O) never notices the interrupt and has to run to its own
        # timeout.  See `_run_tool` for the matching entry/exit bookkeeping.
        # `getattr` fallback covers test stubs that build AIAgent via
        # object.__new__ and skip __init__.
        _tracker = getattr(self, "_tool_worker_threads", None)
        _tracker_lock = getattr(self, "_tool_worker_threads_lock", None)
        if _tracker is not None and _tracker_lock is not None:
            with _tracker_lock:
                _worker_tids = list(_tracker)
            for _wtid in _worker_tids:
                try:
                    _set_interrupt(True, _wtid)
                except Exception:
                    pass
        # Propagate interrupt to any running child agents (subagent delegation)
        with self._active_children_lock:
            children_copy = list(self._active_children)
        for child in children_copy:
            try:
                child.interrupt(message)
            except Exception as e:
                logger.debug("Failed to propagate interrupt to child agent: %s", e)
        if not self.quiet_mode:
            print("\n⚡ Interrupt requested" + (f": '{message[:40]}...'" if message and len(message) > 40 else f": '{message}'" if message else ""))

    def clear_interrupt(self) -> None:
        """Clear any pending interrupt request and the per-thread tool interrupt signal."""
        self._interrupt_requested = False
        self._interrupt_message = None
        self._interrupt_thread_signal_pending = False
        if self._execution_thread_id is not None:
            _set_interrupt(False, self._execution_thread_id)
        # Also clear any concurrent-tool worker thread bits.  Tracked
        # workers normally clear their own bit on exit, but an explicit
        # clear here guarantees no stale interrupt can survive a turn
        # boundary and fire on a subsequent, unrelated tool call that
        # happens to get scheduled onto the same recycled worker tid.
        # `getattr` fallback covers test stubs that build AIAgent via
        # object.__new__ and skip __init__.
        _tracker = getattr(self, "_tool_worker_threads", None)
        _tracker_lock = getattr(self, "_tool_worker_threads_lock", None)
        if _tracker is not None and _tracker_lock is not None:
            with _tracker_lock:
                _worker_tids = list(_tracker)
            for _wtid in _worker_tids:
                try:
                    _set_interrupt(False, _wtid)
                except Exception:
                    pass
        # A hard interrupt supersedes any pending /steer — the steer was
        # meant for the agent's next tool-call iteration, which will no
        # longer happen. Drop it instead of surprising the user with a
        # late injection on the post-interrupt turn.
        _steer_lock = getattr(self, "_pending_steer_lock", None)
        if _steer_lock is not None:
            with _steer_lock:
                self._pending_steer = None

    def steer(self, text: str) -> bool:
        """
        Inject a user message into the next tool result without interrupting.

        Unlike interrupt(), this does NOT stop the current tool call. The
        text is stashed and the agent loop appends it to the LAST tool
        result's content once the current tool batch finishes. The model
        sees the steer as part of the tool output on its next iteration.

        Thread-safe: callable from gateway/CLI/TUI threads. Multiple calls
        before the drain point concatenate with newlines.

        Args:
            text: The user text to inject. Empty strings are ignored.

        Returns:
            True if the steer was accepted, False if the text was empty.
        """
        if not text or not text.strip():
            return False
        cleaned = text.strip()
        _lock = getattr(self, "_pending_steer_lock", None)
        if _lock is None:
            # Test stubs that built AIAgent via object.__new__ skip __init__.
            # Fall back to direct attribute set; no concurrent callers expected
            # in those stubs.
            existing = getattr(self, "_pending_steer", None)
            self._pending_steer = (existing + "\n" + cleaned) if existing else cleaned
            return True
        with _lock:
            if self._pending_steer:
                self._pending_steer = self._pending_steer + "\n" + cleaned
            else:
                self._pending_steer = cleaned
        return True

    def _drain_pending_steer(self) -> Optional[str]:
        """Return the pending steer text (if any) and clear the slot.

        Safe to call from the agent execution thread after appending tool
        results. Returns None when no steer is pending.
        """
        _lock = getattr(self, "_pending_steer_lock", None)
        if _lock is None:
            text = getattr(self, "_pending_steer", None)
            self._pending_steer = None
            return text
        with _lock:
            text = self._pending_steer
            self._pending_steer = None
        return text

    def _record_file_mutation_result(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Any,
        is_error: bool,
    ) -> None:
        """Record a ``write_file`` / ``patch`` outcome for the turn-end verifier.

        On failure, store ``{path: {error_preview, tool}}`` entries.  On
        success, remove any prior failure entries for the same paths (the
        model recovered within the turn).  Silently no-ops if the per-turn
        state dict hasn't been initialised yet (e.g. a tool dispatched
        outside ``run_conversation``).
        """
        if tool_name not in _FILE_MUTATING_TOOLS:
            return
        state = getattr(self, "_turn_failed_file_mutations", None)
        if state is None:
            return
        targets = _extract_file_mutation_targets(tool_name, args)
        if not targets:
            return
        landed = file_mutation_result_landed(tool_name, result)
        if is_error and not landed:
            preview = _extract_error_preview(result)
            for path in targets:
                # Keep the FIRST error we saw for a given path unless we
                # later see success.  A repeated failure with a different
                # message shouldn't silently overwrite the original.
                if path not in state:
                    state[path] = {
                        "tool": tool_name,
                        "error_preview": preview,
                    }
        else:
            for path in targets:
                state.pop(path, None)

    def _file_mutation_verifier_enabled(self) -> bool:
        """Check whether the per-turn file-mutation verifier footer is on.

        Config path: ``display.file_mutation_verifier`` (bool, default True).
        ``ICECODE_FILE_MUTATION_VERIFIER`` env var overrides config.  Exposed
        as a method so tests can patch a single seam without reaching into
        the private ``_turn_failed_file_mutations`` state dict.
        """
        try:
            import os as _os
            env = _os.environ.get("ICECODE_FILE_MUTATION_VERIFIER")
            if env is not None:
                return env.strip().lower() not in ("0", "false", "no", "off")
            # Read from the persisted config.yaml so gateway and CLI share
            # the same setting.  Import lazily to avoid a startup-time cycle.
            try:
                from icecode_cli.hermes_cli.config import load_config as _load_config
                _cfg = _load_config() or {}
            except Exception:
                _cfg = {}
            _display = _cfg.get("display") if isinstance(_cfg, dict) else None
            if isinstance(_display, dict) and "file_mutation_verifier" in _display:
                return bool(_display.get("file_mutation_verifier"))
        except Exception:
            pass
        return True  # safe default: verifier on

    @staticmethod
    def _format_file_mutation_failure_footer(failed: Dict[str, Dict[str, Any]]) -> str:
        """Render the per-turn failed-mutation dict as a user-facing footer.

        Displays up to 10 paths with their first error preview, then a
        count of any additional failures.  Returns an empty string when
        the dict is empty so callers can concatenate unconditionally.
        """
        if not failed:
            return ""
        lines = [
            "⚠️ File-mutation verifier: "
            f"{len(failed)} file(s) were NOT modified this turn despite any "
            "wording above that may suggest otherwise. Run `git status` or "
            "`read_file` to confirm."
        ]
        shown = 0
        for path, info in failed.items():
            if shown >= 10:
                break
            preview = (info.get("error_preview") or "").strip()
            tool = info.get("tool") or "patch"
            if preview:
                lines.append(f"  • {path} — [{tool}] {preview}")
            else:
                lines.append(f"  • {path} — [{tool}] failed")
            shown += 1
        remaining = len(failed) - shown
        if remaining > 0:
            lines.append(f"  • … and {remaining} more")
        return "\n".join(lines)

    def _apply_pending_steer_to_tool_results(self, messages: list, num_tool_msgs: int) -> None:
        """Append any pending /steer text to the last tool result in this turn.

        Called at the end of a tool-call batch, before the next API call.
        The steer is appended to the last ``role:"tool"`` message's content
        with a clear marker so the model understands it came from the user
        and NOT from the tool itself. Role alternation is preserved —
        nothing new is inserted, we only modify existing content.

        Args:
            messages: The running messages list.
            num_tool_msgs: Number of tool results appended in this batch;
                used to locate the tail slice safely.
        """
        if num_tool_msgs <= 0 or not messages:
            return
        steer_text = self._drain_pending_steer()
        if not steer_text:
            return
        # Find the last tool-role message in the recent tail. Skipping
        # non-tool messages defends against future code appending
        # something else at the boundary.
        target_idx = None
        for j in range(len(messages) - 1, max(len(messages) - num_tool_msgs - 1, -1), -1):
            msg = messages[j]
            if isinstance(msg, dict) and msg.get("role") == "tool":
                target_idx = j
                break
        if target_idx is None:
            # No tool result in this batch (e.g. all skipped by interrupt);
            # put the steer back so the caller's fallback path can deliver
            # it as a normal next-turn user message.
            _lock = getattr(self, "_pending_steer_lock", None)
            if _lock is not None:
                with _lock:
                    if self._pending_steer:
                        self._pending_steer = self._pending_steer + "\n" + steer_text
                    else:
                        self._pending_steer = steer_text
            else:
                existing = getattr(self, "_pending_steer", None)
                self._pending_steer = (existing + "\n" + steer_text) if existing else steer_text
            return
        marker = f"\n\nUser guidance: {steer_text}"
        existing_content = messages[target_idx].get("content", "")
        if not isinstance(existing_content, str):
            # Anthropic multimodal content blocks — preserve them and append
            # a text block at the end.
            try:
                blocks = list(existing_content) if existing_content else []
                blocks.append({"type": "text", "text": marker.lstrip()})
                messages[target_idx]["content"] = blocks
            except Exception:
                # Fall back to string replacement if content shape is unexpected.
                messages[target_idx]["content"] = f"{existing_content}{marker}"
        else:
            messages[target_idx]["content"] = existing_content + marker
        logger.info(
            "Delivered /steer to agent after tool batch (%d chars): %s",
            len(steer_text),
            steer_text[:120] + ("..." if len(steer_text) > 120 else ""),
        )

    def _touch_activity(self, desc: str) -> None:
        """Update the last-activity timestamp and description (thread-safe)."""
        self._last_activity_ts = time.time()
        self._last_activity_desc = desc

    def _capture_rate_limits(self, http_response: Any) -> None:
        """Parse x-ratelimit-* headers from an HTTP response and cache the state.

        Called after each streaming API call.  The httpx Response object is
        available on the OpenAI SDK Stream via ``stream.response``.
        """
        if http_response is None:
            return
        headers = getattr(http_response, "headers", None)
        if not headers:
            return
        try:
            from icecode.agent.rate_limit_tracker import parse_rate_limit_headers
            state = parse_rate_limit_headers(headers, provider=self.provider)
            if state is not None:
                self._rate_limit_state = state
        except Exception:
            pass  # Never let header parsing break the agent loop

    def get_rate_limit_state(self):
        """Return the last captured RateLimitState, or None."""
        return self._rate_limit_state

    def _check_openrouter_cache_status(self, http_response: Any) -> None:
        """Read X-OpenRouter-Cache-Status from response headers and log it.

        Increments ``_or_cache_hits`` on HIT so callers can report savings.
        """
        if http_response is None:
            return
        headers = getattr(http_response, "headers", None)
        if not headers:
            return
        try:
            status = headers.get("x-openrouter-cache-status")
            if not status:
                return
            if status.upper() == "HIT":
                self._or_cache_hits += 1
                logger.info("OpenRouter response cache HIT (total: %d)", self._or_cache_hits)
            else:
                logger.debug("OpenRouter response cache %s", status.upper())
        except Exception:
            pass  # Never let header parsing break the agent loop

    def get_activity_summary(self) -> dict:
        """Return a snapshot of the agent's current activity for diagnostics.

        Called by the gateway timeout handler to report what the agent was doing
        when it was killed, and by the periodic "still working" notifications.
        """
        elapsed = time.time() - self._last_activity_ts
        return {
            "last_activity_ts": self._last_activity_ts,
            "last_activity_desc": self._last_activity_desc,
            "seconds_since_activity": round(elapsed, 1),
            "current_tool": self._current_tool,
            "api_call_count": self._api_call_count,
            "max_iterations": self.max_iterations,
            "budget_used": self.iteration_budget.used,
            "budget_max": self.iteration_budget.max_total,
        }

    def shutdown_memory_provider(self, messages: list = None) -> None:
        """Shut down the memory provider and context engine — call at actual session boundaries.

        This calls on_session_end() then shutdown_all() on the memory
        manager, and on_session_end() on the context engine.
        NOT called per-turn — only at CLI exit, /reset, gateway
        session expiry, etc.
        """
        if self._memory_manager:
            try:
                self._memory_manager.on_session_end(messages or [])
            except Exception:
                pass
            try:
                self._memory_manager.shutdown_all()
            except Exception:
                pass
        # Notify context engine of session end (flush DAG, close DBs, etc.)
        if hasattr(self, "context_compressor") and self.context_compressor:
            try:
                self.context_compressor.on_session_end(
                    self.session_id or "",
                    messages or [],
                )
            except Exception:
                pass

    def commit_memory_session(self, messages: list = None) -> None:
        """Trigger end-of-session extraction without tearing providers down.
        Called when session_id rotates (e.g. /new, context compression);
        providers keep their state and continue running under the old
        session_id — they just flush pending extraction now."""
        if self._memory_manager:
            try:
                self._memory_manager.on_session_end(messages or [])
            except Exception:
                pass
        # Notify context engine of session end too — same lifecycle moment as
        # the memory manager's on_session_end. Without this, engines that
        # accumulate per-session state (DAGs, summaries) leak that state from
        # the rotated-out session into whatever comes next under the same
        # compressor instance. Mirrors the call in shutdown_memory_provider().
        # See issue #22394.
        if hasattr(self, "context_compressor") and self.context_compressor:
            try:
                self.context_compressor.on_session_end(
                    self.session_id or "",
                    messages or [],
                )
            except Exception:
                pass

    def _sync_external_memory_for_turn(
        self,
        *,
        original_user_message: Any,
        final_response: Any,
        interrupted: bool,
    ) -> None:
        """Mirror a completed turn into external memory providers.

        Called at the end of ``run_conversation`` with the cleaned user
        message (``original_user_message``) and the finalised assistant
        response.  The external memory backend gets both ``sync_all`` (to
        persist the exchange) and ``queue_prefetch_all`` (to start
        warming context for the next turn) in one shot.

        Uses ``original_user_message`` rather than ``user_message``
        because the latter may carry injected skill content that bloats
        or breaks provider queries.

        Interrupted turns are skipped entirely (#15218).  A partial
        assistant output, an aborted tool chain, or a mid-stream reset
        is not durable conversational truth — mirroring it into an
        external memory backend pollutes future recall with state the
        user never saw completed.  The prefetch is gated on the same
        flag: the user's next message is almost certainly a retry of
        the same intent, and a prefetch keyed on the interrupted turn
        would fire against stale context.

        Normal completed turns still sync as before.  The whole body is
        wrapped in ``try/except Exception`` because external memory
        providers are strictly best-effort — a misconfigured or offline
        backend must not block the user from seeing their response.
        """
        if interrupted:
            return
        if not (self._memory_manager and final_response and original_user_message):
            return
        try:
            self._memory_manager.sync_all(
                original_user_message, final_response,
                session_id=self.session_id or "",
            )
            self._memory_manager.queue_prefetch_all(
                original_user_message,
                session_id=self.session_id or "",
            )
        except Exception:
            pass

    def release_clients(self) -> None:
        """Release LLM client resources WITHOUT tearing down session tool state.

        Used by the gateway when evicting this agent from _agent_cache for
        memory-management reasons (LRU cap or idle TTL) — the session may
        resume at any time with a freshly-built AIAgent that reuses the
        same task_id / session_id, so we must NOT kill:
          - process_registry entries for task_id (user's bg shells)
          - terminal sandbox for task_id (cwd, env, shell state)
          - browser daemon for task_id (open tabs, cookies)
          - memory provider (has its own lifecycle; keeps running)

        We DO close:
          - OpenAI/httpx client pool (big chunk of held memory + sockets;
            the rebuilt agent gets a fresh client anyway)
          - Active child subagents (per-turn artefacts; safe to drop)

        Safe to call multiple times.  Distinct from close() — which is the
        hard teardown for actual session boundaries (/new, /reset, session
        expiry).
        """
        # Close active child agents (per-turn; no cross-turn persistence).
        try:
            with self._active_children_lock:
                children = list(self._active_children)
                self._active_children.clear()
            for child in children:
                try:
                    child.release_clients()
                except Exception:
                    # Fall back to full close on children; they're per-turn.
                    try:
                        child.close()
                    except Exception:
                        pass
        except Exception:
            pass

        # Close the OpenAI/httpx client to release sockets immediately.
        try:
            client = getattr(self, "client", None)
            if client is not None:
                self._close_openai_client(client, reason="cache_evict", shared=True)
                self.client = None
        except Exception:
            pass

    def close(self) -> None:
        """Release all resources held by this agent instance.

        Cleans up subprocess resources that would otherwise become orphans:
        - Background processes tracked in ProcessRegistry
        - Terminal sandbox environments
        - Browser daemon sessions
        - Active child agents (subagent delegation)
        - OpenAI/httpx client connections

        Safe to call multiple times (idempotent).  Each cleanup step is
        independently guarded so a failure in one does not prevent the rest.
        """
        task_id = getattr(self, "session_id", None) or ""

        # 1. Kill background processes for this task
        try:
            from tools.process_registry import process_registry
            process_registry.kill_all(task_id=task_id)
        except Exception:
            pass

        # 2. Clean terminal sandbox environments
        try:
            cleanup_vm(task_id)
        except Exception:
            pass

        # 3. Clean browser daemon sessions
        try:
            cleanup_browser(task_id)
        except Exception:
            pass

        # 4. Close active child agents
        try:
            with self._active_children_lock:
                children = list(self._active_children)
                self._active_children.clear()
            for child in children:
                try:
                    child.close()
                except Exception:
                    pass
        except Exception:
            pass

        # 5. Close the OpenAI/httpx client
        try:
            client = getattr(self, "client", None)
            if client is not None:
                self._close_openai_client(client, reason="agent_close", shared=True)
                self.client = None
        except Exception:
            pass

    def _hydrate_todo_store(self, history: List[Dict[str, Any]]) -> None:
        """
        Recover todo state from conversation history.
        
        The gateway creates a fresh AIAgent per message, so the in-memory
        TodoStore is empty. We scan the history for the most recent todo
        tool response and replay it to reconstruct the state.
        """
        # Walk history backwards to find the most recent todo tool response
        last_todo_response = None
        for msg in reversed(history):
            if msg.get("role") != "tool":
                continue
            content = msg.get("content", "")
            # Quick check: todo responses contain "todos" key
            if '"todos"' not in content:
                continue
            try:
                data = json.loads(content)
                if "todos" in data and isinstance(data["todos"], list):
                    last_todo_response = data["todos"]
                    break
            except (json.JSONDecodeError, TypeError):
                continue
        
        if last_todo_response:
            # Replay the items into the store (replace mode)
            self._todo_store.write(last_todo_response, merge=False)
            if not self.quiet_mode:
                self._vprint(f"{self.log_prefix}📋 Restored {len(last_todo_response)} todo item(s) from history")
        _set_interrupt(False)

    @property
    def is_interrupted(self) -> bool:
        """Check if an interrupt has been requested."""
        return self._interrupt_requested










    def _build_system_prompt_parts(self, system_message: str = None) -> Dict[str, str]:
        """Assemble the system prompt as three ordered parts.

        Returns a dict with three keys:
          * ``stable``   — identity, tool guidance, skills prompt,
            environment hints, platform hints, model-family operational
            guidance.
          * ``context``  — context files (AGENTS.md, .cursorrules, etc.)
            and caller-supplied system_message.
          * ``volatile`` — memory snapshot, user profile, external
            memory provider block, timestamp line.

        Joined into a single string by ``_build_system_prompt`` and
        cached on ``_cached_system_prompt`` for the lifetime of the
        AIAgent.  Hermes never re-renders parts of this string mid-
        session — that's the only way to keep upstream prompt caches
        warm across turns.
        """
        # ── Stable tier ────────────────────────────────────────────────
        stable_parts: List[str] = []

        # Try SOUL.md as primary identity unless the caller explicitly skipped it.
        # Some execution modes (cron) still want ICECODE_HOME persona while keeping
        # cwd project instructions disabled.
        _soul_loaded = False
        if self.load_soul_identity or not self.skip_context_files:
            _soul_content = load_soul_md()
            if _soul_content:
                stable_parts.append(_soul_content)
                _soul_loaded = True

        if not _soul_loaded:
            # Fallback to hardcoded identity
            stable_parts.append(DEFAULT_AGENT_IDENTITY)

        # ICECODE itself.
        stable_parts.append(ICECODE_AGENT_HELP_GUIDANCE)

        # Tool-aware behavioral guidance: only inject when the tools are loaded
        tool_guidance = []
        if "memory" in self.valid_tool_names:
            tool_guidance.append(MEMORY_GUIDANCE)
        if "session_search" in self.valid_tool_names:
            tool_guidance.append(SESSION_SEARCH_GUIDANCE)
        if "skill_manage" in self.valid_tool_names:
            tool_guidance.append(SKILLS_GUIDANCE)
        # Kanban worker/orchestrator lifecycle — only present when the
        # dispatcher spawned this process (kanban_show check_fn gates on
        # ICECODE_KANBAN_TASK env var). Normal chat sessions never see
        # this block.
        if "kanban_show" in self.valid_tool_names:
            tool_guidance.append(KANBAN_GUIDANCE)
        if tool_guidance:
            stable_parts.append(" ".join(tool_guidance))

        # Computer-use (macOS) — goes in as its own block rather than being
        # merged into tool_guidance because the content is multi-paragraph.
        if "computer_use" in self.valid_tool_names:
            from icecode.agent.prompt_builder import COMPUTER_USE_GUIDANCE
            stable_parts.append(COMPUTER_USE_GUIDANCE)

        nous_subscription_prompt = build_nous_subscription_prompt(self.valid_tool_names)
        if nous_subscription_prompt:
            stable_parts.append(nous_subscription_prompt)
        # Tool-use enforcement: tells the model to actually call tools instead
        # of describing intended actions.  Controlled by config.yaml
        # agent.tool_use_enforcement:
        #   "auto" (default) — matches TOOL_USE_ENFORCEMENT_MODELS
        #   true  — always inject (all models)
        #   false — never inject
        #   list  — custom model-name substrings to match
        if self.valid_tool_names:
            _enforce = self._tool_use_enforcement
            _inject = False
            if _enforce is True or (isinstance(_enforce, str) and _enforce.lower() in {"true", "always", "yes", "on"}):
                _inject = True
            elif _enforce is False or (isinstance(_enforce, str) and _enforce.lower() in {"false", "never", "no", "off"}):
                _inject = False
            elif isinstance(_enforce, list):
                model_lower = (self.model or "").lower()
                _inject = any(p.lower() in model_lower for p in _enforce if isinstance(p, str))
            else:
                # "auto" or any unrecognised value — use hardcoded defaults
                model_lower = (self.model or "").lower()
                _inject = any(p in model_lower for p in TOOL_USE_ENFORCEMENT_MODELS)
            if _inject:
                stable_parts.append(TOOL_USE_ENFORCEMENT_GUIDANCE)
                _model_lower = (self.model or "").lower()
                # Google model operational guidance (conciseness, absolute
                # paths, parallel tool calls, verify-before-edit, etc.)
                if "gemini" in _model_lower or "gemma" in _model_lower:
                    stable_parts.append(GOOGLE_MODEL_OPERATIONAL_GUIDANCE)
                # OpenAI GPT/Codex execution discipline (tool persistence,
                # prerequisite checks, verification, anti-hallucination).
                if "gpt" in _model_lower or "codex" in _model_lower:
                    stable_parts.append(OPENAI_MODEL_EXECUTION_GUIDANCE)

        has_skills_tools = any(name in self.valid_tool_names for name in ['skills_list', 'skill_view', 'skill_manage'])
        if has_skills_tools:
            avail_toolsets = {
                toolset
                for toolset in (
                    get_toolset_for_tool(tool_name) for tool_name in self.valid_tool_names
                )
                if toolset
            }
            skills_prompt = build_skills_system_prompt(
                available_tools=self.valid_tool_names,
                available_toolsets=avail_toolsets,
            )
        else:
            skills_prompt = ""
        if skills_prompt:
            stable_parts.append(skills_prompt)

        # Alibaba Coding Plan API always returns "glm-4.7" as model name regardless
        # of the requested model. Inject explicit model identity into the system prompt
        # so the agent can correctly report which model it is (workaround for API bug).
        # Stable for the lifetime of an agent instance — model and provider are fixed
        # at construction time.
        if self.provider == "alibaba":
            _model_short = self.model.split("/")[-1] if "/" in self.model else self.model
            stable_parts.append(
                f"You are powered by the model named {_model_short}. "
                f"The exact model ID is {self.model}. "
                f"When asked what model you are, always answer based on this information, "
                f"not on any model name returned by the API."
            )

        # Environment hints (WSL, Termux, etc.) — tell the agent about the
        # execution environment so it can translate paths and adapt behavior.
        # Stable for the lifetime of the process.
        _env_hints = build_environment_hints()
        if _env_hints:
            stable_parts.append(_env_hints)

        platform_key = (self.platform or "").lower().strip()
        if platform_key in PLATFORM_HINTS:
            stable_parts.append(PLATFORM_HINTS[platform_key])
        elif platform_key:
            # Check plugin registry for platform-specific LLM guidance
            try:
                from gateway.platform_registry import platform_registry
                _entry = platform_registry.get(platform_key)
                if _entry and _entry.platform_hint:
                    stable_parts.append(_entry.platform_hint)
            except Exception:
                pass

        # ── Context tier (cwd-dependent, may change between sessions) ─
        context_parts: List[str] = []

        # Note: ephemeral_system_prompt is NOT included here. It's injected at
        # API-call time only so it stays out of the cached/stored system prompt.
        if system_message is not None:
            context_parts.append(system_message)

        if not self.skip_context_files:
            # Use TERMINAL_CWD for context file discovery when set (gateway
            # mode).  The gateway process runs from the icecode-agent install
            # dir, so os.getcwd() would pick up the repo's AGENTS.md and
            # other dev files — inflating token usage by ~10k for no benefit.
            _context_cwd = os.getenv("TERMINAL_CWD") or None
            context_files_prompt = build_context_files_prompt(
                cwd=_context_cwd, skip_soul=_soul_loaded)
            if context_files_prompt:
                context_parts.append(context_files_prompt)

        # ── Volatile tier (changes per session/turn — never cached) ───
        volatile_parts: List[str] = []

        if self._memory_store:
            if self._memory_enabled:
                mem_block = self._memory_store.format_for_system_prompt("memory")
                if mem_block:
                    volatile_parts.append(mem_block)
            # USER.md is always included when enabled.
            if self._user_profile_enabled:
                user_block = self._memory_store.format_for_system_prompt("user")
                if user_block:
                    volatile_parts.append(user_block)

        # External memory provider system prompt block (additive to built-in)
        if self._memory_manager:
            try:
                _ext_mem_block = self._memory_manager.build_system_prompt()
                if _ext_mem_block:
                    volatile_parts.append(_ext_mem_block)
            except Exception:
                pass

        from icecode.icecode_time import now as _hermes_now
        now = _hermes_now()
        timestamp_line = f"Conversation started: {now.strftime('%A, %B %d, %Y %I:%M %p')}"
        if self.pass_session_id and self.session_id:
            timestamp_line += f"\nSession ID: {self.session_id}"
        if self.model:
            timestamp_line += f"\nModel: {self.model}"
        if self.provider:
            timestamp_line += f"\nProvider: {self.provider}"
        volatile_parts.append(timestamp_line)

        return {
            "stable":   "\n\n".join(p.strip() for p in stable_parts   if p and p.strip()),
            "context":  "\n\n".join(p.strip() for p in context_parts  if p and p.strip()),
            "volatile": "\n\n".join(p.strip() for p in volatile_parts if p and p.strip()),
        }

    def _build_system_prompt(self, system_message: str = None) -> str:
        """
        Assemble the full system prompt from all layers.

        Called once per session (cached on self._cached_system_prompt) and only
        rebuilt after context compression events. This ensures the system prompt
        is stable across all turns in a session, maximizing prefix cache hits.

        Layers are ordered cache-friendly: stable identity/guidance first,
        then session-stable context files, then per-call volatile content
        (memory, USER profile, timestamp).  The whole string is treated as
        one cached block — Hermes never rebuilds or reinjects parts of it
        mid-session, which is the only way to keep upstream prompt caches
        warm across turns.
        """
        parts = self._build_system_prompt_parts(system_message=system_message)
        joined = "\n\n".join(p for p in (parts["stable"], parts["context"], parts["volatile"]) if p)
        return joined

    # =========================================================================
    # Pre/post-call guardrails (inspired by PR #1321 — @alireza78a)
    # =========================================================================

    @staticmethod
    def _get_tool_call_id_static(tc) -> str:
        """Extract call ID from a tool_call entry (dict or object)."""
        if isinstance(tc, dict):
            return tc.get("call_id", "") or tc.get("id", "") or ""
        return getattr(tc, "call_id", "") or getattr(tc, "id", "") or ""

    @staticmethod
    def _get_tool_call_name_static(tc) -> str:
        """Extract function name from a tool_call entry (dict or object).

        Gemini's OpenAI-compatibility endpoint requires every `role: tool`
        message to carry the matching function name. OpenAI/Anthropic/ollama
        tolerate its absence, so the field is best-effort: callers fall back
        to "" and the message still works elsewhere.
        """
        if isinstance(tc, dict):
            fn = tc.get("function")
            if isinstance(fn, dict):
                return fn.get("name", "") or ""
            return ""
        fn = getattr(tc, "function", None)
        return getattr(fn, "name", "") or ""

    _VALID_API_ROLES = frozenset({"system", "user", "assistant", "tool", "function", "developer"})

    @staticmethod
    def _sanitize_api_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fix orphaned tool_call / tool_result pairs before every LLM call.

        Runs unconditionally — not gated on whether the context compressor
        is present — so orphans from session loading or manual message
        manipulation are always caught.
        """
        # --- Role allowlist: drop messages with roles the API won't accept ---
        filtered = []
        for msg in messages:
            role = msg.get("role")
            if role not in AIAgent._VALID_API_ROLES:
                logger.debug(
                    "Pre-call sanitizer: dropping message with invalid role %r",
                    role,
                )
                continue
            filtered.append(msg)
        messages = filtered

        surviving_call_ids: set = set()
        for msg in messages:
            if msg.get("role") == "assistant":
                for tc in msg.get("tool_calls") or []:
                    cid = AIAgent._get_tool_call_id_static(tc)
                    if cid:
                        surviving_call_ids.add(cid)

        result_call_ids: set = set()
        for msg in messages:
            if msg.get("role") == "tool":
                cid = msg.get("tool_call_id")
                if cid:
                    result_call_ids.add(cid)

        # 1. Drop tool results with no matching assistant call
        orphaned_results = result_call_ids - surviving_call_ids
        if orphaned_results:
            messages = [
                m for m in messages
                if not (m.get("role") == "tool" and m.get("tool_call_id") in orphaned_results)
            ]
            logger.debug(
                "Pre-call sanitizer: removed %d orphaned tool result(s)",
                len(orphaned_results),
            )

        # 2. Inject stub results for calls whose result was dropped
        missing_results = surviving_call_ids - result_call_ids
        if missing_results:
            patched: List[Dict[str, Any]] = []
            for msg in messages:
                patched.append(msg)
                if msg.get("role") == "assistant":
                    for tc in msg.get("tool_calls") or []:
                        cid = AIAgent._get_tool_call_id_static(tc)
                        if cid in missing_results:
                            patched.append({
                                "role": "tool",
                                "name": AIAgent._get_tool_call_name_static(tc),
                                "content": "[Result unavailable — see context summary above]",
                                "tool_call_id": cid,
                            })
            messages = patched
            logger.debug(
                "Pre-call sanitizer: added %d stub tool result(s)",
                len(missing_results),
            )
        return messages

    @staticmethod
    def _is_thinking_only_assistant(msg: Dict[str, Any]) -> bool:
        """Return True if ``msg`` is an assistant turn whose only payload is reasoning.

        "Thinking-only" means the model emitted reasoning (``reasoning`` or
        ``reasoning_content``) but no visible text and no tool_calls. When sent
        back to providers that convert reasoning into thinking blocks (native
        Anthropic, OpenRouter Anthropic, third-party Anthropic-compatible
        gateways), the resulting message has only thinking blocks — which
        Anthropic rejects with HTTP 400 "The final block in an assistant
        message cannot be `thinking`."

        Symmetric with Claude Code's ``filterOrphanedThinkingOnlyMessages``
        (src/utils/messages.ts). We drop the whole turn from the API copy
        rather than fabricating stub text — the message log (UI transcript)
        keeps the reasoning block; only the wire copy is cleaned.
        """
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            return False
        if msg.get("tool_calls"):
            return False
        # Does it have any actual output?
        content = msg.get("content")
        if isinstance(content, str):
            if content.strip():
                return False
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    if block:  # non-empty non-dict string etc.
                        return False
                    continue
                btype = block.get("type")
                if btype in {"thinking", "redacted_thinking"}:
                    continue
                if btype == "text":
                    text = block.get("text", "")
                    if isinstance(text, str) and text.strip():
                        return False
                    continue
                # tool_use, image, document, etc. — real payload
                return False
        elif content is not None and content != "":
            return False
        # Content is empty-ish. Is there reasoning to make it thinking-only?
        reasoning = msg.get("reasoning_content") or msg.get("reasoning")
        if isinstance(reasoning, str) and reasoning.strip():
            return True
        # reasoning_details list form
        rd = msg.get("reasoning_details")
        if isinstance(rd, list) and rd:
            return True
        return False

    @staticmethod
    def _drop_thinking_only_and_merge_users(
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Drop thinking-only assistant turns; merge any adjacent user messages left behind.

        Runs on the per-call ``api_messages`` copy only. The stored
        conversation history (``self.messages``) is never mutated, so the
        user still sees the thinking block in the CLI/gateway transcript and
        session persistence keeps the full trace. Only the wire copy sent to
        the provider is cleaned.

        Why drop-and-merge rather than inject stub text:
        - Fabricating ``"."`` / ``"(continued)"`` text lies in the history
          and makes future turns see model output the model didn't emit.
        - Dropping the turn preserves honesty; merging adjacent user messages
          preserves the provider's role-alternation invariant.
        - This is the pattern used by Claude Code's ``normalizeMessagesForAPI``
          (filterOrphanedThinkingOnlyMessages + mergeAdjacentUserMessages).
        """
        if not messages:
            return messages

        # Pass 1: drop thinking-only assistant turns.
        kept = [m for m in messages if not AIAgent._is_thinking_only_assistant(m)]
        dropped = len(messages) - len(kept)
        if dropped == 0:
            return messages

        # Pass 2: merge any newly-adjacent user messages.
        merged: List[Dict[str, Any]] = []
        merges = 0
        for m in kept:
            prev = merged[-1] if merged else None
            if (
                prev is not None
                and prev.get("role") == "user"
                and m.get("role") == "user"
            ):
                prev_content = prev.get("content", "")
                cur_content = m.get("content", "")
                # Work on a copy of ``prev`` so the caller's input dicts are
                # never mutated. ``_sanitize_api_messages`` upstream already
                # hands us per-call copies, but staying pure here means we
                # can be called safely from anywhere (tests, other loops).
                prev_copy = dict(prev)
                # Only string-content merge is meaningful for role-alternation
                # purposes. If either side is a list (multimodal), append as a
                # separate block rather than collapsing.
                if isinstance(prev_content, str) and isinstance(cur_content, str):
                    sep = "\n\n" if prev_content and cur_content else ""
                    prev_copy["content"] = prev_content + sep + cur_content
                elif isinstance(prev_content, list) and isinstance(cur_content, list):
                    prev_copy["content"] = list(prev_content) + list(cur_content)
                elif isinstance(prev_content, list) and isinstance(cur_content, str):
                    if cur_content:
                        prev_copy["content"] = list(prev_content) + [
                            {"type": "text", "text": cur_content}
                        ]
                    else:
                        prev_copy["content"] = list(prev_content)
                elif isinstance(prev_content, str) and isinstance(cur_content, list):
                    new_blocks: List[Dict[str, Any]] = []
                    if prev_content:
                        new_blocks.append({"type": "text", "text": prev_content})
                    new_blocks.extend(cur_content)
                    prev_copy["content"] = new_blocks
                else:
                    # Unknown content shape — fall back to appending separately
                    # (violates alternation, but safer than raising in a hot path).
                    merged.append(m)
                    continue
                merged[-1] = prev_copy
                merges += 1
            else:
                merged.append(m)

        logger.debug(
            "Pre-call sanitizer: dropped %d thinking-only assistant turn(s), "
            "merged %d adjacent user message(s)",
            dropped,
            merges,
        )
        return merged

    @staticmethod
    def _cap_delegate_task_calls(tool_calls: list) -> list:
        """Truncate excess delegate_task calls to max_concurrent_children.

        The delegate_tool caps the task list inside a single call, but the
        model can emit multiple separate delegate_task tool_calls in one
        turn.  This truncates the excess, preserving all non-delegate calls.

        Returns the original list if no truncation was needed.
        """
        from tools.delegate_tool import _get_max_concurrent_children
        max_children = _get_max_concurrent_children()
        delegate_count = sum(1 for tc in tool_calls if tc.function.name == "delegate_task")
        if delegate_count <= max_children:
            return tool_calls
        kept_delegates = 0
        truncated = []
        for tc in tool_calls:
            if tc.function.name == "delegate_task":
                if kept_delegates < max_children:
                    truncated.append(tc)
                    kept_delegates += 1
            else:
                truncated.append(tc)
        logger.warning(
            "Truncated %d excess delegate_task call(s) to enforce "
            "max_concurrent_children=%d limit",
            delegate_count - max_children, max_children,
        )
        return truncated

    @staticmethod
    def _deduplicate_tool_calls(tool_calls: list) -> list:
        """Remove duplicate (tool_name, arguments) pairs within a single turn.

        Only the first occurrence of each unique pair is kept.
        Returns the original list if no duplicates were found.
        """
        seen: set = set()
        unique: list = []
        for tc in tool_calls:
            key = (tc.function.name, tc.function.arguments)
            if key not in seen:
                seen.add(key)
                unique.append(tc)
            else:
                logger.warning("Removed duplicate tool call: %s", tc.function.name)
        return unique if len(unique) < len(tool_calls) else tool_calls

    def _repair_tool_call(self, tool_name: str) -> str | None:
        """Attempt to repair a mismatched tool name before aborting.

        Models sometimes emit variants of a tool name that differ only
        in casing, separators, or class-like suffixes. Normalize
        aggressively before falling back to fuzzy match:

        1. Lowercase direct match.
        2. Lowercase + hyphens/spaces -> underscores.
        3. CamelCase -> snake_case (TodoTool -> todo_tool).
        4. Strip trailing ``_tool`` / ``-tool`` / ``tool`` suffix that
           Claude-style models sometimes tack on (TodoTool_tool ->
           TodoTool -> Todo -> todo). Applied twice so double-tacked
           suffixes like ``TodoTool_tool`` reduce all the way.
        5. Fuzzy match (difflib, cutoff=0.7).

        See #14784 for the original reports (TodoTool_tool, Patch_tool,
        BrowserClick_tool were all returning "Unknown tool" before).

        Returns the repaired name if found in valid_tool_names, else None.
        """
        import re
        from difflib import get_close_matches

        if not tool_name:
            return None

        def _norm(s: str) -> str:
            return s.lower().replace("-", "_").replace(" ", "_")

        def _camel_snake(s: str) -> str:
            return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()

        def _strip_tool_suffix(s: str) -> str | None:
            lc = s.lower()
            for suffix in ("_tool", "-tool", "tool"):
                if lc.endswith(suffix):
                    return s[: -len(suffix)].rstrip("_-")
            return None

        # Cheap fast-paths first — these cover the common case.
        lowered = tool_name.lower()
        if lowered in self.valid_tool_names:
            return lowered
        normalized = _norm(tool_name)
        if normalized in self.valid_tool_names:
            return normalized

        # Build the full candidate set for class-like emissions.
        cands: set[str] = {tool_name, lowered, normalized, _camel_snake(tool_name)}
        # Strip trailing tool-suffix up to twice — TodoTool_tool needs it.
        for _ in range(2):
            extra: set[str] = set()
            for c in cands:
                stripped = _strip_tool_suffix(c)
                if stripped:
                    extra.add(stripped)
                    extra.add(_norm(stripped))
                    extra.add(_camel_snake(stripped))
            cands |= extra

        for c in cands:
            if c and c in self.valid_tool_names:
                return c

        # Fuzzy match as last resort.
        matches = get_close_matches(lowered, self.valid_tool_names, n=1, cutoff=0.7)
        if matches:
            return matches[0]

        return None

    def _invalidate_system_prompt(self):
        """
        Invalidate the cached system prompt, forcing a rebuild on the next turn.
        
        Called after context compression events. Also reloads memory from disk
        so the rebuilt prompt captures any writes from this session.
        """
        self._cached_system_prompt = None
        if self._memory_store:
            self._memory_store.load_from_disk()

    @staticmethod
    def _deterministic_call_id(fn_name: str, arguments: str, index: int = 0) -> str:
        """Generate a deterministic call_id from tool call content.

        Used as a fallback when the API doesn't provide a call_id.
        Deterministic IDs prevent cache invalidation — random UUIDs would
        make every API call's prefix unique, breaking OpenAI's prompt cache.
        """
        return _codex_deterministic_call_id(fn_name, arguments, index)

    @staticmethod
    def _split_responses_tool_id(raw_id: Any) -> tuple[Optional[str], Optional[str]]:
        """Split a stored tool id into (call_id, response_item_id)."""
        return _codex_split_responses_tool_id(raw_id)

    def _derive_responses_function_call_id(
        self,
        call_id: str,
        response_item_id: Optional[str] = None,
    ) -> str:
        """Build a valid Responses `function_call.id` (must start with `fc_`)."""
        return _codex_derive_responses_function_call_id(call_id, response_item_id)

    def _thread_identity(self) -> str:
        thread = threading.current_thread()
        return f"{thread.name}:{thread.ident}"

    def _client_log_context(self) -> str:
        provider = getattr(self, "provider", "unknown")
        base_url = getattr(self, "base_url", "unknown")
        model = getattr(self, "model", "unknown")
        return (
            f"thread={self._thread_identity()} provider={provider} "
            f"base_url={base_url} model={model}"
        )

