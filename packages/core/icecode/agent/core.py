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


# ── Extended tools from icecode_tools (Hermes) ────────────────────────────────

def _load_extended_tools(skip_registry: bool = False) -> List[Dict]:
    """Load additional tool schemas from packages/tools/icecode_tools."""
    import sys as _sys
    _tools_path = str(Path(__file__).parents[3] / "tools")
    _cli_path   = str(Path(__file__).parents[3] / "cli")
    _core_path  = str(Path(__file__).parents[2])
    for p in (_tools_path, _cli_path, _core_path):
        if p not in _sys.path:
            _sys.path.insert(0, p)

    extended: List[Dict] = []

    _WANT = [
        # (module_path, schema_attr)
        ("tools.todo_tool",             "TODO_SCHEMA"),
        ("tools.memory_tool",           "MEMORY_SCHEMA"),
        ("tools.vision_tools",          "VISION_ANALYZE_SCHEMA"),
        ("tools.vision_tools",          "VIDEO_ANALYZE_SCHEMA"),
        ("tools.session_search_tool",   "SESSION_SEARCH_SCHEMA"),
        ("tools.clarify_tool",          "CLARIFY_SCHEMA"),
        ("tools.image_generation_tool", "IMAGE_GEN_SCHEMA"),
        ("tools.video_generation_tool", "VIDEO_GEN_SCHEMA"),
        ("tools.tts_tool",              "TTS_SCHEMA"),
        ("tools.web_tools",             "WEB_SEARCH_SCHEMA"),
        ("tools.web_tools",             "WEB_EXTRACT_SCHEMA"),
        ("tools.file.file_tools",       "PATCH_SCHEMA"),
        ("tools.file.file_tools",       "SEARCH_FILES_SCHEMA"),
        ("tools.delegate_tool",         "DELEGATE_TASK_SCHEMA"),
        ("tools.cronjob_tools",         "CRONJOB_SCHEMA"),
        ("tools.homeassistant_tool",    "HA_LIST_ENTITIES_SCHEMA"),
        ("tools.homeassistant_tool",    "HA_GET_STATE_SCHEMA"),
        ("tools.homeassistant_tool",    "HA_LIST_SERVICES_SCHEMA"),
        ("tools.homeassistant_tool",    "HA_CALL_SERVICE_SCHEMA"),
        ("tools.kanban_tools",          "KANBAN_SHOW_SCHEMA"),
        ("tools.kanban_tools",          "KANBAN_LIST_SCHEMA"),
        ("tools.kanban_tools",          "KANBAN_COMPLETE_SCHEMA"),
        ("tools.kanban_tools",          "KANBAN_BLOCK_SCHEMA"),
        ("tools.kanban_tools",          "KANBAN_COMMENT_SCHEMA"),
        ("tools.kanban_tools",          "KANBAN_CREATE_SCHEMA"),
        ("tools.kanban_tools",          "KANBAN_UNBLOCK_SCHEMA"),
        ("tools.kanban_tools",          "KANBAN_LINK_SCHEMA"),
        ("tools.rl_training_tool",      "RL_LIST_ENVIRONMENTS_SCHEMA"),
        ("tools.rl_training_tool",      "RL_START_TRAINING_SCHEMA"),
        ("tools.rl_training_tool",      "RL_CHECK_STATUS_SCHEMA"),
        ("tools.rl_training_tool",      "RL_GET_RESULTS_SCHEMA"),
        ("tools.rl_training_tool",      "RL_EDIT_CONFIG_SCHEMA"),
        ("tools.rl_training_tool",      "RL_GET_CURRENT_CONFIG_SCHEMA"),
        ("tools.rl_training_tool",      "RL_STOP_TRAINING_SCHEMA"),
        ("tools.rl_training_tool",      "RL_LIST_RUNS_SCHEMA"),
        ("tools.rl_training_tool",      "RL_SELECT_ENVIRONMENT_SCHEMA"),
        ("tools.rl_training_tool",      "RL_TEST_INFERENCE_SCHEMA"),
        ("tools.discord_tool",          "DISCORD_SCHEMA"),
        # Feishu / Lark integration
        ("tools.feishu_doc_tool",       "FEISHU_DOC_READ_SCHEMA"),
        ("tools.feishu_drive_tool",     "FEISHU_DRIVE_LIST_COMMENTS_SCHEMA"),
        ("tools.feishu_drive_tool",     "FEISHU_DRIVE_LIST_REPLIES_SCHEMA"),
        ("tools.feishu_drive_tool",     "FEISHU_DRIVE_REPLY_SCHEMA"),
        ("tools.feishu_drive_tool",     "FEISHU_DRIVE_ADD_COMMENT_SCHEMA"),
        # Multi-LLM mixture
        ("tools.mixture_of_agents_tool","MOA_SCHEMA"),
        # Skills management
        ("tools.skills_tool",           "SKILLS_LIST_SCHEMA"),
        ("tools.skills_tool",           "SKILL_VIEW_SCHEMA"),
        ("tools.skill_manager_tool",    "SKILL_MANAGE_SCHEMA"),
        # Process & code execution
        ("tools.process_registry",      "PROCESS_SCHEMA"),
    ]

    seen_names = set()
    import importlib as _il
    for mod_path, attr in _WANT:
        try:
            mod = _il.import_module(mod_path)
            schema = getattr(mod, attr, None)
            if schema and schema.get("name") and schema["name"] not in seen_names:
                extended.append({"type": "function", "function": schema})
                seen_names.add(schema["name"])
        except Exception as e:
            logger.debug(f"Extended tool {attr} not loaded: {e}")

    # Load browser tools (exported as a list, not individual schema attrs)
    try:
        browser_mod = _il.import_module("tools.browser_tool")
        browser_schemas = getattr(browser_mod, "BROWSER_TOOL_SCHEMAS", [])
        for schema in browser_schemas:
            if isinstance(schema, dict):
                # may already be wrapped in {"type":"function","function":{...}}
                if "function" in schema:
                    name = schema["function"].get("name", "")
                    if name and name not in seen_names:
                        extended.append(schema)
                        seen_names.add(name)
                elif schema.get("name") and schema["name"] not in seen_names:
                    extended.append({"type": "function", "function": schema})
                    seen_names.add(schema["name"])
    except Exception as e:
        logger.debug(f"Browser tools not loaded: {e}")

    # Trigger import of registry-only modules to ensure they register themselves
    _REGISTRY_ONLY_MODULES = [
        "tools.yuanbao_tools",
        "tools.send_message_tool",
        "tools.code_execution_tool",
        "tools.browser_cdp_tool",
        "tools.browser_dialog_tool",
        "tools.computer_use_tool",
        "tools.mcp_tool",
        "tools.terminal_tool",
    ]
    for mod_path in _REGISTRY_ONLY_MODULES:
        try:
            _il.import_module(mod_path)
        except Exception as e:
            logger.debug(f"Registry-only module {mod_path} not loaded: {e}")

    # Load registry-registered tools, filtered by check_fn (skip if caller handles it)
    if not skip_registry:
        try:
            from tools.registry import registry as _registry
            for schema_entry in _registry.get_available_schemas():
                name = schema_entry.get("function", {}).get("name", "")
                if name and name not in seen_names:
                    extended.append(schema_entry)
                    seen_names.add(name)
        except Exception as e:
            logger.debug(f"Registry sweep not loaded: {e}")

    logger.debug(f"Extended tools loaded: {len(extended)}")
    return extended


