"""
ICECODE Unified Tool Registry
~70 Python tools (Hermes) + 35 TypeScript tools (OpenCode)
"""
from __future__ import annotations
import importlib
import inspect
from pathlib import Path
from typing import Dict, Any, Callable, Optional, List
from loguru import logger


class ToolRegistry:
    """Central registry for all ICECODE tools."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._initialized = False
        return cls._instance

    def register(self, name: str, func: Callable, description: str = "", schema: Dict = None):
        self._tools[name] = {
            "func": func,
            "description": description,
            "schema": schema or {},
        }
        logger.debug(f"Tool registered: {name}")

    def get(self, name: str) -> Optional[Dict]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": k, "description": v["description"]}
            for k, v in self._tools.items()
        ]

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
