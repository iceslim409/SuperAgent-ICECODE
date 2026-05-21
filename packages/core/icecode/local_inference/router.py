"""
ICECODE Local Model Router

Distribuie taskurile inteligent intre modele:
- Model mare local → taskuri complexe (cod, analiza)
- Model mic local → taskuri simple (sumar, clasificare, titluri)
- Cloud fallback → cand nu e niciun model local disponibil

Sursa: mecanismul auxiliary_client din ICECODE Agent
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from loguru import logger

from .manager import get_local_manager


@dataclass
class ModelRoute:
    """Un model disponibil cu caracteristicile sale."""
    name: str
    base_url: str
    api_key: str = ""
    context_length: int = 4096
    server_type: Optional[str] = None
    # Costul relativ 0-1 (0=gratis/local, 1=cel mai scump)
    cost_factor: float = 0.0
    # Viteza relativa token/s (estimata)
    speed_estimate: float = 1.0


@dataclass
class RoutingConfig:
    """Configuratie routing pentru un agent."""
    # Modelul principal (pentru taskuri complexe)
    main_model: str = "qwen2.5:7b"
    main_base_url: str = "http://localhost:11434"
    main_api_key: str = ""

    # Modelul auxiliar mic (pentru sumarizare context, titluri, clasificare)
    aux_model: Optional[str] = "qwen2.5:1.5b"
    aux_base_url: Optional[str] = "http://localhost:11434"
    aux_api_key: str = ""

    # Cloud fallback (cand nu e nimic local)
    cloud_fallback_model: Optional[str] = None
    cloud_fallback_provider: Optional[str] = None

    # Threshold (in tokens) sub care folosim modelul auxiliar
    aux_threshold_tokens: int = 500

    # Toolsets activate (reduce contextul consumat de definitii tools)
    active_toolsets: List[str] = field(default_factory=lambda: ["file", "shell", "web"])


class LocalModelRouter:
    """
    Router inteligent pentru modele locale.

    Principiu: fiecare agent extrage din model exact cat are nevoie.
    - Taskuri simple (titlu, sumar, clasificare) → model mic (1.5B-3B)
    - Taskuri complexe (cod, analiza, research) → model mare (7B-70B)
    - Compresia contextului → model auxiliar mic (nu ocupa contextul modelului principal)
    """

    # Taskuri clasificate dupa complexitate
    SIMPLE_TASKS = {
        "title", "summary", "classify", "label", "tag",
        "translate", "format", "clean", "detect",
    }

    COMPLEX_TASKS = {
        "code", "debug", "analyze", "research", "plan",
        "architect", "review", "generate", "implement",
    }

    def __init__(self, config: Optional[RoutingConfig] = None):
        self.config = config or RoutingConfig()
        self.manager = get_local_manager()
        self._routes: Dict[str, ModelRoute] = {}

    def setup_from_env(self) -> "LocalModelRouter":
        """Auto-configureaza din variabile de mediu si servere detectate."""
        import os

        # Ollama (cel mai comun)
        ollama_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL", "")

        if ollama_model:
            self.config.main_model = ollama_model
            self.config.main_base_url = ollama_url

        # LM Studio
        lmstudio_url = os.getenv("LMSTUDIO_URL", "http://localhost:1234")
        lmstudio_model = os.getenv("LMSTUDIO_MODEL", "")
        if lmstudio_model:
            self.config.main_model = lmstudio_model
            self.config.main_base_url = lmstudio_url

        # Cloud fallback
        if os.getenv("ANTHROPIC_API_KEY"):
            self.config.cloud_fallback_model = "claude-haiku-4-5-20251001"
            self.config.cloud_fallback_provider = "anthropic"
        elif os.getenv("OPENAI_API_KEY"):
            self.config.cloud_fallback_model = "gpt-4o-mini"
            self.config.cloud_fallback_provider = "openai"

        return self

    def route_task(self, task_type: str, estimated_tokens: int = 0) -> ModelRoute:
        """
        Selecteaza modelul potrivit pentru un task.

        Logica:
        1. Task simplu + tokens putini → model auxiliar mic (fast, ieftin)
        2. Task complex → model principal mare
        3. Niciun model local → cloud fallback
        """
        use_aux = (
            task_type in self.SIMPLE_TASKS
            and self.config.aux_model is not None
            and estimated_tokens <= self.config.aux_threshold_tokens
        )

        if use_aux:
            model = self.config.aux_model
            base_url = self.config.aux_base_url or self.config.main_base_url
            api_key = self.config.aux_api_key
            logger.debug(f"[ROUTER] Task '{task_type}' → aux model {model} (minimal resources)")
        else:
            model = self.config.main_model
            base_url = self.config.main_base_url
            api_key = self.config.main_api_key
            logger.debug(f"[ROUTER] Task '{task_type}' → main model {model}")

        # Verifica daca modelul local e disponibil
        if not self._is_available(base_url):
            if self.config.cloud_fallback_model:
                logger.warning(
                    f"[ROUTER] Local model {model} unavailable — "
                    f"fallback to {self.config.cloud_fallback_model}"
                )
                return ModelRoute(
                    name=self.config.cloud_fallback_model,
                    base_url="",
                    cost_factor=0.8,
                )
            raise RuntimeError(
                f"No local model available at {base_url} and no cloud fallback configured.\n"
                f"Start Ollama: ollama serve\n"
                f"Or set ANTHROPIC_API_KEY for cloud fallback."
            )

        # Citeste context length real
        ctx = self.manager.get_context_length(model, base_url, api_key)
        server_type = self.manager.get_server_type(base_url)

        return ModelRoute(
            name=model,
            base_url=base_url,
            api_key=api_key,
            context_length=ctx,
            server_type=server_type,
            cost_factor=0.0,
        )

    def _is_available(self, base_url: str) -> bool:
        if not base_url:
            return False
        try:
            import httpx
            with httpx.Client(timeout=1.5) as c:
                r = c.get(f"{base_url.rstrip('/')}/v1/models")
                return r.status_code in (200, 401)
        except Exception:
            return False

    def get_compression_model(self) -> ModelRoute:
        """
        Returneaza modelul mic pentru comprimarea contextului.
        Aceasta operatie NU trebuie sa consume din contextul modelului principal.
        """
        return self.route_task("summary", estimated_tokens=100)

    def get_title_model(self) -> ModelRoute:
        """Model mic rapid pentru generarea titlurilor de sesiune."""
        return self.route_task("title", estimated_tokens=50)

    def get_main_model(self) -> ModelRoute:
        """Modelul principal pentru taskuri complexe."""
        return self.route_task("code", estimated_tokens=10000)

    def report(self) -> Dict[str, Any]:
        """Raport despre configuratia curenta de routing."""
        servers = self.manager.scan_local_servers()
        main_ctx = 0
        if servers:
            first_url = next(iter(servers.values()))
            models = self.manager.list_available_models(first_url)
        else:
            models = []

        return {
            "local_servers": servers,
            "available_models": models,
            "routing": {
                "main": f"{self.config.main_model} @ {self.config.main_base_url}",
                "aux": f"{self.config.aux_model} @ {self.config.aux_base_url}" if self.config.aux_model else None,
                "cloud_fallback": self.config.cloud_fallback_model,
            },
        }
