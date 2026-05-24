#!/usr/bin/env python3
"""
AI Agent Runner with Tool Calling

This module provides a clean, standalone agent that can execute AI models
with tool calling capabilities. It handles the conversation loop, tool execution,
and response management.

Features:
- Automatic tool calling loop until completion
- Configurable model parameters
- Error handling and recovery
- Message history management
- Support for multiple model providers

Usage:
    from run_agent import AIAgent
    
    agent = AIAgent(base_url="http://localhost:30000/v1", model="claude-opus-4-20250514")
    response = agent.run_conversation("Tell me about the latest Python updates")
"""

# IMPORTANT: hermes_bootstrap must be the very first import — UTF-8 stdio
# on Windows.  No-op on POSIX.  See hermes_bootstrap.py for full rationale.
try:
    import hermes_bootstrap  # noqa: F401
except ModuleNotFoundError:
    # Graceful fallback when hermes_bootstrap isn't registered in the venv
    # yet — happens during partial ``hermes update`` where git-reset landed
    # new code but ``uv pip install -e .`` didn't finish.  Missing bootstrap
    # means UTF-8 stdio setup is skipped on Windows; POSIX is unaffected.
    pass

import asyncio
import base64
import concurrent.futures
import contextvars
import copy
import hashlib
import json
import logging
logger = logging.getLogger(__name__)
import os
import random
import re
import ssl
import sys
import tempfile
import time
import threading
from types import SimpleNamespace
import urllib.request
import uuid
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs, urlunparse
# NOTE: `from openai import OpenAI` is deliberately NOT at module top — the
# SDK pulls ~240 ms of imports. We expose `OpenAI` as a thin proxy object
# that imports the SDK on first call/isinstance check. This preserves:
#   (a) the single in-module `OpenAI(**client_kwargs)` call site at
#       _create_openai_client, and
#   (b) `patch("run_agent.OpenAI", ...)` test patterns used by ~28 test files.
#
# NOTE: `fire` is ONLY used in the `__main__` block below (for running
# run_agent.py directly as a CLI) — it is NOT needed for library usage.
# It is imported there, not here, so that importing run_agent from a
# daemon thread (e.g. curator's forked review agent) never fails with
# ModuleNotFoundError on broken/partial installs where `fire` isn't present.
from datetime import datetime
from pathlib import Path

from icecode.icecode_constants import get_hermes_home
from icecode.agent.engine_sanitize import (  # noqa: F401
    _SURROGATE_RE,
    _sanitize_surrogates,
    _sanitize_structure_surrogates,
    _sanitize_messages_surrogates,
    _escape_invalid_chars_in_json_strings,
    _repair_tool_call_arguments,
    _strip_non_ascii,
    _sanitize_messages_non_ascii,
    _sanitize_tools_non_ascii,
    _strip_images_from_messages,
    _sanitize_structure_non_ascii,
)
from icecode.agent.engine_tool_guard import (  # noqa: F401
    _NEVER_PARALLEL_TOOLS,
    _PARALLEL_SAFE_TOOLS,
    _PATH_SCOPED_TOOLS,
    _DESTRUCTIVE_PATTERNS,
    _REDIRECT_OVERWRITE,
    _is_destructive_command,
    _should_parallelize_tool_batch,
    _extract_parallel_scope_path,
    _paths_overlap,
)
from icecode.agent.engine_multimodal import (  # noqa: F401
    _is_multimodal_tool_result,
    _multimodal_text_summary,
    _append_subdir_hint_to_multimodal,
    _extract_error_preview,
    _trajectory_normalize_msg,
)
from icecode.agent.engine_conversation_mixin import _ConversationMixin, IterationBudget  # noqa: F401
from icecode.agent.engine_session_mixin import _SessionMixin  # noqa: F401
from icecode.agent.engine_api_mixin import _APIMixin  # noqa: F401


_OPENAI_CLS_CACHE: Optional[type] = None


def _load_openai_cls() -> type:
    """Import and cache ``openai.OpenAI``."""
    global _OPENAI_CLS_CACHE
    if _OPENAI_CLS_CACHE is None:
        from openai import OpenAI as _cls
        _OPENAI_CLS_CACHE = _cls
    return _OPENAI_CLS_CACHE


class _OpenAIProxy:
    """Module-level proxy that looks like ``openai.OpenAI`` but imports lazily."""

    __slots__ = ()

    def __call__(self, *args, **kwargs):
        return _load_openai_cls()(*args, **kwargs)

    def __instancecheck__(self, obj):
        return isinstance(obj, _load_openai_cls())

    def __repr__(self):
        return "<lazy openai.OpenAI proxy>"


OpenAI = _OpenAIProxy()

# Load .env from ~/.icecode/.env first, then project root as dev fallback.
# User-managed env files should override stale shell exports on restart.
from icecode_cli.hermes_cli.env_loader import load_hermes_dotenv
from icecode_cli.hermes_cli.timeouts import (
    get_provider_request_timeout,
    get_provider_stale_timeout,
)

_hermes_home = get_hermes_home()
_project_env = Path(__file__).parent / '.env'
_loaded_env_paths = load_hermes_dotenv(hermes_home=_hermes_home, project_env=_project_env)
if _loaded_env_paths:
    for _env_path in _loaded_env_paths:
        logger.info("Loaded environment variables from %s", _env_path)
else:
    logger.info("No .env file found. Using system environment variables.")


# Hermes-runtime imports — these use the old `agent.*` / `tools.*` / `model_tools`
# path convention from the Hermes monorepo. They work when packages/tools is on
# sys.path AND packages/core/icecode is mapped as `agent`. In the ICECODE runtime
# only packages/tools is on the path, so several are unavailable. We wrap the whole
# block so engine.py is always importable; stubs let the class be defined without
# the full Hermes runtime present. Use icecode.agent.core for production ICECODE use.
try:
    from model_tools import (
        get_tool_definitions,
        get_toolset_for_tool,
        handle_function_call,
        check_toolset_requirements,
    )
    from tools.terminal_tool import cleanup_vm, get_active_env, is_persistent_env
    from tools.terminal_tool import (
        set_approval_callback as _set_approval_callback,
        set_sudo_password_callback as _set_sudo_password_callback,
        _get_approval_callback,
        _get_sudo_password_callback,
    )
    from tools.tool_result_storage import maybe_persist_tool_result, enforce_turn_budget
    from tools.interrupt import set_interrupt as _set_interrupt
    from tools.browser_tool import cleanup_browser
    from icecode.agent.memory_manager import StreamingContextScrubber, build_memory_context_block, sanitize_context
    from icecode.agent.think_scrubber import StreamingThinkScrubber
    from icecode.agent.retry_utils import jittered_backoff
    from icecode.agent.error_classifier import classify_api_error, FailoverReason
    from icecode.agent.prompt_builder import (
        DEFAULT_AGENT_IDENTITY, PLATFORM_HINTS,
        MEMORY_GUIDANCE, SESSION_SEARCH_GUIDANCE, SKILLS_GUIDANCE,
        ICECODE_AGENT_HELP_GUIDANCE, KANBAN_GUIDANCE,
        build_nous_subscription_prompt,
        build_skills_system_prompt, build_context_files_prompt,
        build_environment_hints, load_soul_md,
        TOOL_USE_ENFORCEMENT_GUIDANCE, TOOL_USE_ENFORCEMENT_MODELS,
        GOOGLE_MODEL_OPERATIONAL_GUIDANCE, OPENAI_MODEL_EXECUTION_GUIDANCE,
    )
    from icecode.agent.model_metadata import (
        fetch_model_metadata,
        estimate_tokens_rough, estimate_messages_tokens_rough, estimate_request_tokens_rough,
        get_next_probe_tier, parse_context_limit_from_error,
        parse_available_output_tokens_from_error,
        save_context_length, is_local_endpoint,
        query_ollama_num_ctx,
    )
    from icecode.agent.context_compressor import ContextCompressor
    from icecode.agent.subdirectory_hints import SubdirectoryHintTracker
    from icecode.agent.prompt_caching import apply_anthropic_cache_control
    from icecode.agent.usage_pricing import estimate_usage_cost, normalize_usage
    from icecode.agent.codex_responses_adapter import (
        _derive_responses_function_call_id as _codex_derive_responses_function_call_id,
        _deterministic_call_id as _codex_deterministic_call_id,
        _split_responses_tool_id as _codex_split_responses_tool_id,
        _summarize_user_message_for_log,
    )
    from icecode.agent.display import (
        KawaiiSpinner, build_tool_preview as _build_tool_preview,
        get_cute_tool_message as _get_cute_tool_message_impl,
        _detect_tool_failure,
        get_tool_emoji as _get_tool_emoji,
    )
    from icecode.agent.tool_guardrails import (
        ToolCallGuardrailConfig,
        ToolCallGuardrailController,
        ToolGuardrailDecision,
        append_toolguard_guidance,
        toolguard_synthetic_result,
    )
    from icecode.agent.tool_result_classification import (
        FILE_MUTATING_TOOL_NAMES as _FILE_MUTATING_TOOLS,
        file_mutation_result_landed,
    )
    from icecode.agent.trajectory import (
        convert_scratchpad_to_think, has_incomplete_scratchpad,
        save_trajectory as _save_trajectory_to_file,
    )
    from utils import atomic_json_write, base_url_host_matches, base_url_hostname, env_var_enabled, normalize_proxy_url
    from icecode_cli.hermes_cli.config import cfg_get
except (ImportError, ModuleNotFoundError):
    # Stubs for all Hermes-runtime symbols — enables import outside full runtime
    def get_tool_definitions(*a, **kw): return []
    def get_toolset_for_tool(*a, **kw): return None
    def handle_function_call(*a, **kw): return ""
    def check_toolset_requirements(*a, **kw): return None
    def cleanup_vm(): pass
    def get_active_env(): return None
    def is_persistent_env(): return False
    def _set_approval_callback(*a): pass
    def _set_sudo_password_callback(*a): pass
    def _get_approval_callback(): return None
    def _get_sudo_password_callback(): return None
    def maybe_persist_tool_result(*a, **kw): return None
    def enforce_turn_budget(*a, **kw): return None
    def _set_interrupt(*a): pass
    def cleanup_browser(): pass
    class StreamingContextScrubber:
        def __init__(self, *a, **kw): pass
        def feed(self, *a, **kw): return ""
    def build_memory_context_block(*a, **kw): return ""
    def sanitize_context(ctx, *a, **kw): return ctx
    class StreamingThinkScrubber:
        def __init__(self, *a, **kw): pass
        def feed(self, *a, **kw): return ""
    def jittered_backoff(*a, **kw): return 1.0
    def classify_api_error(*a, **kw): return None
    class FailoverReason:
        UNKNOWN = "unknown"
    DEFAULT_AGENT_IDENTITY = ""
    PLATFORM_HINTS = {}
    MEMORY_GUIDANCE = SESSION_SEARCH_GUIDANCE = SKILLS_GUIDANCE = ""
    ICECODE_AGENT_HELP_GUIDANCE = KANBAN_GUIDANCE = ""
    TOOL_USE_ENFORCEMENT_GUIDANCE = GOOGLE_MODEL_OPERATIONAL_GUIDANCE = ""
    OPENAI_MODEL_EXECUTION_GUIDANCE = ""
    TOOL_USE_ENFORCEMENT_MODELS = []
    def build_nous_subscription_prompt(*a, **kw): return ""
    def build_skills_system_prompt(*a, **kw): return ""
    def build_context_files_prompt(*a, **kw): return ""
    def build_environment_hints(*a, **kw): return ""
    def load_soul_md(*a, **kw): return ""
    def fetch_model_metadata(*a, **kw): return {}
    def estimate_tokens_rough(*a, **kw): return 0
    def estimate_messages_tokens_rough(*a, **kw): return 0
    def estimate_request_tokens_rough(*a, **kw): return 0
    def get_next_probe_tier(*a, **kw): return None
    def parse_context_limit_from_error(*a, **kw): return None
    def parse_available_output_tokens_from_error(*a, **kw): return None
    def save_context_length(*a, **kw): pass
    def is_local_endpoint(*a, **kw): return False
    def query_ollama_num_ctx(*a, **kw): return None
    class ContextCompressor:  # type: ignore[no-redef]
        def __init__(self, *a, **kw): pass
        def compress(self, *a, **kw): return None
        def update_model(self, *a, **kw): pass
    class SubdirectoryHintTracker:
        def __init__(self, *a, **kw): pass
    def apply_anthropic_cache_control(*a, **kw): return None
    def estimate_usage_cost(*a, **kw): return 0.0
    def normalize_usage(*a, **kw): return {}
    def _codex_derive_responses_function_call_id(*a, **kw): return ""
    def _codex_deterministic_call_id(*a, **kw): return ""
    def _codex_split_responses_tool_id(*a, **kw): return ("", "")
    def _summarize_user_message_for_log(*a, **kw): return ""
    class KawaiiSpinner:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
    def _build_tool_preview(*a, **kw): return ""
    def _get_cute_tool_message_impl(*a, **kw): return ""
    def _detect_tool_failure(*a, **kw): return False
    def _get_tool_emoji(*a, **kw): return ""
    class ToolCallGuardrailConfig:
        def __init__(self, *a, **kw): pass
    class ToolCallGuardrailController:
        def __init__(self, *a, **kw): pass
    class ToolGuardrailDecision:
        ALLOW = "allow"
    def append_toolguard_guidance(*a, **kw): return ""
    def toolguard_synthetic_result(*a, **kw): return ""
    _FILE_MUTATING_TOOLS: set = set()
    def file_mutation_result_landed(*a, **kw): return False
    def convert_scratchpad_to_think(*a, **kw): return []
    def has_incomplete_scratchpad(*a, **kw): return False
    def _save_trajectory_to_file(*a, **kw): pass
    def atomic_json_write(*a, **kw): pass
    def base_url_host_matches(*a, **kw): return False
    def base_url_hostname(*a, **kw): return ""
    def env_var_enabled(*a, **kw): return False
    def normalize_proxy_url(*a, **kw): return None
    def cfg_get(*a, **kw): return None
from icecode.agent.engine_tool_exec import _ToolExecutionMixin  # noqa: F401



class _SafeWriter:
    """Transparent stdio wrapper that catches OSError/ValueError from broken pipes.

    When icecode-agent runs as a systemd service, Docker container, or headless
    daemon, the stdout/stderr pipe can become unavailable (idle timeout, buffer
    exhaustion, socket reset). Any print() call then raises
    ``OSError: [Errno 5] Input/output error``, which can crash agent setup or
    run_conversation() — especially via double-fault when an except handler
    also tries to print.

    Additionally, when subagents run in ThreadPoolExecutor threads, the shared
    stdout handle can close between thread teardown and cleanup, raising
    ``ValueError: I/O operation on closed file`` instead of OSError.

    This wrapper delegates all writes to the underlying stream and silently
    catches both OSError and ValueError. It is transparent when the wrapped
    stream is healthy.
    """

    __slots__ = ("_inner",)

    def __init__(self, inner):
        object.__setattr__(self, "_inner", inner)

    def write(self, data):
        try:
            return self._inner.write(data)
        except (OSError, ValueError):
            return len(data) if isinstance(data, str) else 0

    def flush(self):
        try:
            self._inner.flush()
        except (OSError, ValueError):
            pass

    def fileno(self):
        return self._inner.fileno()

    def isatty(self):
        try:
            return self._inner.isatty()
        except (OSError, ValueError):
            return False

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _get_proxy_from_env() -> Optional[str]:
    """Read proxy URL from environment variables.

    Checks HTTPS_PROXY, HTTP_PROXY, ALL_PROXY (and lowercase variants) in order.
    Returns the first valid proxy URL found, or None if no proxy is configured.
    """
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
                "https_proxy", "http_proxy", "all_proxy"):
        value = os.environ.get(key, "").strip()
        if value:
            return normalize_proxy_url(value)
    return None


def _get_proxy_for_base_url(base_url: Optional[str]) -> Optional[str]:
    """Return an env-configured proxy unless NO_PROXY excludes this base URL."""
    proxy = _get_proxy_from_env()
    if not proxy or not base_url:
        return proxy

    host = base_url_hostname(base_url)
    if not host:
        return proxy

    try:
        if urllib.request.proxy_bypass_environment(host):
            return None
    except Exception:
        pass

    return proxy


