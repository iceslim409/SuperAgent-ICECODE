"""
ICECODE Agent Core — clean, standalone agent engine.

Uses openai-SDK (compatible with Ollama, LM Studio, vLLM, and all cloud providers).
Supports streaming, tool calling, context window tracking, and skill evolution.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from loguru import logger

# Import computer control tools (lazy — only used when enable_computer=True)
_COMPUTER_TOOLS_LOADED = False
_COMPUTER_TOOLS: List[Dict] = []
_exec_computer_tool = None

def _load_computer_tools():
    global _COMPUTER_TOOLS_LOADED, _COMPUTER_TOOLS, _exec_computer_tool
    if not _COMPUTER_TOOLS_LOADED:
        try:
            from icecode.agent.computer_tools import COMPUTER_TOOLS, exec_computer_tool
            _COMPUTER_TOOLS = COMPUTER_TOOLS
            _exec_computer_tool = exec_computer_tool
            _COMPUTER_TOOLS_LOADED = True
        except Exception as e:
            logger.warning(f"Computer tools not available: {e}")
    return _COMPUTER_TOOLS, _exec_computer_tool

# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the content of a file from disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file on disk (creates parent dirs if needed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and directories at a given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default: current dir)"},
                    "pattern": {"type": "string", "description": "Optional glob pattern"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_terminal",
            "description": "Run a shell command and return stdout+stderr. Timeout 30s.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "cwd": {"type": "string", "description": "Working directory (optional)"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch a URL and return its text content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "max_chars": {"type": "integer", "description": "Max chars to return (default 4000)"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web using DuckDuckGo and return top results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "description": "Number of results (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Store a fact or insight in agent memory for future sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Short identifier"},
                    "value": {"type": "string", "description": "Content to remember"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Recall all stored memories or search by key prefix.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prefix": {"type": "string", "description": "Optional key prefix filter"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a kanban task to track work. Use for multi-step plans.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short task title"},
                    "description": {"type": "string", "description": "Details about the task"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                    "status": {"type": "string", "enum": ["todo", "in_progress", "done", "blocked"]},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List current kanban tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status (optional)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update a task status or details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID"},
                    "status": {"type": "string", "enum": ["todo", "in_progress", "done", "blocked", "cancelled"]},
                    "description": {"type": "string"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_goal",
            "description": "Set a persistent goal that persists across sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The goal to set"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_goals",
            "description": "Get all active persistent goals.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_fetch",
            "description": "Fetch a URL using headless browser (handles JS-rendered pages). Use when web_fetch fails.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "extract": {"type": "string", "enum": ["text", "links", "structured"], "description": "What to extract"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Search the local knowledge base (indexed documents, files, notes). Use this before searching the web if the topic might be in local files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "k": {"type": "integer", "description": "Number of results to return (default 5)", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_to_agent",
            "description": "Delegate a subtask to a specialized sub-agent and get its response. Use for complex subtasks that benefit from focused attention.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "Role/specialization for the sub-agent (e.g. 'researcher', 'coder', 'writer')"},
                    "task": {"type": "string", "description": "Detailed task description for the sub-agent"},
                    "context": {"type": "string", "description": "Optional context to pass to the sub-agent"},
                },
                "required": ["role", "task"],
            },
        },
    },
]


# ── Tool execution ─────────────────────────────────────────────────────────────

async def _exec_tool(name: str, args: Dict) -> str:
    try:
        if name == "read_file":
            p = Path(args["path"]).expanduser()
            if not p.exists():
                return f"Error: file not found: {args['path']}"
            content = p.read_text(errors="replace")
            if len(content) > 8000:
                content = content[:8000] + f"\n... (truncated, {len(content)} total chars)"
            return content

        elif name == "write_file":
            p = Path(args["path"]).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"])
            return f"Written {len(args['content'])} chars to {p}"

        elif name == "list_dir":
            p = Path(args.get("path", ".")).expanduser()
            pattern = args.get("pattern", "*")
            if not p.exists():
                return f"Error: path not found: {p}"
            items = sorted(p.glob(pattern))
            lines = []
            for item in items[:100]:
                kind = "DIR" if item.is_dir() else "FILE"
                size = "" if item.is_dir() else f" ({item.stat().st_size} B)"
                lines.append(f"[{kind}] {item.name}{size}")
            if len(items) > 100:
                lines.append(f"... {len(items) - 100} more items")
            return "\n".join(lines) or "(empty directory)"

        elif name == "run_terminal":
            cmd = args["command"]
            cwd = args.get("cwd") or os.getcwd()
            result = subprocess.run(
                cmd, shell=True, cwd=cwd,
                capture_output=True, text=True, timeout=30,
            )
            out = result.stdout[-4000:] if result.stdout else ""
            err = result.stderr[-2000:] if result.stderr else ""
            parts = []
            if out:
                parts.append(f"STDOUT:\n{out}")
            if err:
                parts.append(f"STDERR:\n{err}")
            parts.append(f"Exit code: {result.returncode}")
            return "\n".join(parts)

        elif name == "web_fetch":
            max_chars = args.get("max_chars", 4000)
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                resp = await client.get(args["url"], headers={"User-Agent": "ICECODE/1.0"})
                text = resp.text[:max_chars]
                return f"[{resp.status_code}] {args['url']}\n\n{text}"

        elif name == "search_web":
            query = args["query"]
            max_results = min(args.get("max_results", 5), 10)
            url = f"https://html.duckduckgo.com/html/?q={httpx.URL(query).query}"
            async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                import re
                results = re.findall(r'<a class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', resp.text)
                lines = [f"{i+1}. {title.strip()} — {url}" for i, (url, title) in enumerate(results[:max_results])]
                return "\n".join(lines) or "No results found"

        elif name == "remember":
            mem_dir = Path.home() / ".icecode" / "agent_memory"
            mem_dir.mkdir(parents=True, exist_ok=True)
            f = mem_dir / "memories.json"
            memories: Dict = json.loads(f.read_text()) if f.exists() else {}
            memories[args["key"]] = {
                "value": args["value"],
                "timestamp": datetime.now().isoformat(),
            }
            f.write_text(json.dumps(memories, indent=2))
            return f"Remembered: {args['key']}"

        elif name == "recall":
            mem_dir = Path.home() / ".icecode" / "agent_memory"
            f = mem_dir / "memories.json"
            if not f.exists():
                return "No memories stored yet"
            memories: Dict = json.loads(f.read_text())
            prefix = args.get("prefix", "")
            filtered = {k: v for k, v in memories.items() if k.startswith(prefix)}
            if not filtered:
                return "No memories found"
            lines = [f"[{k}] {v['value']} (saved: {v['timestamp'][:10]})" for k, v in filtered.items()]
            return "\n".join(lines)

        elif name == "create_task":
            db_file = Path.home() / ".icecode" / "data" / "kanban.json"
            db_file.parent.mkdir(parents=True, exist_ok=True)
            db = json.loads(db_file.read_text()) if db_file.exists() else {"boards": {"default": {"tasks": []}}}
            if "boards" not in db:
                db["boards"] = {"default": {"tasks": []}}
            if "default" not in db["boards"]:
                db["boards"]["default"] = {"tasks": []}
            import uuid as _uuid
            task = {
                "id": f"task_{_uuid.uuid4().hex[:8]}",
                "title": args["title"],
                "description": args.get("description", ""),
                "status": args.get("status", "todo"),
                "priority": args.get("priority", "medium"),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            db["boards"]["default"]["tasks"].append(task)
            db_file.write_text(json.dumps(db, indent=2))
            return f"Task created: [{task['id']}] {task['title']} ({task['status']})"

        elif name == "list_tasks":
            db_file = Path.home() / ".icecode" / "data" / "kanban.json"
            if not db_file.exists():
                return "No tasks yet"
            db = json.loads(db_file.read_text())
            tasks = db.get("boards", {}).get("default", {}).get("tasks", [])
            status_filter = args.get("status")
            if status_filter:
                tasks = [t for t in tasks if t.get("status") == status_filter]
            if not tasks:
                return "No tasks found"
            lines = [f"[{t['id']}] ({t['status']}/{t['priority']}) {t['title']}" for t in tasks]
            return "\n".join(lines)

        elif name == "update_task":
            db_file = Path.home() / ".icecode" / "data" / "kanban.json"
            if not db_file.exists():
                return "No tasks found"
            db = json.loads(db_file.read_text())
            task_id = args["task_id"]
            for t in db.get("boards", {}).get("default", {}).get("tasks", []):
                if t["id"] == task_id:
                    if "status" in args:
                        t["status"] = args["status"]
                    if "description" in args:
                        t["description"] = args["description"]
                    t["updated_at"] = datetime.now().isoformat()
                    db_file.write_text(json.dumps(db, indent=2))
                    return f"Task updated: [{t['id']}] {t['title']} → {t['status']}"
            return f"Task {task_id} not found"

        elif name == "set_goal":
            goals_file = Path.home() / ".icecode" / "data" / "goals.json"
            goals_file.parent.mkdir(parents=True, exist_ok=True)
            goals = json.loads(goals_file.read_text()) if goals_file.exists() else []
            import uuid as _uuid
            goal = {
                "id": f"goal_{_uuid.uuid4().hex[:8]}",
                "text": args["text"],
                "priority": args.get("priority", "medium"),
                "completed": False,
                "created_at": datetime.now().isoformat(),
            }
            goals.append(goal)
            goals_file.write_text(json.dumps(goals, indent=2))
            return f"Goal set: {args['text']}"

        elif name == "get_goals":
            goals_file = Path.home() / ".icecode" / "data" / "goals.json"
            if not goals_file.exists():
                return "No goals set"
            goals = json.loads(goals_file.read_text())
            active = [g for g in goals if not g.get("completed")]
            if not active:
                return "No active goals"
            lines = [f"[{g['priority']}] {g['text']}" for g in active]
            return "Active goals:\n" + "\n".join(lines)

        elif name == "browser_fetch":
            try:
                from playwright.async_api import async_playwright
                url = args["url"]
                extract = args.get("extract", "text")
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
                    page = await browser.new_page()
                    page.set_default_timeout(15000)
                    await page.goto(url, wait_until="load")
                    title = await page.title()
                    if extract == "links":
                        links = await page.eval_on_selector_all(
                            "a[href]", "els => els.slice(0,30).map(e=>({text:e.innerText.trim(),href:e.href}))"
                        )
                        result = f"[{title}] Links:\n" + "\n".join([f"  {l['text']}: {l['href']}" for l in links])
                    elif extract == "structured":
                        data = await page.evaluate("""() => ({
                            h: Array.from(document.querySelectorAll('h1,h2,h3')).slice(0,8).map(e=>e.innerText.trim()),
                            p: Array.from(document.querySelectorAll('p')).slice(0,10).map(e=>e.innerText.trim()).filter(t=>t.length>30)
                        })""")
                        result = f"[{title}]\nHeadings: {data['h']}\nContent: {' | '.join(data['p'][:5])}"
                    else:
                        content = await page.inner_text("body")
                        result = f"[{title}] {url}\n\n{content[:5000]}"
                    await browser.close()
                    return result
            except ImportError:
                # Fallback to regular httpx fetch
                async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                    resp = await client.get(args["url"], headers={"User-Agent": "Mozilla/5.0"})
                    return f"[{resp.status_code}] {args['url']}\n\n{resp.text[:4000]}"

        elif name == "search_knowledge":
            try:
                from icecode.knowledge.manager import KnowledgeManager
                km = KnowledgeManager.instance()
                results = km.search(args["query"], k=args.get("k", 5))
                if not results:
                    return "No results found in knowledge base."
                lines = []
                for i, r in enumerate(results, 1):
                    lines.append(f"[{i}] Source: {r.get('source', 'unknown')} (score: {r.get('score', 0):.3f})")
                    lines.append(r.get("text", ""))
                    lines.append("")
                return "\n".join(lines)
            except ImportError:
                return "Knowledge base not available. Index files first via /api/knowledge/index."
            except Exception as e:
                return f"Knowledge search error: {e}"

        elif name == "delegate_to_agent":
            try:
                from icecode.swarm.worker import SwarmWorker
                worker = SwarmWorker(
                    role=args["role"],
                    max_iterations=5,
                )
                output_parts = []
                async for chunk in worker.run(args["task"], args.get("context", "")):
                    if chunk.get("type") == "text":
                        output_parts.append(chunk.get("content", ""))
                return "".join(output_parts) or "(no output)"
            except Exception as e:
                return f"Delegation error: {e}"

        else:
            return f"Unknown tool: {name}"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30s"
    except Exception as e:
        return f"Tool error ({name}): {type(e).__name__}: {e}"


# ── Provider config ────────────────────────────────────────────────────────────

def _get_client_config(model: str, provider: str, base_url: Optional[str] = None) -> Dict:
    """Return openai SDK init kwargs for the given provider/model."""
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()

    # Explicit custom base_url (e.g. LM Studio, vLLM, other Ollama instance)
    if base_url:
        return {
            "base_url": f"{base_url.rstrip('/')}/v1",
            "api_key": "local",
            "model": model or "local-model",
        }

    # Local Ollama
    if provider in ("ollama", "") or not provider:
        ollama_base = cfg.ollama_host if hasattr(cfg, "ollama_host") else "http://localhost:11434"
        return {
            "base_url": f"{ollama_base}/v1",
            "api_key": "ollama",
            "model": model or cfg.ollama_model or "qwen2.5:7b",
            "_is_ollama": True,
        }

    # Custom local server passed as URL string
    if provider and provider.startswith("http"):
        return {
            "base_url": f"{provider.rstrip('/')}/v1",
            "api_key": "local",
            "model": model,
        }

    # Default: Ollama (no cloud keys)
    return {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "model": model or "qwen2.5:7b",
        "_is_ollama": True,
    }


# ── Usage tracker ──────────────────────────────────────────────────────────────

class UsageTracker:
    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.tool_calls_made = 0
        self.iterations = 0
        self.tools_used: List[str] = []
        self.start_time = time.time()

    def update(self, usage_obj):
        if usage_obj:
            self.prompt_tokens += getattr(usage_obj, "prompt_tokens", 0) or 0
            self.completion_tokens += getattr(usage_obj, "completion_tokens", 0) or 0

    def record_tool(self, tool_name: str):
        self.tool_calls_made += 1
        self.tools_used.append(tool_name)

    def to_dict(self) -> Dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "tool_calls": self.tool_calls_made,
            "tools_used": self.tools_used,
            "iterations": self.iterations,
            "elapsed_seconds": round(time.time() - self.start_time, 1),
        }


# ── Main Agent class ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are ICECODE — an advanced AI super-agent with tool-calling capabilities.

You can:
- Read and write files on the user's system
- Run terminal commands
- Search the web and fetch URLs
- Remember facts across sessions (use `remember` + `recall`)
- Create complete projects, write code, debug, research

Guidelines:
- Think step-by-step. Break complex tasks into sub-tasks.
- Use tools proactively — don't just describe, actually do.
- After completing a task, store lessons learned with `remember`.
- Be concise in text but thorough in actions.
- When creating a project: plan → scaffold → implement → test → summarize.

Current date: {date}
Working directory: {cwd}
"""


