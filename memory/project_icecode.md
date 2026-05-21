---
name: project_icecode
description: ICECODE Super-Agent Network — full system status, architecture, and key file paths
metadata:
  type: project
---

ICECODE Super-Agent Network v1.0.0 — unified platform from Hermes + ClawX + OpenCode.
Location: /home/claudiu/Desktop/super agent/icecode/

**Why:** Merged 3 real projects to create one super-agent platform.
**How to apply:** Use these paths and commands when working on the project.

## Core files
- `start.sh` — start all services, open browser + optional desktop app
- `stop.sh` — stop all services cleanly
- `icecode` — CLI launcher (./icecode [--autonomous] [message])
- `.venv/` — Python venv (activate: source .venv/bin/activate)
- `.env` — API keys (copy from .env.example)

## Agent engine
- `packages/core/icecode/agent/core.py` — ICECodeAgent class (openai SDK, Ollama compatible)
- `packages/core/icecode/agent/computer_tools.py` — computer control (screenshot, click, type)
- `packages/server/icecode_server/routes/chat.py` — SSE streaming chat route
- Server: FastAPI port 13210 (47 routes)

## Interfaces
1. **Terminal**: `./icecode` — rich CLI with streaming, tool calls visible, history, memories
   - `./icecode --autonomous "task"` — computer control mode
2. **Web UI**: `packages/web-ui/index.html` — 1815-line dashboard (10 pages)
3. **Desktop**: `packages/desktop-app/` — Electron app (loads web UI + server)
   - Launch: `packages/desktop-app/node_modules/.bin/electron packages/desktop-app`

## Agent capabilities (all via tool calls)
- read_file, write_file, list_dir, run_terminal, web_fetch, search_web
- remember, recall (persistent memory across sessions)
- screenshot, click, type_text, hotkey, move_mouse, scroll, get_screen_size, open_app (autonomous mode)

## Live test results (2026-05-20)
- Agent created FastAPI project: 3 files in 19s with 3 tool calls
- Agent debugged and ran code: 8s, used run_terminal
- Agent stored memories: 2 keys persisted in ~/.icecode/agent_memory/
- Screen size detected: 1920x1080 via get_screen_size tool
- Local models active: qwen2.5:7b (main), 17 Ollama models total
