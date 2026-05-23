"""Stub for agent.display."""
_EMOJI_MAP = {"browser":"🌐","file":"📄","terminal":"💻","memory":"🧠","search":"🔍","default":"⚡"}
def get_tool_emoji(tool_name: str) -> str:
    for k, v in _EMOJI_MAP.items():
        if k in (tool_name or "").lower(): return v
    return _EMOJI_MAP["default"]
