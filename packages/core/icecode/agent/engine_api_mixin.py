"""engine_api_mixin — backward-compatibility shim.

The original 4334-line _APIMixin has been split into four focused mixins:

  engine_client_mixin.py      — OpenAI client lifecycle and Codex streaming (~600 lines)
  engine_credentials_mixin.py — per-provider credential refresh and pool rotation (~400 lines)
  engine_stream_mixin.py      — streaming API calls, delta delivery, provider fallback (~1720 lines)
  engine_messages_mixin.py    — message prep, API kwargs, vision, reasoning, guardrails (~1770 lines)

_APIMixin is preserved here as a combined class so all existing imports continue to work.
"""
from __future__ import annotations

from icecode.agent.engine_client_mixin import _ClientMixin
from icecode.agent.engine_credentials_mixin import _CredentialsMixin
from icecode.agent.engine_stream_mixin import _StreamMixin
from icecode.agent.engine_messages_mixin import _MessagesMixin


class _APIMixin(_ClientMixin, _CredentialsMixin, _StreamMixin, _MessagesMixin):
    """Combined API mixin — composes all four focused API sub-mixins."""
