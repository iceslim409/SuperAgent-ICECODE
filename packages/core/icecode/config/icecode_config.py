"""
ICECODE Unified Configuration
================================
Single source of truth for all ICECODE settings.
Replaces and unifies: ICECodeSettings (pydantic), hermes_constants, and individual module configs.

Priority order (highest → lowest):
  1. Environment variables (ICECODE_*)
  2. .env file in project root
  3. ~/.icecode/config.yaml
  4. Built-in defaults
"""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


def _env(key: str, default: str = "") -> str:
    """Read ICECODE_* env var with fallback to HERMES_* for backwards compat."""
    return (
        os.environ.get(f"ICECODE_{key}")
        or os.environ.get(f"HERMES_{key}")
        or os.environ.get(key)
        or default
    )


def _icecode_home() -> Path:
    """~/.icecode — the single data directory for ICECODE."""
    p = Path(_env("HOME_DIR") or Path.home() / ".icecode")
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class ICECodeConfig:
    """
    Unified ICECODE configuration.
    All settings derive from env vars, .env file, or defaults.
    """

    # ── Server ─────────────────────────────────────────────────────────────
    host: str = field(default_factory=lambda: _env("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(_env("PORT", "13210")))
    server_secret: str = field(default_factory=lambda: _env("SERVER_SECRET", "icecode-dev-secret"))
    debug: bool = field(default_factory=lambda: _env("DEBUG", "false").lower() == "true")

    # ── Paths ──────────────────────────────────────────────────────────────
    home_dir: Path = field(default_factory=_icecode_home)
    db_path: Path = field(default=None)            # set in __post_init__
    sessions_dir: Path = field(default=None)
    skills_dir: Path = field(default=None)
    knowledge_dir: Path = field(default=None)
    logs_dir: Path = field(default=None)

    # ── Ollama / Local models ─────────────────────────────────────────────
    ollama_host: str = field(default_factory=lambda: _env("OLLAMA_HOST", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: _env("OLLAMA_MODEL", "qwen3.5:4b"))
    ollama_num_ctx: int = field(default_factory=lambda: int(_env("OLLAMA_NUM_CTX", "8192")))
    ollama_num_predict: int = field(default_factory=lambda: int(_env("OLLAMA_NUM_PREDICT", "2048")))
    ollama_think: bool = field(default_factory=lambda: _env("OLLAMA_THINK", "false").lower() == "true")

    # ── Cloud API keys (all optional) ─────────────────────────────────────
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    google_api_key: str = field(default_factory=lambda: _env("GOOGLE_API_KEY"))
    deepseek_api_key: str = field(default_factory=lambda: _env("DEEPSEEK_API_KEY"))
    openrouter_api_key: str = field(default_factory=lambda: _env("OPENROUTER_API_KEY"))

    # ── Agent settings ─────────────────────────────────────────────────────
    max_iterations: int = field(default_factory=lambda: int(_env("MAX_ITERATIONS", "10")))
    enable_computer: bool = field(default_factory=lambda: _env("ENABLE_COMPUTER", "false").lower() == "true")
    enable_rl: bool = field(default_factory=lambda: _env("ENABLE_RL", "false").lower() == "true")
    auto_route_model: bool = field(default_factory=lambda: _env("AUTO_ROUTE_MODEL", "true").lower() == "true")

    # ── Knowledge base ─────────────────────────────────────────────────────
    embedding_model: str = field(default_factory=lambda: _env("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
    knowledge_chunk_size: int = field(default_factory=lambda: int(_env("KNOWLEDGE_CHUNK_SIZE", "512")))
    knowledge_chunk_overlap: int = field(default_factory=lambda: int(_env("KNOWLEDGE_CHUNK_OVERLAP", "80")))

    # ── OpenRouter ─────────────────────────────────────────────────────────
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_models_url: str = "https://openrouter.ai/api/v1/models"

    def __post_init__(self):
        h = self.home_dir
        if self.db_path is None:
            self.db_path = h / "data" / "icecode.db"
        if self.sessions_dir is None:
            self.sessions_dir = h / "sessions"
        if self.skills_dir is None:
            self.skills_dir = h / "skills"
        if self.knowledge_dir is None:
            self.knowledge_dir = h / "data" / "knowledge"
        if self.logs_dir is None:
            self.logs_dir = h / "logs"

        # Create all required directories
        for d in [self.db_path.parent, self.sessions_dir, self.skills_dir,
                  self.knowledge_dir, self.logs_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict:
        return {
            "version": "2.0.0",
            "server": {"host": self.host, "port": self.port, "debug": self.debug},
            "ollama": {
                "host": self.ollama_host,
                "model": self.ollama_model,
                "num_ctx": self.ollama_num_ctx,
                "num_predict": self.ollama_num_predict,
                "think": self.ollama_think,
            },
            "agent": {
                "max_iterations": self.max_iterations,
                "enable_computer": self.enable_computer,
                "auto_route_model": self.auto_route_model,
            },
            "knowledge": {
                "embedding_model": self.embedding_model,
                "chunk_size": self.knowledge_chunk_size,
            },
            "paths": {
                "home": str(self.home_dir),
                "db": str(self.db_path),
                "sessions": str(self.sessions_dir),
                "knowledge": str(self.knowledge_dir),
            },
        }

    @property
    def has_cloud_provider(self) -> bool:
        return bool(self.anthropic_api_key or self.openai_api_key
                    or self.google_api_key or self.openrouter_api_key)

    def default_provider(self) -> str:
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return "ollama"

    def default_model(self) -> str:
        return self.ollama_model


# ── Singleton ──────────────────────────────────────────────────────────────
_cfg: Optional[ICECodeConfig] = None

def get_config() -> ICECodeConfig:
    """Return the global ICECODE config singleton."""
    global _cfg
    if _cfg is None:
        _cfg = ICECodeConfig()
    return _cfg

def reload_config() -> ICECodeConfig:
    """Force reload of config from environment."""
    global _cfg
    _cfg = ICECodeConfig()
    return _cfg
