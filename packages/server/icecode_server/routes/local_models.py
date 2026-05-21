"""
ICECODE Local Models API

Detecteaza, configureaza si ruleaza modele locale mari cu resurse minime.
Suporta: Ollama, LM Studio, vLLM, llama.cpp
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List

sys.path.insert(0, str(Path(__file__).parents[4] / "core"))

router = APIRouter(prefix="/api/local-models", tags=["local-models"])


@router.get("/scan")
async def scan_local_servers():
    """
    Scan local ports and detect running AI servers.
    Detecteaza automat: Ollama (11434), LM Studio (1234), llama.cpp (8080), vLLM (8000).
    """
    try:
        from icecode.local_inference.manager import get_local_manager
        manager = get_local_manager()
        servers = manager.scan_local_servers()
        result = {}
        for name, url in servers.items():
            models = manager.list_available_models(url)
            result[name] = {"url": url, "models": models, "count": len(models)}
        return {"found": len(result), "servers": result}
    except Exception as e:
        return {"found": 0, "servers": {}, "error": str(e)}


@router.get("/models")
async def list_local_models(base_url: str = "http://localhost:11434"):
    """Lista modelele disponibile pe un server local."""
    try:
        from icecode.local_inference.manager import get_local_manager
        manager = get_local_manager()
        models = manager.list_available_models(base_url)
        return {"base_url": base_url, "models": models, "count": len(models)}
    except Exception as e:
        return {"models": [], "error": str(e)}


@router.get("/info")
async def model_info(model: str, base_url: str = "http://localhost:11434"):
    """
    Informatii complete despre un model local.
    Returneaza context length REAL din GGUF metadata (nu defaultul de 2048!).
    """
    try:
        from icecode.local_inference.manager import get_local_manager
        manager = get_local_manager()
        server_type = manager.get_server_type(base_url)
        ctx_length = manager.get_context_length(model, base_url)
        stream_timeout = manager.get_stream_timeout(base_url)
        config = manager.get_client_config(model, base_url)

        return {
            "model": model,
            "base_url": base_url,
            "server_type": server_type,
            "context_length": ctx_length,
            "context_length_kb": round(ctx_length / 1024, 1),
            "stream_timeout_seconds": stream_timeout,
            "compression_threshold_tokens": int(ctx_length * 0.50),
            "ollama_num_ctx": config.get("ollama_num_ctx"),
            "is_local": True,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/routing")
async def get_routing_config():
    """
    Configuratia curenta de routing pentru modele locale.
    Arata care model e folosit pentru ce tip de task.
    """
    try:
        from icecode.local_inference.router import LocalModelRouter
        router_inst = LocalModelRouter()
        router_inst.setup_from_env()
        return router_inst.report()
    except Exception as e:
        return {"error": str(e)}


class SetupLocalRequest(BaseModel):
    main_model: str
    main_base_url: str = "http://localhost:11434"
    aux_model: Optional[str] = None
    aux_base_url: Optional[str] = None
    cloud_fallback: Optional[str] = None


@router.post("/setup")
async def setup_local_routing(req: SetupLocalRequest):
    """
    Configureaza routing-ul local:
    - main_model: modelul principal (ex: qwen2.5:7b, llama3.2:8b, deepseek-r1:8b)
    - aux_model: modelul mic pentru sumar/titluri (ex: qwen2.5:1.5b, phi3.5:3.8b)
    - cloud_fallback: model cloud daca localul nu e disponibil
    """
    import json
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    f = cfg.home_dir / "data" / "local_routing.json"
    f.parent.mkdir(parents=True, exist_ok=True)

    config = {
        "main_model": req.main_model,
        "main_base_url": req.main_base_url,
        "aux_model": req.aux_model,
        "aux_base_url": req.aux_base_url or req.main_base_url,
        "cloud_fallback": req.cloud_fallback,
    }
    f.write_text(json.dumps(config, indent=2))

    # Verifica daca modelul e disponibil
    try:
        from icecode.local_inference.manager import get_local_manager
        manager = get_local_manager()
        ctx = manager.get_context_length(req.main_model, req.main_base_url)
        config["context_length"] = ctx
        config["status"] = "configured"
    except Exception as e:
        config["status"] = "configured_but_model_unavailable"
        config["warning"] = str(e)

    return config


@router.post("/chat")
async def local_chat(
    message: str,
    model: str = "qwen2.5:7b",
    base_url: str = "http://localhost:11434",
    stream: bool = False,
):
    """
    Chat direct cu un model local.
    Foloseste context length real din GGUF si timeout adaptat.
    """
    try:
        from icecode.local_inference.manager import get_local_manager
        manager = get_local_manager()
        config = manager.get_client_config(model, base_url)

        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            base_url=f"{base_url.rstrip('/')}/v1",
            api_key="ollama",
        )

        extra_body = {}
        if config.get("ollama_num_ctx"):
            extra_body["num_ctx"] = config["ollama_num_ctx"]

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": message}],
            stream=False,
            extra_body=extra_body if extra_body else None,
        )
        return {
            "response": response.choices[0].message.content,
            "model": model,
            "context_length_used": config["context_length"],
            "server_type": config["server_type"],
        }
    except Exception as e:
        return {"error": str(e), "hint": f"Asigura-te ca {base_url} este pornit si modelul {model} este descarcat"}