_STATIC_TOOLS_CACHE: Optional[List[Dict]] = None

def _get_extended_tools() -> List[Dict]:
    """Load extended tools. Static module tools are cached; registry tools re-checked each call."""
    global _STATIC_TOOLS_CACHE

    # Build static tools once (module imports are cached by Python anyway)
    if _STATIC_TOOLS_CACHE is None:
        _STATIC_TOOLS_CACHE = _load_extended_tools(skip_registry=True)

    # Registry tools are checked fresh each time so check_fn filters correctly
    try:
        from tools.registry import registry as _reg
        seen = {t["function"]["name"] for t in _STATIC_TOOLS_CACHE}
        dynamic = [
            s for s in _reg.get_available_schemas()
            if s.get("function", {}).get("name") not in seen
        ]
    except Exception:
        dynamic = []

    return _STATIC_TOOLS_CACHE + dynamic


# Tier 1 — always included for any action message (7 tools, ~1400 tokens)
_CORE_TOOL_NAMES = frozenset({
    "read_file", "write_file", "edit_file", "run_terminal", "list_dir",
    "search_web", "web_fetch",
})

# Tier 2 — added when message is about code / file operations (+6 tools = 13 total)
_CODE_KEYWORDS = frozenset({
    "file", "code", "script", "function", "class", "import", "debug",
    "error", "fix", "write", "read", "edit", "create", "delete", "move",
    "git", "commit", "deploy", "build", "test", "refactor", "bug",
    "framework", "library", "database", "backend", "frontend", "docker",
    "container", "middleware", "package", "module", "dependency",
    "fisier", "cod", "script", "baza de date",
})
_CODE_TOOL_NAMES = frozenset({
    "delete_file", "move_file", "search_files", "code_search", "git_command", "patch",
})

