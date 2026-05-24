"""
ICECODE Agents API
Agents from all 3 original projects: ClawX + Hermes (56 toolsets) + OpenCode.
Auto-selects best available Ollama model per agent role.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/agents", tags=["agents"])

# ── Model priority lists per agent role ──────────────────────────────────────
# First match wins against what's actually installed in Ollama.

_CODING_PREF   = ["qwen2.5-coder:7b", "deepseek-r1:8b", "qwen2.5:7b",
                  "qwen3.5:4b", "mistral:7b-instruct", "phi4-mini:latest",
                  "granite4.1:3b", "qwen2.5:3b", "qwen3.5:2b"]
_REASONING_PREF = ["deepseek-r1:8b", "phi4-mini:latest", "qwen2.5:7b",
                   "qwen3.5:4b", "mistral:7b-instruct", "qwen2.5:3b"]
_GENERAL_PREF  = ["qwen2.5:7b", "qwen3.5:4b", "mistral:7b-instruct",
                  "qwen2.5-coder:7b", "qwen2.5:3b", "phi4-mini:latest",
                  "granite4.1:3b", "qwen3.5:2b"]
_FAST_PREF     = ["qwen3.5:4b", "phi4-mini:latest", "qwen2.5:3b",
                  "granite4.1:3b", "qwen3.5:2b", "qwen2.5:1.5b", "llama3.2:1b"]
_MICRO_PREF    = ["qwen2.5:0.5b-instruct", "qwen3.5:0.8b", "qwen2.5:1.5b",
                  "llama3.2:1b", "qwen3.5:2b"]
_BROWSER_PREF  = ["qwen2.5:7b", "qwen3.5:4b", "mistral:7b-instruct",
                  "qwen2.5-coder:7b", "phi4-mini:latest"]
_VISION_PREF   = ["qwen3.6:latest", "qwen2.5:7b", "qwen3.5:4b"]


def _get_ollama_models() -> List[str]:
    """Return list of installed Ollama model names."""
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


def _pick(prefs: List[str], installed: List[str]) -> str:
    """Return first preferred model that is installed, or first installed model."""
    for p in prefs:
        for m in installed:
            # exact match or starts-with (e.g. "qwen2.5:7b" matches "qwen2.5:7b-q4_0")
            if m == p or m.startswith(p.split(":")[0] + ":" + p.split(":")[1]):
                return m
    # fallback: first installed model of any kind
    return installed[0] if installed else "qwen2.5:7b"


def _auto_models() -> dict:
    """Return a role→model mapping based on what's actually installed."""
    installed = _get_ollama_models()
    if not installed:
        # Ollama not reachable — return empty markers so callers know
        return {k: "" for k in ("coding","reasoning","general","fast","micro","browser","vision")}
    return {
        "coding":    _pick(_CODING_PREF, installed),
        "reasoning": _pick(_REASONING_PREF, installed),
        "general":   _pick(_GENERAL_PREF, installed),
        "fast":      _pick(_FAST_PREF, installed),
        "micro":     _pick(_MICRO_PREF, installed),
        "browser":   _pick(_BROWSER_PREF, installed),
        "vision":    _pick(_VISION_PREF, installed),
    }


# ICECODE 56 toolsets + OpenCode) ───────

