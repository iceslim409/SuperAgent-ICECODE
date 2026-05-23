"""Stub for plugins module."""
_registry = {}

def register(name: str, plugin) -> None:
    _registry[name] = plugin

def get(name: str):
    return _registry.get(name)

def list_plugins() -> list:
    return list(_registry.keys())
