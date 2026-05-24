"""engine_messages_mixin — Message prep, API kwargs, reasoning, and context compression.

Builds provider-specific message lists, API call kwargs, vision content
preprocessing, reasoning token handling, context compression, and tool
guardrail helpers. Extracted from engine_api_mixin.
"""
from __future__ import annotations

import base64
import copy
import json
import logging
import os
import random
import re
import ssl
import sys
import threading
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs, urlunparse

try:
    from icecode.icecode_constants import get_hermes_home
    from icecode.agent.engine_sanitize import (
        _sanitize_surrogates,
        _sanitize_messages_surrogates,
        _sanitize_structure_surrogates,
        _escape_invalid_chars_in_json_strings,
        _repair_tool_call_arguments,
        _strip_images_from_messages,
    )
    from icecode.agent.engine_multimodal import (
        _is_multimodal_tool_result,
        _multimodal_text_summary,
        _extract_error_preview,
    )
    from icecode.agent.error_classifier import classify_api_error, FailoverReason
    from icecode.agent.display import KawaiiSpinner
except (ImportError, AttributeError):
    def get_hermes_home():
        from pathlib import Path
        return Path.home() / ".icecode"
    def _sanitize_surrogates(s, *a, **kw): return s
    def _sanitize_messages_surrogates(m, *a, **kw): return m
    def _sanitize_structure_surrogates(s, *a, **kw): return s
    def _escape_invalid_chars_in_json_strings(*a, **kw): return a[0] if a else ""
    def _repair_tool_call_arguments(*a, **kw): return a[0] if a else ""
    def _strip_images_from_messages(m, *a, **kw): return m
    def _is_multimodal_tool_result(*a, **kw): return False
    def _multimodal_text_summary(*a, **kw): return str(a[0]) if a else ""
    def _extract_error_preview(*a, **kw): return ""
    def classify_api_error(*a, **kw): return None
    class FailoverReason:  # type: ignore[no-redef]
        pass
    class KawaiiSpinner:  # type: ignore[no-redef]
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self, *a, **kw): pass
        @staticmethod
        def get_waiting_faces(): return ["(✿◠‿◠)"]

_OPENAI_CLS_CACHE = None

def _load_openai_cls():
    global _OPENAI_CLS_CACHE
    if _OPENAI_CLS_CACHE is None:
        try:
            from openai import OpenAI as _cls
            _OPENAI_CLS_CACHE = _cls
        except ImportError:
            _OPENAI_CLS_CACHE = object
    return _OPENAI_CLS_CACHE

logger = logging.getLogger(__name__)




