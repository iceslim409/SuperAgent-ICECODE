# ICECODE — Super-Agent Network v2.0

**ICECODE** is a unified AI platform built around a powerful Python agent loop, multi-agent orchestration, local knowledge base retrieval, and a real-time Web/Desktop/CLI interface.

---

## What makes ICECODE unique

| Feature | Description |
|---------|-------------|
| **Multi-Agent Swarm** | Pipeline and parallel orchestration — agents collaborate, pass context, vote on answers |
| **Intelligent Model Router** | Auto-selects the optimal Ollama model per task complexity (trivial → 1b, complex → 7b+) |
| **Local RAG** | FAISS + sentence-transformers, 100% offline — index any file, search semantically |
| **WebSocket Chat** | Bidirectional real-time streaming with cancel support |
| **80+ Agent Tools** | File, web, terminal, computer vision, skills, kanban, memory, RL environment |
| **20+ Gateway Platforms** | WhatsApp, Telegram, Email, Feishu, Discord, WeChat, API server, and more |
| **Self-Learning Skills** | Agents learn new skills at runtime, stored and reused across sessions |
| **RL Training Environment** | Built-in reinforcement learning environment for agent improvement |
| **Full TUI + Desktop** | Ink-based terminal UI and Electron desktop app, both connect to the same Python backend |

---

## Quick Start

```bash
# 1. Install
bash install.sh

# 2. Start server
make run

# 3. Open browser
open http://localhost:13210

# 4. Or use the CLI
./icecode chat "design a REST API for a task manager"
```

---

## Architecture

```
icecode/
├── packages/
│   ├── core/               # Python AI engine
│   │   └── icecode/
│   │       ├── agent/      # ICECodeAgent + 80 tools + model adapters
│   │       ├── swarm/      # Multi-agent Swarm (pipeline + parallel)
│   │       ├── knowledge/  # Local RAG (FAISS + sentence-transformers)
│   │       ├── router/     # Intelligent Model Router ← ICECODE original
│   │       ├── config/     # Unified config (icecode_config.py)
│   │       ├── rl/         # RL training environments
│   │       ├── memory/     # Long-term agent memory
│   │       ├── cron/       # Scheduled tasks
│   │       └── kanban/     # Task board
│   ├── server/             # FastAPI backend (port 13210)
│   │   └── icecode_server/
│   │       └── routes/     # 65+ API routes
│   ├── cli/                # Python CLI + TypeScript TUI (Ink)
│   ├── gateway/            # Messaging gateway (20+ platforms)
│   ├── tools/              # 80+ tool implementations
│   ├── plugins/            # Plugin system (Spotify, HomeAssistant, etc.)
│   ├── opencode-ts/        # TypeScript agent runtime
│   ├── clawx-ui/           # React UI components
│   ├── web-ui/             # Single-page web app (18 pages)
│   └── desktop-app/        # Electron desktop app
└── tests/                  # 45+ unit + integration tests
```

---

## Intelligent Model Router

ICECODE automatically selects the right Ollama model for each task:

```
TRIVIAL  (what is 2+2)             → llama3.2:1b    (fastest)
SIMPLE   (summarize this text)     → qwen3.5:2b     (lightweight)
MODERATE (write a Python function) → qwen3.5:4b     (balanced)
COMPLEX  (design an architecture)  → qwen2.5:7b     (most capable)
VISION   (analyze this screenshot) → llava:7b       (vision model)
```

You can override with `?model=qwen2.5:7b` or let ICECODE decide automatically.

```bash
# Ask router what model to use
curl -s http://localhost:13210/api/router/decide \
  -d '{"prompt": "design a distributed caching system"}' \
  -H "Content-Type: application/json"
```

---

## Multi-Agent Swarm

```bash
# Pipeline: researcher → writer
curl -s http://localhost:13210/api/swarm/run \
  -d '{"template": "research_write", "task": "quantum computing trends 2026"}' \
  -H "Content-Type: application/json"

# Parallel: 3 agents analyze from different angles
curl -s http://localhost:13210/api/swarm/run \
  -d '{"template": "multi_perspective", "task": "should we use microservices?"}' \
  -H "Content-Type: application/json"
```

Built-in templates: `research_write`, `code_review`, `brainstorm`, `multi_perspective`

---

## Local Knowledge Base

```bash
# Index your codebase
curl -s http://localhost:13210/api/knowledge/index \
  -d '{"path": "/path/to/project", "recursive": true}' \
  -H "Content-Type: application/json"

# Semantic search
curl -s "http://localhost:13210/api/knowledge/search?q=authentication+middleware"
```

Uses `sentence-transformers/all-MiniLM-L6-v2` (90MB) + FAISS — 100% local, no API keys needed.

---

## Configuration

All settings via environment variables (prefix `ICECODE_`):

```env
ICECODE_PORT=13210
ICECODE_OLLAMA_HOST=http://localhost:11434
ICECODE_OLLAMA_MODEL=qwen3.5:4b
ICECODE_MAX_ITERATIONS=10
ICECODE_AUTO_ROUTE_MODEL=true
ICECODE_ENABLE_COMPUTER=false

# Cloud providers (optional — Ollama works without any)
ICECODE_ANTHROPIC_API_KEY=sk-ant-...
ICECODE_OPENAI_API_KEY=sk-...
ICECODE_OPENROUTER_API_KEY=sk-or-...
```

---

