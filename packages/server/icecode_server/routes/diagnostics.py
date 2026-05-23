"""ICECODE Diagnostics API — full project health checks + debug run endpoint."""
from __future__ import annotations

import asyncio
import importlib
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])

_ROOT = Path(__file__).parents[3]  # packages/
_PROJECT = _ROOT.parent             # project root


# ── helpers ───────────────────────────────────────────────────────────────────

def _check_import(name: str) -> str:
    try:
        mod = __import__(name)
        return getattr(mod, "__version__", "installed")
    except ImportError:
        return "not installed"


def _ok(label: str, detail: str = "") -> Dict:
    return {"status": "ok", "label": label, "detail": detail}


def _fail(label: str, detail: str = "", fix: str = "") -> Dict:
    return {"status": "fail", "label": label, "detail": detail, "fix": fix}


def _warn(label: str, detail: str = "") -> Dict:
    return {"status": "warn", "label": label, "detail": detail}


# ── individual checks ─────────────────────────────────────────────────────────

def check_imports() -> List[Dict]:
    results = []
    for mod, display in [("icecode", "icecode (core)"), ("icecode_server", "icecode_server")]:
        try:
            importlib.import_module(mod)
            results.append(_ok(f"import {display}"))
        except Exception as e:
            results.append(_fail(f"import {display}", str(e),
                                 f"pip install -e packages/{mod.replace('icecode_', '') or 'core'}"))
    return results


def check_packages() -> List[Dict]:
    results = []
    for pkg, mod in [("icecode-core", "icecode"), ("icecode-server", "icecode_server"),
                     ("icecode-tools", "icecode_tools")]:
        try:
            r = subprocess.run(["pip", "show", pkg], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                version = next((l.split(":",1)[1].strip() for l in r.stdout.splitlines()
                                if l.startswith("Version:")), "?")
                results.append(_ok(f"{pkg}", f"v{version} (pip)"))
            else:
                importlib.import_module(mod)
                results.append(_ok(f"{pkg}", "available via PYTHONPATH"))
        except Exception:
            results.append(_fail(f"{pkg}", "missing",
                                 f"pip install -e packages/{pkg.replace('icecode-', '')}"))
    return results


def check_tools() -> List[Dict]:
    try:
        from icecode.agent.core import TOOLS, _load_extended_tools
        ext = _load_extended_tools()
        base_names = {t["function"]["name"] for t in TOOLS}
        all_tools = base_names | {t["function"]["name"] for t in ext}
        count = len(all_tools)
        if count >= 70:
            return [_ok(f"{count} tools active", f"{len(base_names)} base + {len(all_tools)-len(base_names)} extended")]
        return [_warn(f"Only {count} tools active", "expected 70+")]
    except Exception as e:
        return [_fail("Agent tools", str(e))]


def check_routes() -> List[Dict]:
    try:
        from icecode_server.main import create_app
        app = create_app()
        count = len([r for r in app.routes if hasattr(r, "methods")])
        if count >= 150:
            return [_ok(f"{count} API routes registered")]
        return [_warn(f"Only {count} API routes", "expected 150+")]
    except Exception as e:
        return [_fail("API routes", str(e))]


def check_symlinks() -> List[Dict]:
    broken = []
    _SKIP = {"node_modules", ".venv", ".git", "__pycache__"}
    try:
        for link in _PROJECT.rglob("*"):
            if any(p in _SKIP for p in link.parts):
                continue
            if link.is_symlink() and not link.exists():
                broken.append(str(link.relative_to(_PROJECT)))
    except Exception:
        pass
    if broken:
        return [_fail(f"{len(broken)} broken symlinks", ", ".join(broken[:3]),
                      "rm " + broken[0])]
    return [_ok("No broken symlinks")]


def check_tests() -> List[Dict]:
    try:
        tests_dir = _PROJECT / "tests"
        if not tests_dir.exists():
            return [_warn("tests/ directory missing")]
        r = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir), "-q", "--tb=no", "--no-header"],
            capture_output=True, text=True, timeout=120,
            cwd=str(_PROJECT),
            env={**os.environ, "PYTHONPATH": ":".join([
                str(_ROOT / "core"), str(_ROOT / "server"),
                str(_ROOT / "tools"), str(_ROOT / "cli"),
            ])}
        )
        out = r.stdout + r.stderr
        # parse "X passed, Y failed"
        import re as _re
        passed = next((int(p.group(1)) for line in out.splitlines()
                       for p in [_re.search(r'(\d+) passed', line)]
                       if p), 0)
        failed = next((int(p.group(1)) for line in out.splitlines()
                       for p in [_re.search(r'(\d+) failed', line)]
                       if p), 0)
        if failed == 0 and passed > 0:
            return [_ok(f"{passed} tests pass, 0 failed")]
        elif failed > 0:
            return [_fail(f"{failed} tests fail out of {passed+failed}",
                          "Run: make test")]
        return [_warn("No tests found or pytest failed")]
    except subprocess.TimeoutExpired:
        return [_warn("pytest timeout (>120s)")]
    except Exception as e:
        return [_fail("pytest", str(e))]