# Domain groups — each group is only included when its keywords appear in the message.
# Keywords use substring matching (supports multi-word phrases like "home assistant").
# Tool names must match exactly what's registered/defined.
_TOOL_KEYWORD_GROUPS: List[tuple] = [
    # Tasks / Kanban — "task", "taskuri" etc. trigger this too, not just "kanban"
    ({"kanban", "board", "sprint", "backlog",
      "task", "tasks", "taskuri", "taskurile", "todo", "sarcina", "sarcini"},
     {"kanban_show","kanban_list","kanban_complete","kanban_block","kanban_comment",
      "kanban_create","kanban_unblock","kanban_link",
      "create_task","list_tasks","update_task","set_goal","get_goals","todo"}),
    # Memory / remember
    ({"remember", "recall", "memory", "memorie", "aminteste", "retine"},
     {"remember", "recall", "search_knowledge", "memory"}),
    # Knowledge base / docs
    ({"knowledge", "rag", "document", "docs", "documentation", "indexed"},
     {"search_knowledge"}),
    # Home Assistant / smart home
    ({"home assistant", "smart home", "hass", "sensor", "thermostat", "light",
      "automation", "switch", "climate"},
     {"ha_list_entities","ha_get_state","ha_list_services","ha_call_service"}),
    # RL training
    ({"reinforcement", "rl training", "gym", "training run", "rl_"},
     {"rl_list_environments","rl_start_training","rl_check_status","rl_get_results",
      "rl_edit_config","rl_get_current_config","rl_stop_training","rl_list_runs",
      "rl_select_environment","rl_test_inference"}),
    # Feishu / Lark
    ({"feishu", "lark", "飞书"},
     {"feishu_doc_read","feishu_drive_list_comments","feishu_drive_list_comment_replies",
      "feishu_drive_reply_comment","feishu_drive_add_comment"}),
    # Browser / web automation
    ({"browser", "screenshot", "navigate", "click", "scroll", "webpage", "chromium",
      "playwright", "puppeteer", "cdp", "dialog"},
     {"browser_navigate","browser_snapshot","browser_click","browser_type",
      "browser_scroll","browser_back","browser_press","browser_get_images",
      "browser_vision","browser_console","browser_fetch","web_extract",
      "browser_cdp","browser_dialog"}),
    # Computer use / desktop automation
    ({"computer use", "desktop", "mouse", "keyboard", "screen", "gui", "automate desktop"},
     {"computer_use"}),
    # Images
    ({"image", "photo", "picture", "generate image", "dall", "midjourney", "imagine"},
     {"image_generate", "vision_analyze"}),
    # Video
    ({"video", "mp4", "generate video", "analyze video"},
     {"video_generate", "video_analyze"}),
    # Speech / TTS
    ({"speech", "tts", "text to speech", "audio", "voice", "speak"},
     {"text_to_speech"}),
    # Messaging
    ({"telegram", "discord", "slack", "whatsapp", "send message", "notify",
      "mesaj", "notificare"},
     {"send_message", "discord"}),
    # Skills management
    ({"skill", "teach", "learn skill", "add skill", "abilitate"},
     {"skills_list", "skill_view", "skill_manage"}),
    # Multi-agent / delegation
    ({"delegate", "multi-agent", "swarm", "sub-agent", "orchestrate"},
     {"delegate_task", "delegate_to_agent", "mixture_of_agents"}),
    # Code execution / sandbox
    ({"execute code", "run code", "python exec", "sandbox", "executa cod"},
     {"execute_code", "process"}),
    # HTTP / REST API calls
    ({"api", "http request", "rest api", "webhook", "endpoint", "curl"},
     {"http_request"}),
    # Session / conversation history
    ({"session", "history", "past conversation", "conversatie anterioara"},
     {"session_search"}),
    # Cron / scheduling
    ({"cron", "schedule", "recurring", "programeaza", "planifica"},
     {"cronjob"}),
    # Yuanbao
    ({"yuanbao"},
     {"yb_query_group_info","yb_query_group_members","yb_send_dm",
      "yb_search_sticker","yb_send_sticker"}),
]