class ICECodeAgent:
    """Clean ICECODE agent — openai-SDK streaming, full tool loop, usage tracking."""

    def __init__(
        self,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        max_iterations: int = 10,
        session_id: Optional[str] = None,
        enable_computer: bool = False,
        system_extra: str = "",
    ):
        self.model = model
        self.provider = provider or "ollama"
        self.base_url = base_url
        self.max_iterations = max_iterations
        self.session_id = session_id or f"s_{uuid.uuid4().hex[:8]}"
        self.history: List[Dict] = []
        self.usage = UsageTracker()
        self.enable_computer = enable_computer
        self.system_extra = system_extra

    def _system(self) -> str:
        extra = ""

        # Inject active goals
        try:
            goals_file = Path.home() / ".icecode" / "data" / "goals.json"
            if goals_file.exists():
                goals = json.loads(goals_file.read_text())
                active = [g for g in goals if not g.get("completed")]
                if active:
                    lines = ["STANDING GOALS (always keep these in mind):"]
                    for g in active:
                        emoji = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(g.get("priority", "medium"), "•")
                        lines.append(f"  {emoji} {g['text']}")
                    extra += "\n\n" + "\n".join(lines)
        except Exception:
            pass

        if self.enable_computer:
            extra += (
                "\n\nCOMPUTER CONTROL ENABLED:\n"
                "You can also control the desktop:\n"
                "- screenshot: see the screen\n"
                "- click: click at coordinates\n"
                "- type_text: type keyboard input\n"
                "- hotkey: press key combos\n"
                "- open_app: launch applications\n"
                "- scroll, move_mouse, focus_window\n"
                "Always screenshot first to understand the current screen state before clicking.\n"
                "You are fully autonomous — complete tasks without user intervention.\n"
            )
        if self.system_extra:
            extra += f"\n\n{self.system_extra}"
        return SYSTEM_PROMPT.format(
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            cwd=os.getcwd(),
        ) + extra

    async def stream(self, user_message: str) -> AsyncGenerator[Dict, None]:
        """Stream chunks: {type: session|text|tool_call|tool_result|usage|done|error}"""
        from openai import AsyncOpenAI

        yield {"type": "session", "session_id": self.session_id}

        # Build active tool list
        active_tools = list(TOOLS)
        computer_exec = None
        if self.enable_computer:
            computer_tool_defs, computer_exec = _load_computer_tools()
            active_tools = active_tools + computer_tool_defs

        cfg = _get_client_config(self.model or "", self.provider, self.base_url)
        actual_model = cfg.pop("model")
        is_ollama = cfg.pop("_is_ollama", False)

        client = AsyncOpenAI(
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            timeout=300.0,
        )

        self.history.append({"role": "user", "content": user_message})

        # Trim history to last N exchanges to avoid context overflow on small models.
        # Keep system prompt (injected separately) + last 12 messages = ~6 exchanges.
        trimmed = self.history[-12:] if len(self.history) > 12 else self.history
        messages = [{"role": "system", "content": self._system()}] + trimmed

        # Ollama performance options: limit context window + disable thinking for qwen3/deepseek-r1
        _ollama_extra: Dict = {}
        if is_ollama:
            opts: Dict = {"num_ctx": 8192, "num_predict": 2048}
            model_lower = actual_model.lower()
            # Disable extended thinking for models that support /no_think
            if any(x in model_lower for x in ("qwen3", "deepseek-r1", "qwq")):
                opts["think"] = False
            _ollama_extra = {"extra_body": {"options": opts}}

        self.usage.iterations = 0

        try:
            for _ in range(self.max_iterations):
                self.usage.iterations += 1

                # Attempt streaming; fall back to non-streaming if unsupported
                try:
                    full_text = ""
                    tool_calls_raw: Dict[int, Dict] = {}

                    stream = await client.chat.completions.create(
                        model=actual_model,
                        messages=messages,
                        tools=active_tools,
                        tool_choice="auto",
                        stream=True,
                        temperature=0.3,
                        stream_options={"include_usage": True},
                        **_ollama_extra,
                    )

                    async for chunk in stream:
                        # Usage chunk (Ollama sends a final chunk with empty choices)
                        if hasattr(chunk, "usage") and chunk.usage:
                            self.usage.update(chunk.usage)

                        delta = chunk.choices[0].delta if chunk.choices else None
                        if not delta:
                            continue

                        # Text content
                        if delta.content:
                            full_text += delta.content
                            yield {"type": "text", "content": delta.content}

                        # Tool calls accumulate across chunks
                        if delta.tool_calls:
                            for tc in delta.tool_calls:
                                idx = tc.index
                                if idx not in tool_calls_raw:
                                    tool_calls_raw[idx] = {
                                        "id": tc.id or "",
                                        "name": "",
                                        "arguments": "",
                                    }
                                if tc.id:
                                    tool_calls_raw[idx]["id"] = tc.id
                                if tc.function:
                                    if tc.function.name:
                                        tool_calls_raw[idx]["name"] += tc.function.name
                                    if tc.function.arguments:
                                        tool_calls_raw[idx]["arguments"] += tc.function.arguments

                except Exception as stream_err:
                    # Some local models don't support streaming + tools together
                    logger.debug(f"Stream failed ({stream_err}), retrying without stream")
                    full_text = ""
                    tool_calls_raw = {}

                    resp = await client.chat.completions.create(
                        model=actual_model,
                        messages=messages,
                        tools=active_tools,
                        tool_choice="auto",
                        stream=False,
                        temperature=0.3,
                    )
                    choice = resp.choices[0]
                    if choice.message.content:
                        full_text = choice.message.content
                        yield {"type": "text", "content": full_text}
                    if choice.message.tool_calls:
                        for tc in choice.message.tool_calls:
                            tool_calls_raw[tc.index if hasattr(tc, "index") else len(tool_calls_raw)] = {
                                "id": tc.id,
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            }
                    if resp.usage:
                        self.usage.update(resp.usage)

                # Build assistant message
                assistant_msg: Dict[str, Any] = {"role": "assistant", "content": full_text or None}
                tool_calls_list = list(tool_calls_raw.values())

                if tool_calls_list:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc["id"] or f"tc_{uuid.uuid4().hex[:8]}",
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in tool_calls_list
                    ]

                messages.append(assistant_msg)

                # Execute tools
                if tool_calls_list:
                    for tc in tool_calls_list:
                        tool_name = tc["name"]
                        try:
                            tool_args = json.loads(tc["arguments"] or "{}")
                        except json.JSONDecodeError:
                            tool_args = {}

                        self.usage.record_tool(tool_name)
                        yield {"type": "tool_call", "name": tool_name, "args": tool_args}

                        # Route to computer tools if applicable
                        computer_tool_names = {t["function"]["name"] for t in (active_tools if self.enable_computer else [])}
                        if self.enable_computer and tool_name in computer_tool_names and tool_name not in {t["function"]["name"] for t in TOOLS}:
                            result = await computer_exec(tool_name, tool_args) if computer_exec else "Computer tools not available"
                        else:
                            result = await _exec_tool(tool_name, tool_args)
                        yield {"type": "tool_result", "name": tool_name, "result": result[:500]}

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"] or f"tc_{uuid.uuid4().hex[:8]}",
                            "content": result,
                        })

                else:
                    # No tool calls — we're done
                    self.history.append({"role": "assistant", "content": full_text})
                    break

            yield {"type": "usage", "usage": self.usage.to_dict()}

        except Exception as e:
            logger.error(f"Agent error: {e}")
            yield {"type": "error", "content": str(e)}

        yield {"type": "done"}

    async def run(self, user_message: str) -> str:
        """Non-streaming run, returns final text."""
        parts = []
        async for chunk in self.stream(user_message):
            if chunk.get("type") == "text":
                parts.append(chunk["content"])
        return "".join(parts)

    def get_usage(self) -> Dict:
        return self.usage.to_dict()