## API Routes (65+)

| Group | Routes |
|-------|--------|
| **Chat** | `POST /api/chat/`, `POST /api/chat/stream`, `WS /api/chat/ws/{id}` |
| **Router** | `POST /api/router/decide`, `GET /api/router/describe`, `POST /api/router/assess` |
| **Swarm** | `POST /api/swarm/run`, `GET /api/swarm/templates` |
| **Knowledge** | `POST /api/knowledge/index`, `GET /api/knowledge/search`, `POST /api/knowledge/upload` |
| **Agents** | `GET /api/agents/`, `POST /api/agents/`, `PATCH /api/agents/{id}` |
| **Sessions** | `GET /api/chat/sessions`, `GET /api/chat/sessions/{id}` |
| **Models** | `GET /api/models/`, `GET /api/local-models/` |
| **Skills** | `GET /api/skills/`, `POST /api/skills/` |
| **Usage** | `GET /api/usage/`, `GET /api/usage/stats` |
| **Kanban** | `GET /api/kanban/`, `POST /api/kanban/tasks` |
| **Cron** | `GET /api/cron/`, `POST /api/cron/` |
| **MCP** | `GET /api/mcp/`, `POST /api/mcp/connect` |
| **Gateway** | `POST /api/gateway/send`, `GET /api/gateway/status` |

---

## Development

```bash
make install      # First-time setup
make run          # Production server
make dev          # Hot-reload dev server
make test         # Run all tests
make test-unit    # Unit tests only
make status       # Check server health
make clean        # Remove cache and build artifacts
```

---

## Package Status

| Package | Language | Status | Notes |
|---------|----------|--------|-------|
| `packages/core` | Python | ✅ Production | Agent engine, swarm, RAG, skills |
| `packages/server` | Python | ✅ Production | FastAPI server, 26 rute API |
| `packages/web-ui` | HTML/JS | ✅ Production | 18 pagini, PWA, WebSocket + SSE |
| `packages/desktop-app` | Electron | ✅ Production | Desktop wrapper nativ (Electron 33) |
| `packages/gateway` | Python | ✅ Production | 34 platforme (Telegram, Discord, etc.) |
| `packages/mcp` | TypeScript | ✅ Compilat | MCP client + OAuth — `dist/` generat |
| `packages/sdk` | TypeScript | ✅ Compilat | HTTP client tipizat — `dist/` generat |
| `packages/shared` | TypeScript | ✅ Compilat | Tipuri partajate — `dist/` generat |
| `packages/ts-core` | TypeScript | ✅ Compilat | Core utilities — `dist/` generat |
| `packages/ts-runtime` | TypeScript | ✅ Compilat | Agent TS runtime — `dist/` generat |
| `packages/llm` | TypeScript | ✅ Compilat | 10 provideri LLM — `dist/` generat |
| `packages/tools` | TypeScript | ✅ Compilat | Registry 70+ tools — `dist/` generat |
| `packages/plugin` | TypeScript | ✅ Compilat | Plugin API — `dist/` generat |
| `packages/ui` | TypeScript | ✅ Compilat | UI components (Solid.js) — `dist/` generat |
| `packages/react-ui` | TypeScript | ✅ Compilat | Desktop UI alternativ — `dist/` 22MB bundle |
| `packages/cli` | TypeScript | 🧪 Experimental | TUI — compilat, neintegrat cu Python |

> **Notă:** Toate 11 pachete TypeScript au `dist/` generat cu `bun build`. Interfața principală rămâne Web UI la `http://localhost:13210`. Integrarea TypeScript↔Python este planificată pentru v2.1.

---

## Python ↔ TypeScript Bridge

ICECODE uses a **deliberate HTTP bridge** between the Python backend and TypeScript frontends.

```
┌─────────────────────────┐       HTTP / WebSocket        ┌──────────────────────────┐
│  TypeScript frontends   │  ◄────────────────────────►   │  Python FastAPI backend  │
│  - CLI TUI (Ink)        │  GET/POST /api/*               │  - Agent engine (core)   │
│  - React UI (desktop)   │  WS /ws/{session_id}           │  - RAG / Knowledge       │
│  - Web browser          │  SSE /api/chat/stream          │  - Swarm orchestration   │
└─────────────────────────┘                               └──────────────────────────┘
```

The `@icecode/server` TypeScript package (`packages/server/src/index.ts`) provides:
- Shared API types (`ChatMessage`, `StreamChunk`, `Session`, `KanbanTask`, etc.)
- A typed HTTP client (`apiGet`, `apiPost`, `streamChat`)
- WebSocket streaming helper

This design means TypeScript packages **never import Python code directly** — they only call the REST/WS API. This keeps the runtimes completely independent and allows the web UI, desktop app, and CLI to all connect to the same backend.

**To run TypeScript packages:**
```bash
pnpm install          # installs all TS dependencies + generates lockfile
pnpm --filter @icecode/shared build    # build shared types first
pnpm --filter @icecode/server build    # build server client
pnpm --filter @icecode/cli dev         # run TUI
```

---

## Version

**ICECODE v2.0.0** — 2026-05-20

Built with: Python 3.10+, FastAPI, Ollama, FAISS, sentence-transformers, Electron.

---

*License: ICECODE Source Available Non-Commercial License v1.0. Copyright (c) 2026 Claudiu. Commercial use prohibited — contact iceslim409@gmail.com.*
