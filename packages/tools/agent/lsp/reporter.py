def report_for_file(path: str, **kw) -> str: return ""
def truncate(text: str, max_len: int = 500) -> str:
    return text if len(text) <= max_len else text[:max_len] + "…"