# ── Session storage ────────────────────────────────────────────────────────────

class SessionStore:
    """Simple JSON-based session persistence in ~/.icecode/sessions/"""

    def __init__(self):
        self.session_dir = Path.home() / ".icecode" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _make_title(messages: List[Dict]) -> str:
        """Generate a short title from the first user message."""
        for m in messages:
            if m.get("role") == "user":
                text = m.get("content", "")
                if isinstance(text, list):
                    for part in text:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text = part["text"]
                            break
                text = str(text).strip()
                if text:
                    title = text[:60].replace("\n", " ")
                    return title + ("…" if len(text) > 60 else "")
        return "New session"

    def save(self, session_id: str, messages: List[Dict], metadata: Dict = None):
        f = self.session_dir / f"{session_id}.json"
        # Preserve existing title; only generate on first save
        existing_title = None
        if f.exists():
            try:
                existing_title = json.loads(f.read_text()).get("title")
            except Exception:
                pass
        title = existing_title or self._make_title(messages)
        data = {
            "session_id": session_id,
            "title": title,
            "messages": messages,
            "metadata": metadata or {},
            "updated_at": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat() if not existing_title else None,
        }
        f.write_text(json.dumps(data, indent=2))

    def load(self, session_id: str) -> Optional[Dict]:
        f = self.session_dir / f"{session_id}.json"
        if f.exists():
            return json.loads(f.read_text())
        return None

    def list_sessions(self) -> List[Dict]:
        sessions = []
        for f in sorted(self.session_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text())
                msgs = data.get("messages", [])
                # Build preview from last assistant reply
                preview = ""
                for m in reversed(msgs):
                    if m.get("role") == "assistant":
                        c = m.get("content", "")
                        if isinstance(c, list):
                            for part in c:
                                if isinstance(part, dict) and part.get("type") == "text":
                                    c = part["text"]
                                    break
                        preview = str(c).strip()[:80]
                        break
                sessions.append({
                    "session_id": data["session_id"],
                    "title": data.get("title") or self._make_title(msgs),
                    "message_count": len(msgs),
                    "preview": preview,
                    "updated_at": data.get("updated_at", ""),
                    "created_at": data.get("created_at", ""),
                    "model": data.get("metadata", {}).get("model", ""),
                })
            except Exception:
                pass
        return sessions


_session_store = SessionStore()


def get_session_store() -> SessionStore:
    return _session_store
