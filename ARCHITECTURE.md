# ICECODE Architecture

This document explains the overall design so a new contributor can understand how the pieces fit together without reading 1100+ Python files.

---

## High-level picture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Clients                                 │
│  Web UI (vanilla JS)  │  React UI  │  CLI (Python/TypeScript)  │
└──────────────┬──────────────────────────────────┬──────────────┘
               │  HTTP / SSE / WebSocket          │  CLI flags
               ▼                                  ▼
┌─────────────────────────┐         ┌─────────────────────────────┐
│   FastAPI Server        │         │   Gateway Runner            │
│   packages/server/      │         │   packages/gateway/         │
│   port 13210            │         │   WhatsApp / Telegram /     │
│   185 API endpoints     │         │   Discord / Slack / 16 more │
└──────────┬──────────────┘         └────────────┬────────────────┘
           │ uses                                │ uses
           ▼                                     ▼
┌─────────────────────────┐         ┌─────────────────────────────┐
│   ICECodeAgent          │         │   AIAgent                   │
│   packages/core/        │         │   packages/core/            │
│   icecode/agent/core.py │         │   icecode/agent/engine.py   │
│   OpenAI-SDK compatible │         │   Hermes-derived, full      │
│   streaming + tools     │         │   multi-provider support    │
└─────────────────────────┘         └─────────────────────────────┘
           │                                     │
           └──────────────┬──────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Shared Core Modules                           │
│  knowledge/  swarm/  rl/  learning/  memory/  kanban/  cron/   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Two agent implementations — why?

ICECODE was built by merging three projects:

| Project | Agent class | Use case |
|---------|------------|---------|
| Hermes  | `AIAgent` (engine.py) | Long-running gateway sessions on 20+ messaging platforms |
| ClawX   | —          | Desktop/Electron shell |
| OpenCode| `ICECodeAgent` (core.py) | Clean, standalone, OpenAI-SDK compatible |

Both agents are kept because they serve different purposes and have different trade-offs:

### `ICECodeAgent` — `packages/core/icecode/agent/core.py`

- **Used by**: FastAPI server (all `/api/chat/` routes), Swarm workers, tests
- **Design**: Clean, 1600 lines, no inheritance. Uses the OpenAI Python SDK directly.
- **Streaming**: `async def stream(message) → AsyncGenerator[dict, None]`
- **Tool calling**: 30+ tools loaded dynamically, JSON schema-based
- **State**: `SessionStore` saves conversations as JSON files in `~/.icecode/sessions/`
- **Best for**: Adding new features, understanding the codebase, extending

```python
from icecode.agent.core import ICECodeAgent

agent = ICECodeAgent(
    model="llama3.2",
    provider="ollama",
    base_url="http://localhost:11434/v1",
)
async for chunk in agent.stream("What is 2+2?"):
    print(chunk["content"], end="")
```

### `AIAgent` — `packages/core/icecode/agent/engine.py` + mixins

- **Used by**: Gateway runner only
- **Design**: Mixin-based, 3355 lines + 7 mixin files (~13k lines total). Hermes-derived.
- **Mixins**: `_ToolExecutionMixin`, `_ConversationMixin`, `_SessionMixin`, `_APIMixin`
- **Extra**: Multi-provider fallback, session caching per user, credential pooling, RL trajectory compression
- **Best for**: Understanding gateway-specific behavior; **do not extend** — use ICECodeAgent for new features

```
engine.py (AIAgent)
  ├── engine_api_mixin.py        — OpenAI client creation, streaming loop, API calls
  ├── engine_conversation_mixin.py — run_conversation(), chat(), full agent loop
  ├── engine_session_mixin.py    — session save/load, history management
  ├── engine_tool_exec.py        — tool calling, function dispatch
  ├── engine_tool_guard.py       — tool safety / guardrails
  ├── engine_multimodal.py       — image/vision preprocessing
  └── engine_sanitize.py         — output sanitization
```

### `GatewayRunner` — `packages/gateway/icecode_gateway/run.py`

- Wraps `AIAgent` with platform lifecycle management
- 7 mixins: `_AgentRunnerMixin`, `_MessageHandlerMixin`, `_LifecycleMixin`, `_SessionMixin`, `_KanbanMixin`, `_ConfigLoaderMixin`, `_SlashCommandsMixin`
- Handles: incoming messages → `AIAgent` → outgoing messages for 20 platforms

