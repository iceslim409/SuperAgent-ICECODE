"""Stub for toolsets module — values must be dicts with 'tools' key."""
from typing import List, Dict, Any

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

def resolve_toolset(name: str) -> List[str]:
    return get_toolset(name)

def get_all_toolsets() -> Dict[str, Dict]:
    return dict(TOOLSETS)
