"""toolsets.py — re-exports from icecode.toolsets (56 toolsets, canonical).

Falls back to a minimal 9-entry stub when packages/core is not on sys.path
(e.g. when icecode-tools is installed standalone without icecode-core).
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional, Set

try:
    from icecode.toolsets import (  # canonical — 56 toolsets
        TOOLSETS,
        get_toolset,
        resolve_toolset,
        get_all_toolsets,
        get_toolset_names,
        validate_toolset,
        create_custom_toolset,
        get_toolset_info,
        resolve_multiple_toolsets,
    )
except ImportError:
    # Minimal fallback when icecode-core is not installed
    TOOLSETS: Dict[str, Dict] = {
        "web":        {"tools": ["search_web", "web_fetch", "browser_fetch"], "description": "Web browsing and search"},
        "file":       {"tools": ["read_file", "write_file", "edit_file", "list_dir"], "description": "File operations"},
        "shell":      {"tools": ["run_terminal", "git_command"], "description": "Terminal and git"},
        "memory":     {"tools": ["remember", "recall", "memory"], "description": "Memory and recall"},
        "research":   {"tools": ["search_web", "web_fetch", "read_file", "remember"], "description": "Research tasks"},
        "coding":     {"tools": ["read_file", "write_file", "edit_file", "run_terminal", "code_search", "git_command"], "description": "Software development"},
        "full_stack": {"tools": ["search_web", "web_fetch", "read_file", "write_file", "edit_file", "run_terminal", "git_command", "code_search", "remember"], "description": "Full-stack development"},
        "data":       {"tools": ["read_file", "write_file", "run_terminal", "search_web"], "description": "Data analysis"},
        "writing":    {"tools": ["read_file", "write_file", "search_web", "remember"], "description": "Writing and editing"},
    }

    def get_toolset(name: str) -> List[str]:
        return TOOLSETS.get(name, {}).get("tools", [])

    def resolve_toolset(name: str, visited: Optional[Set[str]] = None) -> List[str]:
        return get_toolset(name)

    def resolve_multiple_toolsets(names: List[str]) -> List[str]:
        seen: List[str] = []
        for n in names:
            for t in get_toolset(n):
                if t not in seen:
                    seen.append(t)
        return seen

    def get_all_toolsets() -> Dict[str, Dict[str, Any]]:
        return dict(TOOLSETS)

    def get_toolset_names() -> List[str]:
        return list(TOOLSETS.keys())

    def validate_toolset(name: str) -> bool:
        return name in TOOLSETS

    def create_custom_toolset(name: str, tools: List[str], description: str = "") -> Dict[str, Any]:
        TOOLSETS[name] = {"tools": tools, "description": description}
        return TOOLSETS[name]

    def get_toolset_info(name: str) -> Dict[str, Any]:
        ts = TOOLSETS.get(name, {})
        return {"name": name, "tools": ts.get("tools", []), "description": ts.get("description", ""), "exists": bool(ts)}