def _install_safe_stdio() -> None:
    """Wrap stdout/stderr so best-effort console output cannot crash the agent."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and not isinstance(stream, _SafeWriter):
            setattr(sys, stream_name, _SafeWriter(stream))



# _NEVER_PARALLEL_TOOLS, _PARALLEL_SAFE_TOOLS, _PATH_SCOPED_TOOLS,
# _DESTRUCTIVE_PATTERNS, _REDIRECT_OVERWRITE, _is_destructive_command,
# _should_parallelize_tool_batch, _extract_parallel_scope_path, _paths_overlap
# → imported from engine_tool_guard.py (see import block near top of file).

# _SURROGATE_RE and all sanitization/repair functions are imported from
# engine_sanitize.py (see import block near top of file).


# _is_multimodal_tool_result, _multimodal_text_summary, _append_subdir_hint_to_multimodal,
# _extract_error_preview, _trajectory_normalize_msg
# → imported from engine_multimodal.py (see import block near top of file).


# =========================================================================
# Large tool result handler — save oversized output to temp file
# =========================================================================


# =========================================================================
# Qwen Portal headers — mimics QwenCode CLI for portal.qwen.ai compatibility.
# Extracted as a module-level helper so both __init__ and
# _apply_client_headers_for_base_url can share it.
# =========================================================================
_QWEN_CODE_VERSION = "0.14.1"


def _routermint_headers() -> dict:
    """Return the User-Agent RouterMint needs to avoid Cloudflare 1010 blocks."""
    from icecode_cli.hermes_cli import __version__ as _ICECODE_VERSION

    return {
        "User-Agent": f"ICECODEAgent/{_ICECODE_VERSION}",
    }


def _pool_may_recover_from_rate_limit(
    pool, *, provider: str | None = None, base_url: str | None = None
) -> bool:
    """Decide whether to wait for credential-pool rotation instead of falling back.

    The existing pool-rotation path requires the pool to (1) exist and (2) have
    at least one entry not currently in exhaustion cooldown.  But rotation is
    only meaningful when the pool has more than one entry.

    With a single-credential pool (common for Gemini OAuth, Vertex service
    accounts, and any "one personal key" configuration), the primary entry
    just 429'd and there is nothing to rotate to.  Waiting for the pool
    cooldown to expire means retrying against the same exhausted quota — the
    daily-quota 429 will recur immediately, and the retry budget is burned.

    Additionally, Google CloudCode / Gemini CLI rate limits are ACCOUNT-level
    throttles — even a multi-entry pool shares the same quota window, so
    rotation won't recover.  Skip straight to the fallback for those (#13636).

    In those cases we must fall back to the configured ``fallback_model``
    instead.  Returns True only when rotation has somewhere to go.

    See issues #11314 and #13636.
    """
    if pool is None:
        return False
    if not pool.has_available():
        return False
    # CloudCode / Gemini CLI quotas are account-wide — all pool entries share
    # the same throttle window, so rotation can't recover.  Prefer fallback.
    if provider == "google-gemini-cli" or str(base_url or "").startswith("cloudcode-pa://"):
        return False
    return len(pool.entries()) > 1


def _qwen_portal_headers() -> dict:
    """Return default HTTP headers required by Qwen Portal API."""
    import platform as _plat

    _ua = f"QwenCode/{_QWEN_CODE_VERSION} ({_plat.system().lower()}; {_plat.machine()})"
    return {
        "User-Agent": _ua,
        "X-DashScope-CacheControl": "enable",
        "X-DashScope-UserAgent": _ua,
        "X-DashScope-AuthType": "qwen-oauth",
    }


class AIAgent(_ToolExecutionMixin, _ConversationMixin, _SessionMixin, _APIMixin):
    """
    AI Agent with tool calling capabilities.

    This class manages the conversation flow, tool execution, and response handling
    for AI models that support function calling.
    """

    _TOOL_CALL_ARGUMENTS_CORRUPTION_MARKER = (
        "[icecode-agent: tool call arguments were corrupted in this session and "
        "have been dropped to keep the conversation alive. See issue #15236.]"
    )

    @property
    def base_url(self) -> str:
        return self._base_url

    @base_url.setter
    def base_url(self, value: str) -> None:
        self._base_url = value
        self._base_url_lower = value.lower() if value else ""
        self._base_url_hostname = base_url_hostname(value)

    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        provider: str = None,
        api_mode: str = None,
        acp_command: str = None,
        acp_args: list[str] | None = None,
        command: str = None,
        args: list[str] | None = None,
        model: str = "",
        max_iterations: int = 90,  # Default tool-calling iterations (shared with subagents)
        tool_delay: float = 1.0,
        enabled_toolsets: List[str] = None,
        disabled_toolsets: List[str] = None,
        save_trajectories: bool = False,
        verbose_logging: bool = False,
        quiet_mode: bool = False,
        ephemeral_system_prompt: str = None,
        log_prefix_chars: int = 100,
        log_prefix: str = "",
        providers_allowed: List[str] = None,
        providers_ignored: List[str] = None,
        providers_order: List[str] = None,
        provider_sort: str = None,
        provider_require_parameters: bool = False,
        provider_data_collection: str = None,
        openrouter_min_coding_score: Optional[float] = None,
        session_id: str = None,
        tool_progress_callback: callable = None,
        tool_start_callback: callable = None,
        tool_complete_callback: callable = None,
        thinking_callback: callable = None,
        reasoning_callback: callable = None,
        clarify_callback: callable = None,
        step_callback: callable = None,
        stream_delta_callback: callable = None,
        interim_assistant_callback: callable = None,
        tool_gen_callback: callable = None,
        status_callback: callable = None,
        max_tokens: int = None,
        reasoning_config: Dict[str, Any] = None,
        service_tier: str = None,
        request_overrides: Dict[str, Any] = None,
        prefill_messages: List[Dict[str, Any]] = None,
        platform: str = None,
        user_id: str = None,
        user_name: str = None,
        chat_id: str = None,
        chat_name: str = None,
        chat_type: str = None,
        thread_id: str = None,
        gateway_session_key: str = None,
        skip_context_files: bool = False,
        load_soul_identity: bool = False,
        skip_memory: bool = False,
        session_db=None,
        parent_session_id: str = None,
        iteration_budget: "IterationBudget" = None,
        fallback_model: Dict[str, Any] = None,
        credential_pool=None,
        checkpoints_enabled: bool = False,
        checkpoint_max_snapshots: int = 20,
        checkpoint_max_total_size_mb: int = 500,
        checkpoint_max_file_size_mb: int = 10,
        pass_session_id: bool = False,
    ):
        """
        Initialize the AI Agent.

        Args:
            base_url (str): Base URL for the model API (optional)
            api_key (str): API key for authentication (optional, uses env var if not provided)
            provider (str): Provider identifier (optional; used for telemetry/routing hints)
            api_mode (str): API mode override: "chat_completions" or "codex_responses"
            model (str): Model name to use (default: "anthropic/claude-opus-4.6")
            max_iterations (int): Maximum number of tool calling iterations (default: 90)
            tool_delay (float): Delay between tool calls in seconds (default: 1.0)
            enabled_toolsets (List[str]): Only enable tools from these toolsets (optional)
            disabled_toolsets (List[str]): Disable tools from these toolsets (optional)
            save_trajectories (bool): Whether to save conversation trajectories to JSONL files (default: False)
            verbose_logging (bool): Enable verbose logging for debugging (default: False)
            quiet_mode (bool): Suppress progress output for clean CLI experience (default: False)
            ephemeral_system_prompt (str): System prompt used during agent execution but NOT saved to trajectories (optional)
            log_prefix_chars (int): Number of characters to show in log previews for tool calls/responses (default: 100)
            log_prefix (str): Prefix to add to all log messages for identification in parallel processing (default: "")
            providers_allowed (List[str]): OpenRouter providers to allow (optional)
            providers_ignored (List[str]): OpenRouter providers to ignore (optional)
            providers_order (List[str]): OpenRouter providers to try in order (optional)
            provider_sort (str): Sort providers by price/throughput/latency (optional)
            openrouter_min_coding_score (float): Coding-score floor (0.0-1.0) for the
                openrouter/pareto-code router. Only applied when model == "openrouter/pareto-code".
                None or empty = let OpenRouter pick the strongest available coder.
            session_id (str): Pre-generated session ID for logging (optional, auto-generated if not provided)
            tool_progress_callback (callable): Callback function(tool_name, args_preview) for progress notifications
            clarify_callback (callable): Callback function(question, choices) -> str for interactive user questions.
                Provided by the platform layer (CLI or gateway). If None, the clarify tool returns an error.
            max_tokens (int): Maximum tokens for model responses (optional, uses model default if not set)
            reasoning_config (Dict): OpenRouter reasoning configuration override (e.g. {"effort": "none"} to disable thinking).
                If None, defaults to {"enabled": True, "effort": "medium"} for OpenRouter. Set to disable/customize reasoning.
            prefill_messages (List[Dict]): Messages to prepend to conversation history as prefilled context.
                Useful for injecting a few-shot example or priming the model's response style.
                Example: [{"role": "user", "content": "Hi!"}, {"role": "assistant", "content": "Hello!"}]
                NOTE: Anthropic Sonnet 4.6+ and Opus 4.6+ reject a conversation that ends on an
                assistant-role message (400 error).  For those models use structured outputs or
                output_config.format instead of a trailing-assistant prefill.
            platform (str): The interface platform the user is on (e.g. "cli", "telegram", "discord", "whatsapp").
                Used to inject platform-specific formatting hints into the system prompt.
            skip_context_files (bool): If True, skip auto-injection of SOUL.md, AGENTS.md, and .cursorrules
                into the system prompt. Use this for batch processing and data generation to avoid
                polluting trajectories with user-specific persona or project instructions.
            load_soul_identity (bool): If True, still use ~/.icecode/SOUL.md as the primary
                identity even when skip_context_files=True. Project context files from the cwd
                remain skipped.
        """
        _install_safe_stdio()

        self.model = model
        self.max_iterations = max_iterations
        # Shared iteration budget — parent creates, children inherit.
        # Consumed by every LLM turn across parent + all subagents.
        self.iteration_budget = iteration_budget or IterationBudget(max_iterations)
        self.tool_delay = tool_delay
        self.save_trajectories = save_trajectories
        self.verbose_logging = verbose_logging
        self.quiet_mode = quiet_mode
        self.ephemeral_system_prompt = ephemeral_system_prompt
        self.platform = platform  # "cli", "telegram", "discord", "whatsapp", etc.
        self._user_id = user_id  # Platform user identifier (gateway sessions)
        self._user_name = user_name
        self._chat_id = chat_id
        self._chat_name = chat_name
        self._chat_type = chat_type
        self._thread_id = thread_id
        self._gateway_session_key = gateway_session_key  # Stable per-chat key (e.g. agent:main:telegram:dm:123)
        # Pluggable print function — CLI replaces this with _cprint so that
        # raw ANSI status lines are routed through prompt_toolkit's renderer
        # instead of going directly to stdout where patch_stdout's StdoutProxy
        # would mangle the escape sequences.  None = use builtins.print.
        self._print_fn = None
        self.background_review_callback = None  # Optional sync callback for gateway delivery
        self.skip_context_files = skip_context_files
        self.load_soul_identity = load_soul_identity
        self.pass_session_id = pass_session_id
        self._credential_pool = credential_pool
        self.log_prefix_chars = log_prefix_chars
        self.log_prefix = f"{log_prefix} " if log_prefix else ""
        # Store effective base URL for feature detection (prompt caching, reasoning, etc.)
        self.base_url = base_url or ""
        provider_name = provider.strip().lower() if isinstance(provider, str) and provider.strip() else None
        self.provider = provider_name or ""
        self.acp_command = acp_command or command
        self.acp_args = list(acp_args or args or [])
        if api_mode in {"chat_completions", "codex_responses", "anthropic_messages", "bedrock_converse", "codex_app_server"}:
            self.api_mode = api_mode
        elif self.provider == "openai-codex":
            self.api_mode = "codex_responses"
        elif self.provider == "xai":
            self.api_mode = "codex_responses"
        elif (provider_name is None) and (
            self._base_url_hostname == "chatgpt.com"
            and "/backend-api/codex" in self._base_url_lower
        ):
            self.api_mode = "codex_responses"
            self.provider = "openai-codex"
        elif (provider_name is None) and self._base_url_hostname == "api.x.ai":
            self.api_mode = "codex_responses"
            self.provider = "xai"
        elif self.provider == "anthropic" or (provider_name is None and self._base_url_hostname == "api.anthropic.com"):
            self.api_mode = "anthropic_messages"
            self.provider = "anthropic"
        elif self._base_url_lower.rstrip("/").endswith("/anthropic"):
            # Third-party Anthropic-compatible endpoints (e.g. MiniMax, DashScope)
            # use a URL convention ending in /anthropic. Auto-detect these so the
            # Anthropic Messages API adapter is used instead of chat completions.
            self.api_mode = "anthropic_messages"
        elif self.provider == "bedrock" or (
            self._base_url_hostname.startswith("bedrock-runtime.")
            and base_url_host_matches(self._base_url_lower, "amazonaws.com")
        ):
            # AWS Bedrock — auto-detect from provider name or base URL
            # (bedrock-runtime.<region>.amazonaws.com).
            self.api_mode = "bedrock_converse"
        else:
            self.api_mode = "chat_completions"

        # Eagerly warm the transport cache so import errors surface at init,
        # not mid-conversation.  Also validates the api_mode is registered.
        try:
            self._get_transport()
        except Exception:
            pass  # Non-fatal — transport may not exist for all modes yet

        try:
            from icecode_cli.hermes_cli.model_normalize import (
                _AGGREGATOR_PROVIDERS,
                normalize_model_for_provider,
            )

            if self.provider not in _AGGREGATOR_PROVIDERS:
                self.model = normalize_model_for_provider(self.model, self.provider)
        except Exception:
            pass

        # GPT-5.x models usually require the Responses API path, but some
        # providers have exceptions (for example Copilot's gpt-5-mini still
        # uses chat completions). Also auto-upgrade for direct OpenAI URLs
        # (api.openai.com) since all newer tool-calling models prefer
        # Responses there. ACP runtimes are excluded: CopilotACPClient
        # handles its own routing and does not implement the Responses API
        # surface.
        # When api_mode was explicitly provided, respect it — the user
        # knows what their endpoint supports (#10473).
        # Exception: Azure OpenAI serves gpt-5.x on /chat/completions and
        # does NOT support the Responses API — skip the upgrade for Azure
        # (openai.azure.com), even though it looks OpenAI-compatible.
        if (
            api_mode is None
            and self.api_mode == "chat_completions"
            and self.provider != "copilot-acp"
            and not str(self.base_url or "").lower().startswith("acp://copilot")
            and not str(self.base_url or "").lower().startswith("acp+tcp://")
            and not self._is_azure_openai_url()
            and (
                self._is_direct_openai_url()
                or self._provider_model_requires_responses_api(
                    self.model,
                    provider=self.provider,
                )
            )
        ):
            self.api_mode = "codex_responses"
            # Invalidate the eager-warmed transport cache — api_mode changed
            # from chat_completions to codex_responses after the warm at __init__.
            if hasattr(self, "_transport_cache"):
                self._transport_cache.clear()

        # Pre-warm OpenRouter model metadata cache in a background thread.
        # fetch_model_metadata() is cached for 1 hour; this avoids a blocking
        # HTTP request on the first API response when pricing is estimated.
        # Use a process-level Event so this thread is only spawned once — a new
        # AIAgent is created for every gateway request, so without the guard
        # each message leaks one OS thread and the process eventually exhausts
        # the system thread limit (RuntimeError: can't start new thread).
        if (self.provider == "openrouter" or self._is_openrouter_url()) and \
                not _openrouter_prewarm_done.is_set():
            _openrouter_prewarm_done.set()
            threading.Thread(
                target=fetch_model_metadata,
                daemon=True,
                name="openrouter-prewarm",
            ).start()

        self.tool_progress_callback = tool_progress_callback
        self.tool_start_callback = tool_start_callback
        self.tool_complete_callback = tool_complete_callback
        self.suppress_status_output = False
        self.thinking_callback = thinking_callback
        self.reasoning_callback = reasoning_callback
        self.clarify_callback = clarify_callback
        self.step_callback = step_callback
        self.stream_delta_callback = stream_delta_callback
        self.interim_assistant_callback = interim_assistant_callback
        self.status_callback = status_callback
        self.tool_gen_callback = tool_gen_callback

        
        # Tool execution state — allows _vprint during tool execution
        # even when stream consumers are registered (no tokens streaming then)
        self._executing_tools = False
        self._tool_guardrails = ToolCallGuardrailController()
        self._tool_guardrail_halt_decision: ToolGuardrailDecision | None = None

        # Interrupt mechanism for breaking out of tool loops
        self._interrupt_requested = False
        self._interrupt_message = None  # Optional message that triggered interrupt
        self._execution_thread_id: int | None = None  # Set at run_conversation() start
        self._interrupt_thread_signal_pending = False
        self._client_lock = threading.RLock()

        # /steer mechanism — inject a user note into the next tool result
        # without interrupting the agent. Unlike interrupt(), steer() does
        # NOT set _interrupt_requested; it waits for the current tool batch
        # to finish naturally, then the drain hook appends the text to the
        # last tool result's content so the model sees it on its next
        # iteration. Message-role alternation is preserved (we modify an
        # existing tool message rather than inserting a new user turn).
        self._pending_steer: Optional[str] = None
        self._pending_steer_lock = threading.Lock()

        # Concurrent-tool worker thread tracking.  `_execute_tool_calls_concurrent`
        # runs each tool on its own ThreadPoolExecutor worker — those worker
        # threads have tids distinct from `_execution_thread_id`, so
        # `_set_interrupt(True, _execution_thread_id)` alone does NOT cause
        # `is_interrupted()` inside the worker to return True.  Track the
        # workers here so `interrupt()` / `clear_interrupt()` can fan out to
        # their tids explicitly.
        self._tool_worker_threads: set[int] = set()
        self._tool_worker_threads_lock = threading.Lock()
        
        # Subagent delegation state
        self._delegate_depth = 0        # 0 = top-level agent, incremented for children
        self._active_children = []      # Running child AIAgents (for interrupt propagation)
        self._active_children_lock = threading.Lock()
        
        # Store OpenRouter provider preferences
        self.providers_allowed = providers_allowed
        self.providers_ignored = providers_ignored
        self.providers_order = providers_order
        self.provider_sort = provider_sort
        self.provider_require_parameters = provider_require_parameters
        self.provider_data_collection = provider_data_collection
        self.openrouter_min_coding_score = openrouter_min_coding_score

        # Store toolset filtering options
        self.enabled_toolsets = enabled_toolsets
        self.disabled_toolsets = disabled_toolsets
        
        # Model response configuration
        self.max_tokens = max_tokens  # None = use model default
        self.reasoning_config = reasoning_config  # None = use default (medium for OpenRouter)
        self.service_tier = service_tier
        self.request_overrides = dict(request_overrides or {})
        self.prefill_messages = prefill_messages or []  # Prefilled conversation turns
        self._force_ascii_payload = False
        
        # Anthropic prompt caching: auto-enabled for Claude models on native
        # Anthropic, OpenRouter, and third-party gateways that speak the
        # Anthropic protocol (``api_mode == 'anthropic_messages'``). Reduces
        # input costs by ~75% on multi-turn conversations. Uses system_and_3
        # strategy (4 breakpoints). See ``_anthropic_prompt_cache_policy``
        # for the layout-vs-transport decision.
        self._use_prompt_caching, self._use_native_cache_layout = (
            self._anthropic_prompt_cache_policy()
        )
        # Anthropic supports "5m" (default) and "1h" cache TTL tiers. Read from
        # config.yaml under prompt_caching.cache_ttl; unknown values keep "5m".
        # 1h tier costs 2x on write vs 1.25x for 5m, but amortizes across long
        # sessions with >5-minute pauses between turns (#14971).
        self._cache_ttl = "5m"
        try:
            from icecode_cli.hermes_cli.config import load_config as _load_pc_cfg

            _pc_cfg = _load_pc_cfg().get("prompt_caching", {}) or {}
            _ttl = _pc_cfg.get("cache_ttl", "5m")
            if _ttl in {"5m", "1h"}:
                self._cache_ttl = _ttl
        except Exception:
            pass

        # Iteration budget: the LLM is only notified when it actually exhausts
        # the iteration budget (api_call_count >= max_iterations).  At that
        # point we inject ONE message, allow one final API call, and if the
        # model doesn't produce a text response, force a user-message asking
        # it to summarise.  No intermediate pressure warnings — they caused
        # models to "give up" prematurely on complex tasks (#7915).
        self._budget_exhausted_injected = False
        self._budget_grace_call = False

        # Activity tracking — updated on each API call, tool execution, and
        # stream chunk.  Used by the gateway timeout handler to report what the
        # agent was doing when it was killed, and by the "still working"
        # notifications to show progress.
        self._last_activity_ts: float = time.time()
        self._last_activity_desc: str = "initializing"
        self._current_tool: str | None = None
        self._api_call_count: int = 0

        # Rate limit tracking — updated from x-ratelimit-* response headers
        # after each API call.  Accessed by /usage slash command.
        self._rate_limit_state: Optional["RateLimitState"] = None

        # OpenRouter response cache hit counter — incremented when
        # X-OpenRouter-Cache-Status: HIT is seen in streaming response headers.
        self._or_cache_hits: int = 0

        # Centralized logging — agent.log (INFO+) and errors.log (WARNING+)
        # both live under ~/.icecode/logs/.  Idempotent, so gateway mode
        # (which creates a new AIAgent per message) won't duplicate handlers.
        from icecode.icecode_logging import setup_logging, setup_verbose_logging
        setup_logging(hermes_home=_hermes_home)

        if self.verbose_logging:
            setup_verbose_logging()
            logger.info("Verbose logging enabled (third-party library logs suppressed)")
        elif self.quiet_mode:
            # In quiet mode (CLI default), keep console output clean —
            # but DO NOT raise per-logger levels. Doing so prevents the
            # root logger's file handlers (agent.log, errors.log) from
            # ever seeing the records, because Python checks
            # logger.isEnabledFor() before handler propagation. We rely
            # on the fact that hermes_logging.setup_logging() does not
            # install a console StreamHandler in quiet mode — so INFO
            # records flow to the file handlers but never reach a
            # console. Any future noise reduction belongs at the
            # handler level inside hermes_logging.py, not here.
            pass
        
        # Internal stream callback (set during streaming TTS).
        # Initialized here so _vprint can reference it before run_conversation.
        self._stream_callback = None
        # Deferred paragraph break flag — set after tool iterations so a
        # single "\n\n" is prepended to the next real text delta.
        self._stream_needs_break = False
        # Stateful scrubber for <memory-context> spans split across stream
        # deltas (#5719).  sanitize_context() alone can't survive chunk
        # boundaries because the block regex needs both tags in one string.
        self._stream_context_scrubber = StreamingContextScrubber()
        # Stateful scrubber for reasoning/thinking tags in streamed deltas
        # (#17924).  Replaces the per-delta _strip_think_blocks regex that
        # destroyed downstream state (e.g. MiniMax-M2.7 streaming
        # '<think>' as delta1 and 'Let me check' as delta2 — the regex
        # erased delta1, so downstream state machines never learned a
        # block was open and leaked delta2 as content).
        self._stream_think_scrubber = StreamingThinkScrubber()
        # Visible assistant text already delivered through live token callbacks
        # during the current model response. Used to avoid re-sending the same
        # commentary when the provider later returns it as a completed interim
        # assistant message.
        self._current_streamed_assistant_text = ""

        # Optional current-turn user-message override used when the API-facing
        # user message intentionally differs from the persisted transcript
        # (e.g. CLI voice mode adds a temporary prefix for the live call only).
        self._persist_user_message_idx = None
        self._persist_user_message_override = None

        # Cache anthropic image-to-text fallbacks per image payload/URL so a
        # single tool loop does not repeatedly re-run auxiliary vision on the
        # same image history.
        self._anthropic_image_fallback_cache: Dict[str, str] = {}

        # Initialize LLM client via centralized provider router.
        # The router handles auth resolution, base URL, headers, and
        # Codex/Anthropic wrapping for all known providers.
        # raw_codex=True because the main agent needs direct responses.stream()
        # access for Codex Responses API streaming.
        self._anthropic_client = None
        self._is_anthropic_oauth = False

        # Resolve per-provider / per-model request timeout once up front so
        # every client construction path below (Anthropic native, OpenAI-wire,
        # router-based implicit auth) can apply it consistently.  Bedrock
        # Claude uses its own timeout path and is not covered here.
        _provider_timeout = get_provider_request_timeout(self.provider, self.model)

        if self.api_mode == "anthropic_messages":
            from icecode.agent.anthropic_adapter import build_anthropic_client, resolve_anthropic_token
            # Bedrock + Claude → use AnthropicBedrock SDK for full feature parity
            # (prompt caching, thinking budgets, adaptive thinking).
            _is_bedrock_anthropic = self.provider == "bedrock"
            if _is_bedrock_anthropic:
                from icecode.agent.anthropic_adapter import build_anthropic_bedrock_client
                _region_match = re.search(r"bedrock-runtime\.([a-z0-9-]+)\.", base_url or "")
                _br_region = _region_match.group(1) if _region_match else "us-east-1"
                self._bedrock_region = _br_region
                self._anthropic_client = build_anthropic_bedrock_client(_br_region)
                self._anthropic_api_key = "aws-sdk"
                self._anthropic_base_url = base_url
                self._is_anthropic_oauth = False
                self.api_key = "aws-sdk"
                self.client = None
                self._client_kwargs = {}
                if not self.quiet_mode:
                    print(f"🤖 AI Agent initialized with model: {self.model} (AWS Bedrock + AnthropicBedrock SDK, {_br_region})")
            else:
                # Only fall back to ANTHROPIC_TOKEN when the provider is actually Anthropic.
                # Other anthropic_messages providers (MiniMax, Alibaba, etc.) must use their own API key.
                # Falling back would send Anthropic credentials to third-party endpoints (Fixes #1739, #minimax-401).
                _is_native_anthropic = self.provider == "anthropic"
                effective_key = (api_key or resolve_anthropic_token() or "") if _is_native_anthropic else (api_key or "")
                self.api_key = effective_key
                self._anthropic_api_key = effective_key
                self._anthropic_base_url = base_url
                # Only mark the session as OAuth-authenticated when the token
                # genuinely belongs to native Anthropic.  Third-party providers
                # (MiniMax, Kimi, GLM, LiteLLM proxies) that accept the
                # Anthropic protocol must never trip OAuth code paths — doing
                # so injects Claude-Code identity headers and system prompts
                # that cause 401/403 on their endpoints.  Guards #1739 and
                # the third-party identity-injection bug.
                from icecode.agent.anthropic_adapter import _is_oauth_token as _is_oat
                self._is_anthropic_oauth = _is_oat(effective_key) if _is_native_anthropic else False
                self._anthropic_client = build_anthropic_client(effective_key, base_url, timeout=_provider_timeout)
                # No OpenAI client needed for Anthropic mode
                self.client = None
                self._client_kwargs = {}
                if not self.quiet_mode:
                    print(f"🤖 AI Agent initialized with model: {self.model} (Anthropic native)")
                    if effective_key and len(effective_key) > 12:
                        print(f"🔑 Using token: {effective_key[:8]}...{effective_key[-4:]}")
        elif self.api_mode == "bedrock_converse":
            # AWS Bedrock — uses boto3 directly, no OpenAI client needed.
            # Region is extracted from the base_url or defaults to us-east-1.
            _region_match = re.search(r"bedrock-runtime\.([a-z0-9-]+)\.", base_url or "")
            self._bedrock_region = _region_match.group(1) if _region_match else "us-east-1"
            # Guardrail config — read from config.yaml at init time.
            self._bedrock_guardrail_config = None
            try:
                from icecode_cli.hermes_cli.config import load_config as _load_br_cfg
                _gr = _load_br_cfg().get("bedrock", {}).get("guardrail", {})
                if _gr.get("guardrail_identifier") and _gr.get("guardrail_version"):
                    self._bedrock_guardrail_config = {
                        "guardrailIdentifier": _gr["guardrail_identifier"],
                        "guardrailVersion": _gr["guardrail_version"],
                    }
                    if _gr.get("stream_processing_mode"):
                        self._bedrock_guardrail_config["streamProcessingMode"] = _gr["stream_processing_mode"]
                    if _gr.get("trace"):
                        self._bedrock_guardrail_config["trace"] = _gr["trace"]
            except Exception:
                pass
            self.client = None
            self._client_kwargs = {}
            if not self.quiet_mode:
                _gr_label = " + Guardrails" if self._bedrock_guardrail_config else ""
                print(f"🤖 AI Agent initialized with model: {self.model} (AWS Bedrock, {self._bedrock_region}{_gr_label})")
        else:
            if api_key and base_url:
                # Explicit credentials from CLI/gateway — construct directly.
                # The runtime provider resolver already handled auth for us.
                # Extract query params (e.g. Azure api-version) from base_url
                # and pass via default_query to prevent loss during SDK URL
                # joining (httpx drops query string when joining paths).
                _parsed_url = urlparse(base_url)
                if _parsed_url.query:
                    _clean_url = urlunparse(_parsed_url._replace(query=""))
                    _query_params = {
                        k: v[0] for k, v in parse_qs(_parsed_url.query).items()
                    }
                    client_kwargs = {
                        "api_key": api_key,
                        "base_url": _clean_url,
                        "default_query": _query_params,
                    }
                else:
                    client_kwargs = {"api_key": api_key, "base_url": base_url}
                if _provider_timeout is not None:
                    client_kwargs["timeout"] = _provider_timeout
                if self.provider == "copilot-acp":
                    client_kwargs["command"] = self.acp_command
                    client_kwargs["args"] = self.acp_args
                effective_base = base_url
                if base_url_host_matches(effective_base, "openrouter.ai"):
                    from icecode.agent.auxiliary_client import build_or_headers
                    client_kwargs["default_headers"] = build_or_headers()
                elif base_url_host_matches(effective_base, "api.routermint.com"):
                    client_kwargs["default_headers"] = _routermint_headers()
                elif base_url_host_matches(effective_base, "api.githubcopilot.com"):
                    from icecode_cli.hermes_cli.models import copilot_default_headers

                    client_kwargs["default_headers"] = copilot_default_headers()
                elif base_url_host_matches(effective_base, "api.kimi.com"):
                    client_kwargs["default_headers"] = {
                        "User-Agent": "claude-code/0.1.0",
                    }
                elif base_url_host_matches(effective_base, "portal.qwen.ai"):
                    client_kwargs["default_headers"] = _qwen_portal_headers()
                elif base_url_host_matches(effective_base, "chatgpt.com"):
                    from icecode.agent.auxiliary_client import _codex_cloudflare_headers
                    client_kwargs["default_headers"] = _codex_cloudflare_headers(api_key)
                elif "default_headers" not in client_kwargs:
                    # Fall back to profile.default_headers for providers that
                    # declare custom headers (e.g. Vercel AI Gateway attribution,
                    # Kimi User-Agent on non-kimi.com endpoints).
                    try:
                        from providers import get_provider_profile as _gpf
                        _ph = _gpf(self.provider)
                        if _ph and _ph.default_headers:
                            client_kwargs["default_headers"] = dict(_ph.default_headers)
                    except Exception:
                        pass
            else:
                # No explicit creds — use the centralized provider router
                from icecode.agent.auxiliary_client import resolve_provider_client
                _routed_client, _ = resolve_provider_client(
                    self.provider or "auto", model=self.model, raw_codex=True)
                if _routed_client is not None:
                    client_kwargs = {
                        "api_key": _routed_client.api_key,
                        "base_url": str(_routed_client.base_url),
                    }
                    if _provider_timeout is not None:
                        client_kwargs["timeout"] = _provider_timeout
                    # Preserve any default_headers the router set
                    if hasattr(_routed_client, '_default_headers') and _routed_client._default_headers:
                        client_kwargs["default_headers"] = dict(_routed_client._default_headers)
                else:
                    # When the user explicitly chose a non-OpenRouter provider
                    # but no credentials were found, fail fast with a clear
                    # message instead of silently routing through OpenRouter.
                    _explicit = (self.provider or "").strip().lower()
                    if _explicit and _explicit not in {"auto", "openrouter", "custom"}:
                        # Look up the actual env var name from the provider
                        # config — some providers use non-standard names
                        # (e.g. alibaba → DASHSCOPE_API_KEY, not ALIBABA_API_KEY).
                        _env_hint = f"{_explicit.upper()}_API_KEY"
                        try:
                            from icecode_cli.hermes_cli.auth import PROVIDER_REGISTRY
                            _pcfg = PROVIDER_REGISTRY.get(_explicit)
                            if _pcfg and _pcfg.api_key_env_vars:
                                _env_hint = _pcfg.api_key_env_vars[0]
                        except Exception:
                            pass
                        # --- Init-time fallback (#17929) ---
                        _fb_entries = []
                        if isinstance(fallback_model, list):
                            _fb_entries = [
                                f for f in fallback_model
                                if isinstance(f, dict) and f.get("provider") and f.get("model")
                            ]
                        elif isinstance(fallback_model, dict) and fallback_model.get("provider") and fallback_model.get("model"):
                            _fb_entries = [fallback_model]
                        _fb_resolved = False
                        for _fb in _fb_entries:
                            _fb_explicit_key = (_fb.get("api_key") or "").strip() or None
                            if not _fb_explicit_key:
                                _fb_key_env = (_fb.get("key_env") or _fb.get("api_key_env") or "").strip()
                                if _fb_key_env:
                                    _fb_explicit_key = os.getenv(_fb_key_env, "").strip() or None
                            _fb_client, _fb_model = resolve_provider_client(
                                _fb["provider"], model=_fb["model"], raw_codex=True,
                                explicit_base_url=_fb.get("base_url"),
                                explicit_api_key=_fb_explicit_key,
                            )
                            if _fb_client is not None:
                                self.provider = _fb["provider"]
                                self.model = _fb_model or _fb["model"]
                                self._fallback_activated = True
                                client_kwargs = {
                                    "api_key": _fb_client.api_key,
                                    "base_url": str(_fb_client.base_url),
                                }
                                if _provider_timeout is not None:
                                    client_kwargs["timeout"] = _provider_timeout
                                if hasattr(_fb_client, "_default_headers") and _fb_client._default_headers:
                                    client_kwargs["default_headers"] = dict(_fb_client._default_headers)
                                _fb_resolved = True
                                break
                        if not _fb_resolved:
                            raise RuntimeError(
                                f"Provider '{_explicit}' is set in config.yaml but no API key "
                                f"was found. Set the {_env_hint} environment "
                                f"variable, or switch to a different provider with `hermes model`."
                            )
                    if not getattr(self, "_fallback_activated", False):
                        # No provider configured — reject with a clear message.
                        raise RuntimeError(
                            "No LLM provider configured. Run `hermes model` to "
                            "select a provider, or run `hermes setup` for first-time "
                            "configuration."
                        )
            
            self._client_kwargs = client_kwargs  # stored for rebuilding after interrupt

            # Enable fine-grained tool streaming for Claude on OpenRouter.
            # Without this, Anthropic buffers the entire tool call and goes
            # silent for minutes while thinking — OpenRouter's upstream proxy
            # times out during the silence.  The beta header makes Anthropic
            # stream tool call arguments token-by-token, keeping the
            # connection alive.
            _effective_base = str(client_kwargs.get("base_url", "")).lower()
            if base_url_host_matches(_effective_base, "openrouter.ai") and "claude" in (self.model or "").lower():
                headers = client_kwargs.get("default_headers") or {}
                existing_beta = headers.get("x-anthropic-beta", "")
                _FINE_GRAINED = "fine-grained-tool-streaming-2025-05-14"
                if _FINE_GRAINED not in existing_beta:
                    if existing_beta:
                        headers["x-anthropic-beta"] = f"{existing_beta},{_FINE_GRAINED}"
                    else:
                        headers["x-anthropic-beta"] = _FINE_GRAINED
                    client_kwargs["default_headers"] = headers

            self.api_key = client_kwargs.get("api_key", "")
            self.base_url = client_kwargs.get("base_url", self.base_url)
            try:
                self.client = self._create_openai_client(client_kwargs, reason="agent_init", shared=True)
                if not self.quiet_mode:
                    print(f"🤖 AI Agent initialized with model: {self.model}")
                    if base_url:
                        print(f"🔗 Using custom base URL: {base_url}")
                    # Always show API key info (masked) for debugging auth issues
                    key_used = client_kwargs.get("api_key", "none")
                    if key_used and key_used != "dummy-key" and len(key_used) > 12:
                        print(f"🔑 Using API key: {key_used[:8]}...{key_used[-4:]}")
                    else:
                        print(f"⚠️  Warning: API key appears invalid or missing (got: '{key_used[:20] if key_used else 'none'}...')")
            except Exception as e:
                raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
        
        # Provider fallback chain — ordered list of backup providers tried
        # when the primary is exhausted (rate-limit, overload, connection
        # failure).  Supports both legacy single-dict ``fallback_model`` and
        # new list ``fallback_providers`` format.
        if isinstance(fallback_model, list):
            self._fallback_chain = [
                f for f in fallback_model
                if isinstance(f, dict) and f.get("provider") and f.get("model")
            ]
        elif isinstance(fallback_model, dict) and fallback_model.get("provider") and fallback_model.get("model"):
            self._fallback_chain = [fallback_model]
        else:
            self._fallback_chain = []
        self._fallback_index = 0
        self._fallback_activated = getattr(self, "_fallback_activated", False)
        # Legacy attribute kept for backward compat (tests, external callers)
        self._fallback_model = self._fallback_chain[0] if self._fallback_chain else None
        if self._fallback_chain and not self.quiet_mode:
            if len(self._fallback_chain) == 1:
                fb = self._fallback_chain[0]
                print(f"🔄 Fallback model: {fb['model']} ({fb['provider']})")
            else:
                print(f"🔄 Fallback chain ({len(self._fallback_chain)} providers): " +
                      " → ".join(f"{f['model']} ({f['provider']})" for f in self._fallback_chain))

        # Get available tools with filtering
        self.tools = get_tool_definitions(
            enabled_toolsets=enabled_toolsets,
            disabled_toolsets=disabled_toolsets,
            quiet_mode=self.quiet_mode,
        )
        
        # Show tool configuration and store valid tool names for validation
        self.valid_tool_names = set()
        if self.tools:
            self.valid_tool_names = {tool["function"]["name"] for tool in self.tools}
            tool_names = sorted(self.valid_tool_names)
            if not self.quiet_mode:
                print(f"🛠️  Loaded {len(self.tools)} tools: {', '.join(tool_names)}")
                
                # Show filtering info if applied
                if enabled_toolsets:
                    print(f"   ✅ Enabled toolsets: {', '.join(enabled_toolsets)}")
                if disabled_toolsets:
                    print(f"   ❌ Disabled toolsets: {', '.join(disabled_toolsets)}")
        elif not self.quiet_mode:
            print("🛠️  No tools loaded (all tools filtered out or unavailable)")
        
        # Check tool requirements
        if self.tools and not self.quiet_mode:
            requirements = check_toolset_requirements()
            missing_reqs = [name for name, available in requirements.items() if not available]
            if missing_reqs:
                print(f"⚠️  Some tools may not work due to missing requirements: {missing_reqs}")
        
        # Show trajectory saving status
        if self.save_trajectories and not self.quiet_mode:
            print("📝 Trajectory saving enabled")
        
        # Show ephemeral system prompt status
        if self.ephemeral_system_prompt and not self.quiet_mode:
            prompt_preview = self.ephemeral_system_prompt[:60] + "..." if len(self.ephemeral_system_prompt) > 60 else self.ephemeral_system_prompt
            print(f"🔒 Ephemeral system prompt: '{prompt_preview}' (not saved to trajectories)")
        
        # Show prompt caching status
        if self._use_prompt_caching and not self.quiet_mode:
            if self._use_native_cache_layout and self.provider == "anthropic":
                source = "native Anthropic"
            elif self._use_native_cache_layout:
                source = "Anthropic-compatible endpoint"
            else:
                source = "Claude via OpenRouter"
            print(f"💾 Prompt caching: ENABLED ({source}, {self._cache_ttl} TTL)")
        
        # Session logging setup - auto-save conversation trajectories for debugging
        self.session_start = datetime.now()
        if session_id:
            # Use provided session ID (e.g., from CLI)
            self.session_id = session_id
        else:
            # Generate a new session ID
            timestamp_str = self.session_start.strftime("%Y%m%d_%H%M%S")
            short_uuid = uuid.uuid4().hex[:6]
            self.session_id = f"{timestamp_str}_{short_uuid}"

        # Expose session ID to tools (terminal, execute_code) so agents can
        # reference their own session for --resume commands, cross-session
        # coordination, and logging.  Uses the ContextVar system from
        # session_context.py for concurrency safety (gateway runs multiple
        # sessions in one process).  Also writes os.environ as fallback for
        # CLI mode where ContextVars aren't used.
        os.environ["ICECODE_SESSION_ID"] = self.session_id
        try:
            from gateway.session_context import _SESSION_ID
            _SESSION_ID.set(self.session_id)
        except Exception:
            pass  # CLI/test mode — ContextVar not needed

        # Session logs go into ~/.icecode/sessions/ alongside gateway sessions
        hermes_home = get_hermes_home()
        self.logs_dir = hermes_home / "sessions"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.session_log_file = self.logs_dir / f"session_{self.session_id}.json"
        
        # Track conversation messages for session logging
        self._session_messages: List[Dict[str, Any]] = []
        self._memory_write_origin = "assistant_tool"
        self._memory_write_context = "foreground"
        
        # Cached system prompt -- built once per session, only rebuilt on compression
        self._cached_system_prompt: Optional[str] = None
        
        # Filesystem checkpoint manager (transparent — not a tool)
        from tools.checkpoint_manager import CheckpointManager
        self._checkpoint_mgr = CheckpointManager(
            enabled=checkpoints_enabled,
            max_snapshots=checkpoint_max_snapshots,
            max_total_size_mb=checkpoint_max_total_size_mb,
            max_file_size_mb=checkpoint_max_file_size_mb,
        )
        
        # SQLite session store (optional -- provided by CLI or gateway)
        self._session_db = session_db
        self._parent_session_id = parent_session_id
        self._last_flushed_db_idx = 0  # tracks DB-write cursor to prevent duplicate writes
        self._session_db_created = False  # DB row deferred to run_conversation()
        self._session_init_model_config = {
            "max_iterations": self.max_iterations,
            "reasoning_config": reasoning_config,
            "max_tokens": max_tokens,
        }
        
        # In-memory todo list for task planning (one per agent/session)
        from tools.todo_tool import TodoStore
        self._todo_store = TodoStore()
        
        # Load config once for memory, skills, and compression sections
        try:
            from icecode_cli.hermes_cli.config import load_config as _load_agent_config
            _agent_cfg = _load_agent_config()
        except Exception:
            _agent_cfg = {}
        try:
            self._tool_guardrails = ToolCallGuardrailController(
                ToolCallGuardrailConfig.from_mapping(
                    _agent_cfg.get("tool_loop_guardrails", {})
                )
            )
        except Exception as _tlg_err:
            logger.warning("Tool loop guardrail config ignored: %s", _tlg_err)
        # Cache only the derived auxiliary compression context override that is
        # needed later by the startup feasibility check.  Avoid exposing a
        # broad pseudo-public config object on the agent instance.
        self._aux_compression_context_length_config = None

        # Persistent memory (MEMORY.md + USER.md) -- loaded from disk
        self._memory_store = None
        self._memory_enabled = False
        self._user_profile_enabled = False
        self._memory_nudge_interval = 10
        self._turns_since_memory = 0
        self._iters_since_skill = 0
        if not skip_memory:
            try:
                mem_config = _agent_cfg.get("memory", {})
                self._memory_enabled = mem_config.get("memory_enabled", False)
                self._user_profile_enabled = mem_config.get("user_profile_enabled", False)
                self._memory_nudge_interval = int(mem_config.get("nudge_interval", 10))
                if self._memory_enabled or self._user_profile_enabled:
                    from tools.memory_tool import MemoryStore
                    self._memory_store = MemoryStore(
                        memory_char_limit=mem_config.get("memory_char_limit", 2200),
                        user_char_limit=mem_config.get("user_char_limit", 1375),
                    )
                    self._memory_store.load_from_disk()
            except Exception:
                pass  # Memory is optional -- don't break agent init
        


        # Memory provider plugin (external — one at a time, alongside built-in)
        # Reads memory.provider from config to select which plugin to activate.
        self._memory_manager = None
        if not skip_memory:
            try:
                _mem_provider_name = mem_config.get("provider", "") if mem_config else ""

                if _mem_provider_name:
                    from icecode.agent.memory_manager import MemoryManager as _MemoryManager
                    from plugins.memory import load_memory_provider as _load_mem
                    self._memory_manager = _MemoryManager()
                    _mp = _load_mem(_mem_provider_name)
                    if _mp and _mp.is_available():
                        self._memory_manager.add_provider(_mp)
                    if self._memory_manager.providers:
                        _init_kwargs = {
                            "session_id": self.session_id,
                            "platform": platform or "cli",
                            "hermes_home": str(get_hermes_home()),
                            "agent_context": "primary",
                        }
                        # Thread session title for memory provider scoping
                        # (e.g. honcho uses this to derive chat-scoped session keys)
                        if self._session_db:
                            try:
                                _st = self._session_db.get_session_title(self.session_id)
                                if _st:
                                    _init_kwargs["session_title"] = _st
                            except Exception:
                                pass
                        # Thread gateway user identity for per-user memory scoping
                        if self._user_id:
                            _init_kwargs["user_id"] = self._user_id
                        if self._user_name:
                            _init_kwargs["user_name"] = self._user_name
                        if self._chat_id:
                            _init_kwargs["chat_id"] = self._chat_id
                        if self._chat_name:
                            _init_kwargs["chat_name"] = self._chat_name
                        if self._chat_type:
                            _init_kwargs["chat_type"] = self._chat_type
                        if self._thread_id:
                            _init_kwargs["thread_id"] = self._thread_id
                        # Thread gateway session key for stable per-chat Honcho session isolation
                        if self._gateway_session_key:
                            _init_kwargs["gateway_session_key"] = self._gateway_session_key
                        # Profile identity for per-profile provider scoping
                        try:
                            from icecode_cli.hermes_cli.profiles import get_active_profile_name
                            _profile = get_active_profile_name()
                            _init_kwargs["agent_identity"] = _profile
                            _init_kwargs["agent_workspace"] = "hermes"
                        except Exception:
                            pass
                        self._memory_manager.initialize_all(**_init_kwargs)
                        logger.info("Memory provider '%s' activated", _mem_provider_name)
                    else:
                        logger.debug("Memory provider '%s' not found or not available", _mem_provider_name)
                        self._memory_manager = None
            except Exception as _mpe:
                logger.warning("Memory provider plugin init failed: %s", _mpe)
                self._memory_manager = None

        # Inject memory provider tool schemas into the tool surface.
        # Skip tools whose names already exist (plugins may register the
        # same tools via ctx.register_tool(), which lands in self.tools
        # through get_tool_definitions()).  Duplicate function names cause
        # 400 errors on providers that enforce unique names (e.g. Xiaomi
        # MiMo via Nous Portal).
        if self._memory_manager and self.tools is not None:
            _existing_tool_names = {
                t.get("function", {}).get("name")
                for t in self.tools
                if isinstance(t, dict)
            }
            for _schema in self._memory_manager.get_all_tool_schemas():
                _tname = _schema.get("name", "")
                if _tname and _tname in _existing_tool_names:
                    continue  # already registered via plugin path
                _wrapped = {"type": "function", "function": _schema}
                self.tools.append(_wrapped)
                if _tname:
                    self.valid_tool_names.add(_tname)
                    _existing_tool_names.add(_tname)

        # Skills config: nudge interval for skill creation reminders
        self._skill_nudge_interval = 10
        try:
            skills_config = _agent_cfg.get("skills", {})
            self._skill_nudge_interval = int(skills_config.get("creation_nudge_interval", 10))
        except Exception:
            pass

        # Tool-use enforcement config: "auto" (default — matches hardcoded
        # model list), true (always), false (never), or list of substrings.
        _agent_section = _agent_cfg.get("agent", {})
        if not isinstance(_agent_section, dict):
            _agent_section = {}
        self._tool_use_enforcement = _agent_section.get("tool_use_enforcement", "auto")

        # App-level API retry count (wraps each model API call).  Default 3,
        # overridable via agent.api_max_retries in config.yaml.  See #11616.
        try:
            _raw_api_retries = _agent_section.get("api_max_retries", 3)
            _api_retries = int(_raw_api_retries)
            _api_retries = max(_api_retries, 1)  # 1 = no retry (single attempt)
        except (TypeError, ValueError):
            _api_retries = 3
        self._api_max_retries = _api_retries

        # Initialize context compressor for automatic context management
        # Compresses conversation when approaching model's context limit
        # Configuration via config.yaml (compression section)
        _compression_cfg = _agent_cfg.get("compression", {})
        if not isinstance(_compression_cfg, dict):
            _compression_cfg = {}
        compression_threshold = float(_compression_cfg.get("threshold", 0.50))
        try:
            from icecode.agent.auxiliary_client import _compression_threshold_for_model as _cthresh_fn
            _model_cthresh = _cthresh_fn(self.model)
            if _model_cthresh is not None:
                compression_threshold = _model_cthresh
        except Exception:
            pass
        compression_enabled = str(_compression_cfg.get("enabled", True)).lower() in {"true", "1", "yes"}
        compression_target_ratio = float(_compression_cfg.get("target_ratio", 0.20))
        compression_protect_last = int(_compression_cfg.get("protect_last_n", 20))
        # protect_first_n is the number of non-system messages to protect at
        # the head, in addition to the system prompt (which is always
        # implicitly protected by the compressor).  Floor at 0 — a value of
        # 0 means "preserve only the system prompt + summary + tail", which
        # is a legitimate (and common) configuration for long-running
        # rolling-compaction sessions.
        compression_protect_first = max(
            0, int(_compression_cfg.get("protect_first_n", 3))
        )

        # Read optional explicit context_length override for the auxiliary
        # compression model. Custom endpoints often cannot report this via
        # /models, so the startup feasibility check needs the config hint.
        try:
            _aux_cfg = cfg_get(_agent_cfg, "auxiliary", "compression", default={})
        except Exception:
            _aux_cfg = {}
        if isinstance(_aux_cfg, dict):
            _aux_context_config = _aux_cfg.get("context_length")
        else:
            _aux_context_config = None
        if _aux_context_config is not None:
            try:
                _aux_context_config = int(_aux_context_config)
            except (TypeError, ValueError):
                _aux_context_config = None
        self._aux_compression_context_length_config = _aux_context_config

        # Read explicit model output-token override from config when the
        # caller did not pass one directly.
        _model_cfg = _agent_cfg.get("model", {})
        if self.max_tokens is None and isinstance(_model_cfg, dict):
            _config_max_tokens = _model_cfg.get("max_tokens")
            if _config_max_tokens is not None:
                try:
                    if isinstance(_config_max_tokens, bool):
                        raise ValueError
                    _parsed_max_tokens = int(_config_max_tokens)
                    if _parsed_max_tokens <= 0:
                        raise ValueError
                    self.max_tokens = _parsed_max_tokens
                except (TypeError, ValueError):
                    logger.warning(
                        "Invalid model.max_tokens in config.yaml: %r — "
                        "must be a positive integer (e.g. 4096). "
                        "Falling back to provider default.",
                        _config_max_tokens,
                    )
                    print(
                        f"\n⚠ Invalid model.max_tokens in config.yaml: {_config_max_tokens!r}\n"
                        f"  Must be a positive integer (e.g. 4096).\n"
                        f"  Falling back to provider default.\n",
                        file=sys.stderr,
                    )
        self._session_init_model_config["max_tokens"] = self.max_tokens

        # Read explicit context_length override from model config
        if isinstance(_model_cfg, dict):
            _config_context_length = _model_cfg.get("context_length")
        else:
            _config_context_length = None
        if _config_context_length is not None:
            try:
                _config_context_length = int(_config_context_length)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid model.context_length in config.yaml: %r — "
                    "must be a plain integer (e.g. 256000, not '256K'). "
                    "Falling back to auto-detection.",
                    _config_context_length,
                )
                print(
                    f"\n⚠ Invalid model.context_length in config.yaml: {_config_context_length!r}\n"
                    f"  Must be a plain integer (e.g. 256000, not '256K').\n"
                    f"  Falling back to auto-detected context window.\n",
                    file=sys.stderr,
                )
                _config_context_length = None

        # Resolve custom_providers list once for reuse below (startup
        # context-length override and plugin context-engine init).
        try:
            from icecode_cli.hermes_cli.config import get_compatible_custom_providers
            _custom_providers = get_compatible_custom_providers(_agent_cfg)
        except Exception:
            _custom_providers = _agent_cfg.get("custom_providers")
            if not isinstance(_custom_providers, list):
                _custom_providers = []

        # Store for reuse by _check_compression_model_feasibility (auxiliary
        # compression model context-length detection needs the same list).
        self._custom_providers = _custom_providers

        # Check custom_providers per-model context_length
        if _config_context_length is None and _custom_providers:
            try:
                from icecode_cli.hermes_cli.config import get_custom_provider_context_length
                _cp_ctx_resolved = get_custom_provider_context_length(
                    model=self.model,
                    base_url=self.base_url,
                    custom_providers=_custom_providers,
                )
                if _cp_ctx_resolved:
                    _config_context_length = int(_cp_ctx_resolved)
            except Exception:
                _cp_ctx_resolved = None

            # Surface a clear warning if the user set a context_length but it
            # wasn't a valid positive int — the helper silently skips those.
            if _config_context_length is None:
                _target = self.base_url.rstrip("/") if self.base_url else ""
                for _cp_entry in _custom_providers:
                    if not isinstance(_cp_entry, dict):
                        continue
                    _cp_url = (_cp_entry.get("base_url") or "").rstrip("/")
                    if _target and _cp_url == _target:
                        _cp_models = _cp_entry.get("models", {})
                        if isinstance(_cp_models, dict):
                            _cp_model_cfg = _cp_models.get(self.model, {})
                            if isinstance(_cp_model_cfg, dict):
                                _cp_ctx = _cp_model_cfg.get("context_length")
                                if _cp_ctx is not None:
                                    try:
                                        _parsed = int(_cp_ctx)
                                        if _parsed <= 0:
                                            raise ValueError
                                    except (TypeError, ValueError):
                                        logger.warning(
                                            "Invalid context_length for model %r in "
                                            "custom_providers: %r — must be a positive "
                                            "integer (e.g. 256000, not '256K'). "
                                            "Falling back to auto-detection.",
                                            self.model, _cp_ctx,
                                        )
                                        print(
                                            f"\n⚠ Invalid context_length for model {self.model!r} in custom_providers: {_cp_ctx!r}\n"
                                            f"  Must be a positive integer (e.g. 256000, not '256K').\n"
                                            f"  Falling back to auto-detected context window.\n",
                                            file=sys.stderr,
                                        )
                        break

        # Persist for reuse on switch_model / fallback activation. Must come
        # AFTER the custom_providers branch so per-model overrides aren't lost.
        self._config_context_length = _config_context_length

        self._ensure_lmstudio_runtime_loaded(_config_context_length)



        # Select context engine: config-driven (like memory providers).
        # 1. Check config.yaml context.engine setting
        # 2. Check plugins/context_engine/<name>/ directory (repo-shipped)
        # 3. Check general plugin system (user-installed plugins)
        # 4. Fall back to built-in ContextCompressor
        _selected_engine = None
        _engine_name = "compressor"  # default
        try:
            _ctx_cfg = _agent_cfg.get("context", {}) if isinstance(_agent_cfg, dict) else {}
            _engine_name = _ctx_cfg.get("engine", "compressor") or "compressor"
        except Exception:
            pass

        if _engine_name != "compressor":
            # Try loading from plugins/context_engine/<name>/
            try:
                from plugins.context_engine import load_context_engine
                _selected_engine = load_context_engine(_engine_name)
            except Exception as _ce_load_err:
                logger.debug("Context engine load from plugins/context_engine/: %s", _ce_load_err)

            # Try general plugin system as fallback
            if _selected_engine is None:
                try:
                    from icecode_cli.hermes_cli.plugins import get_plugin_context_engine
                    _candidate = get_plugin_context_engine()
                    if _candidate and _candidate.name == _engine_name:
                        _selected_engine = _candidate
                except Exception:
                    pass

            if _selected_engine is None:
                logger.warning(
                    "Context engine '%s' not found — falling back to built-in compressor",
                    _engine_name,
                )
        # else: config says "compressor" — use built-in, don't auto-activate plugins

        if _selected_engine is not None:
            self.context_compressor = _selected_engine
            # Resolve context_length for plugin engines — mirrors switch_model() path
            from icecode.agent.model_metadata import get_model_context_length
            _plugin_ctx_len = get_model_context_length(
                self.model,
                base_url=self.base_url,
                api_key=getattr(self, "api_key", ""),
                config_context_length=_config_context_length,
                provider=self.provider,
                custom_providers=_custom_providers,
            )
            self.context_compressor.update_model(
                model=self.model,
                context_length=_plugin_ctx_len,
                base_url=self.base_url,
                api_key=getattr(self, "api_key", ""),
                provider=self.provider,
            )
            if not self.quiet_mode:
                logger.info("Using context engine: %s", _selected_engine.name)
        else:
            self.context_compressor = ContextCompressor(
                model=self.model,
                threshold_percent=compression_threshold,
                protect_first_n=compression_protect_first,
                protect_last_n=compression_protect_last,
                summary_target_ratio=compression_target_ratio,
                summary_model_override=None,
                quiet_mode=self.quiet_mode,
                base_url=self.base_url,
                api_key=getattr(self, "api_key", ""),
                config_context_length=_config_context_length,
                provider=self.provider,
                api_mode=self.api_mode,
            )
        self.compression_enabled = compression_enabled

        # Reject models whose context window is below the minimum required
        # for reliable tool-calling workflows (64K tokens).
        from icecode.agent.model_metadata import MINIMUM_CONTEXT_LENGTH
        _ctx = getattr(self.context_compressor, "context_length", 0)
        if _ctx and _ctx < MINIMUM_CONTEXT_LENGTH:
            raise ValueError(
                f"Model {self.model} has a context window of {_ctx:,} tokens, "
                f"which is below the minimum {MINIMUM_CONTEXT_LENGTH:,} required "
                f"by ICECODE Agent.  Choose a model with at least "
                f"{MINIMUM_CONTEXT_LENGTH // 1000}K context, or set "
                f"model.context_length in config.yaml to override."
            )

        # Inject context engine tool schemas (e.g. lcm_grep, lcm_describe, lcm_expand).
        # Skip names that are already present — the get_tool_definitions()
        # quiet_mode cache returned a shared list pre-#17335, so a stray
        # mutation here would poison subsequent agent inits in the same
        # Gateway process and trip provider-side 'duplicate tool name'
        # errors. Even with the cache fix, dedup is the right defense
        # against plugin paths that may register the same schemas via
        # ctx.register_tool(). Mirrors the memory tools dedup above.
        self._context_engine_tool_names: set = set()
        if hasattr(self, "context_compressor") and self.context_compressor and self.tools is not None:
            _existing_tool_names = {
                t.get("function", {}).get("name")
                for t in self.tools
                if isinstance(t, dict)
            }
            for _schema in self.context_compressor.get_tool_schemas():
                _tname = _schema.get("name", "")
                if _tname and _tname in _existing_tool_names:
                    continue  # already registered via plugin/cache path
                _wrapped = {"type": "function", "function": _schema}
                self.tools.append(_wrapped)
                if _tname:
                    self.valid_tool_names.add(_tname)
                    self._context_engine_tool_names.add(_tname)
                    _existing_tool_names.add(_tname)

        # Notify context engine of session start
        if hasattr(self, "context_compressor") and self.context_compressor:
            try:
                self.context_compressor.on_session_start(
                    self.session_id,
                    hermes_home=str(get_hermes_home()),
                    platform=self.platform or "cli",
                    model=self.model,
                    context_length=getattr(self.context_compressor, "context_length", 0),
                )
            except Exception as _ce_err:
                logger.debug("Context engine on_session_start: %s", _ce_err)

        self._subdirectory_hints = SubdirectoryHintTracker(
            working_dir=os.getenv("TERMINAL_CWD") or None,
        )
        self._user_turn_count = 0

        # Cumulative token usage for the session
        self.session_prompt_tokens = 0
        self.session_completion_tokens = 0
        self.session_total_tokens = 0
        self.session_api_calls = 0
        self.session_input_tokens = 0
        self.session_output_tokens = 0
        self.session_cache_read_tokens = 0
        self.session_cache_write_tokens = 0
        self.session_reasoning_tokens = 0
        self.session_estimated_cost_usd = 0.0
        self.session_cost_status = "unknown"
        self.session_cost_source = "none"
        
        # ── Ollama num_ctx injection ──
        # Ollama defaults to 2048 context regardless of the model's capabilities.
        # When running against an Ollama server, detect the model's max context
        # and pass num_ctx on every chat request so the full window is used.
        # User override: set model.ollama_num_ctx in config.yaml to cap VRAM use.
        # If model.context_length is set, it caps num_ctx so the user's VRAM
        # budget is respected even when GGUF metadata advertises a larger window.
        self._ollama_num_ctx: int | None = None
        _ollama_num_ctx_override = None
        if isinstance(_model_cfg, dict):
            _ollama_num_ctx_override = _model_cfg.get("ollama_num_ctx")
        if _ollama_num_ctx_override is not None:
            try:
                self._ollama_num_ctx = int(_ollama_num_ctx_override)
            except (TypeError, ValueError):
                logger.debug("Invalid ollama_num_ctx config value: %r", _ollama_num_ctx_override)
        if self._ollama_num_ctx is None and self.base_url and is_local_endpoint(self.base_url):
            try:
                _detected = query_ollama_num_ctx(self.model, self.base_url, api_key=self.api_key or "")
                if _detected and _detected > 0:
                    self._ollama_num_ctx = _detected
            except Exception as exc:
                logger.debug("Ollama num_ctx detection failed: %s", exc)
        # Cap auto-detected ollama_num_ctx to the user's explicit context_length.
        # Without this, GGUF metadata can advertise 256K+ which Ollama honours
        # by allocating that much VRAM — blowing up small GPUs even though the
        # user explicitly set a smaller context_length in config.yaml.
        if (
            self._ollama_num_ctx
            and _config_context_length
            and _ollama_num_ctx_override is None  # don't override explicit ollama_num_ctx
            and self._ollama_num_ctx > _config_context_length
        ):
            logger.info(
                "Ollama num_ctx capped: %d -> %d (model.context_length override)",
                self._ollama_num_ctx, _config_context_length,
            )
            self._ollama_num_ctx = _config_context_length
        if self._ollama_num_ctx and not self.quiet_mode:
            logger.info(
                "Ollama num_ctx: will request %d tokens (model max from /api/show)",
                self._ollama_num_ctx,
            )

        if not self.quiet_mode:
            if compression_enabled:
                print(f"📊 Context limit: {self.context_compressor.context_length:,} tokens (compress at {int(compression_threshold*100)}% = {self.context_compressor.threshold_tokens:,})")
            else:
                print(f"📊 Context limit: {self.context_compressor.context_length:,} tokens (auto-compression disabled)")

        # Check immediately so CLI users see the warning at startup.
        # Gateway status_callback is not yet wired, so any warning is stored
        # in _compression_warning and replayed in the first run_conversation().
        self._compression_warning = None
        self._check_compression_model_feasibility()

        # Snapshot primary runtime for per-turn restoration.  When fallback
        # activates during a turn, the next turn restores these values so the
        # preferred model gets a fresh attempt each time.  Uses a single dict
        # so new state fields are easy to add without N individual attributes.
        _cc = self.context_compressor
        self._primary_runtime = {
            "model": self.model,
            "provider": self.provider,
            "base_url": self.base_url,
            "api_mode": self.api_mode,
            "api_key": getattr(self, "api_key", ""),
            "client_kwargs": dict(self._client_kwargs),
            "use_prompt_caching": self._use_prompt_caching,
            "use_native_cache_layout": self._use_native_cache_layout,
            # Context engine state that _try_activate_fallback() overwrites.
            # Use getattr for model/base_url/api_key/provider since plugin
            # engines may not have these (they're ContextCompressor-specific).
            "compressor_model": getattr(_cc, "model", self.model),
            "compressor_base_url": getattr(_cc, "base_url", self.base_url),
            "compressor_api_key": getattr(_cc, "api_key", ""),
            "compressor_provider": getattr(_cc, "provider", self.provider),
            "compressor_context_length": _cc.context_length,
            "compressor_threshold_tokens": _cc.threshold_tokens,
        }
        if self.api_mode == "anthropic_messages":
            self._primary_runtime.update({
                "anthropic_api_key": self._anthropic_api_key,
                "anthropic_base_url": self._anthropic_base_url,
                "is_anthropic_oauth": self._is_anthropic_oauth,
            })

    def _get_session_db_for_recall(self):
        """Return a SessionDB for recall, lazily creating it if an entrypoint forgot.

        Most frontends pass ``session_db`` into ``AIAgent`` explicitly, but recall
        is important enough that a missing constructor argument should degrade by
        opening the default state DB instead of making the advertised
        ``session_search`` tool unusable.
        """
        if self._session_db is not None:
            return self._session_db
        try:
            from icecode.icecode_state import SessionDB

            self._session_db = SessionDB()
            return self._session_db
        except Exception as exc:
            logger.debug("SessionDB unavailable for recall", exc_info=True)
            return None

    def _ensure_db_session(self) -> None:
        """Create session DB row on first use. Disables _session_db on failure."""
        if self._session_db_created or not self._session_db:
            return
        try:
            self._session_db.create_session(
                session_id=self.session_id,
                source=self.platform or os.environ.get("ICECODE_SESSION_SOURCE", "cli"),
                model=self.model,
                model_config=self._session_init_model_config,
                system_prompt=self._cached_system_prompt,
                user_id=None,
                parent_session_id=self._parent_session_id,
            )
            self._session_db_created = True
        except Exception as e:
            # Transient failure (e.g. SQLite lock). Keep _session_db alive —
            # _session_db_created stays False so next run_conversation() retries.
            logger.warning(
                "Session DB creation failed (will retry next turn): %s", e
            )

    def reset_session_state(self):
        """Reset all session-scoped token counters to 0 for a fresh session.
        
        This method encapsulates the reset logic for all session-level metrics
        including:
        - Token usage counters (input, output, total, prompt, completion)
        - Cache read/write tokens
        - API call count
        - Reasoning tokens
        - Estimated cost tracking
        - Context compressor internal counters
        
        The method safely handles optional attributes (e.g., context compressor)
        using ``hasattr`` checks.
        
        This keeps the counter reset logic DRY and maintainable in one place
        rather than scattering it across multiple methods.
        """
        # Token usage counters
        self.session_total_tokens = 0
        self.session_input_tokens = 0
        self.session_output_tokens = 0
        self.session_prompt_tokens = 0
        self.session_completion_tokens = 0
        self.session_cache_read_tokens = 0
        self.session_cache_write_tokens = 0
        self.session_reasoning_tokens = 0
        self.session_api_calls = 0
        self.session_estimated_cost_usd = 0.0
        self.session_cost_status = "unknown"
        self.session_cost_source = "none"
        
        # Turn counter (added after reset_session_state was first written — #2635)
        self._user_turn_count = 0

        # Context engine reset (works for both built-in compressor and plugins)
        if hasattr(self, "context_compressor") and self.context_compressor:
            self.context_compressor.on_session_reset()

    def _ensure_lmstudio_runtime_loaded(self, config_context_length: Optional[int] = None) -> None:
        """
        Preload the LM Studio model with at least Hermes' minimum context.
        """
        if (self.provider or "").strip().lower() != "lmstudio":
            return
        try:
            from icecode.agent.model_metadata import MINIMUM_CONTEXT_LENGTH
            from icecode_cli.hermes_cli.models import ensure_lmstudio_model_loaded
            if config_context_length is None:
                config_context_length = getattr(self, "_config_context_length", None)
            target_ctx = max(config_context_length or 0, MINIMUM_CONTEXT_LENGTH)
            loaded_ctx = ensure_lmstudio_model_loaded(
                self.model, self.base_url, getattr(self, "api_key", ""), target_ctx,
            )
            if loaded_ctx:
                # Push into the live compressor so the status bar reflects the
                # real loaded ctx the moment the load resolves, instead of
                # holding the previous model's value (or "ctx --") through the
                # next render tick.
                cc = getattr(self, "context_compressor", None)
                if cc is not None:
                    cc.update_model(
                        model=self.model,
                        context_length=loaded_ctx,
                        base_url=self.base_url,
                        api_key=getattr(self, "api_key", ""),
                        provider=self.provider,
                        api_mode=self.api_mode,
                    )
        except Exception as err:
            logger.debug("LM Studio preload skipped: %s", err)

    def switch_model(self, new_model, new_provider, api_key='', base_url='', api_mode=''):
        """Switch the model/provider in-place for a live agent.

        Called by the /model command handlers (CLI and gateway) after
        ``model_switch.switch_model()`` has resolved credentials and
        validated the model.  This method performs the actual runtime
        swap: rebuilding clients, updating caching flags, and refreshing
        the context compressor.

        The implementation mirrors ``_try_activate_fallback()`` for the
        client-swap logic but also updates ``_primary_runtime`` so the
        change persists across turns (unlike fallback which is
        turn-scoped).
        """
        from icecode_cli.hermes_cli.providers import determine_api_mode

        # ── Determine api_mode if not provided ──
        if not api_mode:
            api_mode = determine_api_mode(new_provider, base_url)

        # Defense-in-depth: ensure OpenCode base_url doesn't carry a trailing
        # /v1 into the anthropic_messages client, which would cause the SDK to
        # hit /v1/v1/messages.  `model_switch.switch_model()` already strips
        # this, but we guard here so any direct callers (future code paths,
        # tests) can't reintroduce the double-/v1 404 bug.
        if (
            api_mode == "anthropic_messages"
            and new_provider in {"opencode-zen", "opencode-go"}
            and isinstance(base_url, str)
            and base_url
        ):
            base_url = re.sub(r"/v1/?$", "", base_url)

        old_model = self.model
        old_provider = self.provider

        # Clear the per-config context_length override so the new model's
        # actual context window is resolved via get_model_context_length()
        # instead of inheriting the stale value from the previous model.
        self._config_context_length = None

        # ── Swap core runtime fields ──
        self.model = new_model
        self.provider = new_provider
        # Use new base_url when provided; only fall back to current when the
        # new provider genuinely has no endpoint (e.g. native SDK providers).
        # Without this guard the old provider's URL (e.g. Ollama's localhost
        # address) would persist silently after switching to a cloud provider
        # that returns an empty base_url string.
        if base_url:
            self.base_url = base_url
        self.api_mode = api_mode
        # Invalidate transport cache — new api_mode may need a different transport
        if hasattr(self, "_transport_cache"):
            self._transport_cache.clear()
        if api_key:
            self.api_key = api_key

        # ── Build new client ──
        if api_mode == "anthropic_messages":
            from icecode.agent.anthropic_adapter import (
                build_anthropic_client,
                resolve_anthropic_token,
                _is_oauth_token,
            )
            # Only fall back to ANTHROPIC_TOKEN when the provider is actually Anthropic.
            # Other anthropic_messages providers (MiniMax, Alibaba, etc.) must use their own
            # API key — falling back would send Anthropic credentials to third-party endpoints.
            _is_native_anthropic = new_provider == "anthropic"
            effective_key = (api_key or self.api_key or resolve_anthropic_token() or "") if _is_native_anthropic else (api_key or self.api_key or "")
            self.api_key = effective_key
            self._anthropic_api_key = effective_key
            self._anthropic_base_url = base_url or getattr(self, "_anthropic_base_url", None)
            self._anthropic_client = build_anthropic_client(
                effective_key, self._anthropic_base_url,
                timeout=get_provider_request_timeout(self.provider, self.model),
            )
            self._is_anthropic_oauth = _is_oauth_token(effective_key) if _is_native_anthropic else False
            self.client = None
            self._client_kwargs = {}
        else:
            effective_key = api_key or self.api_key
            effective_base = base_url or self.base_url
            self._client_kwargs = {
                "api_key": effective_key,
                "base_url": effective_base,
            }
            _sm_timeout = get_provider_request_timeout(self.provider, self.model)
            if _sm_timeout is not None:
                self._client_kwargs["timeout"] = _sm_timeout
            self.client = self._create_openai_client(
                dict(self._client_kwargs),
                reason="switch_model",
                shared=True,
            )

        # ── Re-evaluate prompt caching ──
        self._use_prompt_caching, self._use_native_cache_layout = (
            self._anthropic_prompt_cache_policy(
                provider=new_provider,
                base_url=self.base_url,
                api_mode=api_mode,
                model=new_model,
            )
        )

        # ── LM Studio: preload before probing context length ──
        self._ensure_lmstudio_runtime_loaded()

        # ── Update context compressor ──
        if hasattr(self, "context_compressor") and self.context_compressor:
            from icecode.agent.model_metadata import get_model_context_length
            # Re-read custom_providers from live config so per-model
            # context_length overrides are honored when switching to a
            # custom provider mid-session (closes #15779).
            _sm_custom_providers = None
            try:
                from icecode_cli.hermes_cli.config import load_config, get_compatible_custom_providers
                _sm_cfg = load_config()
                _sm_custom_providers = get_compatible_custom_providers(_sm_cfg)
            except Exception:
                _sm_custom_providers = None
            new_context_length = get_model_context_length(
                self.model,
                base_url=self.base_url,
                api_key=self.api_key,
                provider=self.provider,
                config_context_length=getattr(self, "_config_context_length", None),
                custom_providers=_sm_custom_providers,
            )
            self.context_compressor.update_model(
                model=self.model,
                context_length=new_context_length,
                base_url=self.base_url,
                api_key=getattr(self, "api_key", ""),
                provider=self.provider,
                api_mode=self.api_mode,
            )

        # ── Invalidate cached system prompt so it rebuilds next turn ──
        self._cached_system_prompt = None

        # ── Update _primary_runtime so the change persists across turns ──
        _cc = self.context_compressor if hasattr(self, "context_compressor") and self.context_compressor else None
        self._primary_runtime = {
            "model": self.model,
            "provider": self.provider,
            "base_url": self.base_url,
            "api_mode": self.api_mode,
            "api_key": getattr(self, "api_key", ""),
            "client_kwargs": dict(self._client_kwargs),
            "use_prompt_caching": self._use_prompt_caching,
            "use_native_cache_layout": self._use_native_cache_layout,
            "compressor_model": getattr(_cc, "model", self.model) if _cc else self.model,
            "compressor_base_url": getattr(_cc, "base_url", self.base_url) if _cc else self.base_url,
            "compressor_api_key": getattr(_cc, "api_key", "") if _cc else "",
            "compressor_provider": getattr(_cc, "provider", self.provider) if _cc else self.provider,
            "compressor_context_length": _cc.context_length if _cc else 0,
            "compressor_threshold_tokens": _cc.threshold_tokens if _cc else 0,
        }
        if api_mode == "anthropic_messages":
            self._primary_runtime.update({
                "anthropic_api_key": self._anthropic_api_key,
                "anthropic_base_url": self._anthropic_base_url,
                "is_anthropic_oauth": self._is_anthropic_oauth,
            })

        # ── Reset fallback state ──
        self._fallback_activated = False
        self._fallback_index = 0

        # When the user deliberately swaps primary providers (e.g. openrouter
        # → anthropic), drop any fallback entries that target the OLD primary
        # or the NEW one.  The chain was seeded from config at agent init for
        # the original provider — without pruning, a failed turn on the new
        # primary silently re-activates the provider the user just rejected,
        # which is exactly what was reported during TUI v2 blitz testing
        # ("switched to anthropic, tui keeps trying openrouter").
        old_norm = (old_provider or "").strip().lower()
        new_norm = (new_provider or "").strip().lower()
        fallback_chain = list(getattr(self, "_fallback_chain", []) or [])
        if old_norm and new_norm and old_norm != new_norm:
            fallback_chain = [
                entry for entry in fallback_chain
                if (entry.get("provider") or "").strip().lower() not in {old_norm, new_norm}
            ]
        self._fallback_chain = fallback_chain
        self._fallback_model = fallback_chain[0] if fallback_chain else None

        logging.info(
            "Model switched in-place: %s (%s) -> %s (%s)",
            old_model, old_provider, new_model, new_provider,
        )

    def _safe_print(self, *args, **kwargs):
        """Print that silently handles broken pipes / closed stdout.

        In headless environments (systemd, Docker, nohup) stdout may become
        unavailable mid-session.  A raw ``print()`` raises ``OSError`` which
        can crash cron jobs and lose completed work.

        Internally routes through ``self._print_fn`` (default: builtin
        ``print``) so callers such as the CLI can inject a renderer that
        handles ANSI escape sequences properly (e.g. prompt_toolkit's
        ``print_formatted_text(ANSI(...))``) without touching this method.
        """
        try:
            fn = self._print_fn or print
            fn(*args, **kwargs)
        except (OSError, ValueError):
            pass

    def _vprint(self, *args, force: bool = False, **kwargs):
        """Verbose print — suppressed when actively streaming tokens.

        Pass ``force=True`` for error/warning messages that should always be
        shown even during streaming playback (TTS or display).

        During tool execution (``_executing_tools`` is True), printing is
        allowed even with stream consumers registered because no tokens
        are being streamed at that point.

        After the main response has been delivered and the remaining tool
        calls are post-response housekeeping (``_mute_post_response``),
        all non-forced output is suppressed.

        ``suppress_status_output`` is a stricter CLI automation mode used by
        parseable single-query flows such as ``hermes chat -q``. In that mode,
        all status/diagnostic prints routed through ``_vprint`` are suppressed
        so stdout stays machine-readable.
        """
        if getattr(self, "suppress_status_output", False):
            return
        if not force and getattr(self, "_mute_post_response", False):
            return
        if not force and self._has_stream_consumers() and not self._executing_tools:
            return
        self._safe_print(*args, **kwargs)

    def _should_start_quiet_spinner(self) -> bool:
        """Return True when quiet-mode spinner output has a safe sink.

        In headless/stdio-protocol environments, a raw spinner with no custom
        ``_print_fn`` falls back to ``sys.stdout`` and can corrupt protocol
        streams such as ACP JSON-RPC. Allow quiet spinners only when either:
        - output is explicitly rerouted via ``_print_fn``; or
        - stdout is a real TTY.
        """
        if self._print_fn is not None:
            return True
        stream = getattr(sys, "stdout", None)
        if stream is None:
            return False
        try:
            return bool(stream.isatty())
        except (AttributeError, ValueError, OSError):
            return False

    def _should_emit_quiet_tool_messages(self) -> bool:
        """Return True when quiet-mode tool summaries should print directly.

        Quiet mode is used by both the interactive CLI and embedded/library
        callers. The CLI may still want compact progress hints when no callback
        owns rendering. Embedded/library callers, on the other hand, expect
        quiet mode to be truly silent.
        """
        return (
            self.quiet_mode
            and not self.tool_progress_callback
            and getattr(self, "platform", "") == "cli"
        )

    def _emit_status(self, message: str) -> None:
        """Emit a lifecycle status message to both CLI and gateway channels.

        CLI users see the message via ``_vprint(force=True)`` so it is always
        visible regardless of verbose/quiet mode.  Gateway consumers receive
        it through ``status_callback("lifecycle", ...)``.

        This helper never raises — exceptions are swallowed so it cannot
        interrupt the retry/fallback logic.
        """
        try:
            self._vprint(f"{self.log_prefix}{message}", force=True)
        except Exception:
            pass
        if self.status_callback:
            try:
                self.status_callback("lifecycle", message)
            except Exception:
                logger.debug("status_callback error in _emit_status", exc_info=True)

    def _emit_warning(self, message: str) -> None:
        """Emit a user-visible warning through the same status plumbing.

        Unlike debug logs, these warnings are meant for degraded side paths
        such as auxiliary compression or memory flushes where the main turn can
        continue but the user needs to know something important failed.
        """
        try:
            self._vprint(f"{self.log_prefix}{message}", force=True)
        except Exception:
            pass
        if self.status_callback:
            try:
                self.status_callback("warn", message)
            except Exception:
                logger.debug("status_callback error in _emit_warning", exc_info=True)

    # Headers we capture from the dying stream's HTTP response so post-mortem
    # diagnosis can answer "which CF edge / which OpenRouter downstream
    # provider / which request id".  Lowercased; httpx returns CIMultiDict.
    _STREAM_DIAG_HEADERS = (
        "cf-ray",
        "cf-cache-status",
        "x-openrouter-provider",
        "x-openrouter-model",
        "x-openrouter-id",
        "x-request-id",
        "x-vercel-id",
        "via",
        "server",
        "x-forwarded-for",
    )

    @staticmethod
    def _stream_diag_init() -> Dict[str, Any]:
        """Return a fresh per-attempt diagnostic dict.

        Mutated in-place by the streaming functions and read from the retry
        block when a stream dies.  Lives on ``request_client_holder`` so it
        survives across the closure boundary.
        """
        return {
            "started_at": time.time(),
            "first_chunk_at": None,
            "chunks": 0,
            "bytes": 0,
            "headers": {},
            "http_status": None,
        }

    def _stream_diag_capture_response(
        self, diag: Dict[str, Any], http_response: Any
    ) -> None:
        """Snapshot interesting headers + HTTP status from the live stream.

        Called once at stream open (before iterating chunks) so the metadata
        survives even if the stream dies before any chunk arrives.  Failures
        are swallowed — diag is best-effort.
        """
        if http_response is None or not isinstance(diag, dict):
            return
        try:
            diag["http_status"] = getattr(http_response, "status_code", None)
        except Exception:
            pass
        try:
            headers = getattr(http_response, "headers", None) or {}
            captured: Dict[str, str] = {}
            for name in self._STREAM_DIAG_HEADERS:
                try:
                    val = headers.get(name)
                    if val:
                        # Truncate single-value to keep log lines bounded.
                        captured[name] = str(val)[:120]
                except Exception:
                    continue
            diag["headers"] = captured
        except Exception:
            pass

    @staticmethod
    def _flatten_exception_chain(error: BaseException) -> str:
        """Return a compact ``Outer(msg) <- Inner(msg) <- ...`` rendering.

        OpenAI SDK wraps httpx errors as ``APIConnectionError`` /
        ``APIError`` and only the wrapper's class is visible at the catch
        site — but the underlying ``RemoteProtocolError`` /
        ``ConnectError`` / ``ReadError`` is what tells us WHY the stream
        died.  Walks ``__cause__`` then ``__context__`` (deduped, max 4
        deep) to surface the chain in one line.
        """
        seen: List[BaseException] = []
        link: Optional[BaseException] = error
        while link is not None and len(seen) < 4:
            if link in seen:
                break
            seen.append(link)
            nxt = getattr(link, "__cause__", None) or getattr(
                link, "__context__", None
            )
            if nxt is None or nxt is link:
                break
            link = nxt
        parts: List[str] = []
        for e in seen:
            msg = str(e).strip().replace("\n", " ")
            if len(msg) > 140:
                msg = msg[:140] + "…"
            parts.append(f"{type(e).__name__}({msg})" if msg else type(e).__name__)
        return " <- ".join(parts) if parts else type(error).__name__

    def _log_stream_retry(
        self,
        *,
        kind: str,
        error: BaseException,
        attempt: int,
        max_attempts: int,
        mid_tool_call: bool,
        diag: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a transient stream-drop and retry to ``agent.log``.

        Always logs a structured WARNING so users have a breadcrumb regardless
        of UI verbosity.  Subagents in particular benefit because their
        retries no longer spam the parent's terminal — but the file log keeps
        full detail (provider, error class, attempt, base_url, subagent_id).

        When *diag* is provided (the per-attempt stream-diagnostic dict from
        ``_stream_diag_init``), the WARNING also captures upstream headers
        (cf-ray, x-openrouter-provider, x-openrouter-id), HTTP status, bytes
        streamed before the drop, and elapsed time on the dying attempt.
        These are the breadcrumbs needed to answer "is one CF edge / one
        downstream provider responsible, or is it random across runs?"
        """
        try:
            try:
                _summary = self._summarize_api_error(error)
            except Exception:
                _summary = str(error)
            if _summary and len(_summary) > 240:
                _summary = _summary[:240] + "…"

            # Inner-cause chain (httpx errors hide under openai.APIError).
            try:
                _chain = self._flatten_exception_chain(error)
            except Exception:
                _chain = type(error).__name__

            # Per-attempt counters and upstream headers.
            _now = time.time()
            _bytes = 0
            _chunks = 0
            _elapsed = 0.0
            _ttfb = None
            _headers_repr = "-"
            _http_status = "-"
            if isinstance(diag, dict):
                try:
                    _bytes = int(diag.get("bytes") or 0)
                    _chunks = int(diag.get("chunks") or 0)
                    _started = float(diag.get("started_at") or _now)
                    _elapsed = max(0.0, _now - _started)
                    _first = diag.get("first_chunk_at")
                    if _first is not None:
                        _ttfb = max(0.0, float(_first) - _started)
                    headers = diag.get("headers") or {}
                    if isinstance(headers, dict) and headers:
                        _headers_repr = " ".join(
                            f"{k}={v}" for k, v in headers.items()
                        )
                    if diag.get("http_status") is not None:
                        _http_status = str(diag.get("http_status"))
                except Exception:
                    pass

            logger.warning(
                "Stream %s on attempt %s/%s — retrying. "
                "subagent_id=%s depth=%s provider=%s base_url=%s "
                "error_type=%s error=%s "
                "chain=%s "
                "http_status=%s bytes=%d chunks=%d elapsed=%.2fs ttfb=%s "
                "upstream=[%s]",
                kind,
                attempt,
                max_attempts,
                getattr(self, "_subagent_id", None) or "-",
                getattr(self, "_delegate_depth", 0),
                self.provider or "-",
                self.base_url or "-",
                type(error).__name__,
                _summary,
                _chain,
                _http_status,
                _bytes,
                _chunks,
                _elapsed,
                f"{_ttfb:.2f}s" if _ttfb is not None else "-",
                _headers_repr,
                extra={"mid_tool_call": mid_tool_call},
            )
        except Exception:
            logger.debug("stream-retry log emit failed", exc_info=True)

    def _emit_stream_drop(
        self,
        *,
        error: BaseException,
        attempt: int,
        max_attempts: int,
        mid_tool_call: bool,
        diag: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a single user-visible line for a stream drop+retry.

        Both top-level agents and subagents announce drops in the UI — the
        parent prefixes subagent lines with ``[subagent-N]`` via ``log_prefix``
        so they're easy to attribute.  All cases also write a structured
        WARNING to ``agent.log`` via :meth:`_log_stream_retry` with the full
        diagnostic detail (subagent_id, provider, base_url, error_type,
        cf-ray, x-openrouter-provider, bytes/chunks, elapsed) for post-hoc
        analysis.

        The user-visible status line is intentionally compact: provider,
        error class, attempt N/M, plus ``after Xs`` when the stream dropped
        mid-flight.  Full diagnostic detail goes to ``agent.log`` only —
        ``hermes logs --level WARNING | grep "Stream drop"`` to inspect.
        """
        kind = "drop mid tool-call" if mid_tool_call else "drop"
        self._log_stream_retry(
            kind=kind,
            error=error,
            attempt=attempt,
            max_attempts=max_attempts,
            mid_tool_call=mid_tool_call,
            diag=diag,
        )
        provider = self.provider or "provider"
        # Compose a brief "after Xs" suffix when we have timing data — helps
        # the user distinguish "couldn't connect" (0s) from "died after 30s
        # of streaming" (likely upstream idle-kill or proxy timeout).
        _suffix = ""
        if isinstance(diag, dict):
            try:
                started = diag.get("started_at")
                if started is not None:
                    _suffix = f" after {max(0.0, time.time() - float(started)):.1f}s"
            except Exception:
                pass
        try:
            self._emit_status(
                f"⚠️ {provider} stream {kind} ({type(error).__name__}){_suffix} "
                f"— reconnecting, retry {attempt}/{max_attempts}"
            )
            self._touch_activity(
                f"stream retry {attempt}/{max_attempts} "
                f"after {type(error).__name__}"
            )
        except Exception:
            pass

    def _emit_auxiliary_failure(self, task: str, exc: BaseException) -> None:
        """Surface a compact warning for failed auxiliary work."""
        try:
            detail = self._summarize_api_error(exc)
        except Exception:
            detail = str(exc)
        detail = (detail or exc.__class__.__name__).strip()
        if len(detail) > 220:
            detail = detail[:217].rstrip() + "..."
        self._emit_warning(f"⚠ Auxiliary {task} failed: {detail}")

    def _current_main_runtime(self) -> Dict[str, str]:
        """Return the live main runtime for session-scoped auxiliary routing."""
        return {
            "model": getattr(self, "model", "") or "",
            "provider": getattr(self, "provider", "") or "",
            "base_url": getattr(self, "base_url", "") or "",
            "api_key": getattr(self, "api_key", "") or "",
            "api_mode": getattr(self, "api_mode", "") or "",
        }

    def _check_compression_model_feasibility(self) -> None:
        """Warn at session start if the auxiliary compression model's context
        window is smaller than the main model's compression threshold.

        When the auxiliary model cannot fit the content that needs summarising,
        compression will either fail outright (the LLM call errors) or produce
        a severely truncated summary.

        Called during ``__init__`` so CLI users see the warning immediately
        (via ``_vprint``).  The gateway sets ``status_callback`` *after*
        construction, so ``_replay_compression_warning()`` re-sends the
        stored warning through the callback on the first
        ``run_conversation()`` call.
        """
        if not self.compression_enabled:
            return
        try:
            from icecode.agent.auxiliary_client import (
                _resolve_task_provider_model,
                get_text_auxiliary_client,
            )
            from icecode.agent.model_metadata import (
                MINIMUM_CONTEXT_LENGTH,
                get_model_context_length,
            )

            client, aux_model = get_text_auxiliary_client(
                "compression",
                main_runtime=self._current_main_runtime(),
            )
            # Best-effort aux provider label for the warning message. The
            # configured provider may be "auto", in which case we fall back
            # to the client's base_url hostname so the user can still tell
            # where the compression model is actually being called.
            try:
                _aux_cfg_provider, _, _, _, _ = _resolve_task_provider_model("compression")
            except Exception:
                _aux_cfg_provider = ""
            if client is None or not aux_model:
                msg = (
                    "⚠ No auxiliary LLM provider configured — context "
                    "compression will drop middle turns without a summary. "
                    "Run `hermes setup` or set OPENROUTER_API_KEY."
                )
                self._compression_warning = msg
                self._emit_status(msg)
                logger.warning(
                    "No auxiliary LLM provider for compression — "
                    "summaries will be unavailable."
                )
                return

            aux_base_url = str(getattr(client, "base_url", ""))
            aux_api_key = str(getattr(client, "api_key", ""))

            aux_context = get_model_context_length(
                aux_model,
                base_url=aux_base_url,
                api_key=aux_api_key,
                config_context_length=getattr(self, "_aux_compression_context_length_config", None),
                # Each model must be resolved with its own provider so that
                # provider-specific paths (e.g. Bedrock static table, OpenRouter API)
                # are invoked for the correct client, not inherited from the main model.
                provider=(_aux_cfg_provider if _aux_cfg_provider and _aux_cfg_provider != "auto" else getattr(self, "provider", "")),
                custom_providers=self._custom_providers,
            )

            # Hard floor: the auxiliary compression model must have at least
            # MINIMUM_CONTEXT_LENGTH (64K) tokens of context.  The main model
            # is already required to meet this floor (checked earlier in
            # __init__), so the compression model must too — otherwise it
            # cannot summarise a full threshold-sized window of main-model
            # content.  Mirrors the main-model rejection pattern.
            if aux_context and aux_context < MINIMUM_CONTEXT_LENGTH:
                raise ValueError(
                    f"Auxiliary compression model {aux_model} has a context "
                    f"window of {aux_context:,} tokens, which is below the "
                    f"minimum {MINIMUM_CONTEXT_LENGTH:,} required by ICECODE "
                    f"Agent.  Choose a compression model with at least "
                    f"{MINIMUM_CONTEXT_LENGTH // 1000}K context (set "
                    f"auxiliary.compression.model in config.yaml), or set "
                    f"auxiliary.compression.context_length to override the "
                    f"detected value if it is wrong."
                )

            threshold = self.context_compressor.threshold_tokens
            if aux_context < threshold:
                # Auto-correct: lower the live session threshold so
                # compression actually works this session.  The hard floor
                # above guarantees aux_context >= MINIMUM_CONTEXT_LENGTH,
                # so the new threshold is always >= 64K.
                #
                # The compression summariser sends a single user-role
                # prompt (no system prompt, no tools) to the aux model, so
                # new_threshold == aux_context is safe: the request is
                # the raw messages plus a small summarisation instruction.
                old_threshold = threshold
                new_threshold = aux_context
                self.context_compressor.threshold_tokens = new_threshold
                # Keep threshold_percent in sync so future main-model
                # context_length changes (update_model) re-derive from a
                # sensible number rather than the original too-high value.
                main_ctx = self.context_compressor.context_length
                if main_ctx:
                    self.context_compressor.threshold_percent = (
                        new_threshold / main_ctx
                    )
                safe_pct = int((aux_context / main_ctx) * 100) if main_ctx else 50
                # Build human-readable "model (provider)" labels for both
                # the main model and the compression model so users can
                # tell at a glance which provider each side is actually
                # using. When the configured provider is empty or "auto",
                # fall back to the client's base_url hostname.
                _main_model = getattr(self, "model", "") or "?"
                _main_provider = getattr(self, "provider", "") or ""
                _aux_provider_label = (
                    _aux_cfg_provider
                    if _aux_cfg_provider and _aux_cfg_provider != "auto"
                    else ""
                )
                if not _aux_provider_label:
                    try:
                        from urllib.parse import urlparse
                        _aux_provider_label = (
                            urlparse(aux_base_url).hostname or aux_base_url
                        )
                    except Exception:
                        _aux_provider_label = aux_base_url or "auto"
                _main_label = (
                    f"{_main_model} ({_main_provider})"
                    if _main_provider
                    else _main_model
                )
                _aux_label = f"{aux_model} ({_aux_provider_label})"
                msg = (
                    f"⚠ Compression model {_aux_label} context is "
                    f"{aux_context:,} tokens, but the main model "
                    f"{_main_label}'s compression threshold was "
                    f"{old_threshold:,} tokens. "
                    f"Auto-lowered this session's threshold to "
                    f"{new_threshold:,} tokens so compression can run.\n"
                    f"  To make this permanent, edit config.yaml — either:\n"
                    f"  1. Use a larger compression model:\n"
                    f"       auxiliary:\n"
                    f"         compression:\n"
                    f"           model: <model-with-{old_threshold:,}+-context>\n"
                    f"  2. Lower the compression threshold:\n"
                    f"       compression:\n"
                    f"         threshold: 0.{safe_pct:02d}"
                )
                self._compression_warning = msg
                self._emit_status(msg)
                logger.warning(
                    "Auxiliary compression model %s has %d token context, "
                    "below the main model's compression threshold of %d "
                    "tokens — auto-lowered session threshold to %d to "
                    "keep compression working.",
                    aux_model,
                    aux_context,
                    old_threshold,
                    new_threshold,
                )
        except ValueError:
            # Hard rejections (aux below minimum context) must propagate
            # so the session refuses to start.
            raise
        except Exception as exc:
            logger.debug(
                "Compression feasibility check failed (non-fatal): %s", exc
            )

    def _replay_compression_warning(self) -> None:
        """Re-send the compression warning through ``status_callback``.

        During ``__init__`` the gateway's ``status_callback`` is not yet
        wired, so ``_emit_status`` only reaches ``_vprint`` (CLI).  This
        method is called once at the start of the first
        ``run_conversation()`` — by then the gateway has set the callback,
        so every platform (Telegram, Discord, Slack, etc.) receives the
        warning.
        """
        msg = getattr(self, "_compression_warning", None)
        if msg and self.status_callback:
            try:
                self.status_callback("lifecycle", msg)
            except Exception:
                pass

    def _is_direct_openai_url(self, base_url: str = None) -> bool:
        """Return True when a base URL targets OpenAI's native API."""
        if base_url is not None:
            hostname = base_url_hostname(base_url)
        else:
            hostname = getattr(self, "_base_url_hostname", "") or base_url_hostname(
                getattr(self, "_base_url_lower", "")
            )
        return hostname == "api.openai.com"

    def _is_azure_openai_url(self, base_url: str = None) -> bool:
        """Return True when a base URL targets Azure OpenAI.

        Azure OpenAI exposes an OpenAI-compatible endpoint at
        ``{resource}.openai.azure.com/openai/v1`` that accepts the
        standard ``openai`` Python client.  Unlike api.openai.com it
        does NOT support the Responses API — gpt-5.x models are served
        on the regular ``/chat/completions`` path — so routing decisions
        must treat Azure separately from direct OpenAI.
        """
        if base_url is not None:
            url = str(base_url).lower()
        else:
            url = getattr(self, "_base_url_lower", "") or ""
        return "openai.azure.com" in url

    def _is_github_copilot_url(self, base_url: str = None) -> bool:
        """Return True when a base URL targets GitHub Copilot's OpenAI-compatible API."""
        if base_url is not None:
            hostname = base_url_hostname(base_url)
        else:
            hostname = getattr(self, "_base_url_hostname", "") or base_url_hostname(
                getattr(self, "_base_url_lower", "")
            )
        return hostname == "api.githubcopilot.com"

    def _resolved_api_call_timeout(self) -> float:
        """Resolve the effective per-call request timeout in seconds.

        Priority:
          1. ``providers.<id>.models.<model>.timeout_seconds`` (per-model override)
          2. ``providers.<id>.request_timeout_seconds`` (provider-wide)
          3. ``ICECODE_API_TIMEOUT`` env var (legacy escape hatch)
          4. 1800.0s default

        Used by OpenAI-wire chat completions (streaming and non-streaming) so
        the per-provider config knob wins over the 1800s default.  Without this
        helper, the hardcoded ``ICECODE_API_TIMEOUT`` fallback would always be
        passed as a per-call ``timeout=`` kwarg, overriding the client-level
        timeout the AIAgent.__init__ path configured.
        """
        cfg = get_provider_request_timeout(self.provider, self.model)
        if cfg is not None:
            return cfg
        return float(os.getenv("ICECODE_API_TIMEOUT", 1800.0))

    def _resolved_api_call_stale_timeout_base(self) -> tuple[float, bool]:
        """Resolve the base non-stream stale timeout and whether it is implicit.

        Priority:
          1. ``providers.<id>.models.<model>.stale_timeout_seconds``
          2. ``providers.<id>.stale_timeout_seconds``
          3. ``ICECODE_API_CALL_STALE_TIMEOUT`` env var
          4. 300.0s default

        Returns ``(timeout_seconds, uses_implicit_default)`` so the caller can
        preserve legacy behaviors that only apply when the user has *not*
        explicitly configured a stale timeout, such as auto-disabling the
        detector for local endpoints.
        """
        cfg = get_provider_stale_timeout(self.provider, self.model)
        if cfg is not None:
            return cfg, False

        env_timeout = os.getenv("ICECODE_API_CALL_STALE_TIMEOUT")
        if env_timeout is not None:
            return float(env_timeout), False

        return 300.0, True

    def _compute_non_stream_stale_timeout(self, messages: list[dict[str, Any]]) -> float:
        """Compute the effective non-stream stale timeout for this request."""
        stale_base, uses_implicit_default = self._resolved_api_call_stale_timeout_base()
        base_url = getattr(self, "_base_url", None) or self.base_url or ""
        if uses_implicit_default and base_url and is_local_endpoint(base_url):
            return float("inf")

        est_tokens = sum(len(str(v)) for v in messages) // 4
        if est_tokens > 100_000:
            return max(stale_base, 600.0)
        if est_tokens > 50_000:
            return max(stale_base, 450.0)
        return stale_base

    def _is_openrouter_url(self) -> bool:
        """Return True when the base URL targets OpenRouter."""
        return base_url_host_matches(self._base_url_lower, "openrouter.ai")

    def _anthropic_prompt_cache_policy(
        self,
        *,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        api_mode: Optional[str] = None,
        model: Optional[str] = None,
    ) -> tuple[bool, bool]:
        """Decide whether to apply Anthropic prompt caching and which layout to use.

        Returns ``(should_cache, use_native_layout)``:
          * ``should_cache`` — inject ``cache_control`` breakpoints for this
            request (applies to OpenRouter Claude, native Anthropic, and
            third-party gateways that speak the native Anthropic protocol).
          * ``use_native_layout`` — place markers on the *inner* content
            blocks (native Anthropic accepts and requires this layout);
            when False markers go on the message envelope (OpenRouter and
            OpenAI-wire proxies expect the looser layout).

        Third-party providers using the native Anthropic transport
        (``api_mode == 'anthropic_messages'`` + Claude-named model) get
        caching with the native layout so they benefit from the same
        cost reduction as direct Anthropic callers, provided their
        gateway implements the Anthropic cache_control contract
        (MiniMax, Zhipu GLM, LiteLLM's Anthropic proxy mode all do).

        Qwen / Alibaba-family models on OpenCode, OpenCode Go, and direct
        Alibaba (DashScope) also honour Anthropic-style ``cache_control``
        markers on OpenAI-wire chat completions. Upstream pi-mono #3392 /
        pi #3393 documented this for opencode-go Qwen. Without markers
        these providers serve zero cache hits, re-billing the full prompt
        on every turn.
        """
        eff_provider = (provider if provider is not None else self.provider) or ""
        eff_base_url = base_url if base_url is not None else (self.base_url or "")
        eff_api_mode = api_mode if api_mode is not None else (self.api_mode or "")
        eff_model = (model if model is not None else self.model) or ""

        model_lower = eff_model.lower()
        provider_lower = eff_provider.lower()
        is_claude = "claude" in model_lower
        is_openrouter = base_url_host_matches(eff_base_url, "openrouter.ai")
        # Nous Portal proxies to OpenRouter behind the scenes — identical
        # OpenAI-wire envelope cache_control semantics. Treat it as an
        # OpenRouter-equivalent endpoint for caching layout purposes.
        is_nous_portal = "nousresearch" in eff_base_url.lower()
        is_anthropic_wire = eff_api_mode == "anthropic_messages"
        is_native_anthropic = (
            is_anthropic_wire
            and (eff_provider == "anthropic" or base_url_hostname(eff_base_url) == "api.anthropic.com")
        )

        if is_native_anthropic:
            return True, True
        if (is_openrouter or is_nous_portal) and is_claude:
            return True, False
        # Nous Portal Qwen (e.g. qwen3.6-plus) takes the same envelope-layout
        # cache_control path as Portal Claude. Portal proxies to OpenRouter
        # and the upstream Qwen route accepts cache_control markers; without
        # this branch the alibaba-family check below only matches
        # provider=opencode/alibaba and Portal traffic falls through to
        # (False, False), serving 0% cache hits and re-billing the full
        # prompt on every turn.
        if is_nous_portal and "qwen" in model_lower:
            return True, False
        if is_anthropic_wire and is_claude:
            # Third-party Anthropic-compatible gateway.
            return True, True

        # MiniMax on its Anthropic-compatible endpoint serves its own
        # model family (MiniMax-M2.7, M2.5, M2.1, M2) with documented
        # cache_control support (0.1× read pricing, 5-minute TTL).  The
        # blanket is_claude gate above excludes these — opt them in
        # explicitly via provider id or host match so users on
        # provider=minimax / minimax-cn (or custom endpoints pointing at
        # api.minimax.io/anthropic / api.minimaxi.com/anthropic) get the
        # same cost reduction as Claude traffic.
        # Docs: https://platform.minimax.io/docs/api-reference/anthropic-api-compatible-cache
        if is_anthropic_wire:
            is_minimax_provider = provider_lower in {"minimax", "minimax-cn"}
            is_minimax_host = (
                base_url_host_matches(eff_base_url, "api.minimax.io")
                or base_url_host_matches(eff_base_url, "api.minimaxi.com")
            )
            if is_minimax_provider or is_minimax_host:
                return True, True

        # Qwen/Alibaba on OpenCode (Zen/Go) and native DashScope: OpenAI-wire
        # transport that accepts Anthropic-style cache_control markers and
        # rewards them with real cache hits.  Without this branch
        # qwen3.6-plus on opencode-go reports 0% cached tokens and burns
        # through the subscription on every turn.
        model_is_qwen = "qwen" in model_lower
        provider_is_alibaba_family = provider_lower in {
            "opencode", "opencode-zen", "opencode-go", "alibaba",
        }
        if provider_is_alibaba_family and model_is_qwen:
            # Envelope layout (native_anthropic=False): markers on inner
            # content parts, not top-level tool messages.  Matches
            # pi-mono's "alibaba" cacheControlFormat.
            return True, False

        return False, False

    @staticmethod
    def _model_requires_responses_api(model: str) -> bool:
        """Return True for models that require the Responses API path.

        GPT-5.x models are rejected on /v1/chat/completions by both
        OpenAI and OpenRouter (error: ``unsupported_api_for_model``).
        Detect these so the correct api_mode is set regardless of
        which provider is serving the model.
        """
        m = model.lower()
        # Strip vendor prefix (e.g. "openai/gpt-5.4" → "gpt-5.4")
        if "/" in m:
            m = m.rsplit("/", 1)[-1]
        return m.startswith("gpt-5")

    @staticmethod
    def _provider_model_requires_responses_api(
        model: str,
        *,
        provider: Optional[str] = None,
    ) -> bool:
        """Return True when this provider/model pair should use Responses API."""
        normalized_provider = (provider or "").strip().lower()
        # Nous serves GPT-5.x models via its OpenAI-compatible chat
        # completions endpoint; its /v1/responses endpoint returns 404.
        if normalized_provider == "nous":
            return False
        if normalized_provider == "copilot":
            try:
                from icecode_cli.hermes_cli.models import _should_use_copilot_responses_api
                return _should_use_copilot_responses_api(model)
            except Exception:
                # Fall back to the generic GPT-5 rule if Copilot-specific
                # logic is unavailable for any reason.
                pass
        return AIAgent._model_requires_responses_api(model)

    def _max_tokens_param(self, value: int) -> dict:
        """Return the correct max tokens kwarg for the current provider.

        OpenAI's newer models (gpt-4o, o-series, gpt-5+) require
        'max_completion_tokens'. Azure OpenAI also requires
        'max_completion_tokens' for gpt-5.x models served via the
        OpenAI-compatible endpoint. OpenRouter, local models, and older
        OpenAI models use 'max_tokens'.
        """
        if self._is_direct_openai_url() or self._is_azure_openai_url() or self._is_github_copilot_url():
            return {"max_completion_tokens": value}
        return {"max_tokens": value}

    def _has_content_after_think_block(self, content: str) -> bool:
        """
        Check if content has actual text after any reasoning/thinking blocks.

        This detects cases where the model only outputs reasoning but no actual
        response, which indicates an incomplete generation that should be retried.
        Must stay in sync with _strip_think_blocks() tag variants.

        Args:
            content: The assistant message content to check

        Returns:
            True if there's meaningful content after think blocks, False otherwise
        """
        if not content:
            return False

        # Remove all reasoning tag variants (must match _strip_think_blocks)
        cleaned = self._strip_think_blocks(content)

        # Check if there's any non-whitespace content remaining
        return bool(cleaned.strip())

    def _strip_think_blocks(self, content: str) -> str:
        """Remove reasoning/thinking blocks from content, returning only visible text.

        Handles four cases:
          1. Closed tag pairs (``<think>…</think>``) — the common path when
             the provider emits complete reasoning blocks.
          2. Unterminated open tag at a block boundary (start of text or
             after a newline) — e.g. MiniMax M2.7 / NIM endpoints where the
             closing tag is dropped.  Everything from the open tag to end
             of string is stripped.  The block-boundary check mirrors
             ``gateway/stream_consumer.py``'s filter so models that mention
             ``<think>`` in prose aren't over-stripped.
          3. Stray orphan open/close tags that slip through.
          4. Tag variants: ``<think>``, ``<thinking>``, ``<reasoning>``,
             ``<REASONING_SCRATCHPAD>``, ``<thought>`` (Gemma 4), all
             case-insensitive.

        Additionally strips standalone tool-call XML blocks that some open
        models (notably Gemma variants on OpenRouter) emit inside assistant
        content instead of via the structured ``tool_calls`` field:
          * ``<tool_call>…</tool_call>``
          * ``<tool_calls>…</tool_calls>``
          * ``<tool_result>…</tool_result>``
          * ``<function_call>…</function_call>``
          * ``<function_calls>…</function_calls>``
          * ``<function name="…">…</function>`` (Gemma style)
        Ported from openclaw/openclaw#67318. The ``<function>`` variant is
        boundary-gated (only strips when the tag sits at start-of-line or
        after punctuation and carries a ``name="..."`` attribute) so prose
        mentions like "Use <function> in JavaScript" are preserved.
        """
        if not content:
            return ""
        # 1. Closed tag pairs — case-insensitive for all variants so
        #    mixed-case tags (<THINK>, <Thinking>) don't slip through to
        #    the unterminated-tag pass and take trailing content with them.
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<thinking>.*?</thinking>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<reasoning>.*?</reasoning>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<REASONING_SCRATCHPAD>.*?</REASONING_SCRATCHPAD>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL | re.IGNORECASE)
        # 1b. Tool-call XML blocks (openclaw/openclaw#67318). Handle the
        #     generic tag names first — they have no attribute gating since
        #     a literal <tool_call> in prose is already vanishingly rare.
        for _tc_name in ("tool_call", "tool_calls", "tool_result",
                          "function_call", "function_calls"):
            content = re.sub(
                rf'<{_tc_name}\b[^>]*>.*?</{_tc_name}>',
                '',
                content,
                flags=re.DOTALL | re.IGNORECASE,
            )
        # 1c. <function name="...">...</function> — Gemma-style standalone
        #     tool call. Only strip when the tag sits at a block boundary
        #     (start of text, after a newline, or after sentence-ending
        #     punctuation) AND carries a name="..." attribute. This keeps
        #     prose mentions like "Use <function> to declare" safe.
        content = re.sub(
            r'(?:(?<=^)|(?<=[\n\r.!?:]))[ \t]*'
            r'<function\b[^>]*\bname\s*=[^>]*>'
            r'(?:(?:(?!</function>).)*)</function>',
            '',
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # 2. Unterminated reasoning block — open tag at a block boundary
        #    (start of text, or after a newline) with no matching close.
        #    Strip from the tag to end of string.  Fixes #8878 / #9568
        #    (MiniMax M2.7 leaking raw reasoning into assistant content).
        content = re.sub(
            r'(?:^|\n)[ \t]*<(?:think|thinking|reasoning|thought|REASONING_SCRATCHPAD)\b[^>]*>.*$',
            '',
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # 3. Stray orphan open/close tags that slipped through.
        content = re.sub(
            r'</?(?:think|thinking|reasoning|thought|REASONING_SCRATCHPAD)>\s*',
            '',
            content,
            flags=re.IGNORECASE,
        )
        # 3b. Stray tool-call closers. (We do NOT strip bare <function> or
        #     unterminated <function name="..."> because a truncated tail
        #     during streaming may still be valuable to the user; matches
        #     OpenClaw's intentional asymmetry.)
        content = re.sub(
            r'</(?:tool_call|tool_calls|tool_result|function_call|function_calls|function)>\s*',
            '',
            content,
            flags=re.IGNORECASE,
        )
        return content

    @staticmethod
    def _has_natural_response_ending(content: str) -> bool:
        """Heuristic: does visible assistant text look intentionally finished?"""
        if not content:
            return False
        stripped = content.rstrip()
        if not stripped:
            return False
        if stripped.endswith("```"):
            return True
        return stripped[-1] in '.!?:)"\']}。！？：）】」』》'

    def _is_ollama_glm_backend(self) -> bool:
        """Detect the narrow backend family affected by Ollama/GLM stop misreports."""
        model_lower = (self.model or "").lower()
        provider_lower = (self.provider or "").lower()
        if "glm" not in model_lower and provider_lower != "zai":
            return False
        if "ollama" in self._base_url_lower or ":11434" in self._base_url_lower:
            return True
        return bool(self.base_url and is_local_endpoint(self.base_url))

    def _should_treat_stop_as_truncated(
        self,
        finish_reason: str,
        assistant_message,
        messages: Optional[list] = None,
    ) -> bool:
        """Detect conservative stop->length misreports for Ollama-hosted GLM models."""
        if finish_reason != "stop" or self.api_mode != "chat_completions":
            return False
        if not self._is_ollama_glm_backend():
            return False
        if not any(
            isinstance(msg, dict) and msg.get("role") == "tool"
            for msg in (messages or [])
        ):
            return False
        if assistant_message is None or getattr(assistant_message, "tool_calls", None):
            return False

        content = getattr(assistant_message, "content", None)
        if not isinstance(content, str):
            return False

        visible_text = self._strip_think_blocks(content).strip()
        if not visible_text:
            return False
        if len(visible_text) < 20 or not re.search(r"\s", visible_text):
            return False

        return not self._has_natural_response_ending(visible_text)

    def _looks_like_codex_intermediate_ack(
        self,
        user_message: str,
        assistant_content: str,
        messages: List[Dict[str, Any]],
    ) -> bool:
        """Detect a planning/ack message that should continue instead of ending the turn."""
        if any(isinstance(msg, dict) and msg.get("role") == "tool" for msg in messages):
            return False

        assistant_text = self._strip_think_blocks(assistant_content or "").strip().lower()
        if not assistant_text:
            return False
        if len(assistant_text) > 1200:
            return False

        has_future_ack = bool(
            re.search(r"\b(i['’]ll|i will|let me|i can do that|i can help with that)\b", assistant_text)
        )
        if not has_future_ack:
            return False

        action_markers = (
            "look into",
            "look at",
            "inspect",
            "scan",
            "check",
            "analyz",
            "review",
            "explore",
            "read",
            "open",
            "run",
            "test",
            "fix",
            "debug",
            "search",
            "find",
            "walkthrough",
            "report back",
            "summarize",
        )
        workspace_markers = (
            "directory",
            "current directory",
            "current dir",
            "cwd",
            "repo",
            "repository",
            "codebase",
            "project",
            "folder",
            "filesystem",
            "file tree",
            "files",
            "path",
        )

        user_text = (user_message or "").strip().lower()
        user_targets_workspace = (
            any(marker in user_text for marker in workspace_markers)
            or "~/" in user_text
            or "/" in user_text
        )
        assistant_mentions_action = any(marker in assistant_text for marker in action_markers)
        assistant_targets_workspace = any(
            marker in assistant_text for marker in workspace_markers
        )
        return (user_targets_workspace or assistant_targets_workspace) and assistant_mentions_action


    def _extract_reasoning(self, assistant_message) -> Optional[str]:
        """
        Extract reasoning/thinking content from an assistant message.
        
        OpenRouter and various providers can return reasoning in multiple formats:
        1. message.reasoning - Direct reasoning field (DeepSeek, Qwen, etc.)
        2. message.reasoning_content - Alternative field (Moonshot AI, Novita, etc.)
        3. message.reasoning_details - Array of {type, summary, ...} objects (OpenRouter unified)
        
        Args:
            assistant_message: The assistant message object from the API response
            
        Returns:
            Combined reasoning text, or None if no reasoning found
        """
        reasoning_parts = []
        
        # Check direct reasoning field
        if hasattr(assistant_message, 'reasoning') and assistant_message.reasoning:
            reasoning_parts.append(assistant_message.reasoning)
        
        # Check reasoning_content field (alternative name used by some providers)
        if hasattr(assistant_message, 'reasoning_content') and assistant_message.reasoning_content:
            # Don't duplicate if same as reasoning
            if assistant_message.reasoning_content not in reasoning_parts:
                reasoning_parts.append(assistant_message.reasoning_content)
        
        # Check reasoning_details array (OpenRouter unified format)
        # Format: [{"type": "reasoning.summary", "summary": "...", ...}, ...]
        if hasattr(assistant_message, 'reasoning_details') and assistant_message.reasoning_details:
            for detail in assistant_message.reasoning_details:
                if isinstance(detail, dict):
                    # Extract summary from reasoning detail object
                    summary = (
                        detail.get('summary')
                        or detail.get('thinking')
                        or detail.get('content')
                        or detail.get('text')
                    )
                    if summary and summary not in reasoning_parts:
                        reasoning_parts.append(summary)

        # Some providers embed reasoning directly inside assistant content
        # instead of returning structured reasoning fields.  Only fall back
        # to inline extraction when no structured reasoning was found.
        content = getattr(assistant_message, "content", None)
        if not reasoning_parts and isinstance(content, list):
            # DeepSeek V4 Pro (and compatible providers) return content as a
            # list of typed blocks, e.g.:
            #   [{"type": "thinking", "thinking": "..."}, {"type": "output", ...}]
            # Without this branch the thinking text is silently dropped and the
            # next turn fails with HTTP 400 ("thinking must be passed back").
            # Refs #21944.
            for block in content:
                if isinstance(block, dict) and block.get("type") == "thinking":
                    thinking_text = block.get("thinking") or block.get("text") or ""
                    thinking_text = thinking_text.strip()
                    if thinking_text and thinking_text not in reasoning_parts:
                        reasoning_parts.append(thinking_text)
        if not reasoning_parts and isinstance(content, str) and content:
            inline_patterns = (
                r"<think>(.*?)</think>",
                r"<thinking>(.*?)</thinking>",
                r"<thought>(.*?)</thought>",
                r"<reasoning>(.*?)</reasoning>",
                r"<REASONING_SCRATCHPAD>(.*?)</REASONING_SCRATCHPAD>",
            )
            for pattern in inline_patterns:
                flags = re.DOTALL | re.IGNORECASE
                for block in re.findall(pattern, content, flags=flags):
                    cleaned = block.strip()
                    if cleaned and cleaned not in reasoning_parts:
                        reasoning_parts.append(cleaned)
        
        # Combine all reasoning parts
        if reasoning_parts:
            return "\n\n".join(reasoning_parts)
        
        return None