# Punctuation + hyphen normalizer: "codul?" → "codul", "fa-mi" → "fa mi", "script-ul" → "script ul"
_PUNCT_TRANS = str.maketrans("?!,.:;()[]{}\"'/\\-–—", "                   ")

def _tokenize(text: str) -> set:
    """Split text into words, stripping punctuation so 'codul?' matches 'codul'."""
    return set(text.lower().translate(_PUNCT_TRANS).split())


_ACTION_KEYWORDS = {
    # English action verbs (whole words)
    "read", "write", "create", "delete", "move", "run", "execute", "fix", "debug",
    "search", "find", "fetch", "edit", "install", "deploy", "build", "test",
    "generate", "analyze", "scan", "open", "show", "list", "check", "make",
    # Romanian action verbs — "fa" safe (word-boundary: "faci"≠"fa"; "fa-mi"→"fa mi")
    "fa", "citeste", "scrie", "creeaza", "creez", "construieste", "construiesc",
    "sterge", "muta", "ruleaza", "cauta", "arata", "afiseaza", "listeaza",
    "modifica", "verifica", "descarca", "compileaza", "instaleaza", "instala",
    "porneste", "opreste", "adauga", "pune", "trimite", "trimit",
    "implementeaza", "implementez", "dezvolta", "dezvolt", "repara",
    # Romanian object nouns — WITH and WITHOUT article (fisier + fisierul etc.)
    "fisier", "fisierul", "cod", "codul", "script", "scriptul",
    "proiect", "proiectul", "director", "directorul", "folder", "folderul",
    "server", "serverul", "aplicatie", "aplicatia", "pagina", "site",
    "baza", "bot", "api", "eroare", "problema", "functie", "clasa",
}


def _needs_tools(message: str) -> bool:
    """Return True if this message likely requires tool use."""
    if len(message) > 80:
        return True
    msg_lower = message.lower()
    # Punctuation-normalized word-boundary match (no substring false-positives)
    words = _tokenize(msg_lower)
    if words & _ACTION_KEYWORDS:
        return True
    # Code/file keyword present anywhere in message (handles "cu codul", "script-ul")
    if any(kw in msg_lower for kw in _CODE_KEYWORDS):
        return True
    # Domain keyword match (multi-word phrases like "home assistant" supported)
    for keywords, _ in _TOOL_KEYWORD_GROUPS:
        if any(kw in msg_lower for kw in keywords):
            return True
    return False


def _is_pure_greeting(message: str) -> bool:
    """Return True only for very short, clearly conversational messages with NO task intent."""
    if len(message) > 50:
        return False
    words = _tokenize(message.lower())
    # Any known action/code/domain keyword → not a pure greeting
    if words & _ACTION_KEYWORDS:
        return False
    if any(kw in message.lower() for kw in _CODE_KEYWORDS):
        return False
    for keywords, _ in _TOOL_KEYWORD_GROUPS:
        if any(kw in message.lower() for kw in keywords):
            return False
    return True


