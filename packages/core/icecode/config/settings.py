"""ICECODE unified configuration — merges ICECODE YAML config + OpenCode JSONC config."""
from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field

    class ICECodeSettings(BaseSettings):
        # Paths
        home_dir: Path = Field(default_factory=lambda: Path.home() / ".icecode")
        db_path: Optional[Path] = Field(default=None)

        # Server
        host_api_port: int = Field(default=13210)
        server_secret: str = Field(default="")

        # AI Providers
        anthropic_api_key: str = Field(default="")
        openai_api_key: str = Field(default="")
        openrouter_api_key: str = Field(default="")
        google_api_key: str = Field(default="")
        deepseek_api_key: str = Field(default="")
        xai_api_key: str = Field(default="")
        ollama_host: str = Field(default="http://localhost:11434")
        ollama_model: str = Field(default="")
        default_model: str = Field(default="qwen2.5-coder:7b")
        default_provider: str = Field(default="ollama")

        # Memory
        memory_provider: str = Field(default="local")
        mem0_api_key: str = Field(default="")
        honcho_api_key: str = Field(default="")
        supermemory_api_key: str = Field(default="")

        # Web search
        brave_search_api_key: str = Field(default="")
        exa_api_key: str = Field(default="")
        firecrawl_api_key: str = Field(default="")
        tavily_api_key: str = Field(default="")
        searxng_url: str = Field(default="")

        # Gateway platforms
        telegram_bot_token: str = Field(default="")
        discord_bot_token: str = Field(default="")
        slack_bot_token: str = Field(default="")
        matrix_homeserver: str = Field(default="")
        matrix_access_token: str = Field(default="")
        feishu_app_id: str = Field(default="")
        feishu_app_secret: str = Field(default="")

        # Features
        enable_self_learning: bool = Field(default=True)
        enable_goals: bool = Field(default=True)
        enable_cron: bool = Field(default=True)
        enable_kanban: bool = Field(default=True)
        enable_voice: bool = Field(default=False)
        enable_rl_training: bool = Field(default=False)

        # Agent limits
        max_tokens: int = Field(default=8192)
        max_tool_calls: int = Field(default=100)
        task_timeout_seconds: int = Field(default=300)

        # === LOCAL INFERENCE (modele locale cu resurse minime) ===
        # Server local (Ollama, LM Studio, vLLM, llama.cpp)
        local_main_model: str = Field(default="")
        local_main_url: str = Field(default="http://localhost:11434")
        local_aux_model: str = Field(default="")  # model mic pentru sumar/titluri
        local_aux_url: str = Field(default="http://localhost:11434")
        # Context compression: comprima automat la X% din context window
        # 0.50 = at 50% context fill, the model compresses old messages
        context_compression_threshold: float = Field(default=0.50)
        # Timeout pentru inferenta locala (modelele locale au prefill lent)
        local_stream_timeout: float = Field(default=1800.0)
        # Prioritizeaza modelele locale cand sunt disponibile
        prefer_local_models: bool = Field(default=False)

        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "ignore"

        def model_post_init(self, __context: Any) -> None:
            if self.db_path is None:
                self.db_path = self.home_dir / "data" / "icecode.db"
            self.home_dir.mkdir(parents=True, exist_ok=True)
            (self.home_dir / "data").mkdir(parents=True, exist_ok=True)
            (self.home_dir / "skills").mkdir(parents=True, exist_ok=True)
            (self.home_dir / "logs").mkdir(parents=True, exist_ok=True)

        def to_dict(self) -> Dict[str, Any]:
            d = self.model_dump()
            # Redact secrets
            for k in list(d.keys()):
                if "key" in k or "token" in k or "secret" in k:
                    if d[k]:
                        d[k] = "***"
            return d

except ImportError:
    # Fallback if pydantic not installed yet
    @dataclass
    class ICECodeSettings:  # type: ignore
        home_dir: Path = field(default_factory=lambda: Path.home() / ".icecode")
        db_path: Optional[Path] = None
        host_api_port: int = field(default_factory=lambda: int(os.getenv("HOST_API_PORT", "13210")))
        server_secret: str = field(default_factory=lambda: os.getenv("SERVER_SECRET", ""))
        anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
        openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
        openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
        google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
        deepseek_api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
        xai_api_key: str = field(default_factory=lambda: os.getenv("XAI_API_KEY", ""))
        ollama_host: str = "http://localhost:11434"
        ollama_model: str = ""
        default_model: str = "qwen2.5:7b"
        default_provider: str = "ollama"
        memory_provider: str = "local"
        mem0_api_key: str = ""
        brave_search_api_key: str = ""
        exa_api_key: str = ""
        firecrawl_api_key: str = ""
        tavily_api_key: str = ""
        searxng_url: str = ""
        telegram_bot_token: str = ""
        discord_bot_token: str = ""
        slack_bot_token: str = ""
        enable_self_learning: bool = True
        enable_goals: bool = True
        enable_cron: bool = True
        enable_kanban: bool = True
        enable_voice: bool = False
        enable_rl_training: bool = False
        max_tokens: int = 8192
        max_tool_calls: int = 100
        task_timeout_seconds: int = 300
        local_main_model: str = ""
        local_main_url: str = "http://localhost:11434"
        local_aux_model: str = ""
        local_aux_url: str = "http://localhost:11434"
        context_compression_threshold: float = 0.50
        local_stream_timeout: float = 1800.0
        prefer_local_models: bool = False

        def __post_init__(self):
            if self.db_path is None:
                self.db_path = self.home_dir / "data" / "icecode.db"
            self.home_dir.mkdir(parents=True, exist_ok=True)
            (self.home_dir / "data").mkdir(parents=True, exist_ok=True)
            (self.home_dir / "skills").mkdir(parents=True, exist_ok=True)
            (self.home_dir / "logs").mkdir(parents=True, exist_ok=True)

        def to_dict(self) -> Dict[str, Any]:
            import dataclasses
            d = dataclasses.asdict(self)
            for k in list(d.keys()):
                if "key" in k or "token" in k or "secret" in k:
                    if d[k]:
                        d[k] = "***"
            return d