def _default_agents() -> List[dict]:
    """Build default agents with auto-detected models."""
    m = _auto_models()

    return [
        # ── FROM OPENCODE: build + plan agents ───────────────────────────────
        {
            "id": "agent_build",
            "name": "Build Agent",
            "description": "Main execution agent — writes code, runs commands, modifies files.",
            "model": m["coding"],
            "provider": "ollama",
            "tools": ["read_file", "write_file", "list_dir", "run_terminal", "web_fetch", "search_web"],
            "system_prompt": (
                "You are the main execution agent. You write code, modify files, "
                "run terminal commands and deliver complete solutions. "
                "You act directly without asking confirmation for reversible operations."
            ),
            "mode": "primary",
            "source": "opencode",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },
        {
            "id": "agent_plan",
            "name": "Plan Agent",
            "description": "Planning mode — analyzes and plans without modifying files.",
            "model": m["reasoning"],
            "provider": "ollama",
            "tools": ["read_file", "list_dir", "web_fetch", "search_web", "recall", "remember"],
            "system_prompt": (
                "You are a planning agent. You analyze the problem, read relevant files "
                "and create a detailed plan. Do NOT modify files and do NOT run code. "
                "Clearly explain what steps need to be followed and why."
            ),
            "mode": "primary",
            "source": "opencode",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },

        # ── FROM HERMES: hermes-cli toolset (full featured) ──────────────────
        {
            "id": "agent_fullstack",
            "name": "Full Stack Agent",
            "description": "Full agent with all toolsets: web, terminal, files, memory, code.",
            "model": m["coding"],
            "provider": "ollama",
            "tools": ["read_file", "write_file", "list_dir", "run_terminal",
                      "web_fetch", "search_web", "remember", "recall"],
            "system_prompt": (
                "You are a full-stack agent with full system access. "
                "You can read/write files, run commands, search the web and store information. "
                "You solve complex tasks that require multiple capabilities simultaneously."
            ),
            "source": "hermes",
            "toolset": "hermes-cli",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },

        # ── FROM HERMES: browser toolset ─────────────────────────────────────
        {
            "id": "agent_browser",
            "name": "Browser Agent",
            "description": "Browser automation — navigate, extract data, interact with web pages.",
            "model": m["browser"],
            "provider": "ollama",
            "tools": ["web_fetch", "search_web", "read_file", "write_file", "run_terminal"],
            "system_prompt": (
                "You are an agent specialized in web navigation and data extraction. "
                "You navigate web pages, extract information, fill forms and "
                "automate tasks that require browser interaction."
            ),
            "source": "hermes",
            "toolset": "browser",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },

        # ── FROM HERMES: computer_use toolset ────────────────────────────────
        {
            "id": "agent_computer",
            "name": "Autonomous Computer Agent",
            "description": "Full desktop control — screenshot, click, typing, open applications.",
            "model": m["general"],
            "provider": "ollama",
            "tools": ["screenshot", "click", "type_text", "hotkey", "open_app",
                      "move_mouse", "scroll", "get_screen_size",
                      "read_file", "write_file", "run_terminal"],
            "system_prompt": (
                "You are an autonomous agent that controls the computer. "
                "You take screenshots to understand screen state, click on elements, "
                "type text, open applications and complete complex tasks without human intervention. "
                "Always verify with screenshots that actions have the desired effect."
            ),
            "enable_computer": True,
            "source": "clawx+hermes",
            "toolset": "computer_use",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },

        # ── FROM HERMES: research/web toolset ────────────────────────────────
        {
            "id": "agent_research",
            "name": "Research Agent",
            "description": "Deep web research, analysis and reports.",
            "model": m["general"],
            "provider": "ollama",
            "tools": ["web_fetch", "search_web", "read_file", "write_file", "remember", "recall"],
            "system_prompt": (
                "You are a research agent. You search information from multiple sources, "
                "analyze content, verify facts and create comprehensive reports. "
                "You save important information to memory for later use."
            ),
            "source": "hermes",
            "toolset": "web+memory",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },

        # ── FROM HERMES: code_execution + terminal toolset ───────────────────
        {
            "id": "agent_coder",
            "name": "Coding Agent",
            "description": "Code specialist — writes, tests and debugs code.",
            "model": m["coding"],
            "provider": "ollama",
            "tools": ["read_file", "write_file", "list_dir", "run_terminal", "web_fetch"],
            "system_prompt": (
                "You are a programming expert. You write clean and efficient code, "
                "create complete projects, debug errors and optimize performance. "
                "You test everything you write by running code in the terminal."
            ),
            "source": "hermes",
            "toolset": "code_execution+terminal",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },

        # ── FROM HERMES: memory + skills toolset ─────────────────────────────
        {
            "id": "agent_memory",
            "name": "Memory Agent",
            "description": "Persistent memory and self-learning.",
            "model": m["fast"],
            "provider": "ollama",
            "tools": ["remember", "recall", "read_file", "write_file", "search_web"],
            "system_prompt": (
                "You are an agent with persistent memory. You save important information, "
                "you remember context from previous sessions and learn from interactions. "
                "When asked something, you check memory first before answering."
            ),
            "source": "hermes",
            "toolset": "memory+skills",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },

        # ── FROM HERMES: kanban + delegation (multi-agent orchestration) ──────
        {
            "id": "agent_orchestrator",
            "name": "Orchestrator Agent",
            "description": "Multi-agent coordination, task delegation, kanban management.",
            "model": m["reasoning"],
            "provider": "ollama",
            "tools": ["read_file", "write_file", "run_terminal", "web_fetch", "remember", "recall"],
            "system_prompt": (
                "You are an orchestrator agent. You analyze complex tasks, break them into "
                "subtasks, coordinate execution and monitor progress. "
                "You delegate subtasks to specialized agents and integrate the results."
            ),
            "source": "hermes",
            "toolset": "kanban+delegation",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },

        # ── FROM HERMES: todo + cronjob toolset ──────────────────────────────
        {
            "id": "agent_scheduler",
            "name": "Scheduler Agent",
            "description": "Task scheduling, cron jobs, and todo lists.",
            "model": m["fast"],
            "provider": "ollama",
            "tools": ["read_file", "write_file", "run_terminal", "remember", "recall"],
            "system_prompt": (
                "You are a planning and scheduling agent. You manage task lists, "
                "create cron jobs, track deadlines and report progress. "
                "You organize work efficiently and ensure nothing is missed."
            ),
            "source": "hermes",
            "toolset": "todo+cronjob",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },

        # ── FROM HERMES: safe toolset (no terminal) ───────────────────────────
        {
            "id": "agent_safe",
            "name": "Safe Agent",
            "description": "Agent without terminal access — read-only files and web. Ideal for restricted environments.",
            "model": m["fast"],
            "provider": "ollama",
            "tools": ["read_file", "web_fetch", "search_web", "remember", "recall"],
            "system_prompt": (
                "You are a safe agent without terminal access or file modification. "
                "You can read files, search the web and store information. "
                "You provide analysis, explanations and answers without executing code."
            ),
            "source": "hermes",
            "toolset": "safe",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },

        # ── FROM HERMES: debugging toolset ───────────────────────────────────
        {
            "id": "agent_debugger",
            "name": "Debug Agent",
            "description": "Bug diagnosis and resolution. Toolset 'debugging' from ICECODE.",
            "model": m["coding"],
            "provider": "ollama",
            "tools": ["read_file", "write_file", "list_dir", "run_terminal", "web_fetch"],
            "system_prompt": (
                "You are a debugging expert. You analyze errors, study stack traces, "
                "identify the root cause of problems and apply fixes. "
                "You run code step by step and verify each hypothesis before fixing."
            ),
            "source": "hermes",
            "toolset": "debugging",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },

        # ── FROM HERMES: data analysis (hermes-acp) ───────────────────────────
        {
            "id": "agent_data",
            "name": "Data Analysis Agent",
            "description": "Data analysis, statistics, charts. Inspired by toolset hermes-acp (VS Code/editor integration).",
            "model": m["coding"],
            "provider": "ollama",
            "tools": ["read_file", "write_file", "run_terminal", "list_dir", "web_fetch"],
            "system_prompt": (
                "You are a data analysis agent. You process CSV, JSON, SQL, create visualizations "
                "with Python (matplotlib, pandas), calculate statistics and explain results clearly. "
                "You write clean and documented Python scripts."
            ),
            "source": "hermes",
            "toolset": "hermes-acp",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },

        # ── FROM CLAWX: model-agnostic fast agent ─────────────────────────────
        {
            "id": "agent_fast",
            "name": "Fast Agent",
            "description": "Fast responses with the smallest available model.",
            "model": m["micro"],
            "provider": "ollama",
            "tools": ["read_file", "list_dir", "remember"],
            "system_prompt": "You are a fast and concise assistant. You respond briefly, directly and to the point.",
            "source": "clawx",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },

        # ── VISION agent (uses largest/multimodal model) ──────────────────────
        {
            "id": "agent_vision",
            "name": "Vision Agent",
            "description": "Image and screen analysis. Uses the most capable vision model available.",
            "model": m["vision"],
            "provider": "ollama",
            "tools": ["screenshot", "read_file", "write_file", "web_fetch"],
            "system_prompt": (
                "You are an agent specialized in visual analysis. You analyze images, "
                "take screenshots and describe what you see in detail. "
                "You can read text from images, identify UI elements and analyze visual content."
            ),
            "source": "hermes",
            "toolset": "vision",
            "enabled": True,
            "created_at": "2026-05-20T00:00:00",
        },
    ]