def _select_tools_for_message(message: str, all_tools: List[Dict]) -> List[Dict]:
    """Return the tools relevant to this message.
    Core tools (7) are ALWAYS included unless the message is a pure short greeting.
    Domain tools are added when their keywords appear.
    Code tools are added when code/file keywords appear.
    """
    msg_lower = message.lower()
    words = _tokenize(msg_lower)

    # Pure short greetings: "salut", "buna ziua", "ok", "multumesc" → 0 tools, pure chat
    if _is_pure_greeting(message):
        return []

    # Core tools always included (mirrors icecode1 — agents always have tools available)
    selected_names: set = set(_CORE_TOOL_NAMES)

    # Code tier: added when message mentions code/file work
    if any(kw in msg_lower for kw in _CODE_KEYWORDS) or (words & _CODE_KEYWORDS):
        selected_names |= _CODE_TOOL_NAMES

    # Domain tools: added when their keyword groups match
    for keywords, tool_names in _TOOL_KEYWORD_GROUPS:
        if any(kw in msg_lower for kw in keywords):
            selected_names |= tool_names

    return [t for t in all_tools if t.get("function", {}).get("name") in selected_names]


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
            "description": "Fetch the content of a KNOWN URL and return its text. Use this only when you already have a specific URL from search results. Do NOT guess URLs.",
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
            "description": "Search the internet using DuckDuckGo. Use this FIRST to find information online — train schedules, prices, news, recipes, anything. Returns real URLs and summaries. Always use search_web before web_fetch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (can be in any language)"},
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
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file by replacing a specific text section with new content. Safer than write_file — only changes what you specify. Use for targeted code edits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to edit"},
                    "old_text": {"type": "string", "description": "Exact text to find and replace (must be unique in the file)"},
                    "new_text": {"type": "string", "description": "New text to replace it with"},
                    "replace_all": {"type": "boolean", "description": "Replace all occurrences (default false — only first)"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file or empty directory from disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File or directory path to delete"},
                    "recursive": {"type": "boolean", "description": "Delete directory and all its contents (default false)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "Move or rename a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "Source path"},
                    "dst": {"type": "string", "description": "Destination path"},
                },
                "required": ["src", "dst"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_request",
            "description": "Make an HTTP request to any API endpoint. Use for REST APIs, webhooks, or any HTTP service.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"], "description": "HTTP method"},
                    "url": {"type": "string", "description": "Full URL to request"},
                    "headers": {"type": "object", "description": "Optional request headers as key-value pairs"},
                    "body": {"type": "object", "description": "Optional JSON body for POST/PUT/PATCH"},
                    "params": {"type": "object", "description": "Optional URL query parameters"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 15)"},
                },
                "required": ["method", "url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_command",
            "description": "Run a git command in a repository. Use for status, diff, log, add, commit, push, pull, branch, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Git subcommand and args (e.g. 'status', 'diff HEAD', 'log --oneline -10', 'add .', 'commit -m \"msg\"')"},
                    "cwd": {"type": "string", "description": "Repository path (default: current dir)"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "code_search",
            "description": "Search for a pattern or text across files in a directory using grep. Great for finding function definitions, usages, imports, TODOs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Text or regex pattern to search for"},
                    "path": {"type": "string", "description": "Directory to search in (default: current dir)"},
                    "file_pattern": {"type": "string", "description": "Glob to filter files (e.g. '*.py', '*.ts', '*.js')"},
                    "case_sensitive": {"type": "boolean", "description": "Case-sensitive search (default false)"},
                    "max_results": {"type": "integer", "description": "Max lines to return (default 50)"},
                },
                "required": ["pattern"],
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
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    hits = list(ddgs.text(query, max_results=max_results))
                if not hits:
                    return "No results found"
                lines = []
                for i, h in enumerate(hits, 1):
                    lines.append(f"{i}. {h['title']}\n   {h['href']}\n   {h.get('body','')[:200]}")
                return "\n\n".join(lines)
            except Exception as e:
                return f"Search failed: {e}"

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

        elif name == "edit_file":
            p = Path(args["path"]).expanduser()
            if not p.exists():
                return f"Error: file not found: {args['path']}"
            content = p.read_text(errors="replace")
            old_text = args["old_text"]
            new_text = args["new_text"]
            if old_text not in content:
                return f"Error: text not found in {args['path']}. Make sure old_text matches exactly (including whitespace)."
            count = content.count(old_text)
            if args.get("replace_all"):
                new_content = content.replace(old_text, new_text)
                replaced = count
            else:
                new_content = content.replace(old_text, new_text, 1)
                replaced = 1
            p.write_text(new_content)
            return f"Edited {args['path']}: replaced {replaced} occurrence(s). File is now {len(new_content)} chars."

        elif name == "delete_file":
            import shutil as _shutil
            p = Path(args["path"]).expanduser()
            if not p.exists():
                return f"Error: path not found: {args['path']}"
            if p.is_dir():
                if args.get("recursive"):
                    _shutil.rmtree(p)
                    return f"Deleted directory (recursive): {p}"
                else:
                    try:
                        p.rmdir()
                        return f"Deleted empty directory: {p}"
                    except OSError:
                        return f"Error: directory not empty. Use recursive=true to delete with contents."
            else:
                p.unlink()
                return f"Deleted file: {p}"

        elif name == "move_file":
            import shutil as _shutil
            src = Path(args["src"]).expanduser()
            dst = Path(args["dst"]).expanduser()
            if not src.exists():
                return f"Error: source not found: {args['src']}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            _shutil.move(str(src), str(dst))
            return f"Moved: {src} → {dst}"

        elif name == "http_request":
            method = args["method"].upper()
            url = args["url"]
            headers = args.get("headers") or {}
            body = args.get("body")
            params = args.get("params")
            timeout = args.get("timeout", 15)
            async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
                resp = await client.request(
                    method, url,
                    headers=headers,
                    json=body,
                    params=params,
                )
                try:
                    data = resp.json()
                    body_str = json.dumps(data, indent=2, ensure_ascii=False)[:3000]
                except Exception:
                    body_str = resp.text[:3000]
                return (f"HTTP {method} {url}\n"
                        f"Status: {resp.status_code}\n"
                        f"Headers: {dict(resp.headers)}\n\n"
                        f"{body_str}")

        elif name == "git_command":
            cwd = args.get("cwd") or os.getcwd()
            git_cmd = f"git {args['command']}"
            result = subprocess.run(
                git_cmd, shell=True, cwd=cwd,
                capture_output=True, text=True, timeout=30,
            )
            out = (result.stdout or "").strip()
            err = (result.stderr or "").strip()
            parts = []
            if out:
                parts.append(out[-3000:])
            if err:
                parts.append(f"[stderr] {err[-1000:]}")
            parts.append(f"[exit {result.returncode}]")
            return "\n".join(parts)

        elif name == "code_search":
            pattern = args["pattern"]
            search_path = args.get("path", ".")
            file_pat = args.get("file_pattern", "")
            case_flag = "" if args.get("case_sensitive") else "-i"
            max_results = args.get("max_results", 50)
            include = f"--include='{file_pat}'" if file_pat else ""
            cmd = f"grep -rn {case_flag} {include} '{pattern}' '{search_path}' 2>/dev/null | head -{max_results}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            out = result.stdout.strip()
            if not out:
                return f"No matches found for '{pattern}' in {search_path}"
            lines = out.split("\n")
            suffix = f"\n... ({len(lines)} results shown, use max_results to see more)" if len(lines) >= max_results else ""
            return out + suffix

        else:
            # Try routing to extended icecode_tools (Hermes tools)
            return await _exec_extended_tool(name, args)

    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30s"
    except Exception as e:
        return f"Tool error ({name}): {type(e).__name__}: {e}"


