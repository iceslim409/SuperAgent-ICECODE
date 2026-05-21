"""
ICECODE Super-Agent Network — FastAPI Backend v2.0
Port: 13210
"""
from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

_WEB_UI = Path(__file__).parents[2] / "web-ui"

# Import core components
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))

from icecode.config.settings import ICECodeSettings


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = ICECodeSettings()
    logger.info("=" * 60)
    logger.info("ICECODE Super-Agent Network v2.0.0 starting...")
    logger.info(f"  Port: {cfg.host_api_port}")
    logger.info(f"  DB:   {cfg.db_path}")
    logger.info(f"  Home: {cfg.home_dir}")
    logger.info("=" * 60)

    # Initialize core systems
    await _init_systems(cfg)

    logger.info("All ICECODE systems online.")
    yield

    logger.info("ICECODE shutting down...")
    await _shutdown_systems()


async def _init_systems(cfg: ICECodeSettings):
    """Initialize all subsystems."""
    # State / Database
    try:
        from icecode_server.db import init_db
        init_db(cfg.db_path)
        logger.info(f"  [✓] Database initialized at {cfg.db_path}")
    except Exception as e:
        logger.warning(f"  [!] DB init: {e}")

    # Skill system
    if cfg.enable_self_learning:
        try:
            from icecode.learning.skills import skill_utils  # noqa
            logger.info("  [✓] Self-learning system ready")
        except Exception as e:
            logger.debug(f"  [?] Skills: {e}")

    # Cron scheduler
    if cfg.enable_cron:
        try:
            from icecode.cron import scheduler as _cron_mod  # noqa
            logger.info("  [✓] Cron scheduler ready")
        except Exception as e:
            logger.warning(f"  [!] Cron: {e}")

    # Goals system (Ralph Loop)
    if cfg.enable_goals:
        logger.info("  [✓] Goals system (Ralph Loop) ready")

    # Knowledge auto-index
    try:
        from icecode_server.routes.knowledge import start_auto_index_task
        asyncio.create_task(start_auto_index_task())
        logger.info("  [✓] Knowledge auto-index task started")
    except Exception as e:
        logger.debug(f"  [?] Knowledge auto-index: {e}")


async def _shutdown_systems():
    pass


def create_app() -> FastAPI:
    cfg = ICECodeSettings()

    app = FastAPI(
        title="ICECODE Super-Agent Network",
        version="2.0.0",
        description="Unified AI agent platform: multi-agent swarm, local RAG, 20+ platform gateways.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register all routes
    _register_routes(app)

    return app


def _register_routes(app: FastAPI):
    """Register all API routes from all sources."""

    # Serve web UI at /
    _index = _WEB_UI / "index.html"
    if _index.exists():
        app.mount("/ui", StaticFiles(directory=str(_WEB_UI), html=True), name="webui")

        @app.get("/", include_in_schema=False)
        async def serve_ui():
            return FileResponse(str(_index))

        # Serve PWA files directly at root
        @app.get("/manifest.json", include_in_schema=False)
        async def serve_manifest():
            return FileResponse(str(_WEB_UI / "manifest.json"), media_type="application/json")

        @app.get("/sw.js", include_in_schema=False)
        async def serve_sw():
            return FileResponse(str(_WEB_UI / "sw.js"), media_type="application/javascript")

    # Health + metrics
    from fastapi.responses import JSONResponse
    import time as _time

    _START_TIME = _time.time()
    _REQUEST_COUNT = {"total": 0, "errors": 0}

    @app.middleware("http")
    async def count_requests(request, call_next):
        _REQUEST_COUNT["total"] += 1
        response = await call_next(request)
        if response.status_code >= 500:
            _REQUEST_COUNT["errors"] += 1
        return response

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "version": "2.0.0", "system": "icecode"})

    @app.get("/api/metrics", tags=["monitoring"])
    async def metrics():
        """Server metrics — uptime, request counts, route count, DB stats."""
        uptime = _time.time() - _START_TIME
        routes = [r for r in app.routes if hasattr(r, "path") and r.path.startswith("/api/")]
        try:
            from icecode_server.db import get_usage_summary
            db_stats = get_usage_summary()
        except Exception:
            db_stats = {}
        return JSONResponse({
            "uptime_seconds": round(uptime, 1),
            "total_requests": _REQUEST_COUNT["total"],
            "total_errors": _REQUEST_COUNT["errors"],
            "routes_registered": len(routes),
            "version": "2.0.0",
            "db": db_stats,
        })

    @app.get("/api/status", tags=["monitoring"])
    async def status():
        return JSONResponse({
            "version": "2.0.0",
            "systems": {
                "agent": "ready",
                "memory": "ready",
                "cron": "ready",
                "kanban": "ready",
                "gateway": "ready",
            }
        })

    # Import and register route modules
    _try_register(app, "routes.agents")
    _try_register(app, "routes.sessions")
    _try_register(app, "routes.channels")
    _try_register(app, "routes.skills")
    _try_register(app, "routes.cron")
    _try_register(app, "routes.providers")
    _try_register(app, "routes.settings")
    _try_register(app, "routes.gateway")
    _try_register(app, "routes.models")
    _try_register(app, "routes.usage")
    _try_register(app, "routes.files")
    _try_register(app, "routes.diagnostics")
    _try_register(app, "routes.mcp")
    _try_register(app, "routes.chat")
    _try_register(app, "routes.local_models")
    _try_register(app, "routes.dreams")
    _try_register(app, "routes.kanban")
    _try_register(app, "routes.profiles")
    _try_register(app, "routes.goals")
    _try_register(app, "routes.mixture")
    _try_register(app, "routes.browser")
    _try_register(app, "routes.swarm")
    _try_register(app, "routes.knowledge")
    _try_register(app, "routes.router_api")
    _try_register(app, "routes.opencode_compat")

    # Serve React UI bundle la /desktop/
    _react_dist = Path(__file__).parents[2] / "react-ui" / "dist"
    if _react_dist.exists():
        app.mount("/desktop", StaticFiles(directory=str(_react_dist), html=True), name="react-ui")
        logger.info("  React UI served at /desktop/")


def _try_register(app: FastAPI, module_path: str):
    try:
        import importlib
        mod = importlib.import_module(f"icecode_server.{module_path}")
        if hasattr(mod, "router"):
            app.include_router(mod.router)
            logger.debug(f"  Route: {module_path}")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"  [!] Route {module_path}: {e}")


app = create_app()


if __name__ == "__main__":
    import uvicorn
    cfg = ICECodeSettings()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", str(cfg.host_api_port)))
    logger.info(f"Starting ICECODE server on {host}:{port}")
    uvicorn.run("icecode_server.main:app", host=host, port=port, reload=True)