# ── Persistence ───────────────────────────────────────────────────────────────

def _get_file():
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    return cfg.home_dir / "data" / "agents.json"


def _load_agents():
    import json
    f = _get_file()
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    # First run — seed with auto-detected defaults
    agents = _default_agents()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(agents, indent=2))
    return agents


def _save_agents(agents):
    import json
    f = _get_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(agents, indent=2))


# ── Schema ────────────────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    model: str = "auto"       # "auto" → pick best available
    provider: str = "ollama"
    tools: List[str] = []
    system_prompt: Optional[str] = None
    channel_ids: List[str] = []
    enabled: bool = True
    mode: Optional[str] = None
    enable_computer: bool = False


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    tools: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    enabled: Optional[bool] = None
    enable_computer: Optional[bool] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/")
@router.get("")
async def list_agents():
    return _load_agents()


@router.get("/auto-models")
async def get_auto_models():
    """Show which model would be auto-selected per role."""
    installed = _get_ollama_models()
    models = _auto_models()
    return {
        "installed": installed,
        "auto_selected": models,
        "total_installed": len(installed),
    }


@router.post("/reload-defaults")
async def reload_defaults():
    """Regenerate default agents with currently available models."""
    import json
    agents = _default_agents()
    f = _get_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(agents, indent=2))
    return {
        "ok": True,
        "count": len(agents),
        "models_used": _auto_models(),
        "message": f"Reloaded {len(agents)} agents with available models",
    }


