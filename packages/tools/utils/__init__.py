"""Minimal utils stubs for icecode_tools compatibility."""
from pathlib import Path
import json, os, re


def atomic_replace(path: str, content: str, encoding: str = "utf-8") -> None:
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        tmp.write_text(content, encoding=encoding)
        tmp.replace(p)
    except Exception:
        if tmp.exists(): tmp.unlink()
        raise

def atomic_json_write(path: str, data) -> None:
    atomic_replace(path, json.dumps(data, indent=2, ensure_ascii=False))

def is_truthy_value(v) -> bool:
    if isinstance(v, bool): return v
    if isinstance(v, str): return v.lower() in ("1","true","yes","on")
    return bool(v)

def base_url_hostname(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1) if m else url

def ensure_dir(path: str) -> Path:
    p = Path(path); p.mkdir(parents=True, exist_ok=True); return p

def read_text(path: str, default: str = "") -> str:
    try: return Path(path).read_text()
    except Exception: return default

def truncate(text: str, max_len: int = 4000) -> str:
    return text if len(text) <= max_len else text[:max_len] + f"…(+{len(text)-max_len})"
