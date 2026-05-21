"""
ICECODE Local Inference Manager

Gestioneaza modele locale (Ollama, LM Studio, vLLM, llama.cpp) cu:
- Auto-detectare server type
- Context length real din GGUF metadata
- Timeout adaptat pentru prefill lent
- Context compression automata la 50% threshold
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from loguru import logger

# ICECODE (codul real)
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from agent.model_metadata import (
        is_local_endpoint,
        detect_local_server_type,
        query_ollama_num_ctx,
        get_model_context_length,
    )
    _METADATA_AVAILABLE = True
except ImportError:
    _METADATA_AVAILABLE = False
    logger.warning("model_metadata not available — basic local inference only")


class LocalInferenceManager:
    """
    Manager pentru inferenta locala cu resurse minime.

    Detecteaza automat: Ollama, LM Studio, vLLM, llama.cpp
    Citeste context length real din GGUF metadata
    Adapteaza timeout-uri pentru prefill lent
    """

    # Servere locale cunoscute (detectate automat)
    LOCAL_SERVERS = {
        "ollama": "http://localhost:11434",
        "lm-studio": "http://localhost:1234",
        "llamacpp": "http://localhost:8080",
        "vllm": "http://localhost:8000",
    }

    def __init__(self):
        self._detected_servers: Dict[str, str] = {}
        self._context_cache: Dict[str, int] = {}

    def scan_local_servers(self) -> Dict[str, str]:
        """Cauta servere locale pornite."""
        found = {}
        import httpx

        for name, url in self.LOCAL_SERVERS.items():
            try:
                with httpx.Client(timeout=1.0) as c:
                    r = c.get(f"{url}/v1/models")
                    if r.status_code in (200, 401):
                        found[name] = url
                        logger.info(f"[LOCAL] {name} detectat la {url}")
            except Exception:
                pass

        self._detected_servers = found
        return found

    def get_server_type(self, base_url: str) -> Optional[str]:
        """Detecteaza tipul serverului local."""
        if not _METADATA_AVAILABLE:
            if "11434" in base_url:
                return "ollama"
            if "1234" in base_url:
                return "lm-studio"
            return None
        try:
            return detect_local_server_type(base_url)
        except Exception:
            return None

    def get_context_length(self, model: str, base_url: str, api_key: str = "") -> int:
        """
        Citeste context length-ul real al modelului din GGUF metadata.
        Nu foloseste default-ul de 2048 — citeste valoarea reala.
        """
        cache_key = f"{base_url}:{model}"
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]

        ctx = 4096  # fallback conservator

        if _METADATA_AVAILABLE:
            try:
                detected = query_ollama_num_ctx(model, base_url, api_key=api_key)
                if detected and detected > 512:
                    ctx = detected
                    logger.info(f"[LOCAL] {model} context length din GGUF: {ctx:,} tokens")
                else:
                    ctx = get_model_context_length(model)
                    logger.info(f"[LOCAL] {model} context length din catalog: {ctx:,} tokens")
            except Exception as e:
                logger.debug(f"[LOCAL] context length fallback: {e}")

        self._context_cache[cache_key] = ctx
        return ctx

    def get_stream_timeout(self, base_url: str, base_timeout: float = 1800.0) -> float:
        """
        Returneaza timeout adaptat pentru modelele locale.
        Modelele locale au prefill lent (minute inainte de primul token).
        """
        if _METADATA_AVAILABLE and is_local_endpoint(base_url):
            logger.debug(f"[LOCAL] timeout ridicat la {base_timeout}s pentru {base_url}")
            return base_timeout
        return 120.0  # 2 minute pentru cloud

    def get_client_config(self, model: str, base_url: str, api_key: str = "") -> Dict[str, Any]:
        """
        Returneaza configuratia completa pentru un model local.
        Include: context_length, timeout, server_type, num_ctx (Ollama).
        """
        server_type = self.get_server_type(base_url)
        ctx_length = self.get_context_length(model, base_url, api_key)
        stream_timeout = self.get_stream_timeout(base_url)

        config = {
            "base_url": base_url,
            "model": model,
            "server_type": server_type,
            "context_length": ctx_length,
            "stream_timeout": stream_timeout,
            "is_local": True,
        }

        # Ollama: trebuie sa trimitem num_ctx explicit
        if server_type == "ollama":
            config["ollama_num_ctx"] = ctx_length

        # LM Studio: reasoning effort
        if server_type == "lm-studio":
            config["lmstudio_reasoning"] = True

        logger.info(
            f"[LOCAL] {server_type or 'unknown'} / {model} — "
            f"ctx={ctx_length:,} timeout={stream_timeout:.0f}s"
        )
        return config

    def is_local(self, base_url: str) -> bool:
        if _METADATA_AVAILABLE:
            return is_local_endpoint(base_url)
        return any(
            h in base_url
            for h in ("localhost", "127.0.0.1", "0.0.0.0", "::1")
        )

    def list_available_models(self, base_url: str, api_key: str = "") -> list:
        """Lista modelele disponibile pe serverul local."""
        import httpx
        try:
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            with httpx.Client(timeout=3.0) as c:
                r = c.get(f"{base_url.rstrip('/')}/v1/models", headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    models = data.get("data") or data.get("models") or []
                    return [m.get("id") or m.get("name") or m for m in models]
        except Exception as e:
            logger.debug(f"list_models error: {e}")
        return []


# Singleton global
_manager: Optional[LocalInferenceManager] = None


def get_local_manager() -> LocalInferenceManager:
    global _manager
    if _manager is None:
        _manager = LocalInferenceManager()
    return _manager