@router.post("/")
@router.post("")
async def create_agent(req: AgentCreate):
    agents = _load_agents()

    # Auto-resolve model if "auto" or empty
    model = req.model
    if not model or model == "auto":
        model = _pick(_GENERAL_PREF, _get_ollama_models())

    agent = {
        "id": f"agent_{uuid.uuid4().hex[:8]}",
        "name": req.name,
        "description": req.description or "",
        "model": model,
        "provider": req.provider,
        "tools": req.tools,
        "system_prompt": req.system_prompt,
        "channel_ids": req.channel_ids,
        "enabled": req.enabled,
        "mode": req.mode,
        "enable_computer": req.enable_computer,
        "source": "user",
        "created_at": datetime.now().isoformat(),
    }
    agents.append(agent)
    _save_agents(agents)
    return agent


@router.put("/{agent_id}")
async def update_agent(agent_id: str, req: AgentUpdate):
    agents = _load_agents()
    for agent in agents:
        if agent["id"] == agent_id:
            if req.name is not None:            agent["name"] = req.name
            if req.description is not None:     agent["description"] = req.description
            if req.model is not None:
                model = req.model
                if model == "auto":
                    model = _pick(_GENERAL_PREF, _get_ollama_models())
                agent["model"] = model
            if req.provider is not None:        agent["provider"] = req.provider
            if req.tools is not None:           agent["tools"] = req.tools
            if req.system_prompt is not None:   agent["system_prompt"] = req.system_prompt
            if req.enabled is not None:         agent["enabled"] = req.enabled
            if req.enable_computer is not None: agent["enable_computer"] = req.enable_computer
            _save_agents(agents)
            return agent
    raise HTTPException(status_code=404, detail="Agent not found")


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    agents = _load_agents()
    agents = [a for a in agents if a["id"] != agent_id]
    _save_agents(agents)
    return {"ok": True}