---

## Package layout

```
packages/
├── core/               Python — ICECodeAgent, knowledge, swarm, RL, skills
│   └── icecode/
│       ├── agent/      Core agent (core.py) + Hermes engine (engine.py + mixins)
│       │   └── provider_adapters/  Anthropic, Gemini, Bedrock, Codex adapters
│       ├── knowledge/  RAG: FAISS store + Ollama embeddings (nomic-embed-text)
│       ├── swarm/      Multi-agent: coordinator, pipeline, parallel
│       ├── rl/         Reinforcement learning: trajectory compressor, toolsets
│       ├── learning/   Skill evolution: curator, skill manager
│       ├── memory/     Memory providers (8 integrations: Mem0, Holographic, etc.)
│       ├── kanban/     Task board: boards, cards, columns
│       └── cron/       Scheduled jobs
│
├── server/             FastAPI server — 185 endpoints, SSE, WebSocket
│   └── icecode_server/
│       └── routes/     One file per domain (chat, skills, knowledge, swarm, …)
│
├── gateway/            Messaging platform bridge (20 platforms)
│   └── icecode_gateway/
│       └── platforms/  One file per platform (telegram, discord, whatsapp, …)
│
├── tools/              Hermes-derived tool implementations
│   ├── agent/          Stub modules for Hermes import compatibility
│   ├── tools/          Actual tool code (vision, web, file, kanban, …)
│   └── utils/          Utility functions (subset of icecode/utils.py)
│
├── cli/                Python CLI (icecode_cli) + TypeScript TUI (src/)
├── web-ui/             Vanilla JS single-page app (27 pages, no build step)
├── react-ui/           React/TypeScript UI (built → dist/, served at /desktop/)
├── ts-core/            TypeScript core utilities (built → dist/)
├── ts-runtime/         TypeScript CLI runtime (built → dist/)
└── gateway/            (also has TypeScript source — independent of Python gateway)
```

---

## Import conventions — 3 styles

The codebase has three valid import styles, each resolving to a different location:

### Style 1: `from agent.X import Y`
```python
from agent.memory_manager import sanitize_context
```
Resolves to `packages/tools/agent/X.py` — these are **Hermes stub modules**. Only a subset of symbols are available. Used in engine.py and gateway (where `packages/tools` is on sys.path).

**All such imports are wrapped in try/except:**
```python
try:
    from agent.memory_manager import sanitize_context
except (ImportError, ModuleNotFoundError):
    from icecode.agent.memory_manager import sanitize_context
```

### Style 2: `from icecode.X import Y`
```python
from icecode.agent.core import ICECodeAgent
from icecode.knowledge.manager import KnowledgeManager
```
Resolves to `packages/core/icecode/X.py` — the **canonical ICECODE modules**. Always use this style for new code.

### Style 3: `from tools.X import Y`
```python
from tools.vision_tools import VISION_ANALYZE_SCHEMA
```
Resolves to `packages/tools/tools/X.py` — **Hermes tool implementations**. Always available when the server runs (conftest.py and install.sh add `packages/tools` to sys.path).

---

## Server request lifecycle

```
Client POST /api/chat/stream
  → routes/chat.py: _sse_stream()
    → ICECodeAgent(model, provider, base_url, system_prompt)
      → agent.stream(user_message)
        → tool loop:
            OpenAI-compatible /v1/chat/completions
            → if tool_call: execute tool, append result, loop
            → if text: yield {"type": "text", "content": chunk}
    → store.save(session_id, agent.history, metadata)
  → StreamingResponse(SSE chunks)
```

---

## Knowledge base (RAG)

```
POST /api/knowledge/index  →  KnowledgeManager.index_file(path)
                               → DocumentIndexer: chunk text (512 tokens, 50 overlap)
                               → RAGRetriever.embed_via_ollama(chunks)
                                   (model: nomic-embed-text, 768-dim)
                               → VectorStore.add(embeddings, metadata)
                                   (FAISS IndexFlatL2, persisted to ~/.icecode/data/knowledge/)

GET /api/knowledge/search?q=X  →  KnowledgeManager.search(query, k=5)
                                   → embed query → FAISS.search → top-k chunks
```