class _MessagesMixin:
    """Message preparation, API kwargs construction, vision, reasoning, and guardrails."""

    # ── End provider fallback ──────────────────────────────────────────────

    @staticmethod
    def _content_has_image_parts(content: Any) -> bool:
        if not isinstance(content, list):
            return False
        for part in content:
            if isinstance(part, dict) and part.get("type") in {"image_url", "input_image"}:
                return True
        return False

    @staticmethod
    def _materialize_data_url_for_vision(image_url: str) -> tuple[str, Optional[Path]]:
        header, _, data = str(image_url or "").partition(",")
        mime = "image/jpeg"
        if header.startswith("data:"):
            mime_part = header[len("data:"):].split(";", 1)[0].strip()
            if mime_part.startswith("image/"):
                mime = mime_part
        suffix = {
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
        }.get(mime, ".jpg")
        tmp = tempfile.NamedTemporaryFile(prefix="anthropic_image_", suffix=suffix, delete=False)
        try:
            with tmp:
                tmp.write(base64.b64decode(data))
        except Exception:
            # delete=False means a corrupt/unsupported data URL would otherwise
            # leak a zero-byte temp file on every failed materialization.
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise
        path = Path(tmp.name)
        return str(path), path

    def _describe_image_for_anthropic_fallback(self, image_url: str, role: str) -> str:
        cache_key = hashlib.sha256(str(image_url or "").encode("utf-8")).hexdigest()
        cached = self._anthropic_image_fallback_cache.get(cache_key)
        if cached:
            return cached

        role_label = {
            "assistant": "assistant",
            "tool": "tool result",
        }.get(role, "user")
        analysis_prompt = (
            "Describe everything visible in this image in thorough detail. "
            "Include any text, code, UI, data, objects, people, layout, colors, "
            "and any other notable visual information."
        )

        vision_source = str(image_url or "")
        cleanup_path: Optional[Path] = None
        if vision_source.startswith("data:"):
            vision_source, cleanup_path = self._materialize_data_url_for_vision(vision_source)

        description = ""
        try:
            from icecode_tools.vision_tools import vision_analyze_tool

            result_json = asyncio.run(
                vision_analyze_tool(image_url=vision_source, user_prompt=analysis_prompt)
            )
            result = json.loads(result_json) if isinstance(result_json, str) else {}
            description = (result.get("analysis") or "").strip()
        except Exception as e:
            description = f"Image analysis failed: {e}"
        finally:
            if cleanup_path and cleanup_path.exists():
                try:
                    cleanup_path.unlink()
                except OSError:
                    pass

        if not description:
            description = "Image analysis failed."

        note = f"[The {role_label} attached an image. Here's what it contains:\n{description}]"
        if vision_source and not str(image_url or "").startswith("data:"):
            note += (
                f"\n[If you need a closer look, use vision_analyze with image_url: {vision_source}]"
            )

        self._anthropic_image_fallback_cache[cache_key] = note
        return note

    def _model_supports_vision(self) -> bool:
        """Return True if the active provider+model reports native vision.

        Used to decide whether to strip image content parts from API-bound
        messages (for non-vision models) or let the provider adapter handle
        them natively (for vision-capable models).
        """
        try:
            from icecode.agent.models_dev import get_model_capabilities
            provider = (getattr(self, "provider", "") or "").strip()
            model = (getattr(self, "model", "") or "").strip()
            if not provider or not model:
                return False
            caps = get_model_capabilities(provider, model)
            if caps is None:
                return False
            return bool(caps.supports_vision)
        except Exception:
            return False

    def _preprocess_anthropic_content(self, content: Any, role: str) -> Any:
        if not self._content_has_image_parts(content):
            return content

        text_parts: List[str] = []
        image_notes: List[str] = []
        for part in content:
            if isinstance(part, str):
                if part.strip():
                    text_parts.append(part.strip())
                continue
            if not isinstance(part, dict):
                continue

            ptype = part.get("type")
            if ptype in {"text", "input_text"}:
                text = str(part.get("text", "") or "").strip()
                if text:
                    text_parts.append(text)
                continue

            if ptype in {"image_url", "input_image"}:
                image_data = part.get("image_url", {})
                image_url = image_data.get("url", "") if isinstance(image_data, dict) else str(image_data or "")
                if image_url:
                    image_notes.append(self._describe_image_for_anthropic_fallback(image_url, role))
                else:
                    image_notes.append("[An image was attached but no image source was available.]")
                continue

            text = str(part.get("text", "") or "").strip()
            if text:
                text_parts.append(text)

        prefix = "\n\n".join(note for note in image_notes if note).strip()
        suffix = "\n".join(text for text in text_parts if text).strip()
        if prefix and suffix:
            return f"{prefix}\n\n{suffix}"
        if prefix:
            return prefix
        if suffix:
            return suffix
        return "[A multimodal message was converted to text for Anthropic compatibility.]"

    def _get_transport(self, api_mode: str = None):
        """Return the cached transport for the given (or current) api_mode.

        Lazy-initializes on first call per api_mode. Returns None if no
        transport is registered for the mode.
        """
        mode = api_mode or self.api_mode
        cache = getattr(self, "_transport_cache", None)
        if cache is None:
            cache = {}
            self._transport_cache = cache
        t = cache.get(mode)
        if t is None:
            from icecode.agent.transports import get_transport
            t = get_transport(mode)
            cache[mode] = t
        return t

    def _prepare_anthropic_messages_for_api(self, api_messages: list) -> list:
        # Fast exit when no message carries image content at all.
        if not any(
            isinstance(msg, dict) and self._content_has_image_parts(msg.get("content"))
            for msg in api_messages
        ):
            return api_messages

        # The Anthropic adapter (agent/anthropic_adapter.py:_convert_content_part_to_anthropic)
        # already translates OpenAI-style image_url/input_image parts into
        # native Anthropic ``{"type": "image", "source": ...}`` blocks. When
        # the active model supports vision we let the adapter do its job and
        # skip this legacy text-fallback preprocessor entirely.
        if self._model_supports_vision():
            return api_messages

        # Non-vision Anthropic model (rare today, but keep the fallback for
        # compat): replace each image part with a vision_analyze text note.
        transformed = copy.deepcopy(api_messages)
        for msg in transformed:
            if not isinstance(msg, dict):
                continue
            msg["content"] = self._preprocess_anthropic_content(
                msg.get("content"),
                str(msg.get("role", "user") or "user"),
            )
        return transformed

    def _prepare_messages_for_non_vision_model(self, api_messages: list) -> list:
        """Strip native image parts when the active model lacks vision.

        Runs on the chat.completions / codex_responses paths. Vision-capable
        models pass through unchanged (provider and any downstream translator
        handle the image parts natively). Non-vision models get each image
        replaced by a cached vision_analyze text description so the turn
        doesn't fail with "model does not support image input".
        """
        if not any(
            isinstance(msg, dict) and self._content_has_image_parts(msg.get("content"))
            for msg in api_messages
        ):
            return api_messages

        if self._model_supports_vision():
            return api_messages

        transformed = copy.deepcopy(api_messages)
        for msg in transformed:
            if not isinstance(msg, dict):
                continue
            # Reuse the Anthropic text-fallback preprocessor — the behaviour is
            # identical (walk content parts, replace images with cached
            # descriptions, merge back into a single text or structured
            # content). Naming is historical.
            msg["content"] = self._preprocess_anthropic_content(
                msg.get("content"),
                str(msg.get("role", "user") or "user"),
            )
        return transformed

    def _try_shrink_image_parts_in_messages(self, api_messages: list) -> bool:
        """Re-encode all native image parts at a smaller size to recover from
        image-too-large errors (Anthropic 5 MB, unknown other providers).

        Mutates ``api_messages`` in place. Returns True if any image part was
        actually replaced, False if there were no image parts to shrink or
        Pillow couldn't help (caller should surface the original error).

        Strategy: look for ``image_url`` / ``input_image`` parts carrying a
        ``data:image/...;base64,...`` payload.  For each one whose encoded
        size exceeds 4 MB (a safe target that slides under Anthropic's 5 MB
        ceiling with header overhead), write the base64 to a tempfile, call
        ``vision_tools._resize_image_for_vision`` to produce a smaller data
        URL, and substitute it in place.

        Non-data-URL images (http/https URLs) are not touched — the provider
        fetches those itself and the size limit is different.
        """
        if not api_messages:
            return False

        try:
            from icecode_tools.vision_tools import _resize_image_for_vision
        except Exception as exc:
            logger.warning("image-shrink recovery: vision_tools unavailable — %s", exc)
            return False

        # 4 MB target leaves comfortable headroom under Anthropic's 5 MB.
        # Non-Anthropic providers we haven't observed rejecting are fine with
        # much larger; shrinking to 4 MB here loses quality but only fires
        # after a confirmed provider rejection, so the alternative is failure.
        target_bytes = 4 * 1024 * 1024
        changed_count = 0

        def _shrink_data_url(url: str) -> Optional[str]:
            """Return a smaller data URL, or None if shrink can't help."""
            if not isinstance(url, str) or not url.startswith("data:"):
                return None
            if len(url) <= target_bytes:
                # This specific image wasn't the oversized one.
                return None
            try:
                header, _, data = url.partition(",")
                mime = "image/jpeg"
                if header.startswith("data:"):
                    mime_part = header[len("data:"):].split(";", 1)[0].strip()
                    if mime_part.startswith("image/"):
                        mime = mime_part
                import base64 as _b64
                raw = _b64.b64decode(data)
                suffix = {
                    "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp",
                    "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/bmp": ".bmp",
                }.get(mime, ".jpg")
                tmp = tempfile.NamedTemporaryFile(
                    prefix="hermes_shrink_", suffix=suffix, delete=False,
                )
                try:
                    tmp.write(raw)
                    tmp.close()
                    resized = _resize_image_for_vision(
                        Path(tmp.name),
                        mime_type=mime,
                        max_base64_bytes=target_bytes,
                    )
                finally:
                    try:
                        Path(tmp.name).unlink(missing_ok=True)
                    except Exception:
                        pass
                if not resized or len(resized) >= len(url):
                    # Shrink didn't help (or made it bigger — corrupt input?).
                    return None
                return resized
            except Exception as exc:
                logger.warning("image-shrink recovery: re-encode failed — %s", exc)
                return None

        for msg in api_messages:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype not in {"image_url", "input_image"}:
                    continue
                image_value = part.get("image_url")
                # OpenAI chat.completions: {"image_url": {"url": "data:..."}}
                # OpenAI Responses: {"image_url": "data:..."}
                if isinstance(image_value, dict):
                    url = image_value.get("url", "")
                    resized = _shrink_data_url(url)
                    if resized:
                        image_value["url"] = resized
                        changed_count += 1
                elif isinstance(image_value, str):
                    resized = _shrink_data_url(image_value)
                    if resized:
                        part["image_url"] = resized
                        changed_count += 1

        if changed_count:
            logger.info(
                "image-shrink recovery: re-encoded %d image part(s) to fit under %.0f MB",
                changed_count, target_bytes / (1024 * 1024),
            )
        return changed_count > 0

    def _anthropic_preserve_dots(self) -> bool:
        """True when using an anthropic-compatible endpoint that preserves dots in model names.
        Alibaba/DashScope keeps dots (e.g. qwen3.5-plus).
        MiniMax keeps dots (e.g. MiniMax-M2.7).
        Xiaomi MiMo keeps dots (e.g. mimo-v2.5, mimo-v2.5-pro).
        OpenCode Go/Zen keeps dots for non-Claude models (e.g. minimax-m2.5-free).
        ZAI/Zhipu keeps dots (e.g. glm-4.7, glm-5.1).
        AWS Bedrock uses dotted inference-profile IDs
        (e.g. ``global.anthropic.claude-opus-4-7``,
        ``us.anthropic.claude-sonnet-4-5-20250929-v1:0``) and rejects
        the hyphenated form with
        ``HTTP 400 The provided model identifier is invalid``.
        Regression for #11976; mirrors the opencode-go fix for #5211
        (commit f77be22c), which extended this same allowlist."""
        if (getattr(self, "provider", "") or "").lower() in {
            "alibaba", "minimax", "minimax-cn",
            "opencode-go", "opencode-zen",
            "zai", "bedrock",
            "xiaomi",
        }:
            return True
        base = (getattr(self, "base_url", "") or "").lower()
        return (
            "dashscope" in base
            or "aliyuncs" in base
            or "minimax" in base
            or "opencode.ai/zen/" in base
            or "bigmodel.cn" in base
            or "xiaomimimo.com" in base
            # AWS Bedrock runtime endpoints — defense-in-depth when
            # ``provider`` is unset but ``base_url`` still names Bedrock.
            or "bedrock-runtime." in base
        )

    def _is_qwen_portal(self) -> bool:
        """Return True when the base URL targets Qwen Portal."""
        return base_url_host_matches(self._base_url_lower, "portal.qwen.ai")

    def _qwen_prepare_chat_messages(self, api_messages: list) -> list:
        prepared = copy.deepcopy(api_messages)
        if not prepared:
            return prepared

        for msg in prepared:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if isinstance(content, str):
                msg["content"] = [{"type": "text", "text": content}]
            elif isinstance(content, list):
                # Normalize: convert bare strings to text dicts, keep dicts as-is.
                # deepcopy already created independent copies, no need for dict().
                normalized_parts = []
                for part in content:
                    if isinstance(part, str):
                        normalized_parts.append({"type": "text", "text": part})
                    elif isinstance(part, dict):
                        normalized_parts.append(part)
                if normalized_parts:
                    msg["content"] = normalized_parts

        # Inject cache_control on the last part of the system message.
        for msg in prepared:
            if isinstance(msg, dict) and msg.get("role") == "system":
                content = msg.get("content")
                if isinstance(content, list) and content and isinstance(content[-1], dict):
                    content[-1]["cache_control"] = {"type": "ephemeral"}
                break

        return prepared

    def _qwen_prepare_chat_messages_inplace(self, messages: list) -> None:
        """In-place variant — mutates an already-copied message list."""
        if not messages:
            return

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if isinstance(content, str):
                msg["content"] = [{"type": "text", "text": content}]
            elif isinstance(content, list):
                normalized_parts = []
                for part in content:
                    if isinstance(part, str):
                        normalized_parts.append({"type": "text", "text": part})
                    elif isinstance(part, dict):
                        normalized_parts.append(part)
                if normalized_parts:
                    msg["content"] = normalized_parts

        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "system":
                content = msg.get("content")
                if isinstance(content, list) and content and isinstance(content[-1], dict):
                    content[-1]["cache_control"] = {"type": "ephemeral"}
                break

    def _build_api_kwargs(self, api_messages: list) -> dict:
        """Build the keyword arguments dict for the active API mode."""
        tools_for_api = self.tools

        if self.api_mode == "anthropic_messages":
            _transport = self._get_transport()
            anthropic_messages = self._prepare_anthropic_messages_for_api(api_messages)
            ctx_len = getattr(self, "context_compressor", None)
            ctx_len = ctx_len.context_length if ctx_len else None
            ephemeral_out = getattr(self, "_ephemeral_max_output_tokens", None)
            if ephemeral_out is not None:
                self._ephemeral_max_output_tokens = None  # consume immediately
            return _transport.build_kwargs(
                model=self.model,
                messages=anthropic_messages,
                tools=tools_for_api,
                max_tokens=ephemeral_out if ephemeral_out is not None else self.max_tokens,
                reasoning_config=self.reasoning_config,
                is_oauth=self._is_anthropic_oauth,
                preserve_dots=self._anthropic_preserve_dots(),
                context_length=ctx_len,
                base_url=getattr(self, "_anthropic_base_url", None),
                fast_mode=(self.request_overrides or {}).get("speed") == "fast",
                drop_context_1m_beta=bool(getattr(self, "_oauth_1m_beta_disabled", False)),
            )

        # AWS Bedrock native Converse API — bypasses the OpenAI client entirely.
        # The adapter handles message/tool conversion and boto3 calls directly.
        if self.api_mode == "bedrock_converse":
            _bt = self._get_transport()
            region = getattr(self, "_bedrock_region", None) or "us-east-1"
            guardrail = getattr(self, "_bedrock_guardrail_config", None)
            return _bt.build_kwargs(
                model=self.model,
                messages=api_messages,
                tools=tools_for_api,
                max_tokens=self.max_tokens or 4096,
                region=region,
                guardrail_config=guardrail,
            )

        if self.api_mode == "codex_responses":
            _ct = self._get_transport()
            is_github_responses = (
                base_url_host_matches(self.base_url, "models.github.ai")
                or base_url_host_matches(self.base_url, "api.githubcopilot.com")
            )
            is_codex_backend = (
                self.provider == "openai-codex"
                or (
                    self._base_url_hostname == "chatgpt.com"
                    and "/backend-api/codex" in self._base_url_lower
                )
            )
            is_xai_responses = self.provider == "xai" or self._base_url_hostname == "api.x.ai"
            _msgs_for_codex = self._prepare_messages_for_non_vision_model(api_messages)
            return _ct.build_kwargs(
                model=self.model,
                messages=_msgs_for_codex,
                tools=tools_for_api,
                reasoning_config=self.reasoning_config,
                session_id=getattr(self, "session_id", None),
                max_tokens=self.max_tokens,
                request_overrides=self.request_overrides,
                is_github_responses=is_github_responses,
                is_codex_backend=is_codex_backend,
                is_xai_responses=is_xai_responses,
                github_reasoning_extra=self._github_models_reasoning_extra_body() if is_github_responses else None,
            )

        # ── chat_completions (default) ─────────────────────────────────────
        _ct = self._get_transport()

        # Provider detection flags
        _is_qwen = self._is_qwen_portal()
        _is_or = self._is_openrouter_url()
        _is_gh = (
            base_url_host_matches(self._base_url_lower, "models.github.ai")
            or base_url_host_matches(self._base_url_lower, "api.githubcopilot.com")
        )
        _is_nous = "nousresearch" in self._base_url_lower
        _is_nvidia = "integrate.api.nvidia.com" in self._base_url_lower
        _is_kimi = (
            base_url_host_matches(self.base_url, "api.kimi.com")
            or base_url_host_matches(self.base_url, "moonshot.ai")
            or base_url_host_matches(self.base_url, "moonshot.cn")
        )
        _is_tokenhub = base_url_host_matches(self._base_url_lower, "tokenhub.tencentmaas.com")
        _is_lmstudio = (self.provider or "").strip().lower() == "lmstudio"

        # Temperature: _fixed_temperature_for_model may return OMIT_TEMPERATURE
        # sentinel (temperature omitted entirely), a numeric override, or None.
        try:
            from icecode.agent.auxiliary_client import _fixed_temperature_for_model, OMIT_TEMPERATURE
            _ft = _fixed_temperature_for_model(self.model, self.base_url)
            _omit_temp = _ft is OMIT_TEMPERATURE
            _fixed_temp = _ft if not _omit_temp else None
        except Exception:
            _omit_temp = False
            _fixed_temp = None

        # Provider preferences (OpenRouter-style)
        _prefs: Dict[str, Any] = {}
        if self.providers_allowed:
            _prefs["only"] = self.providers_allowed
        if self.providers_ignored:
            _prefs["ignore"] = self.providers_ignored
        if self.providers_order:
            _prefs["order"] = self.providers_order
        if self.provider_sort:
            _prefs["sort"] = self.provider_sort
        if self.provider_require_parameters:
            _prefs["require_parameters"] = True
        if self.provider_data_collection:
            _prefs["data_collection"] = self.provider_data_collection

        # Claude max-output override on aggregators
        _ant_max = None
        if (_is_or or _is_nous) and "claude" in (self.model or "").lower():
            try:
                from icecode.agent.anthropic_adapter import _get_anthropic_max_output
                _ant_max = _get_anthropic_max_output(self.model)
            except Exception:
                pass

        # Qwen session metadata
        _qwen_meta = None
        if _is_qwen:
            _qwen_meta = {
                "sessionId": self.session_id or "hermes",
                "promptId": str(uuid.uuid4()),
            }

        # ── Provider profile path (registered providers) ───────────────────
        # Profiles handle per-provider quirks via hooks. When a profile is
        # found, delegate fully; otherwise fall through to the legacy flag path.
        try:
            from providers import get_provider_profile
            _profile = get_provider_profile(self.provider)
        except Exception:
            _profile = None

        if _profile:
            _ephemeral_out = getattr(self, "_ephemeral_max_output_tokens", None)
            if _ephemeral_out is not None:
                self._ephemeral_max_output_tokens = None

            return _ct.build_kwargs(
                model=self.model,
                messages=api_messages,
                tools=tools_for_api,
                base_url=self.base_url,
                timeout=self._resolved_api_call_timeout(),
                max_tokens=self.max_tokens,
                ephemeral_max_output_tokens=_ephemeral_out,
                max_tokens_param_fn=self._max_tokens_param,
                reasoning_config=self.reasoning_config,
                request_overrides=self.request_overrides,
                session_id=getattr(self, "session_id", None),
                provider_profile=_profile,
                ollama_num_ctx=self._ollama_num_ctx,
                # Context forwarded to profile hooks:
                provider_preferences=_prefs or None,
                openrouter_min_coding_score=self.openrouter_min_coding_score,
                anthropic_max_output=_ant_max,
                supports_reasoning=self._supports_reasoning_extra_body(),
                qwen_session_metadata=_qwen_meta,
            )

        # ── Legacy flag path ────────────────────────────────────────────
        # Reached only when get_provider_profile() returns None — i.e. a
        # completely unknown provider not in providers/ registry.
        _ephemeral_out = getattr(self, "_ephemeral_max_output_tokens", None)
        if _ephemeral_out is not None:
            self._ephemeral_max_output_tokens = None

        # Strip image parts for non-vision models (no-op when vision-capable).
        _msgs_for_chat = self._prepare_messages_for_non_vision_model(api_messages)

        return _ct.build_kwargs(
            model=self.model,
            messages=_msgs_for_chat,
            tools=tools_for_api,
            base_url=self.base_url,
            timeout=self._resolved_api_call_timeout(),
            max_tokens=self.max_tokens,
            ephemeral_max_output_tokens=_ephemeral_out,
            max_tokens_param_fn=self._max_tokens_param,
            reasoning_config=self.reasoning_config,
            request_overrides=self.request_overrides,
            session_id=getattr(self, "session_id", None),
            model_lower=(self.model or "").lower(),
            is_openrouter=_is_or,
            is_nous=_is_nous,
            is_qwen_portal=_is_qwen,
            is_github_models=_is_gh,
            is_nvidia_nim=_is_nvidia,
            is_kimi=_is_kimi,
            is_tokenhub=_is_tokenhub,
            is_lmstudio=_is_lmstudio,
            is_custom_provider=self.provider == "custom",
            ollama_num_ctx=self._ollama_num_ctx,
            provider_preferences=_prefs or None,
            openrouter_min_coding_score=self.openrouter_min_coding_score,
            qwen_prepare_fn=self._qwen_prepare_chat_messages if _is_qwen else None,
            qwen_prepare_inplace_fn=self._qwen_prepare_chat_messages_inplace if _is_qwen else None,
            qwen_session_metadata=_qwen_meta,
            fixed_temperature=_fixed_temp,
            omit_temperature=_omit_temp,
            supports_reasoning=self._supports_reasoning_extra_body(),
            github_reasoning_extra=self._github_models_reasoning_extra_body() if _is_gh else None,
            lmstudio_reasoning_options=self._lmstudio_reasoning_options_cached() if _is_lmstudio else None,
            anthropic_max_output=_ant_max,
            provider_name=self.provider,
        )

    def _supports_reasoning_extra_body(self) -> bool:
        """Return True when reasoning extra_body is safe to send for this route/model.

        OpenRouter forwards unknown extra_body fields to upstream providers.
        Some providers/routes reject `reasoning` with 400s, so gate it to
        known reasoning-capable model families and direct Nous Portal.
        """
        if base_url_host_matches(self._base_url_lower, "nousresearch.com"):
            return True
        if base_url_host_matches(self._base_url_lower, "ai-gateway.vercel.sh"):
            return True
        if (
            base_url_host_matches(self._base_url_lower, "models.github.ai")
            or base_url_host_matches(self._base_url_lower, "api.githubcopilot.com")
        ):
            try:
                from icecode_cli.hermes_cli.models import github_model_reasoning_efforts

                return bool(github_model_reasoning_efforts(self.model))
            except Exception:
                return False
        if (self.provider or "").strip().lower() == "lmstudio":
            opts = self._lmstudio_reasoning_options_cached()
            # "off-only" (or absent) means no real reasoning capability.
            return any(opt and opt != "off" for opt in opts)
        if "openrouter" not in self._base_url_lower:
            return False
        if "api.mistral.ai" in self._base_url_lower:
            return False

        model = (self.model or "").lower()
        reasoning_model_prefixes = (
            "deepseek/",
            "anthropic/",
            "openai/",
            "x-ai/",
            "google/gemini-2",
            "qwen/qwen3",
            "tencent/hy3-preview",
            "xiaomi/",
        )
        return any(model.startswith(prefix) for prefix in reasoning_model_prefixes)

    def _lmstudio_reasoning_options_cached(self) -> list[str]:
        """Probe LM Studio's published reasoning ``allowed_options`` once per
        (model, base_url). The list (e.g. ``["off","on"]`` or
        ``["off","minimal","low"]``) is needed both for the supports-reasoning
        gate and for clamping the emitted ``reasoning_effort`` so toggle-style
        models don't 400 on ``high``. Cache is keyed on (model, base_url) so
        ``/model`` swaps and base-URL changes don't reuse a stale list.
        Non-empty results are cached permanently (model capabilities don't
        change). Empty results (transient probe failure OR genuinely
        non-reasoning model) are cached with a 60-second TTL to avoid an
        HTTP round-trip on every turn while still retrying reasonably soon.
        """
        import time as _time

        cache = getattr(self, "_lm_reasoning_opts_cache", None)
        if cache is None:
            cache = self._lm_reasoning_opts_cache = {}
        key = (self.model, self.base_url)
        cached = cache.get(key)
        if cached is not None:
            opts, ts = cached
            # Non-empty → permanent. Empty → 60s TTL.
            if opts or (_time.monotonic() - ts) < 60:
                return opts
        try:
            from icecode_cli.hermes_cli.models import lmstudio_model_reasoning_options
            opts = lmstudio_model_reasoning_options(
                self.model, self.base_url, getattr(self, "api_key", ""),
            )
        except Exception:
            opts = []
        cache[key] = (opts, _time.monotonic())
        return opts

    def _resolve_lmstudio_summary_reasoning_effort(self) -> Optional[str]:
        """Resolve a safe top-level ``reasoning_effort`` for LM Studio.

        The iteration-limit summary path calls ``chat.completions.create()``
        directly, bypassing the transport. Share the helper so the two paths
        can't drift on effort resolution and clamping.
        """
        from icecode.agent.lmstudio_reasoning import resolve_lmstudio_effort
        return resolve_lmstudio_effort(
            self.reasoning_config,
            self._lmstudio_reasoning_options_cached(),
        )

    def _github_models_reasoning_extra_body(self) -> dict | None:
        """Format reasoning payload for GitHub Models/OpenAI-compatible routes."""
        try:
            from icecode_cli.hermes_cli.models import github_model_reasoning_efforts
        except Exception:
            return None

        supported_efforts = github_model_reasoning_efforts(self.model)
        if not supported_efforts:
            return None

        if self.reasoning_config and isinstance(self.reasoning_config, dict):
            if self.reasoning_config.get("enabled") is False:
                return None
            requested_effort = str(
                self.reasoning_config.get("effort", "medium")
            ).strip().lower()
        else:
            requested_effort = "medium"

        if requested_effort == "xhigh" and "high" in supported_efforts:
            requested_effort = "high"
        elif requested_effort not in supported_efforts:
            if requested_effort == "minimal" and "low" in supported_efforts:
                requested_effort = "low"
            elif "medium" in supported_efforts:
                requested_effort = "medium"
            else:
                requested_effort = supported_efforts[0]

        return {"effort": requested_effort}

    def _build_assistant_message(self, assistant_message, finish_reason: str) -> dict:
        """Build a normalized assistant message dict from an API response message.

        Handles reasoning extraction, reasoning_details, and optional tool_calls
        so both the tool-call path and the final-response path share one builder.
        """
        assistant_tool_calls = getattr(assistant_message, "tool_calls", None)
        reasoning_text = self._extract_reasoning(assistant_message)
        _from_structured = bool(reasoning_text)

        # Fallback: extract inline <think> blocks from content when no structured
        # reasoning fields are present (some models/providers embed thinking
        # directly in the content rather than returning separate API fields).
        if not reasoning_text:
            content = assistant_message.content or ""
            think_blocks = re.findall(r'<think>(.*?)</think>', content, flags=re.DOTALL)
            if think_blocks:
                combined = "\n\n".join(b.strip() for b in think_blocks if b.strip())
                reasoning_text = combined or None

        if reasoning_text and self.verbose_logging:
            logging.debug(f"Captured reasoning ({len(reasoning_text)} chars): {reasoning_text}")

        if reasoning_text and self.reasoning_callback:
            # Skip callback when streaming is active — reasoning was already
            # displayed during the stream via one of two paths:
            #   (a) _fire_reasoning_delta (structured reasoning_content deltas)
            #   (b) _stream_delta tag extraction (<think>/<REASONING_SCRATCHPAD>)
            # When streaming is NOT active, always fire so non-streaming modes
            # (gateway, batch, quiet) still get reasoning.
            # Any reasoning that wasn't shown during streaming is caught by the
            # CLI post-response display fallback (cli.py _reasoning_shown_this_turn).
            if not self.stream_delta_callback and not self._stream_callback:
                try:
                    self.reasoning_callback(reasoning_text)
                except Exception:
                    pass

        # Sanitize surrogates from API response — some models (e.g. Kimi/GLM via Ollama)
        # can return invalid surrogate code points that crash json.dumps() on persist.
        _raw_content = assistant_message.content or ""
        _san_content = _sanitize_surrogates(_raw_content)
        if reasoning_text:
            reasoning_text = _sanitize_surrogates(reasoning_text)

        # Strip inline reasoning tags (<think>…</think> etc.) from the stored
        # assistant content.  Reasoning was already captured into
        # ``reasoning_text`` above (either from structured fields or the
        # inline-block fallback), so the raw tags in content are redundant.
        # Leaving them in place caused reasoning to leak to messaging
        # platforms (#8878, #9568), inflate context on subsequent turns
        # (#9306 observed 16% content-size reduction on a real MiniMax
        # session), and pollute generated session titles.  One strip at the
        # storage boundary cleans content for every downstream consumer:
        # API replay, session transcript, gateway delivery, CLI display,
        # compression, title generation.
        if isinstance(_san_content, str) and _san_content:
            _san_content = self._strip_think_blocks(_san_content).strip()

        msg = {
            "role": "assistant",
            "content": _san_content,
            "reasoning": reasoning_text,
            "finish_reason": finish_reason,
        }

        raw_reasoning_content = getattr(assistant_message, "reasoning_content", None)
        if raw_reasoning_content is None and hasattr(assistant_message, "model_extra"):
            model_extra = getattr(assistant_message, "model_extra", None) or {}
            if isinstance(model_extra, dict) and "reasoning_content" in model_extra:
                raw_reasoning_content = model_extra["reasoning_content"]
        if raw_reasoning_content is not None:
            msg["reasoning_content"] = _sanitize_surrogates(raw_reasoning_content)
        elif assistant_tool_calls and self._needs_thinking_reasoning_pad():
            # DeepSeek v4 thinking mode and Kimi / Moonshot thinking mode
            # both require reasoning_content on every assistant tool-call
            # message. Without it, replaying the persisted message causes
            # HTTP 400 ("The reasoning_content in the thinking mode must
            # be passed back to the API"). Include streamed reasoning
            # text when captured; otherwise pad with a single space —
            # DeepSeek V4 Pro tightened validation and rejects empty
            # string ("The reasoning content in the thinking mode must
            # be passed back to the API"). A space satisfies non-empty
            # checks everywhere without leaking fabricated reasoning.
            # Refs #15250, #17400, #17341.
            msg["reasoning_content"] = reasoning_text or " "

        # Additive fallback (refs #16844, #16884). Streaming-only providers
        # (glm, MiniMax, gpt-5.x via aigw, Anthropic via openai-compat shims)
        # accumulate reasoning through ``delta.reasoning_content`` chunks
        # but never land it on the message object as a top-level attribute,
        # so neither branch above fires and the chain-of-thought is stored
        # only under the internal ``reasoning`` key. When the user later
        # replays that history through a DeepSeek-v4 / Kimi thinking model,
        # the missing ``reasoning_content`` causes HTTP 400 ("The
        # reasoning_content in the thinking mode must be passed back to the
        # API.").
        #
        # Promote the already-sanitized streamed ``reasoning_text`` to
        # ``reasoning_content`` at write time, but ONLY when no prior branch
        # already set it AND we actually captured reasoning text. This
        # preserves every existing behavior:
        #   - SDK-exposed ``reasoning_content`` (OpenAI/Moonshot/DeepSeek SDK)
        #     still wins.
        #   - DeepSeek tool-call ""-pad (#15250) still fires.
        #   - Non-thinking turns with no reasoning leave the field absent,
        #     so ``_copy_reasoning_content_for_api``'s cross-provider leak
        #     guard (#15748) and ``reasoning``→``reasoning_content``
        #     promotion tiers still apply at replay time.
        if "reasoning_content" not in msg and reasoning_text:
            msg["reasoning_content"] = reasoning_text

        if hasattr(assistant_message, 'reasoning_details') and assistant_message.reasoning_details:
            # Pass reasoning_details back unmodified so providers (OpenRouter,
            # Anthropic, OpenAI) can maintain reasoning continuity across turns.
            # Each provider may include opaque fields (signature, encrypted_content)
            # that must be preserved exactly.
            raw_details = assistant_message.reasoning_details
            preserved = []
            for d in raw_details:
                if isinstance(d, dict):
                    preserved.append(d)
                elif hasattr(d, "__dict__"):
                    preserved.append(d.__dict__)
                elif hasattr(d, "model_dump"):
                    preserved.append(d.model_dump())
            if preserved:
                msg["reasoning_details"] = preserved

        # Codex Responses API: preserve encrypted reasoning items for
        # multi-turn continuity. These get replayed as input on the next turn.
        codex_items = getattr(assistant_message, "codex_reasoning_items", None)
        if codex_items:
            msg["codex_reasoning_items"] = codex_items

        # Codex Responses API: preserve exact assistant message items (with
        # id/phase) so follow-up turns can replay structured items instead of
        # flattening to plain text. This is required for prefix cache hits.
        codex_message_items = getattr(assistant_message, "codex_message_items", None)
        if codex_message_items:
            msg["codex_message_items"] = codex_message_items

        if assistant_tool_calls:
            tool_calls = []
            for tool_call in assistant_tool_calls:
                raw_id = getattr(tool_call, "id", None)
                call_id = getattr(tool_call, "call_id", None)
                if not isinstance(call_id, str) or not call_id.strip():
                    embedded_call_id, _ = self._split_responses_tool_id(raw_id)
                    call_id = embedded_call_id
                if not isinstance(call_id, str) or not call_id.strip():
                    if isinstance(raw_id, str) and raw_id.strip():
                        call_id = raw_id.strip()
                    else:
                        _fn = getattr(tool_call, "function", None)
                        _fn_name = getattr(_fn, "name", "") if _fn else ""
                        _fn_args = getattr(_fn, "arguments", "{}") if _fn else "{}"
                        call_id = self._deterministic_call_id(_fn_name, _fn_args, len(tool_calls))
                call_id = call_id.strip()

                response_item_id = getattr(tool_call, "response_item_id", None)
                if not isinstance(response_item_id, str) or not response_item_id.strip():
                    _, embedded_response_item_id = self._split_responses_tool_id(raw_id)
                    response_item_id = embedded_response_item_id

                response_item_id = self._derive_responses_function_call_id(
                    call_id,
                    response_item_id if isinstance(response_item_id, str) else None,
                )

                tc_dict = {
                    "id": call_id,
                    "call_id": call_id,
                    "response_item_id": response_item_id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    },
                }
                # Preserve extra_content (e.g. Gemini thought_signature) so it
                # is sent back on subsequent API calls.  Without this, Gemini 3
                # thinking models reject the request with a 400 error.
                extra = getattr(tool_call, "extra_content", None)
                if extra is not None:
                    if hasattr(extra, "model_dump"):
                        extra = extra.model_dump()
                    tc_dict["extra_content"] = extra
                tool_calls.append(tc_dict)
            msg["tool_calls"] = tool_calls

        return msg

    def _needs_thinking_reasoning_pad(self) -> bool:
        """Return True when the active provider enforces reasoning_content echo-back.

        DeepSeek v4 thinking and Kimi / Moonshot thinking both reject replays
        of assistant tool-call messages that omit ``reasoning_content`` (refs
        #15250, #17400). Xiaomi MiMo thinking mode has the same requirement.
        """
        return (
            self._needs_deepseek_tool_reasoning()
            or self._needs_kimi_tool_reasoning()
            or self._needs_mimo_tool_reasoning()
        )

    def _needs_kimi_tool_reasoning(self) -> bool:
        """Return True when the current provider is Kimi / Moonshot thinking mode.

        Kimi ``/coding`` and Moonshot thinking mode both require
        ``reasoning_content`` on every assistant tool-call message; omitting
        it causes the next replay to fail with HTTP 400.
        """
        return (
            self.provider in {"kimi-coding", "kimi-coding-cn"}
            or base_url_host_matches(self.base_url, "api.kimi.com")
            or base_url_host_matches(self.base_url, "moonshot.ai")
            or base_url_host_matches(self.base_url, "moonshot.cn")
        )

    def _needs_deepseek_tool_reasoning(self) -> bool:
        """Return True when the current provider is DeepSeek thinking mode.

        DeepSeek V4 thinking mode requires ``reasoning_content`` on every
        assistant tool-call turn; omitting it causes HTTP 400 when the
        message is replayed in a subsequent API request (#15250).
        """
        provider = (self.provider or "").lower()
        model = (self.model or "").lower()
        return (
            provider == "deepseek"
            or "deepseek" in model
            or base_url_host_matches(self.base_url, "api.deepseek.com")
        )

    def _needs_mimo_tool_reasoning(self) -> bool:
        """Return True when the current provider is Xiaomi MiMo thinking mode.

        MiMo thinking mode requires ``reasoning_content`` on every assistant
        tool-call message when replaying history; omitting it causes HTTP 400.
        Refs: https://platform.xiaomimimo.com/docs/zh-CN/usage-guide/passing-back-reasoning_content
        """
        provider = (self.provider or "").lower()
        model = (self.model or "").lower()
        return (
            provider == "xiaomi"
            or "mimo" in model
            or base_url_host_matches(self.base_url, "api.xiaomimimo.com")
            or base_url_host_matches(self.base_url, "xiaomimimo.com")
        )

    def _copy_reasoning_content_for_api(self, source_msg: dict, api_msg: dict) -> None:
        """Copy provider-facing reasoning fields onto an API replay message."""
        if source_msg.get("role") != "assistant":
            return

        # 1. Explicit reasoning_content already set — preserve it verbatim
        # (includes DeepSeek/Kimi's own space-placeholder written at creation
        # time, and any valid reasoning content from the same provider).
        #
        # Exception: sessions persisted BEFORE #17341 have empty-string
        # placeholders pinned at creation time. DeepSeek V4 Pro rejects
        # those with HTTP 400. When the active provider enforces the
        # thinking-mode echo, upgrade "" → " " on replay so stale history
        # doesn't 400 the user on the next turn.
        existing = source_msg.get("reasoning_content")
        if isinstance(existing, str):
            if existing == "" and self._needs_thinking_reasoning_pad():
                api_msg["reasoning_content"] = " "
            else:
                api_msg["reasoning_content"] = existing
            return

        needs_thinking_pad = self._needs_thinking_reasoning_pad()

        # 2. Cross-provider poisoned history (#15748): on DeepSeek/Kimi,
        # if the source turn has tool_calls AND a 'reasoning' field but no
        # 'reasoning_content' key, the 'reasoning' text was written by a
        # prior provider (e.g. MiniMax) — DeepSeek's own _build_assistant_message
        # pins reasoning_content at creation time for tool-call turns, so the
        # shape (reasoning set, reasoning_content absent, tool_calls present)
        # is unreachable from same-provider DeepSeek history after this fix.
        # Inject a single space to satisfy the API without leaking another
        # provider's chain of thought to DeepSeek/Kimi. Space (not "")
        # because DeepSeek V4 Pro rejects empty-string reasoning_content
        # in thinking mode (refs #17341).
        normalized_reasoning = source_msg.get("reasoning")
        if (
            needs_thinking_pad
            and source_msg.get("tool_calls")
            and isinstance(normalized_reasoning, str)
            and normalized_reasoning
        ):
            api_msg["reasoning_content"] = " "
            return

        # 3. Healthy session: promote 'reasoning' field to 'reasoning_content'
        # for providers that use the internal 'reasoning' key.
        # This must happen before the unconditional empty-string fallback so
        # genuine reasoning content is not overwritten (#15812 regression in
        # PR #15478).
        if isinstance(normalized_reasoning, str) and normalized_reasoning:
            api_msg["reasoning_content"] = normalized_reasoning
            return

        # 4. DeepSeek / Kimi thinking mode: all assistant messages need
        # reasoning_content. Inject a single space to satisfy the provider's
        # requirement when no explicit reasoning content is present. Covers
        # both tool-call turns (already-poisoned history with no reasoning
        # at all) and plain text turns. Space (not "") because DeepSeek V4
        # Pro tightened validation and rejects empty string with HTTP 400
        # ("The reasoning content in the thinking mode must be passed back
        # to the API"). Refs #17341.
        if needs_thinking_pad:
            api_msg["reasoning_content"] = " "
            return

        # 5. reasoning_content was present but not a string (e.g. None after
        # context compaction).  Don't pass null to the API.
        api_msg.pop("reasoning_content", None)

    @staticmethod
    def _sanitize_tool_calls_for_strict_api(api_msg: dict) -> dict:
        """Strip Codex Responses API fields from tool_calls for strict providers.

        Providers like Mistral, Fireworks, and other strict OpenAI-compatible APIs
        validate the Chat Completions schema and reject unknown fields (call_id,
        response_item_id) with 400 or 422 errors. These fields are preserved in
        the internal message history — this method only modifies the outgoing
        API copy.

        Creates new tool_call dicts rather than mutating in-place, so the
        original messages list retains call_id/response_item_id for Codex
        Responses API compatibility (e.g. if the session falls back to a
        Codex provider later).

        Fields stripped: call_id, response_item_id
        """
        tool_calls = api_msg.get("tool_calls")
        if not isinstance(tool_calls, list):
            return api_msg
        _STRIP_KEYS = {"call_id", "response_item_id"}
        api_msg["tool_calls"] = [
            {k: v for k, v in tc.items() if k not in _STRIP_KEYS}
            if isinstance(tc, dict) else tc
            for tc in tool_calls
        ]
        return api_msg

    @staticmethod
    def _sanitize_tool_call_arguments(
        messages: list,
        *,
        logger=None,
        session_id: str = None,
    ) -> int:
        """Repair corrupted assistant tool-call argument JSON in-place."""
        log = logger or logging.getLogger(__name__)
        if not isinstance(messages, list):
            return 0

        repaired = 0
        marker = AIAgent._TOOL_CALL_ARGUMENTS_CORRUPTION_MARKER

        def _prepend_marker(tool_msg: dict) -> None:
            existing = tool_msg.get("content")
            if isinstance(existing, str):
                if not existing:
                    tool_msg["content"] = marker
                elif not existing.startswith(marker):
                    tool_msg["content"] = f"{marker}\n{existing}"
                return
            if existing is None:
                tool_msg["content"] = marker
                return
            try:
                existing_text = json.dumps(existing)
            except TypeError:
                existing_text = str(existing)
            tool_msg["content"] = f"{marker}\n{existing_text}"

        message_index = 0
        while message_index < len(messages):
            msg = messages[message_index]
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                message_index += 1
                continue

            tool_calls = msg.get("tool_calls")
            if not isinstance(tool_calls, list) or not tool_calls:
                message_index += 1
                continue

            insert_at = message_index + 1
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                function = tool_call.get("function")
                if not isinstance(function, dict):
                    continue

                arguments = function.get("arguments")
                if arguments is None or arguments == "":
                    function["arguments"] = "{}"
                    continue
                if isinstance(arguments, str) and not arguments.strip():
                    function["arguments"] = "{}"
                    continue
                if not isinstance(arguments, str):
                    continue

                try:
                    json.loads(arguments)
                except json.JSONDecodeError:
                    tool_call_id = tool_call.get("id")
                    function_name = function.get("name", "?")
                    preview = arguments[:80]
                    log.warning(
                        "Corrupted tool_call arguments repaired before request "
                        "(session=%s, message_index=%s, tool_call_id=%s, function=%s, preview=%r)",
                        session_id or "-",
                        message_index,
                        tool_call_id or "-",
                        function_name,
                        preview,
                    )
                    function["arguments"] = "{}"

                    existing_tool_msg = None
                    scan_index = message_index + 1
                    while scan_index < len(messages):
                        candidate = messages[scan_index]
                        if not isinstance(candidate, dict) or candidate.get("role") != "tool":
                            break
                        if candidate.get("tool_call_id") == tool_call_id:
                            existing_tool_msg = candidate
                            break
                        scan_index += 1

                    if existing_tool_msg is None:
                        messages.insert(
                            insert_at,
                            {
                                "role": "tool",
                                "name": function_name if function_name != "?" else "",
                                "tool_call_id": tool_call_id,
                                "content": marker,
                            },
                        )
                        insert_at += 1
                    else:
                        _prepend_marker(existing_tool_msg)

                    repaired += 1

            message_index += 1

        return repaired

    def _should_sanitize_tool_calls(self) -> bool:
        """Determine if tool_calls need sanitization for strict APIs.

        Codex Responses API uses fields like call_id and response_item_id
        that are not part of the standard Chat Completions schema. These
        fields must be stripped when calling any other API to avoid
        validation errors (400 Bad Request).

        Returns:
            bool: True if sanitization is needed (non-Codex API), False otherwise.
        """
        return self.api_mode != "codex_responses"

    def _compress_context(self, messages: list, system_message: str, *, approx_tokens: int = None, task_id: str = "default", focus_topic: str = None) -> tuple:
        """Compress conversation context and split the session in SQLite.

        Args:
            focus_topic: Optional focus string for guided compression — the
                summariser will prioritise preserving information related to
                this topic.  Inspired by Claude Code's ``/compact <focus>``.

        Returns:
            (compressed_messages, new_system_prompt) tuple
        """
        _pre_msg_count = len(messages)
        logger.info(
            "context compression started: session=%s messages=%d tokens=~%s model=%s focus=%r",
            self.session_id or "none", _pre_msg_count,
            f"{approx_tokens:,}" if approx_tokens else "unknown", self.model,
            focus_topic,
        )
        self._emit_status(
            "🗜️ Compacting context — summarizing earlier conversation so I can continue..."
        )

        # Notify external memory provider before compression discards context
        if self._memory_manager:
            try:
                self._memory_manager.on_pre_compress(messages)
            except Exception:
                pass

        try:
            compressed = self.context_compressor.compress(messages, current_tokens=approx_tokens, focus_topic=focus_topic)
        except TypeError:
            # Plugin context engine with strict signature that doesn't accept
            # focus_topic — fall back to calling without it.
            compressed = self.context_compressor.compress(messages, current_tokens=approx_tokens)

        summary_error = getattr(self.context_compressor, "_last_summary_error", None)
        if summary_error:
            if getattr(self, "_last_compression_summary_warning", None) != summary_error:
                self._last_compression_summary_warning = summary_error
                self._emit_warning(
                    f"⚠ Compression summary failed: {summary_error}. "
                    "Inserted a fallback context marker."
                )
        else:
            # No hard failure — but did the configured aux model error out
            # and get recovered by retrying on main?  Surface that so users
            # know their auxiliary.compression.model setting is broken even
            # though compression succeeded.
            _aux_fail_model = getattr(self.context_compressor, "_last_aux_model_failure_model", None)
            _aux_fail_err = getattr(self.context_compressor, "_last_aux_model_failure_error", None)
            if _aux_fail_model:
                # Dedup on (model, error) so we don't spam on every compaction
                _aux_key = (_aux_fail_model, _aux_fail_err)
                if getattr(self, "_last_aux_fallback_warning_key", None) != _aux_key:
                    self._last_aux_fallback_warning_key = _aux_key
                    self._emit_warning(
                        f"ℹ Configured compression model '{_aux_fail_model}' failed "
                        f"({_aux_fail_err or 'unknown error'}). Recovered using main model — "
                        "check auxiliary.compression.model in config.yaml."
                    )

        todo_snapshot = self._todo_store.format_for_injection()
        if todo_snapshot:
            compressed.append({"role": "user", "content": todo_snapshot})

        self._invalidate_system_prompt()
        new_system_prompt = self._build_system_prompt(system_message)
        self._cached_system_prompt = new_system_prompt

        if self._session_db:
            try:
                # Propagate title to the new session with auto-numbering
                old_title = self._session_db.get_session_title(self.session_id)
                # Trigger memory extraction on the old session before it rotates.
                self.commit_memory_session(messages)
                self._session_db.end_session(self.session_id, "compression")
                old_session_id = self.session_id
                self.session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
                os.environ["ICECODE_SESSION_ID"] = self.session_id
                try:
                    from gateway.session_context import _SESSION_ID
                    _SESSION_ID.set(self.session_id)
                except Exception:
                    pass
                # Update session_log_file to point to the new session's JSON file
                self.session_log_file = self.logs_dir / f"session_{self.session_id}.json"
                self._session_db_created = False
                self._session_db.create_session(
                    session_id=self.session_id,
                    source=self.platform or os.environ.get("ICECODE_SESSION_SOURCE", "cli"),
                    model=self.model,
                    model_config=self._session_init_model_config,
                    parent_session_id=old_session_id,
                )
                self._session_db_created = True
                # Auto-number the title for the continuation session
                if old_title:
                    try:
                        new_title = self._session_db.get_next_title_in_lineage(old_title)
                        self._session_db.set_session_title(self.session_id, new_title)
                    except (ValueError, Exception) as e:
                        logger.debug("Could not propagate title on compression: %s", e)
                self._session_db.update_system_prompt(self.session_id, new_system_prompt)
                # Reset flush cursor — new session starts with no messages written
                self._last_flushed_db_idx = 0
            except Exception as e:
                logger.warning("Session DB compression split failed — new session will NOT be indexed: %s", e)

        # Notify the context engine that the session_id rotated because of
        # compression (not a fresh /new). Plugin engines (e.g. hermes-lcm) use
        # boundary_reason="compression" to preserve DAG lineage across the
        # rollover instead of re-initializing fresh per-session state.
        # See hermes-lcm#68. Built-in ContextCompressor ignores kwargs.
        try:
            _old_sid = locals().get("old_session_id")
            if _old_sid and hasattr(self.context_compressor, "on_session_start"):
                self.context_compressor.on_session_start(
                    self.session_id or "",
                    boundary_reason="compression",
                    old_session_id=_old_sid,
                )
        except Exception as _ce_err:
            logger.debug("context engine on_session_start (compression): %s", _ce_err)

        # Notify memory providers of the compression-driven session_id rotation
        # so provider-cached per-session state (Hindsight's _document_id,
        # accumulated turn buffers, counters) refreshes. reset=False because
        # the logical conversation continues; only the id and DB row rolled
        # over. See #6672.
        try:
            _old_sid = locals().get("old_session_id")
            if _old_sid and self._memory_manager:
                self._memory_manager.on_session_switch(
                    self.session_id or "",
                    parent_session_id=_old_sid,
                    reset=False,
                    reason="compression",
                )
        except Exception as _me_err:
            logger.debug("memory manager on_session_switch (compression): %s", _me_err)

        # Warn on repeated compressions (quality degrades with each pass)
        _cc = self.context_compressor.compression_count
        if _cc >= 2:
            self._vprint(
                f"{self.log_prefix}⚠️  Session compressed {_cc} times — "
                f"accuracy may degrade. Consider /new to start fresh.",
                force=True,
            )

        # Update token estimate after compaction so pressure calculations
        # use the post-compression count, not the stale pre-compression one.
        # Use estimate_request_tokens_rough() so tool schemas are included —
        # with 50+ tools enabled, schemas alone can add 20-30K tokens, and
        # omitting them delays the next compression cycle far past the
        # configured threshold (issue #14695).
        _compressed_est = estimate_request_tokens_rough(
            compressed,
            system_prompt=new_system_prompt or "",
            tools=self.tools or None,
        )
        self.context_compressor.last_prompt_tokens = _compressed_est
        self.context_compressor.last_completion_tokens = 0

        # Clear the file-read dedup cache.  After compression the original
        # read content is summarised away — if the model re-reads the same
        # file it needs the full content, not a "file unchanged" stub.
        try:
            from icecode_tools.file_tools import reset_file_dedup
            reset_file_dedup(task_id)
        except Exception:
            pass

        logger.info(
            "context compression done: session=%s messages=%d->%d tokens=~%s",
            self.session_id or "none", _pre_msg_count, len(compressed),
            f"{_compressed_est:,}",
        )
        return compressed, new_system_prompt

    def _set_tool_guardrail_halt(self, decision: ToolGuardrailDecision) -> None:
        """Record the first guardrail decision that should stop this turn."""
        if decision.should_halt and self._tool_guardrail_halt_decision is None:
            self._tool_guardrail_halt_decision = decision

    def _toolguard_controlled_halt_response(self, decision: ToolGuardrailDecision) -> str:
        tool = decision.tool_name or "a tool"
        return (
            f"I stopped retrying {tool} because it hit the tool-call guardrail "
            f"({decision.code}) after {decision.count} repeated non-progressing "
            "attempts. The last tool result explains the blocker; the next step is "
            "to change strategy instead of repeating the same call."
        )

    def _append_guardrail_observation(
        self,
        tool_name: str,
        function_args: dict,
        function_result: str,
        *,
        failed: bool,
    ) -> str:
        decision = self._tool_guardrails.after_call(
            tool_name,
            function_args,
            function_result,
            failed=failed,
        )
        if decision.action in {"warn", "halt"}:
            function_result = append_toolguard_guidance(function_result, decision)
        if decision.should_halt:
            self._set_tool_guardrail_halt(decision)
        return function_result

    def _guardrail_block_result(self, decision: ToolGuardrailDecision) -> str:
        self._set_tool_guardrail_halt(decision)
        return toolguard_synthetic_result(decision)

    def _handle_max_iterations(self, messages: list, api_call_count: int) -> str:
        """Request a summary when max iterations are reached. Returns the final response text."""
        print(f"⚠️  Reached maximum iterations ({self.max_iterations}). Requesting summary...")

        summary_request = (
            "You've reached the maximum number of tool-calling iterations allowed. "
            "Please provide a final response summarizing what you've found and accomplished so far, "
            "without calling any more tools."
        )
        messages.append({"role": "user", "content": summary_request})

        try:
            # Build API messages, stripping internal-only fields
            # (finish_reason, reasoning) that strict APIs like Mistral reject with 422
            _needs_sanitize = self._should_sanitize_tool_calls()
            api_messages = []
            for msg in messages:
                api_msg = msg.copy()
                self._copy_reasoning_content_for_api(msg, api_msg)
                for internal_field in ("reasoning", "finish_reason", "_thinking_prefill"):
                    api_msg.pop(internal_field, None)
                if _needs_sanitize:
                    self._sanitize_tool_calls_for_strict_api(api_msg)
                api_messages.append(api_msg)

            effective_system = self._cached_system_prompt or ""
            if self.ephemeral_system_prompt:
                effective_system = (effective_system + "\n\n" + self.ephemeral_system_prompt).strip()
            if effective_system:
                api_messages = [{"role": "system", "content": effective_system}] + api_messages
            if self.prefill_messages:
                sys_offset = 1 if effective_system else 0
                for idx, pfm in enumerate(self.prefill_messages):
                    api_messages.insert(sys_offset + idx, pfm.copy())

            # Same safety net as the main loop: repair tool-call/result
            # pairing before asking for a final summary.  Compression and
            # session resume can leave a tool result whose parent assistant
            # tool_call was summarized away; Responses API rejects that as
            # "No tool call found for function call output".
            api_messages = self._sanitize_api_messages(api_messages)

            # Same safety net as the main loop: drop thinking-only assistant
            # turns so Anthropic-family providers don't 400 the summary call.
            api_messages = self._drop_thinking_only_and_merge_users(api_messages)

            summary_extra_body = {}
            try:
                from icecode.agent.auxiliary_client import _fixed_temperature_for_model, OMIT_TEMPERATURE as _OMIT_TEMP
            except Exception:
                _fixed_temperature_for_model = None
                _OMIT_TEMP = None
            _raw_summary_temp = (
                _fixed_temperature_for_model(self.model, self.base_url)
                if _fixed_temperature_for_model is not None
                else None
            )
            _omit_summary_temperature = _raw_summary_temp is _OMIT_TEMP
            _summary_temperature = None if _omit_summary_temperature else _raw_summary_temp
            _is_nous = "nousresearch" in self._base_url_lower
            # LM Studio uses top-level `reasoning_effort` (not extra_body.reasoning).
            # Mirror ChatCompletionsTransport.build_kwargs() so the summary path
            # — which calls chat.completions.create() directly without going
            # through the transport — sends the same shape the transport does.
            _is_lmstudio_summary = (
                (self.provider or "").strip().lower() == "lmstudio"
                and self._supports_reasoning_extra_body()
            )
            _lm_reasoning_effort: str | None = (
                self._resolve_lmstudio_summary_reasoning_effort()
                if _is_lmstudio_summary else None
            )
            if not _is_lmstudio_summary and self._supports_reasoning_extra_body():
                if self.reasoning_config is not None:
                    summary_extra_body["reasoning"] = self.reasoning_config
                else:
                    summary_extra_body["reasoning"] = {
                        "enabled": True,
                        "effort": "medium"
                    }
            if _is_nous:
                from icecode.agent.portal_tags import nous_portal_tags as _portal_tags
                summary_extra_body["tags"] = _portal_tags()

            if self.api_mode == "codex_responses":
                codex_kwargs = self._build_api_kwargs(api_messages)
                codex_kwargs.pop("tools", None)
                summary_response = self._run_codex_stream(codex_kwargs)
                _ct_sum = self._get_transport()
                _cnr_sum = _ct_sum.normalize_response(summary_response)
                final_response = (_cnr_sum.content or "").strip()
            else:
                summary_kwargs = {
                    "model": self.model,
                    "messages": api_messages,
                }
                if _summary_temperature is not None:
                    summary_kwargs["temperature"] = _summary_temperature
                if self.max_tokens is not None:
                    summary_kwargs.update(self._max_tokens_param(self.max_tokens))
                if _lm_reasoning_effort is not None:
                    summary_kwargs["reasoning_effort"] = _lm_reasoning_effort

                # Include provider routing preferences
                provider_preferences = {}
                if self.providers_allowed:
                    provider_preferences["only"] = self.providers_allowed
                if self.providers_ignored:
                    provider_preferences["ignore"] = self.providers_ignored
                if self.providers_order:
                    provider_preferences["order"] = self.providers_order
                if self.provider_sort:
                    provider_preferences["sort"] = self.provider_sort
                if provider_preferences and (
                    (self.provider or "").strip().lower() == "openrouter"
                    or self._is_openrouter_url()
                ):
                    summary_extra_body["provider"] = provider_preferences

                # Pareto Code router plugin — model-gated. Same shape as
                # the main-loop emission so summary calls on
                # openrouter/pareto-code respect the user's coding-score floor.
                if (
                    self.model == "openrouter/pareto-code"
                    and (
                        (self.provider or "").strip().lower() == "openrouter"
                        or self._is_openrouter_url()
                    )
                    and self.openrouter_min_coding_score is not None
                    and self.openrouter_min_coding_score != ""
                ):
                    try:
                        _ps = float(self.openrouter_min_coding_score)
                    except (TypeError, ValueError):
                        _ps = None
                    if _ps is not None and 0.0 <= _ps <= 1.0:
                        summary_extra_body["plugins"] = [
                            {"id": "pareto-router", "min_coding_score": _ps}
                        ]

                if summary_extra_body:
                    summary_kwargs["extra_body"] = summary_extra_body

                if self.api_mode == "anthropic_messages":
                    _tsum = self._get_transport()
                    _ant_kw = _tsum.build_kwargs(model=self.model, messages=api_messages, tools=None,
                                   max_tokens=self.max_tokens, reasoning_config=self.reasoning_config,
                                   is_oauth=self._is_anthropic_oauth,
                                   preserve_dots=self._anthropic_preserve_dots())
                    summary_response = self._anthropic_messages_create(_ant_kw)
                    _summary_result = _tsum.normalize_response(summary_response, strip_tool_prefix=self._is_anthropic_oauth)
                    final_response = (_summary_result.content or "").strip()
                else:
                    summary_response = self._ensure_primary_openai_client(reason="iteration_limit_summary").chat.completions.create(**summary_kwargs)
                    _summary_result = self._get_transport().normalize_response(summary_response)
                    final_response = (_summary_result.content or "").strip()

            if final_response:
                if "<think>" in final_response:
                    final_response = re.sub(r'<think>.*?</think>\s*', '', final_response, flags=re.DOTALL).strip()
                if final_response:
                    messages.append({"role": "assistant", "content": final_response})
                else:
                    final_response = "I reached the iteration limit and couldn't generate a summary."
            else:
                # Retry summary generation
                if self.api_mode == "codex_responses":
                    codex_kwargs = self._build_api_kwargs(api_messages)
                    codex_kwargs.pop("tools", None)
                    retry_response = self._run_codex_stream(codex_kwargs)
                    _ct_retry = self._get_transport()
                    _cnr_retry = _ct_retry.normalize_response(retry_response)
                    final_response = (_cnr_retry.content or "").strip()
                elif self.api_mode == "anthropic_messages":
                    _tretry = self._get_transport()
                    _ant_kw2 = _tretry.build_kwargs(model=self.model, messages=api_messages, tools=None,
                                    is_oauth=self._is_anthropic_oauth,
                                    max_tokens=self.max_tokens, reasoning_config=self.reasoning_config,
                                    preserve_dots=self._anthropic_preserve_dots())
                    retry_response = self._anthropic_messages_create(_ant_kw2)
                    _retry_result = _tretry.normalize_response(retry_response, strip_tool_prefix=self._is_anthropic_oauth)
                    final_response = (_retry_result.content or "").strip()
                else:
                    summary_kwargs = {
                        "model": self.model,
                        "messages": api_messages,
                    }
                    if _summary_temperature is not None:
                        summary_kwargs["temperature"] = _summary_temperature
                    if self.max_tokens is not None:
                        summary_kwargs.update(self._max_tokens_param(self.max_tokens))
                    if _lm_reasoning_effort is not None:
                        summary_kwargs["reasoning_effort"] = _lm_reasoning_effort
                    if summary_extra_body:
                        summary_kwargs["extra_body"] = summary_extra_body

                    summary_response = self._ensure_primary_openai_client(reason="iteration_limit_summary_retry").chat.completions.create(**summary_kwargs)
                    _retry_result = self._get_transport().normalize_response(summary_response)
                    final_response = (_retry_result.content or "").strip()

                if final_response:
                    if "<think>" in final_response:
                        final_response = re.sub(r'<think>.*?</think>\s*', '', final_response, flags=re.DOTALL).strip()
                    if final_response:
                        messages.append({"role": "assistant", "content": final_response})
                    else:
                        final_response = "I reached the iteration limit and couldn't generate a summary."
                else:
                    final_response = "I reached the iteration limit and couldn't generate a summary."

        except Exception as e:
            logging.warning(f"Failed to get summary response: {e}")
            final_response = f"I reached the maximum iterations ({self.max_iterations}) but couldn't summarize. Error: {str(e)}"

        return final_response

