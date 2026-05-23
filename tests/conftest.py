"""Pytest configuration — add all packages to sys.path."""
import sys
from pathlib import Path

_ROOT = Path(__file__).parents[1] / "packages"
for _pkg in ("core", "server", "tools", "cli"):
    _p = str(_ROOT / _pkg)
    if _p not in sys.path:
        sys.path.insert(0, _p)
