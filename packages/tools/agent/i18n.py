"""Stub for agent.i18n — returns key as-is (English pass-through)."""
def t(key: str, **kwargs) -> str:
    try: return key.format(**kwargs)
    except Exception: return key
