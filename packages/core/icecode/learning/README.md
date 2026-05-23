# ICECODE Learning System

The learning system has two components: the **curator** (automatic skill maintenance) and **optional-skills** (curated skill library).

---

## Curator — Background Skill Maintenance

The curator is a background task that periodically reviews agent-created skills, transitions stale ones to archived, and consolidates redundant ones. It runs entirely offline using the auxiliary LLM client — it never touches the main chat session.

### How it works

```
Agent goes idle
    ↓
maybe_run_curator() called
    ↓
should_run_now() checks gates:
  ✓ curator.enabled = true (default)
  ✓ not paused
  ✓ last_run_at > interval_hours ago (default 7 days)
  ✓ idle_for_seconds > min_idle_hours (default 2h)
    ↓
apply_automatic_transitions()
  → active skills unused for stale_after_days (30) → stale
  → stale skills unused for archive_after_days (90) → archived
    ↓
run_curator_review()
  → spawns forked AIAgent with CURATOR_REVIEW_PROMPT
  → LLM reviews all agent-created skills
  → LLM can: pin / archive / consolidate / patch skills
  → writes JSON + Markdown report to ~/.icecode/skills/curator_reports/
```

### State file

Stored at `~/.icecode/skills/.curator_state`:

```json
{
  "last_run_at": "2026-05-20T14:00:00",
  "last_run_duration_seconds": 42.3,
  "last_run_summary": "Archived 2, pinned 1, no changes to 8.",
  "paused": false,
  "run_count": 7
}
```

### Configuration

Add to `~/.icecode/config.yaml`:

```yaml
curator:
  enabled: true          # set false to disable completely
  interval_hours: 168    # how often to run (default: 7 days = 168h)
  min_idle_hours: 2      # agent must be idle this long before running
  stale_after_days: 30   # days without use before skill → stale
  archive_after_days: 90 # days in stale before skill → archived
```

### Skill lifecycle

```
active → stale → archived
          ↑         ↑
       (usage)    (time)
          
pinned → bypasses all transitions forever
```

**Rules:**
- Curator only touches **agent-created** skills (`is_agent_created() == True`)
- Human-created skills are never modified automatically
- Archived skills are **never deleted** — they stay recoverable in `~/.icecode/skills/archive/`
- Pinned skills are frozen in place regardless of usage or age

### Entry point

```python
from icecode.agent.curator import maybe_run_curator

# Called by the agent when it detects idle time
result = maybe_run_curator(
    idle_for_seconds=7500,           # how long the agent has been idle
    on_summary=lambda s: print(s),   # callback when curator prints its summary
)
# result is None if gates didn't pass, or a dict with run details
```

### Module layout

| File | Responsibility |
|------|---------------|
| `curator.py` | Entry point — `maybe_run_curator()`, re-exports from sub-modules |
| `curator_state.py` | Read/write `.curator_state` JSON file |
| `curator_config.py` | Read `curator.*` from `config.yaml` with defaults |
| `curator_scheduler.py` | `should_run_now()` gate check + `apply_automatic_transitions()` |
| `curator_orchestrator.py` | `run_curator_review()` — spawns forked AIAgent for LLM review |
| `curator_prompt.py` | Prompt strings: `CURATOR_REVIEW_PROMPT`, `CURATOR_DRY_RUN_BANNER` |
| `curator_reports.py` | Write JSON + Markdown report per curator run |
| `curator_backup.py` | Snapshot/restore for skills before curator modifies them |

### Dry run

Set the env var to see what the curator *would* do without changing anything:

```bash
ICECODE_CURATOR_DRY_RUN=1 python3 -m icecode.agent.curator
```

---

## Optional Skills Library

Pre-built skills organized by domain in `optional-skills/`:

```
optional-skills/
├── blockchain/          Solidity auditing, DeFi analysis, NFT metadata
├── creative/            Writing, poetry, storytelling assistance
├── devops/              CI/CD pipeline generation, Docker, Kubernetes
├── finance/             Financial analysis, portfolio review, budget planning
├── health/              Symptom analysis, medication lookup (disclaimer required)
├── mcp/                 Model Context Protocol server interaction skills
├── migration/           Database migration, code migration guides
├── mlops/               Model training, evaluation, experiment tracking
├── productivity/        Pomodoro, task prioritization, meeting summaries
├── research/            Academic search, citation formatting, literature review
├── security/            Pen test helpers, CVE lookup, code security review
├── email/               Email drafting, summarization, thread analysis
├── web-development/     HTML/CSS/JS generation, accessibility checks
├── software-development/ Code review, refactoring, architecture design
├── autonomous-ai-agents/ Agent orchestration, prompt engineering
└── dogfood/             ICECODE self-improvement skills
```

### Activating a skill

Skills in `optional-skills/` are **not active by default**. To activate:

```bash
# Via API
curl -X POST http://localhost:13210/api/skills/install \
  -H "Content-Type: application/json" \
  -d '{"slug": "blockchain/solidity-audit"}'

# Or copy to the active skills directory
cp optional-skills/security/pen-test.yaml ~/.icecode/skills/
```

Or activate from the Web UI → Skills page → Optional tab.

### Skill file format

Each skill is a YAML file:

```yaml
name: "Security Code Review"
slug: security/code-review
description: "Reviews code for common security vulnerabilities"
author: icecode
version: "1.0"
tags: [security, code-review, owasp]
prompt: |
  You are a security-focused code reviewer. When reviewing code, check for:
  - SQL injection vulnerabilities
  - XSS attack vectors
  - Insecure deserialization
  - Hardcoded credentials
  ...
```
