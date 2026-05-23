"""
ICECODE Unified Tool Registry
~70 Python tools (Hermes) + 35 TypeScript tools (OpenCode)
"""
from __future__ import annotations
import importlib
import inspect
import json
from pathlib import Path
from typing import Dict, Any, Callable, Optional, List
from loguru import logger


def tool_error(message: str) -> str:
    """Return a standardized error string for tool failures."""
    return json.dumps({"error": message})


def tool_result(data: Any) -> str:
    """Return a standardized success result for tool calls."""
    if isinstance(data, str):
        return data
    return json.dumps(data, ensure_ascii=False, default=str)


class ToolRegistry:
    """Central registry for all ICECODE tools."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._initialized = False
        return cls._instance

    def register(self, name: str, func: Callable = None, description: str = "",
                 schema: Dict = None, handler: Callable = None,
                 toolset: str = "", check_fn: Callable = None,
                 emoji: str = "", **kwargs):
        """Register a tool. Accepts both old-style (func) and new-style (handler) signatures."""
        actual_handler = handler or func
        self._tools[name] = {
            "func": actual_handler,
            "handler": actual_handler,
            "description": description,
            "schema": schema or {},
            "toolset": toolset,
            "check_fn": check_fn,
            "emoji": emoji,
        }
        logger.debug(f"Tool registered: {name}")

    def get(self, name: str) -> Optional[Dict]:
        return self._tools.get(name)

    def get_schema(self, name: str) -> Optional[Dict]:
        t = self._tools.get(name)
        if t and t.get("schema"):
            return {"type": "function", "function": t["schema"]}
        return None

    def get_all_schemas(self) -> List[Dict]:
        """Return all tool schemas in OpenAI function-calling format."""
        schemas = []
        for name, t in self._tools.items():
            s = t.get("schema")
            if s and s.get("name"):
                schemas.append({"type": "function", "function": s})
        return schemas

    def get_available_schemas(self) -> List[Dict]:
        """Return schemas only for tools whose check_fn passes (or have no check_fn)."""
        schemas = []
        for name, t in self._tools.items():
            s = t.get("schema")
            if not (s and s.get("name")):
                continue
            check_fn = t.get("check_fn")
            if check_fn:
                try:
                    if not check_fn():
                        continue
                except Exception:
                    continue
            schemas.append({"type": "function", "function": s})
        return schemas

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": k, "description": v["description"] or v.get("schema", {}).get("description", "")}
            for k, v in self._tools.items()
        ]

    def call(self, name: str, args: Dict, **kwargs) -> str:
        """Execute a registered tool by name."""
        t = self._tools.get(name)
        if not t:
            return tool_error(f"Unknown tool: {name}")
        handler = t.get("handler") or t.get("func")
        if not handler:
            return tool_error(f"No handler for tool: {name}")
        try:
            check_fn = t.get("check_fn")
            if check_fn and not check_fn():
                return tool_error(f"Tool {name} requirements not met")
            return handler(args, **kwargs)
        except Exception as e:
            return tool_error(f"Tool {name} error: {e}")

    def auto_discover(self, package_path: Path):
        """Auto-discover and register tools from all submodules."""
        for py_file in package_path.rglob("*.py"):
            if py_file.name.startswith("_") or py_file.name == "registry.py":
                continue
            module_name = str(py_file.relative_to(package_path.parent)).replace("/", ".").rstrip(".py")
            try:
                mod = importlib.import_module(module_name)
                for name, obj in inspect.getmembers(mod, callable):
                    if hasattr(obj, "_tool_name"):
                        self.register(obj._tool_name, obj, getattr(obj, "_tool_description", ""))
            except Exception as e:
                logger.debug(f"Skip {py_file.name}: {e}")

    @property
    def count(self) -> int:
        return len(self._tools)


# Global registry instance
registry = ToolRegistry()