def check_git() -> List[Dict]:
    results = []
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=str(_PROJECT),
            stderr=subprocess.DEVNULL, text=True).strip()
        commits = subprocess.check_output(
            ["git", "log", "--oneline"], cwd=str(_PROJECT),
            stderr=subprocess.DEVNULL, text=True).strip().count("\n") + 1
        results.append(_ok(f"Branch: {branch}", f"{commits} commits"))

        status = subprocess.check_output(
            ["git", "status", "--short"], cwd=str(_PROJECT),
            stderr=subprocess.DEVNULL, text=True).strip()
        modified = sum(1 for l in status.splitlines() if l.startswith(" M") or l.startswith("M"))
        untracked = sum(1 for l in status.splitlines() if l.startswith("??"))
        if modified == 0 and untracked == 0:
            results.append(_ok("Working tree clean"))
        else:
            if modified:
                results.append(_warn(f"{modified} modified files not committed"))
            if untracked:
                results.append(_warn(f"{untracked} new files not committed"))
    except Exception:
        results.append(_warn("Not a git repo or git unavailable"))
    return results


def check_server() -> List[Dict]:
    try:
        import httpx
        port = int(os.getenv("HOST_API_PORT", "13210"))
        r = httpx.get(f"http://localhost:{port}/health", timeout=3)
        if r.status_code == 200:
            v = r.json().get("version", "?")
            return [_ok(f"Server on :{port}", f"v{v}")]
        return [_warn(f"Server responded HTTP {r.status_code}")]
    except Exception:
        return [_warn("Server not running (start with: make run)")]


def check_critical_files() -> List[Dict]:
    critical = [
        "packages/core/icecode/agent/core.py",
        "packages/server/icecode_server/main.py",
        "packages/web-ui/index.html",
        "packages/tools/icecode_tools/registry.py",
        "tests/conftest.py",
        ".env.example",
    ]
    results = []
    for f in critical:
        path = _PROJECT / f
        if path.exists():
            results.append(_ok(f))
        else:
            results.append(_fail(f, "missing"))
    return results


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
async def diagnostics():
    return {
        "version": "1.0.0",
        "python": sys.version,
        "platform": platform.system(),
        "arch": platform.machine(),
        "packages": {
            "core": _check_import("icecode"),
            "fastapi": _check_import("fastapi"),
            "anthropic": _check_import("anthropic"),
            "openai": _check_import("openai"),
            "sqlalchemy": _check_import("sqlalchemy"),
            "loguru": _check_import("loguru"),
        }
    }


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/run")
async def run_debug():
    """Run all checks and stream structured results via SSE."""

    CHECKS = [
        ("Python imports",      check_imports),
        ("Python packages",     check_packages),
        ("Agent tools",         check_tools),
        ("API routes",          check_routes),
        ("Symlinks",            check_symlinks),
        ("pytest",              check_tests),
        ("Git repository",      check_git),
        ("HTTP server",         check_server),
        ("Critical files",      check_critical_files),
    ]

    async def generate():
        yield f"data: {json.dumps({'event': 'start', 'total': len(CHECKS)})}\n\n"
        total_ok = total_fail = total_warn = 0

        for i, (name, fn) in enumerate(CHECKS):
            t0 = time.time()
            try:
                results = await asyncio.to_thread(fn)
            except Exception as e:
                results = [_fail(name, str(e))]
            elapsed = round((time.time() - t0) * 1000)

            for r in results:
                s = r["status"]
                if s == "ok":    total_ok   += 1
                elif s == "fail": total_fail += 1
                else:             total_warn  += 1

            yield f"data: {json.dumps({'event': 'section', 'name': name, 'idx': i, 'results': results, 'elapsed_ms': elapsed})}\n\n"

        summary = {
            "event": "done",
            "ok": total_ok, "fail": total_fail, "warn": total_warn,
            "status": "ok" if total_fail == 0 and total_warn == 0
                      else ("warn" if total_fail == 0 else "fail")
        }
        yield f"data: {json.dumps(summary)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