**Important**: `OLLAMA_BASE_URL` (used for chat API, includes `/v1`) is different from the Ollama native API host (used for embeddings, no `/v1`). The retriever calls `_ollama_host()` which strips the `/v1` suffix automatically.

---

## Multi-agent Swarm

```
POST /api/swarm/run  {mode: "pipeline"|"parallel", input: "...", agents: [...]}
  → SwarmCoordinator
      pipeline:  A.output → B.input → C.input → …  (sequential)
      parallel:  all agents receive same input simultaneously
  → each agent is an ICECodeAgent with a specific role/system prompt
  → results streamed as SSE
```

---

## Session storage

Sessions are stored as JSON files:

```
~/.icecode/sessions/{session_id}.json
{
  "session_id": "abc123",
  "title": "Auto-generated from first message",
  "messages": [{"role": "user", "content": "…"}, {"role": "assistant", "content": "…"}],
  "metadata": {"model": "llama3.2", "provider": "ollama", "usage": {…}},
  "created_at": "…",
  "updated_at": "…"
}
```

`GET /api/sessions/` reads these files via `SessionStore.list_sessions()` — **not** via SQLAlchemy/SQLite. The SQLite state class (`ICECodeState`) is a legacy holdover that is no longer used by the main chat flow.

---

## Testing strategy

```
tests/
├── conftest.py              — adds packages/core, server, tools to sys.path
├── unit/
│   ├── test_agent_core.py   — ICECodeAgent: stream, tools, sessions
│   ├── test_routes_chat.py  — /api/chat/* endpoints (mocked agent)
│   ├── test_routes_providers.py — /api/providers/* (mocked file I/O)
│   ├── test_routes_skills.py — /api/skills/* (mocked skill list)
│   ├── test_knowledge.py    — VectorStore, RAGRetriever, KnowledgeManager
│   ├── test_swarm.py        — pipeline and parallel swarm execution
│   └── test_database.py     — settings persistence
└── integration/
    ├── test_api.py          — full server: all major routes, mocked agent
    ├── test_routes.py       — additional route smoke tests
    ├── test_e2e.py          — end-to-end flows: chat→session→knowledge→swarm
    ├── test_metrics.py      — usage/metrics endpoints
    └── test_real_llm.py     — REAL Ollama tests (auto-skip if Ollama not running)
```

**Rule**: unit tests must pass with no external services. Integration tests with mocked agents must pass. `test_real_llm.py` is skipped in CI (no Ollama on GitHub Actions).

---

## Configuration

All configuration lives in `~/.icecode/`:

```
~/.icecode/
├── data/
│   ├── providers.json      — API keys and model lists (gitignored)
│   ├── settings.json       — user preferences
│   ├── knowledge/          — FAISS index + metadata
│   │   ├── index.faiss
│   │   ├── meta.json
│   │   └── sources.json
│   └── skills_curator.json — pinned/archived skills, usage counts
├── sessions/               — conversation history JSON files
└── skills/                 — custom skill markdown files
```

Environment variables override file config:

| Variable | Default | Description |
|---|---|---|
| `DEFAULT_PROVIDER` | `ollama` | LLM provider to use |
| `DEFAULT_MODEL` | `llama3.2` | Model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible endpoint |
| `ICECODE_EMBED_MODEL` | `nomic-embed-text` | Ollama embedding model for RAG |
| `HOST_API_PORT` | `13210` | Server port |
| `ANTHROPIC_API_KEY` | — | For Anthropic/Claude |
| `OPENAI_API_KEY` | — | For OpenAI |

---

## Adding a new feature — checklist

1. **New tool**: Add schema + handler in `packages/tools/tools/` or `packages/core/icecode/agent/core.py` (`_load_extended_tools`)
2. **New API endpoint**: Add to `packages/server/icecode_server/routes/` and register in `main.py` via `_try_register`
3. **New platform**: Copy `packages/gateway/icecode_gateway/platforms/telegram.py`, implement `BaseAdapter`, register in `platform_registry.py`
4. **New memory provider**: Copy `packages/core/icecode/memory/providers/mem0/__init__.py`, implement `MemoryProvider` interface
5. **Tests**: Add unit test in `tests/unit/test_<feature>.py` — mock external I/O, test route responses and business logic

Use `ICECodeAgent`, not `AIAgent`, for new features.
