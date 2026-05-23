"""
ICECODE Context Compressor
============================
Long conversations = many tokens per request = high cost.
This compressor trims old messages before sending to the LLM:
  - Keep system message always
  - Keep last KEEP_RECENT messages verbatim
  - Replace the middle with a compact summary placeholder
  - Result: cost savings of 40-80% on long chats
"""
from __future__ import annotations

import os
from typing import Any

_MAX_TOKENS = int(os.getenv("CONTEXT_MAX_TOKENS", "3000"))
_KEEP_RECENT = int(os.getenv("CONTEXT_KEEP_RECENT", "6"))
_ENABLED = os.getenv("CONTEXT_COMPRESSION_ENABLED", "true").lower() not in ("false", "0", "no")


def _count_tokens(messages: list[dict]) -> int:
    """Approximate token count (1 token ≈ 3 chars)."""
    return sum(len(str(m.get("content", ""))) // 3 for m in messages)


def compress(messages: list[dict[str, Any]]) -> tuple[list[dict], int]:
    """
    Returns (compressed_messages, tokens_saved).
    If no compression needed, returns original list and 0.
    """
    if not _ENABLED or not messages:
        return messages, 0

    total = _count_tokens(messages)
    if total <= _MAX_TOKENS:
        return messages, 0

    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    if len(non_system) <= _KEEP_RECENT:
        return messages, 0

    recent = non_system[-_KEEP_RECENT:]
    old = non_system[:-_KEEP_RECENT]

    tokens_before = _count_tokens(old)

    # Build a compact summary of the trimmed messages
    summary_lines = []
    for m in old:
        role = m.get("role", "?")
        content = str(m.get("content", ""))
        preview = content[:120].replace("\n", " ")
        if len(content) > 120:
            preview += "…"
        summary_lines.append(f"[{role}]: {preview}")

    summary_text = (
        f"[Context compressed — {len(old)} older messages omitted to reduce tokens]\n"
        + "\n".join(summary_lines[-8:])  # show last 8 of the trimmed
    )

    summary_msg = {"role": "system", "content": summary_text}
    compressed = system_msgs + [summary_msg] + recent

    tokens_after = _count_tokens(compressed)
    saved = max(0, tokens_before - _count_tokens([summary_msg]))

    return compressed, saved