class AgentGenerateRequest(BaseModel):
    description: str
    name: Optional[str] = None


@router.post("/generate")
async def generate_agent(req: AgentGenerateRequest):
    """
    Auto-generate an agent config from a natural language description.
    Uses the best available Ollama model to produce name, system_prompt, and tools list.
    """
    import httpx as _httpx

    installed = _get_ollama_models()
    model = _pick(_GENERAL_PREF, installed) if installed else "qwen2.5:7b"

    prompt = f"""You are an AI agent configuration generator. Given a description, output a JSON object for an agent.

Description: {req.description}

Available tools: read_file, write_file, list_dir, run_terminal, web_fetch, search_web, remember, recall, create_task, list_tasks, screenshot, click, type_text

Output ONLY valid JSON with these exact fields:
{{
  "name": "short agent name",
  "description": "one sentence description",
  "system_prompt": "detailed system prompt for this agent role",
  "tools": ["tool1", "tool2"],
  "model_role": "coding|reasoning|general|fast|browser|vision"
}}"""

    try:
        r = _httpx.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"num_ctx": 4096, "num_predict": 512, "temperature": 0.2}},
            timeout=30,
        )
        if r.status_code != 200:
            raise Exception(f"Ollama error: {r.status_code}")

        raw = r.json().get("response", "")
        # Extract JSON from response
        import re
        json_match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if not json_match:
            raise Exception("No JSON in response")

        config = json.loads(json_match.group())
        role = config.pop("model_role", "general")
        auto_m = _auto_models()
        chosen_model = auto_m.get(role, auto_m.get("general", "qwen2.5:7b"))

        agent = {
            "id": f"agent_{uuid.uuid4().hex[:8]}",
            "name": req.name or config.get("name", "Generated Agent"),
            "description": config.get("description", req.description),
            "model": chosen_model,
            "provider": "ollama",
            "tools": config.get("tools", ["read_file", "write_file", "run_terminal"]),
            "system_prompt": config.get("system_prompt", ""),
            "enabled": True,
            "source": "generated",
            "created_at": datetime.now().isoformat(),
        }

        agents = _load_agents()
        agents.append(agent)
        _save_agents(agents)
        return {"ok": True, "agent": agent, "model_used": model}

    except Exception as e:
        # Fallback: create basic agent from description keywords
        tools = ["read_file", "write_file", "run_terminal"]
        desc_lower = req.description.lower()
        if any(x in desc_lower for x in ("web", "search", "browser", "scrape")):
            tools = ["web_fetch", "search_web", "read_file", "write_file"]
        elif any(x in desc_lower for x in ("memory", "remember", "learn")):
            tools = ["remember", "recall", "read_file", "write_file"]
        elif any(x in desc_lower for x in ("computer", "desktop", "screen", "click")):
            tools = ["screenshot", "click", "type_text", "run_terminal"]

        auto_m = _auto_models()
        agent = {
            "id": f"agent_{uuid.uuid4().hex[:8]}",
            "name": req.name or "Generated Agent",
            "description": req.description,
            "model": auto_m.get("general", "qwen2.5:7b"),
            "provider": "ollama",
            "tools": tools,
            "system_prompt": f"You are an AI agent: {req.description}",
            "enabled": True,
            "source": "generated",
            "created_at": datetime.now().isoformat(),
        }
        agents = _load_agents()
        agents.append(agent)
        _save_agents(agents)
        return {"ok": True, "agent": agent, "fallback": True, "error": str(e)}
