# Getting Started with ICECODE

Get from zero to a running AI agent in under 10 minutes.

---

## 1. Install

**Requirements:** Python 3.10+, Git

```bash
git clone https://github.com/iceslim409/SuperAgent-ICECODE.git
cd SuperAgent-ICECODE/icecode
bash install.sh
```

`install.sh` creates a `.venv`, installs all Python packages, and writes a starter `.env`. To verify:

```bash
make test       # should print: 256 passed
make status     # server not running yet — that's expected
```

---

## 2. Configure an LLM provider

ICECODE works with **Ollama** (local, free) or any cloud provider (Anthropic, OpenAI, Google, etc.).

### Option A — Ollama (recommended for local use)

```bash
# Install Ollama from https://ollama.com, then pull a model:
ollama pull qwen2.5:7b

# ICECODE auto-detects Ollama — no config needed
make run
```

### Option B — Cloud provider (Anthropic / OpenAI / Google)

Edit `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-...
# or
OPENAI_API_KEY=sk-...
# or
GOOGLE_API_KEY=AIza...
```

Then start:

```bash
make run
```

Open **http://localhost:13210** — you should see the chat interface.

---

## 3. Send your first message

### Via browser

Go to http://localhost:13210, type a message, press Enter.

### Via API

```bash
curl -X POST http://localhost:13210/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 2 + 2?", "stream": false}'
```

Response:

```json
{
  "session_id": "s_a3f8e1c2",
  "response": "2 + 2 = 4.",
  "usage": {"prompt_tokens": 24, "completion_tokens": 8, "iterations": 1}
}
```

### Via Python

```python
import asyncio
import sys
sys.path.insert(0, "packages/core")

from icecode.agent.core import ICECodeAgent

async def main():
    agent = ICECodeAgent(provider="ollama", model="qwen2.5:7b")
    async for chunk in agent.stream("Explain recursion in one sentence."):
        if chunk["type"] == "text":
            print(chunk["content"], end="", flush=True)

asyncio.run(main())
```

---

## 4. Continue a conversation (sessions)

Every chat is stored as a session. Pass `session_id` to continue:

```bash
# First turn
curl -X POST http://localhost:13210/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "My name is Alex.", "session_id": "my_session", "stream": false}'

# Second turn — agent remembers "Alex"
curl -X POST http://localhost:13210/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "What is my name?", "session_id": "my_session", "stream": false}'
```

Session history is stored at `~/.icecode/sessions/<session_id>.json`.

---

## 5. Add documents to the knowledge base

Index any file or directory so the agent can search it semantically:

```bash
# Index a single file
curl -X POST http://localhost:13210/api/knowledge/index \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/your/document.md"}'

# Index a whole directory
curl -X POST http://localhost:13210/api/knowledge/index \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/your/project/", "recursive": true}'

# Or use make
make knowledge-index   # indexes the current ICECODE directory
```

Search it:

```bash
curl "http://localhost:13210/api/knowledge/search?q=your+query&k=5"
```

Supported file types: `.txt`, `.md`, `.py`, `.ts`, `.json`, `.csv`, `.html`, `.pdf`

The knowledge base uses **sentence-transformers + FAISS** — fully local, no API key required.

---

## 6. Run a multi-agent swarm

Use the swarm for tasks that benefit from multiple perspectives or a pipeline of steps.

### Pre-built templates

| Template | Mode | Agents | Use case |
|----------|------|--------|----------|
| `research_write` | pipeline | Researcher → Writer | Long-form content |
| `code_review` | pipeline | Security → Quality → Refactor | Code review |
| `brainstorm` | parallel | Optimist + Critic + Pragmatist | Idea generation |

```bash
curl -X POST http://localhost:13210/api/swarm/run \
  -H "Content-Type: application/json" \
  -d '{"input": "Write a blog post about async Python.", "template": "research_write"}'
```

### Custom swarm

```bash
curl -X POST http://localhost:13210/api/swarm/run \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Summarize this PR: adds async support to the user service",
    "mode": "pipeline",
    "agents": [
      {"role": "Summarizer", "task": "Summarize briefly: {input}"},
      {"role": "Critic",     "task": "Find issues with: {input}"}
    ]
  }'
```

### In the browser

Go to http://localhost:13210 → **Swarm** tab → choose a template → click Run.

---

## 7. Common make targets

```bash
make run          # start server (port 13210)
make dev          # start with hot-reload
make test         # run all 256 tests
make test-unit    # unit tests only
make stop         # kill the server
make logs         # tail server logs
make clean        # remove __pycache__ and .pytest_cache
make docker-run   # run via Docker Compose (needs Docker)
```

---

## 8. Project layout

```
icecode/
├── packages/
│   ├── core/          Python agent engine, swarm, knowledge base, RL
│   ├── server/        FastAPI server (31 routes, port 13210)
│   ├── gateway/       32 messaging platform adapters
│   ├── tools/         80+ tool implementations
│   ├── cli/           Python CLI + TypeScript TUI
│   └── web-ui/        Single-page web app (18 feature pages)
├── tests/
│   ├── unit/          171 unit tests
│   └── integration/   85 integration + E2E tests
├── skills/            Active skills directory
├── Makefile
├── install.sh
└── docker-compose.yml
```

---

## 9. Troubleshooting

**Server won't start**

```bash
make debug      # runs debug.sh which checks all dependencies
```

**Ollama not detected**

```bash
ollama serve    # make sure Ollama is running
ollama list     # verify you have at least one model
```

**Tests fail**

```bash
make test-unit  # run only unit tests (no server needed)
```

**Port 13210 already in use**

```bash
make stop
make run
```

**Import errors**

```bash
bash install.sh     # re-run installer to fix missing packages
```

---

## 10. Next steps

- **Connect a messaging platform**: See `packages/gateway/` — supports Telegram, Discord, WhatsApp, Slack and 28 more
- **Create custom skills**: Add `.yaml` files to `~/.icecode/skills/` — the agent picks them up automatically
- **Use the Web UI**: Full-featured at http://localhost:13210 — chat, knowledge base, swarm, kanban, settings
- **Desktop app**: See `packages/desktop-app/` for the Electron build