async def _exec_extended_tool(name: str, args: Dict) -> str:
    """Route tool calls to icecode_tools (Hermes) registry handlers."""
    import sys as _sys
    _tools_path = str(Path(__file__).parents[4] / "tools")
    if _tools_path not in _sys.path:
        _sys.path.insert(0, _tools_path)

    try:
        from tools.registry import registry
        tool = registry.get(name)
        if tool:
            handler = tool.get("handler") or tool.get("func")
            if handler:
                result = handler(args)
                return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.debug(f"Extended tool {name} registry call failed: {e}")

    # Fallback: try direct module import patterns
    _DIRECT_MAP = {
        "todo":           ("tools.todo_tool",    "todo_tool"),
        "memory":         ("tools.memory_tool",  "memory_tool"),
        "vision_analyze": ("tools.vision_tools", "vision_analyze"),
        "session_search": ("tools.session_search_tool", "session_search"),
        "clarify":        ("tools.clarify_tool", "clarify_tool"),
    }
    if name in _DIRECT_MAP:
        try:
            import importlib as _il
            mod_path, func_name = _DIRECT_MAP[name]
            mod = _il.import_module(mod_path)
            func = getattr(mod, func_name, None)
            if func:
                import asyncio
                if asyncio.iscoroutinefunction(func):
                    result = await func(**args)
                else:
                    result = func(**args)
                return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            return f"Tool {name} error: {e}"

    return f"Unknown tool: {name}"


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

    # Cloud providers — look up API key and base_url from providers.json
    _CLOUD_DEFAULTS = {
        "openai":      {"base_url": "https://api.openai.com/v1"},
        "anthropic":   {"base_url": "https://api.anthropic.com/v1"},
        "groq":        {"base_url": "https://api.groq.com/openai/v1"},
        "openrouter":  {"base_url": "https://openrouter.ai/api/v1"},
        "together":    {"base_url": "https://api.together.xyz/v1"},
        "deepseek":    {"base_url": "https://api.deepseek.com/v1"},
        "mistral":     {"base_url": "https://api.mistral.ai/v1"},
        "google":      {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai"},
    }
    if provider in _CLOUD_DEFAULTS:
        try:
            from pathlib import Path
            import json as _json
            providers_file = Path.home() / ".icecode" / "data" / "providers.json"
            stored = _json.loads(providers_file.read_text()) if providers_file.exists() else []
            found = next((p for p in stored if p.get("id") == provider), None)
            api_key = found.get("api_key", "") if found else ""
            configured_base = found.get("base_url") if found else None
        except Exception:
            api_key = ""
            configured_base = None

        base_url = configured_base or _CLOUD_DEFAULTS[provider]["base_url"]
        if api_key:
            return {
                "base_url": base_url,
                "api_key": api_key,
                "model": model,
            }

    # Default: Ollama (no cloud keys configured)
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

SYSTEM_PROMPT = """You are ICECODE, a helpful AI assistant and coding agent.
{tools_note}
Current date: {date}
Working directory: {cwd}
"""

SYSTEM_PROMPT_WITH_TOOLS = """You are ICECODE — an advanced AI coding agent with tool-calling capabilities.

You can read/write files, run terminal commands, search the web, and more.
Guidelines:
- Think step-by-step. Use tools proactively — don't just describe, actually do it.
- Be concise in text but thorough in actions.

Current date: {date}
Working directory: {cwd}
"""

AUTOPILOT_EXTRA = """
🤖 AUTOPILOT MODE — ACTIVE

You are running in fully autonomous mode. The user has explicitly given you permission to:
- Execute all steps without asking for confirmation
- Make reasonable decisions independently when facing choices
- Create files, run commands, search the web — all without pausing
- If something is unclear, pick the most reasonable option and continue
- Only stop and ask if you hit a hard blocker (missing credential, impossible requirement)
- Aim for the BEST solution, not just a working one: structure code well, add error handling, test it

Work autonomously from start to finish. Report what you did at the end, not during.
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
        autopilot: bool = False,
        system_extra: str = "",
    ):
        self.model = model
        self.provider = provider or "ollama"
        self.base_url = base_url
        self.max_iterations = max_iterations if not autopilot else max(max_iterations, 30)
        self.session_id = session_id or f"s_{uuid.uuid4().hex[:8]}"
        self.history: List[Dict] = []
        self.usage = UsageTracker()
        self.enable_computer = enable_computer
        self.autopilot = autopilot
        self.system_extra = system_extra

    def _system(self, has_tools: bool = True) -> str:
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
                "\n\nCOMPUTER CONTROL ENABLED: You can control the desktop via screenshot, click, type_text, hotkey, open_app, scroll tools."
            )
        if self.autopilot:
            extra += AUTOPILOT_EXTRA
        if self.system_extra:
            extra += f"\n\n{self.system_extra}"

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        cwd = os.getcwd()
        if has_tools:
            return SYSTEM_PROMPT_WITH_TOOLS.format(date=now, cwd=cwd) + extra
        else:
            tools_note = ""
            if extra:
                return SYSTEM_PROMPT.format(date=now, cwd=cwd, tools_note=extra)
            return SYSTEM_PROMPT.format(date=now, cwd=cwd, tools_note="")

    async def stream(self, user_message: str) -> AsyncGenerator[Dict, None]:
        """Stream chunks: {type: session|text|tool_call|tool_result|usage|done|error}"""
        from openai import AsyncOpenAI

        yield {"type": "session", "session_id": self.session_id}

        # Build active tool list: core + extended (Hermes) + computer
        all_tools_pool = list(TOOLS)
        extended = _get_extended_tools()
        core_names = {t["function"]["name"] for t in all_tools_pool}
        for ext in extended:
            if ext["function"]["name"] not in core_names:
                all_tools_pool.append(ext)

        # Select only tools relevant to this message (reduces prompt tokens 80%+)
        active_tools = _select_tools_for_message(user_message, all_tools_pool)

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
        messages = [{"role": "system", "content": self._system(has_tools=bool(active_tools))}] + trimmed

        # Ollama performance options + per-model capability flags
        _ollama_extra: Dict = {}
        model_lower = actual_model.lower()

        # Models that do NOT support function calling / tools
        _NO_TOOLS = ("deepseek-r1", "deepseek-r1-distill", "qwq", "deepseek-v2.5")
        supports_tools = not any(x in model_lower for x in _NO_TOOLS)

        if is_ollama:
            # Large models (7B+) unload after 2 min to free RAM; others stay 5 min
            _is_large = any(x in model_lower for x in (":7b", ":8b", ":13b", ":14b", ":70b",
                                                        "mistral:7b", "llama3:8b", "llama3.1:8b"))
            _keep_alive = "2m" if _is_large else "5m"
            # Let Ollama auto-size num_ctx for the actual input (setting it explicitly
            # forces pre-allocation of the full KV cache, causing 30-50s prefill on CPU)
            opts: Dict = {"keep_alive": _keep_alive}
            # qwen3 supports think:false via options; deepseek-r1 needs /no_think in message
            if any(x in model_lower for x in ("qwen3", "qwq")):
                opts["think"] = False
            _ollama_extra = {"extra_body": {"options": opts}}

        # For deepseek-r1: append /no_think to suppress chain-of-thought output
        if is_ollama and "deepseek-r1" in model_lower:
            last = messages[-1] if messages else None
            if last and last.get("role") == "user":
                messages = messages[:-1] + [{"role": "user", "content": last["content"] + "\n/no_think"}]

        self.usage.iterations = 0

        try:
            for _ in range(self.max_iterations):
                self.usage.iterations += 1

                # Attempt streaming; fall back to non-streaming if unsupported
                try:
                    full_text = ""
                    tool_calls_raw: Dict[int, Dict] = {}

                    _tool_kwargs = (
                        {"tools": active_tools, "tool_choice": "auto"}
                        if supports_tools and active_tools else {}
                    )
                    stream = await client.chat.completions.create(
                        model=actual_model,
                        messages=messages,
                        stream=True,
                        temperature=0.3,
                        stream_options={"include_usage": True},
                        **_tool_kwargs,
                        **_ollama_extra,
                    )

                    _in_thinking = False
                    async for chunk in stream:
                        # Usage chunk (Ollama sends a final chunk with empty choices)
                        if hasattr(chunk, "usage") and chunk.usage:
                            self.usage.update(chunk.usage)

                        delta = chunk.choices[0].delta if chunk.choices else None
                        if not delta:
                            continue

                        # Handle reasoning/thinking field (deepseek-r1, qwq)
                        reasoning = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None)
                        if reasoning:
                            if not _in_thinking:
                                _in_thinking = True
                                yield {"type": "thinking_start"}
                            yield {"type": "thinking", "content": reasoning}

                        # Text content — marks end of thinking phase
                        if delta.content:
                            if _in_thinking:
                                _in_thinking = False
                                yield {"type": "thinking_end"}
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

                    _tool_kwargs2 = (
                        {"tools": active_tools, "tool_choice": "auto"}
                        if supports_tools and active_tools else {}
                    )
                    resp = await client.chat.completions.create(
                        model=actual_model,
                        messages=messages,
                        stream=False,
                        temperature=0.3,
                        **_tool_kwargs2,
                    )
                    choice = resp.choices[0]
                    # Check both content and reasoning fields (deepseek-r1/qwq)
                    msg = choice.message
                    _reasoning = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None)
                    _content = msg.content or ""
                    if _reasoning and not _content:
                        full_text = _reasoning
                    elif _content:
                        full_text = _content
                    if full_text:
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
            err_str = str(e)
            # Friendly messages for common cloud API errors
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                msg = "⚠ Quota depășită (429). "
                if "gemini-2.5-pro" in err_str or "gemini-2.5-pro" in (self.model or ""):
                    msg += "gemini-2.5-pro a atins limita free tier pentru azi. Folosește **gemini-2.5-flash** sau **gemini-2.0-flash** — au cotă mult mai mare."
                elif "gemini" in err_str.lower():
                    msg += "Limita Google Gemini free tier atinsă. Încearcă gemini-2.5-flash sau gemini-2.0-flash."
                else:
                    msg += "Limita API atinsă. Încearcă alt model sau așteaptă resetarea cotei."
                yield {"type": "error", "content": msg}
            elif "401" in err_str or "authentication" in err_str.lower() or "api_key" in err_str.lower():
                yield {"type": "error", "content": "⚠ API key invalid sau lipsă. Verifică Settings → Providers."}
            elif "does not support tools" in err_str:
                yield {"type": "error", "content": f"⚠ Modelul {self.model} nu suportă tool-uri. Selectează alt model."}
            else:
                yield {"type": "error", "content": err_str}

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
