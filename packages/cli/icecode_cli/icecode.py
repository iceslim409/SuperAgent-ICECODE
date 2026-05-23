#!/usr/bin/env python3
"""
ICECODE Terminal Agent — interactive REPL.

./icecode                        interactive REPL
./icecode "task"                 single-shot
./icecode --autopilot "task"     autopilot — no confirmations
./icecode -A "task"              autopilot shortcut
./icecode --autonomous "task"    computer control
./icecode --list-models

Commands (Tab to autocomplete, / + Enter for full menu):
  /             full command menu
  /models       interactive model picker
  /model NAME   switch model directly
  /providers    provider list + key status
  /sessions     pick & load a session
  /session ID   load session by ID
  /new          new session
  /history      messages in current session
  /memories     stored agent memories
  /forget KEY   delete a memory
  /agents  /channels  /cron
  /skills           skills manager — activate/deactivate skills
  /skills library   browse all 166 skills, toggle on/off
  /skills clear     clear all active skills
  /autoskills       toggle auto-detect skills per message
  /status       full system status
  /usage        token stats
  /computer on|off
  /autopilot on|off|toggle
  /clear  /help  /quit
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import argparse

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PTStyle

console = Console()
SERVER_URL = os.getenv("ICECODE_SERVER", "http://localhost:13210")

BANNER = """\
  ██╗ ██████╗███████╗ ██████╗ ██████╗ ██████╗ ███████╗
  ██║██╔════╝██╔════╝██╔════╝██╔═══██╗██╔══██╗██╔════╝
  ██║██║     █████╗  ██║     ██║   ██║██║  ██║█████╗
  ██║██║     ██╔══╝  ██║     ██║   ██║██║  ██║██╔══╝
  ██║╚██████╗███████╗╚██████╗╚██████╔╝██████╔╝███████╗
  ╚═╝ ╚═════╝╚══════╝ ╚═════╝ ╚═════╝ ╚═════╝╚══════╝"""

PT_STYLE = PTStyle.from_dict({
    "ansi_green": "#00ff88 bold",
    "ansi_cyan":  "#58a6ff",
    "ansi_white": "#e6edf3",
    "ansi_dim":   "#8b949e",
})

SLASH_COMMANDS = [
    ("/models",    "🤖 Pick model — all local + cloud"),
    ("/providers", "🔑 Providers — API key status"),
    ("/sessions",  "🗂  Sessions — pick & load"),
    ("/new",       "✨ New session"),
    ("/history",   "📜 Current session messages"),
    ("/memories",  "🧠 Agent memories"),
    ("/forget",    "🗑  Delete a memory"),
    ("/agents",      "👾 Configured agents"),
    ("/channels",    "📡 Channels (Telegram, Discord…)"),
    ("/skills",      "⚡ Skills — manage active skills"),
    ("/autoskills",  "🔮 Auto-skills — auto-detect skills per message"),
    ("/cron",        "⏰ Scheduled jobs"),
    ("/status",      "🔍 System status"),
    ("/usage",       "📊 Token usage"),
    ("/computer",    "🖥  Computer control mode"),
    ("/autopilot",   "🤖 Autopilot — agent runs autonomously without confirmation"),
    ("/clear",     "🧹 Clear screen"),
    ("/help",      "❓ Help"),
    ("/quit",      "👋 Quit"),
]


# ── Tab completer ─────────────────────────────────────────────────────────────

class ICECodeCompleter(Completer):
    def __init__(self, cli: "ICECodeCLI"):
        self.cli = cli

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        word = text.lstrip()
        for cmd, desc in SLASH_COMMANDS:
            if cmd.startswith(word):
                yield Completion(cmd[len(word):], 0,
                                 display=cmd, display_meta=desc)
        if text.startswith("/model ") and not text.startswith("/models"):
            partial = text[7:]
            for m in self.cli.cached_models:
                if m.lower().startswith(partial.lower()):
                    yield Completion(m[len(partial):], 0, display=m)
        if text.startswith("/session ") and not text.startswith("/sessions"):
            partial = text[9:]
            for s in self.cli.cached_sessions:
                sid = s.get("session_id","")
                if sid.startswith(partial):
                    yield Completion(sid[len(partial):], 0, display=sid)
        if text.startswith("/forget "):
            partial = text[8:]
            for k in self.cli.cached_memory_keys:
                if k.startswith(partial):
                    yield Completion(k[len(partial):], 0, display=k)


# ── Inline async picker ───────────────────────────────────────────────────────

async def _pick_async(
    session: PromptSession,
    items: List[Dict],
    title: str = "Select",
    filter_hint: str = "type number or name filter",
) -> Optional[Any]:
    """
    Reliable inline picker that reuses the existing PromptSession.
    Shows a numbered list; user types a number OR partial name to filter.
    Works in every terminal — no extra Application, no event-loop conflicts.
    """
    while True:
        # Print list (filtered if we have a filter string)
        console.print(f"\n[bold cyan]{title}[/bold cyan]")
        console.print(f"[dim]  {filter_hint} — Enter to cancel[/dim]")
        console.print()

        for i, item in enumerate(items, 1):
            desc = f"  [dim]{item.get('description','')[:55]}[/dim]" if item.get("description") else ""
            console.print(f"  [yellow]{i:>2}.[/yellow]  {item['label']}{desc}")

        console.print()
        try:
            raw = await session.prompt_async(
                HTML('<ansi_cyan>  › </ansi_cyan>'),
                style=PT_STYLE,
            )
        except (EOFError, KeyboardInterrupt):
            return None

        raw = raw.strip()
        if not raw:
            return None

        # Numeric selection
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(items):
                return items[idx]["value"]
            console.print(f"[red]  Invalid number. Enter 1–{len(items)}.[/red]")
            continue

        # Text filter — re-render filtered list
        q = raw.lower()
        filtered = [it for it in items
                    if q in it["label"].lower() or q in it.get("description","").lower()]

        if not filtered:
            console.print(f"[yellow]  No matches for '{raw}'. Try again.[/yellow]")
            continue

        if len(filtered) == 1:
            console.print(f"[green]  ✓ {filtered[0]['label']}[/green]")
            return filtered[0]["value"]

        # Multiple matches — show filtered list
        items = filtered          # narrow down and loop
        filter_hint = "filtered — type number to select"


# ── Main CLI class ────────────────────────────────────────────────────────────

class ICECodeCLI:
    def __init__(self, model: str, provider: str, server: str,
                 enable_computer: bool = False, autopilot: bool = False):
        self.model          = model
        self.provider       = provider
        self.server         = server.rstrip("/")
        self.session_id     = f"s_{uuid.uuid4().hex[:8]}"
        self.enable_computer = enable_computer
        self.autopilot      = autopilot
        self.active_skills  : List[str] = []
        self.auto_skills    : bool      = False

        self.cached_models       : List[str]  = []
        self.cached_sessions     : List[Dict] = []
        self.cached_memory_keys  : List[str]  = []

        self.usage_total   = {"prompt_tokens": 0, "completion_tokens": 0,
                              "tool_calls": 0, "total_tokens": 0}
        self.message_count = 0

        hist_file = Path.home() / ".icecode" / "cli_history"
        hist_file.parent.mkdir(parents=True, exist_ok=True)
        self.pt = PromptSession(
            history=FileHistory(str(hist_file)),
            completer=ICECodeCompleter(self),
            complete_while_typing=True,
            style=PT_STYLE,
        )

    # ── API ───────────────────────────────────────────────────────────────────

    def _api(self, path: str, timeout: float = 5.0) -> Optional[Any]:
        try:
            r = httpx.get(f"{self.server}{path}", timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None

    def _online(self) -> bool:
        return self._api("/health") is not None

    # ── Model list ────────────────────────────────────────────────────────────

    def _model_items(self) -> List[Dict]:
        items: List[Dict] = []

        # Local models via Ollama scan
        scan = self._api("/api/local-models/scan", timeout=8) or {}
        for stype, sinfo in scan.get("servers", {}).items():
            for m in sinfo.get("models", []):
                items.append({
                    "label":       f"⚡ {m}",
                    "value":       f"ollama/{m}",
                    "description": f"local — {stype}",
                    "provider":    "ollama",
                    "model":       m,
                })

        # Cloud providers
        catalog = self._api("/api/models") or {}
        for prov, ms in catalog.get("models", {}).items():
            if prov == "ollama" or ms == ["*"]:
                continue
            for m in ms:
                items.append({
                    "label":       f"☁  {prov}/{m}",
                    "value":       f"{prov}/{m}",
                    "description": f"Cloud — {prov}",
                    "provider":    prov,
                    "model":       m,
                })

        self.cached_models = [it["value"] for it in items]
        return items

    # ── Display helpers ───────────────────────────────────────────────────────

    def _table(self, title: str, cols: List, rows: List[List]) -> None:
        t = Table(show_header=True, header_style="bold cyan",
                  box=None, padding=(0, 2), expand=True)
        for c in cols:
            kw = {k: v for k, v in c.items() if k != "name"}
            t.add_column(c["name"], **kw)
        for r in rows:
            t.add_row(*r)
        console.print(Panel(t, title=f"[bold]{title}[/bold]",
                            border_style="cyan", padding=(1, 1)))

    # ── Commands ──────────────────────────────────────────────────────────────

    def cmd_help(self):
        t = Table(show_header=True, header_style="bold cyan",
                  box=None, padding=(0, 2))
        t.add_column("Command",    style="bold yellow", min_width=18)
        t.add_column("Description")
        for cmd, desc in SLASH_COMMANDS:
            t.add_row(cmd, desc)
        t.add_row("", "")
        t.add_row("[dim]/[/dim]",         "[dim]Open full command menu[/dim]")
        t.add_row("[dim]Tab[/dim]",        "[dim]Autocomplete[/dim]")
        t.add_row("[dim]↑ ↓[/dim]",        "[dim]Command history[/dim]")
        t.add_row("[dim]Ctrl+C[/dim]",     "[dim]Cancel generation[/dim]")
        console.print(Panel(t, title="[bold]ICECODE — Commands[/bold]",
                            border_style="cyan", padding=(1, 2)))

    async def cmd_models(self):
        console.print("[dim]Loading models...[/dim]")
        items = self._model_items()
        if not items:
            console.print("[yellow]No models found. Is Ollama running? (ollama serve)[/yellow]")
            return
        chosen = await _pick_async(self.pt, items,
                                   title="Select Model",
                                   filter_hint="type number, or name to filter (e.g. qwen, mistral, gpt)")
        if chosen:
            if "/" in chosen:
                self.provider, self.model = chosen.split("/", 1)
            else:
                self.model = chosen
            console.print(f"[green]✓ Model: [cyan]{self.provider}/{self.model}[/cyan][/green]\n")

    async def cmd_sessions(self):
        sessions = self._api("/api/chat/sessions") or []
        self.cached_sessions = sessions
        if not sessions:
            console.print("[dim]No sessions yet. Start chatting to create one.[/dim]")
            return
        items = []
        for s in sessions[:40]:
            meta = s.get("metadata") or {}
            mstr = (f"{meta.get('provider','')}/{meta.get('model','')}"
                    if meta.get("model") else "—")
            items.append({
                "label":       s["session_id"],
                "value":       s["session_id"],
                "description": (f"{s.get('message_count',0)} msgs · "
                                f"{mstr} · {s.get('updated_at','')[:16]}"),
            })
        chosen = await _pick_async(self.pt, items,
                                   title="Sessions — pick to load",
                                   filter_hint="type number or partial session ID")
        if chosen:
            self.session_id = chosen
            console.print(f"[green]✓ Session: [cyan]{chosen}[/cyan][/green]\n")

    async def cmd_forget_picker(self):
        mems = self._api("/api/chat/memories") or {}
        if not mems:
            console.print("[dim]No memories stored.[/dim]")
            return
        self.cached_memory_keys = list(mems.keys())
        items = []
        for key, val in mems.items():
            v = (val.get("value", str(val)) if isinstance(val, dict) else str(val))[:60]
            items.append({"label": key, "value": key, "description": v})
        chosen = await _pick_async(self.pt, items,
                                   title="Select memory to delete",
                                   filter_hint="type number or key name")
        if chosen:
            self._do_forget(chosen)

    def _do_forget(self, key: str):
        f = Path.home() / ".icecode" / "agent_memory" / "memories.json"
        if not f.exists():
            console.print("[yellow]No memory file found.[/yellow]"); return
        mems = json.loads(f.read_text())
        if key not in mems:
            console.print(f"[yellow]'{key}' not found.[/yellow]"); return
        del mems[key]
        f.write_text(json.dumps(mems, indent=2))
        console.print(f"[green]✓ Deleted: {key}[/green]")

    async def cmd_computer_picker(self):
        items = [
            {"label": "⚡ Enable  — autonomous desktop control",
             "value": "on",
             "description": "Agent can screenshot, click, type, open apps"},
            {"label": "○ Disable — standard mode",
             "value": "off",
             "description": "No computer control"},
        ]
        chosen = await _pick_async(self.pt, items, title="Computer Control Mode")
        if chosen == "on":
            self.enable_computer = True
            console.print("[yellow]⚡ Computer control ENABLED[/yellow]\n")
        elif chosen == "off":
            self.enable_computer = False
            console.print("[dim]Computer control disabled[/dim]\n")

    def cmd_providers(self):
        catalog = (self._api("/api/providers/catalog") or {}).get("providers", [])
        configured = self._api("/api/providers") or []
        conf_ids = {p.get("id") for p in configured}
        rows = []
        for p in catalog:
            pid = p["id"]
            if pid in conf_ids:
                st = "[green]✓ configured[/green]"
            elif pid == "ollama":
                st = "[green]✓ local[/green]"
            elif os.getenv(f"{pid.upper().replace('-','_')}_API_KEY", ""):
                st = "[yellow]env key[/yellow]"
            else:
                st = "[dim]not set[/dim]"
            models = p.get("models") or p.get("static_models") or []
            ms = ", ".join(models[:4])
            if len(models) > 4:
                ms += f" +{len(models)-4}"
            rows.append([p["name"], st, ms])
        self._table("Providers",
                    [{"name":"Provider","min_width":22},
                     {"name":"Status","width":18},
                     {"name":"Models","min_width":40}], rows)
        console.print("  [dim]Configure keys at [yellow]http://localhost:13210[/yellow] → Providers[/dim]\n")

    def cmd_history(self):
        data = self._api(f"/api/chat/sessions/{self.session_id}")
        if not data or not data.get("messages"):
            console.print("[dim]No messages in current session yet.[/dim]"); return
        msgs = data["messages"]
        console.print(Panel(
            f"Session [cyan]{self.session_id}[/cyan] — {len(msgs)} messages",
            border_style="cyan"))
        for m in msgs[-20:]:
            role = m.get("role","?")
            content = str(m.get("content") or "")[:280]
            if role == "user":
                console.print(f"  [bold yellow]You:[/bold yellow]   {content}")
            elif role == "assistant":
                console.print(f"  [bold cyan]Agent:[/bold cyan] {content}")
            elif role == "tool":
                console.print(f"  [dim]  ↳ [tool result][/dim]")
        console.print()

    def cmd_memories(self):
        mems = self._api("/api/chat/memories") or {}
        self.cached_memory_keys = list(mems.keys())
        if not mems:
            console.print("[dim]No memories yet. Agent learns via `remember` tool.[/dim]"); return
        rows = []
        for key, val in mems.items():
            v  = (val.get("value", str(val)) if isinstance(val, dict) else str(val))[:80]
            ts = (val.get("timestamp","")[:10] if isinstance(val, dict) else "")
            rows.append([key, v, ts])
        self._table(f"Memories ({len(mems)})",
                    [{"name":"Key","style":"yellow","min_width":25},
                     {"name":"Value","min_width":50},
                     {"name":"Saved","width":12}], rows)
        console.print("  [dim]Delete with [yellow]/forget[/yellow][/dim]\n")

    def cmd_agents(self):
        agents = self._api("/api/agents/") or []
        if not agents:
            console.print("[dim]No agents. Create at http://localhost:13210 → Agents[/dim]"); return
        rows = [[a.get("name","—"), a.get("model","—"),
                 ", ".join((a.get("tools") or [])[:3]),
                 (a.get("created_at","") or "")[:10]] for a in agents]
        self._table(f"Agents ({len(agents)})",
                    [{"name":"Name","style":"cyan","min_width":18},
                     {"name":"Model","min_width":22},
                     {"name":"Tools","min_width":20},
                     {"name":"Created","width":12}], rows)

    def cmd_channels(self):
        channels = self._api("/api/channels/") or []
        if not channels:
            console.print("[dim]No channels. Add at http://localhost:13210 → Channels[/dim]"); return
        rows = [[c.get("name","—"), c.get("platform","—"),
                 "[green]active[/green]" if c.get("active") else "[dim]inactive[/dim]"]
                for c in channels]
        self._table(f"Channels ({len(channels)})",
                    [{"name":"Name","style":"cyan","min_width":18},
                     {"name":"Platform","width":16},
                     {"name":"Status","width":12}], rows)

    async def cmd_skills(self, arg: str = ""):
        if arg == "clear":
            n = len(self.active_skills)
            self.active_skills.clear()
            console.print(f"[green]✓ Cleared {n} active skill(s)[/green]")
            return
        if arg in ("library", "lib", "browse", "l"):
            await self._cmd_skills_library()
            return
        if arg:
            await self._cmd_skills_toggle(arg)
            return

        # Default: show status panel
        auto_st = "[bold magenta]ON 🔮[/bold magenta]" if self.auto_skills else "[dim]off[/dim]"
        console.print(Panel(
            f"[dim]Auto-detect:[/dim]   {auto_st}\n"
            f"[dim]Active skills:[/dim] [cyan]{len(self.active_skills)}[/cyan] "
            + (f"— {', '.join(self.active_skills[:6])}{'…' if len(self.active_skills)>6 else ''}"
               if self.active_skills else "[dim]none[/dim]"),
            title="[bold]⚡ Skills[/bold]", border_style="cyan"))

        items = [
            {"label": "📚 Browse library — activate/deactivate skills",
             "value": "library", "description": f"166 skills available"},
            {"label": "🔮 Toggle auto-detect",
             "value": "autoskills",
             "description": "Auto on" if self.auto_skills else "Auto off"},
            {"label": "🗑  Clear all active skills",
             "value": "clear",
             "description": f"{len(self.active_skills)} currently active"},
        ]
        chosen = await _pick_async(self.pt, items, title="Skills options",
                                   filter_hint="type number")
        if chosen == "library":
            await self._cmd_skills_library()
        elif chosen == "autoskills":
            self.auto_skills = not self.auto_skills
            if self.auto_skills:
                console.print("[bold magenta]🔮 Auto-skills ON — relevant skills detected per message[/bold magenta]")
            else:
                console.print("[dim]Auto-skills dezactivat[/dim]")
        elif chosen == "clear":
            self.active_skills.clear()
            console.print("[green]✓ All skills cleared[/green]")

    async def _cmd_skills_library(self):
        """Browse all 166 skills from the library with activate/deactivate."""
        console.print("[dim]Loading skills library...[/dim]")
        library = self._api("/api/skills/library", timeout=10) or []
        if not library:
            console.print("[yellow]Skills library empty. Is the server running?[/yellow]")
            return

        # Group by category for display
        by_cat: dict = {}
        for s in library:
            cat = s.get("category", "general")
            by_cat.setdefault(cat, []).append(s)

        # Show categories first
        cat_items = []
        for cat, skills in sorted(by_cat.items()):
            active_in_cat = sum(1 for s in skills if s.get("slug","") in self.active_skills)
            label = f"{cat}  ({len(skills)} skills"
            if active_in_cat:
                label += f", [green]{active_in_cat} active[/green]"
            label += ")"
            cat_items.append({"label": label, "value": cat,
                               "description": f"{len(skills)} skills in category"})
        cat_items.append({"label": "📋 Show ALL skills", "value": "__all__",
                          "description": "Browse all 166 skills together"})
        cat_items.append({"label": "❌ Clear all active", "value": "__clear__",
                          "description": f"{len(self.active_skills)} currently active"})

        chosen_cat = await _pick_async(self.pt, cat_items,
                                       title="Skills Library — pick category",
                                       filter_hint="type number or category name")
        if not chosen_cat:
            return
        if chosen_cat == "__clear__":
            self.active_skills.clear()
            console.print("[green]✓ All skills cleared[/green]")
            return

        skills_to_show = library if chosen_cat == "__all__" else by_cat.get(chosen_cat, [])

        skill_items = []
        for s in skills_to_show:
            slug = s.get("slug", s.get("name", ""))
            is_active = slug in self.active_skills
            status = "[green]✓ active[/green]" if is_active else ""
            label = f"{'● ' if is_active else '○ '}{slug}"
            skill_items.append({
                "label": label,
                "value": slug,
                "description": f"{s.get('description','')[:55]}  {status}",
            })

        chosen_slug = await _pick_async(self.pt, skill_items,
                                        title=f"Skills — {chosen_cat}  (● = active)",
                                        filter_hint="type number or skill name to toggle")
        if chosen_slug:
            await self._cmd_skills_toggle(chosen_slug)

    async def _cmd_skills_toggle(self, slug: str):
        """Toggle a skill on/off by slug."""
        if slug in self.active_skills:
            self.active_skills.remove(slug)
            console.print(f"[dim]○ Skill deactivated: {slug}[/dim]")
        else:
            self.active_skills.append(slug)
            console.print(f"[green]● Skill activated: {slug}[/green]")
        if self.active_skills:
            console.print(f"  [dim]Active ({len(self.active_skills)}): "
                          f"{', '.join(self.active_skills[:6])}"
                          f"{'…' if len(self.active_skills)>6 else ''}[/dim]")

    def cmd_cron(self):
        jobs = self._api("/api/cron/") or []
        if not jobs:
            console.print("[dim]No cron jobs.[/dim]"); return
        rows = [[j.get("schedule","—"), j.get("task","")[:50], j.get("model","—"),
                 "[green]yes[/green]" if j.get("enabled", True) else "[dim]no[/dim]"]
                for j in jobs]
        self._table(f"Cron ({len(jobs)})",
                    [{"name":"Schedule","style":"yellow","width":16},
                     {"name":"Task","min_width":30},
                     {"name":"Model","min_width":18},
                     {"name":"On","width":6}], rows)

    def cmd_status(self):
        health   = self._api("/health") or {}
        status   = self._api("/api/status") or {}
        diag     = self._api("/api/diagnostics/") or {}
        scan     = self._api("/api/local-models/scan", timeout=7) or {}
        sessions = self._api("/api/chat/sessions") or []
        mems     = self._api("/api/chat/memories") or {}

        t = Table(show_header=False, box=None, padding=(0, 2), expand=True)
        t.add_column("", style="dim", width=26)
        t.add_column("")

        online = "[green]● online[/green]" if health else "[red]● offline[/red]"
        t.add_row("Server",          f"{online}  v{health.get('version','?')}  port 13210")
        t.add_row("Python",          diag.get("python","—")[:50])
        t.add_row("Current model",   f"[cyan]{self.provider}/{self.model}[/cyan]")
        t.add_row("Computer mode",   "[yellow]ON ⚡[/yellow]" if self.enable_computer else "off")
        t.add_row("Autopilot",       "[bold green]ON 🤖[/bold green]" if self.autopilot else "off")
        skills_st = (f"[bold magenta]ON 🔮[/bold magenta]" if self.auto_skills
                     else "[dim]off[/dim]")
        t.add_row("Auto-skills",     skills_st)
        if self.active_skills:
            t.add_row("Active skills",
                      f"[cyan]{len(self.active_skills)}[/cyan] — "
                      + ", ".join(self.active_skills[:5])
                      + ("…" if len(self.active_skills) > 5 else ""))
        t.add_row("Active session",  f"[cyan]{self.session_id}[/cyan]")
        t.add_row("Sessions saved",  str(len(sessions)))
        t.add_row("Memories",        str(len(mems)))
        t.add_row("", "")
        for k, v in status.get("systems", {}).items():
            c = "green" if v == "ready" else "yellow"
            t.add_row(f"  {k}", f"[{c}]{v}[/{c}]")
        t.add_row("", "")
        t.add_row("Local AI servers", str(scan.get("found", 0)))
        for stype, sinfo in scan.get("servers", {}).items():
            t.add_row(f"  {stype}",
                      f"{len(sinfo.get('models',[]))} models — {sinfo.get('url','')}")
        t.add_row("", "")
        pkgs = diag.get("packages", {})
        for pkg in ["anthropic","openai","fastapi","pydantic"]:
            if pkg in pkgs:
                t.add_row(f"  {pkg}", pkgs[pkg])
        console.print(Panel(t, title="[bold]ICECODE Status[/bold]",
                            border_style="cyan", padding=(1, 1)))

    def cmd_usage(self):
        u = self.usage_total
        console.print(Panel(
            f"[dim]Session:[/dim]         [cyan]{self.session_id}[/cyan]\n"
            f"[dim]Messages:[/dim]        [yellow]{self.message_count}[/yellow]\n\n"
            f"[dim]Prompt tokens:[/dim]       [green]{u['prompt_tokens']:,}[/green]\n"
            f"[dim]Completion tokens:[/dim]   [green]{u['completion_tokens']:,}[/green]\n"
            f"[dim]Total:[/dim]               [bold]{u['prompt_tokens']+u['completion_tokens']:,}[/bold]\n"
            f"[dim]Tool calls:[/dim]      [cyan]{u['tool_calls']}[/cyan]",
            title="[bold]Usage[/bold]", border_style="cyan"))

    # ── Streaming ─────────────────────────────────────────────────────────────

    async def _stream(self, message: str) -> dict:
        payload = {
            "message": message,
            "session_id": self.session_id,
            "model": self.model,
            "provider": self.provider,
            "enable_computer": self.enable_computer,
            "autopilot": self.autopilot,
            "max_iterations": 30 if self.autopilot else 10,
            "active_skills": self.active_skills,
            "auto_skills": self.auto_skills,
        }
        full_text = ""; tool_calls = []; usage = {}
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream(
                    "POST", f"{self.server}/api/chat/stream", json=payload
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        console.print(f"[red]Server {resp.status_code}: {body[:200]}[/red]")
                        return {}
                    console.print()
                    cur = ""
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        try:
                            c = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue
                        ct = c.get("type")
                        if ct == "session":
                            self.session_id = c.get("session_id", self.session_id)
                        elif ct == "skills_detected":
                            detected = c.get("skills", [])
                            if detected:
                                console.print(f"  [bold magenta]🔮 Skills detectate automat: "
                                              f"{', '.join(detected)}[/bold magenta]")
                        elif ct == "router":
                            m = c.get("model",""); cplx = c.get("complexity","")
                            console.print(f"  [dim]🧭 Router → {m} ({cplx})[/dim]")
                        elif ct == "tool_call":
                            if cur: console.print(); cur = ""
                            name = c.get("name","")
                            tool_calls.append(name)
                            console.print(f"  [bold cyan]⚙  {name}[/bold cyan]"
                                          f"  [dim]{_fmt(c.get('args',{}))}[/dim]")
                        elif ct == "tool_result":
                            r = c.get("result","")
                            console.print(f"  [dim]  ↳ {r[:150].replace(chr(10),' ')}"
                                          f"{'…' if len(r)>150 else ''}[/dim]")
                        elif ct == "text":
                            txt = c.get("content","")
                            full_text += txt; cur += txt
                            console.print(txt, end="", highlight=False)
                        elif ct == "usage":
                            usage = c.get("usage",{})
                            self.usage_total["prompt_tokens"]    += usage.get("prompt_tokens",0)
                            self.usage_total["completion_tokens"]+= usage.get("completion_tokens",0)
                            self.usage_total["total_tokens"]     += usage.get("total_tokens",0)
                            self.usage_total["tool_calls"]       += usage.get("tool_calls",0)
                        elif ct == "error":
                            console.print(f"\n[red]Error: {c.get('content','')}[/red]")
                    if cur:
                        console.print()
        except httpx.ConnectError:
            console.print("[red]Cannot connect. Run ./start.sh first.[/red]")
        except Exception as e:
            console.print(f"[red]{type(e).__name__}: {e}[/red]")
        self.message_count += 1
        return {"text": full_text, "tool_calls": tool_calls, "usage": usage}

    def _usage_line(self, usage: dict):
        if not usage: return
        pt = usage.get("prompt_tokens",0); ct = usage.get("completion_tokens",0)
        tc = usage.get("tool_calls",0);   el = usage.get("elapsed_seconds",0)
        tools = ", ".join(usage.get("tools_used",[])[:5]) or "—"
        console.print(f"  [dim]↑{pt} ↓{ct} tok · {tc} tool{'s' if tc!=1 else ''}"
                      f" ({tools}) · {el}s[/dim]")

    # ── REPL ──────────────────────────────────────────────────────────────────

    async def run(self, single_shot: Optional[str] = None):
        console.print(f"[bold cyan]{BANNER}[/bold cyan]\n")
        if self._online():
            console.print(f"[green]●[/green] Server [green]online[/green] — {self.server}")
        else:
            console.print(f"[red]●[/red] Server offline — run [yellow]./start.sh[/yellow]")
        console.print(f"  Model:   [cyan]{self.provider}/{self.model}[/cyan]")
        console.print(f"  Session: [dim]{self.session_id}[/dim]")
        if self.enable_computer:
            console.print(f"  [bold yellow]⚡ AUTONOMOUS MODE — computer control active[/bold yellow]")
        if self.autopilot:
            console.print(f"  [bold green]🤖 AUTOPILOT ON — agent runs autonomously without confirmation[/bold green]")
        if self.auto_skills:
            console.print(f"  [bold magenta]🔮 AUTO-SKILLS ON — skill-uri detectate automat per mesaj[/bold magenta]")
        if self.active_skills:
            console.print(f"  [cyan]⚡ {len(self.active_skills)} skill(s) active:[/cyan] "
                          f"{', '.join(self.active_skills[:5])}"
                          f"{'…' if len(self.active_skills)>5 else ''}")
        console.print(f"  [dim]/ = command menu   Tab = autocomplete   /skills = skills   /autoskills = auto   /help = all[/dim]\n")

        try: self._model_items()
        except Exception: pass

        if single_shot:
            res = await self._stream(single_shot)
            self._usage_line(res.get("usage", {}))
            return

        while True:
            try:
                mode = " [AUTO]" if self.enable_computer else ""
                pilot = " [🤖AUTOPILOT]" if self.autopilot else ""
                skl = (f" [⚡{len(self.active_skills)}sk]"
                       if self.active_skills else "")
                auto_sk = " [🔮]" if self.auto_skills else ""
                prompt_html = HTML(
                    f'<ansi_green>ICECODE</ansi_green>'
                    f'<ansi_cyan>{mode}{pilot}{skl}{auto_sk} [{self.provider}/{self.model}]</ansi_cyan>'
                    f' <ansi_white>›</ansi_white> '
                )
                user_input = await self.pt.prompt_async(prompt_html, style=PT_STYLE)
                user_input = user_input.strip()
                if not user_input:
                    continue

                # bare "/" → command menu
                if user_input == "/":
                    items = [{"label": cmd, "value": cmd, "description": desc}
                             for cmd, desc in SLASH_COMMANDS]
                    chosen = await _pick_async(self.pt, items, title="ICECODE — Commands",
                                              filter_hint="type number or command name")
                    if not chosen:
                        continue
                    user_input = chosen

                if user_input.startswith("/"):
                    parts = user_input.split(None, 1)
                    cmd = parts[0].lower()
                    arg = parts[1].strip() if len(parts) > 1 else ""

                    if cmd in ("/quit", "/exit", "/q"):
                        console.print("[dim]Goodbye.[/dim]"); break

                    elif cmd == "/help":       self.cmd_help()
                    elif cmd == "/models":     await self.cmd_models()
                    elif cmd == "/model":
                        if arg:
                            if "/" in arg: self.provider, self.model = arg.split("/", 1)
                            else: self.model = arg
                            console.print(f"[green]✓ [cyan]{self.provider}/{self.model}[/cyan][/green]")
                        else: await self.cmd_models()
                    elif cmd == "/providers":  self.cmd_providers()
                    elif cmd == "/sessions":   await self.cmd_sessions()
                    elif cmd == "/session":
                        if arg: self.session_id = arg; console.print(f"[green]✓ [cyan]{arg}[/cyan][/green]")
                        else: await self.cmd_sessions()
                    elif cmd == "/new":
                        self.session_id = f"s_{uuid.uuid4().hex[:8]}"
                        self.usage_total = {"prompt_tokens":0,"completion_tokens":0,"tool_calls":0,"total_tokens":0}
                        self.message_count = 0
                        console.print(f"[green]✓ New session: [cyan]{self.session_id}[/cyan][/green]")
                    elif cmd == "/history":    self.cmd_history()
                    elif cmd == "/memories":   self.cmd_memories()
                    elif cmd == "/forget":
                        if arg: self._do_forget(arg)
                        else: await self.cmd_forget_picker()
                    elif cmd == "/agents":     self.cmd_agents()
                    elif cmd == "/channels":   self.cmd_channels()
                    elif cmd == "/skills":     await self.cmd_skills(arg)
                    elif cmd == "/autoskills":
                        if arg in ("on","1","yes","true"):
                            self.auto_skills = True
                            console.print("[bold magenta]🔮 Auto-skills ON — skill-uri detectate automat per mesaj[/bold magenta]")
                        elif arg in ("off","0","no","false"):
                            self.auto_skills = False
                            console.print("[dim]Auto-skills dezactivat[/dim]")
                        else:
                            self.auto_skills = not self.auto_skills
                            if self.auto_skills:
                                console.print("[bold magenta]🔮 Auto-skills ON — skill-uri detectate automat per mesaj[/bold magenta]")
                            else:
                                console.print("[dim]Auto-skills dezactivat[/dim]")
                    elif cmd == "/cron":       self.cmd_cron()
                    elif cmd == "/status":     self.cmd_status()
                    elif cmd == "/usage":      self.cmd_usage()
                    elif cmd == "/autopilot":
                        if arg in ("on","1","yes","true"):
                            self.autopilot = True
                            console.print("[bold green]🤖 AUTOPILOT ON — agent runs autonomously without confirmation[/bold green]")
                        elif arg in ("off","0","no","false"):
                            self.autopilot = False
                            console.print("[dim]Autopilot dezactivat[/dim]")
                        else:
                            self.autopilot = not self.autopilot
                            if self.autopilot:
                                console.print("[bold green]🤖 AUTOPILOT ON — agent runs autonomously without confirmation[/bold green]")
                            else:
                                console.print("[dim]Autopilot dezactivat[/dim]")
                    elif cmd == "/computer":
                        if arg in ("on","1","yes"):
                            self.enable_computer = True
                            console.print("[yellow]⚡ Computer control ENABLED[/yellow]")
                        elif arg in ("off","0","no"):
                            self.enable_computer = False
                            console.print("[dim]Computer control disabled[/dim]")
                        else: await self.cmd_computer_picker()
                    elif cmd == "/clear":
                        console.clear()
                        console.print(f"[bold cyan]{BANNER}[/bold cyan]\n")
                    else:
                        console.print(f"[yellow]Unknown: {cmd} — type / for menu[/yellow]")
                    continue

                # chat
                res = await self._stream(user_input)
                self._usage_line(res.get("usage", {}))
                console.print()

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted[/yellow]")
            except EOFError:
                console.print("\n[dim]Goodbye.[/dim]"); break


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt(args: dict) -> str:
    return "  ".join(f"{k}={str(v)[:55].replace(chr(10),'↵')}"
                     for k, v in list(args.items())[:3])


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        prog="icecode",
        description="ICECODE Terminal Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ./icecode                                    interactive REPL
  ./icecode "build a REST API"                 single task
  ./icecode --autopilot "build a REST API"     run fully autonomous
  ./icecode -A "creaza un proiect Python"       shortcut -A
  ./icecode --autonomous "open Firefox"         computer control
  ./icecode --auto-skills "debug my code"       auto-detect skills
  ./icecode --skills python-debugpy "fix bug"   with specific skill
  ./icecode --list-models
        """)
    p.add_argument("message",     nargs="?",  help="Single task")
    p.add_argument("--model","-m",default="", help="Model name")
    p.add_argument("--provider","-p",default="",help="Provider")
    p.add_argument("--server","-s",default=SERVER_URL,help="Server URL")
    p.add_argument("--list-models",action="store_true",help="List models and exit")
    p.add_argument("--autonomous","-a",action="store_true",
                   help="Computer control mode")
    p.add_argument("--autopilot","-A",action="store_true",
                   help="Autopilot mode — agent works autonomously without asking for confirmation")
    p.add_argument("--skills", nargs="*", metavar="SLUG",
                   help="Activate skills by slug (e.g. --skills python-debugpy github-pr-workflow)")
    p.add_argument("--auto-skills", action="store_true",
                   help="Auto-detect relevant skills per message")
    args = p.parse_args()

    provider = args.provider or os.getenv("ICECODE_PROVIDER","")
    model    = args.model    or os.getenv("ICECODE_MODEL","")

    if not provider or not model:
        # Check .env for cloud API keys
        env = Path(__file__).parents[3] / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY=") and line.split("=",1)[1].strip():
                    provider = provider or "anthropic"; model = model or "claude-sonnet-4-6"; break
                if line.startswith("OPENAI_API_KEY=") and line.split("=",1)[1].strip():
                    provider = provider or "openai"; model = model or "gpt-4o-mini"; break

        # Check providers.json for configured cloud providers
        if not model:
            try:
                import json as _json
                pf = Path.home() / ".icecode" / "data" / "providers.json"
                if pf.exists():
                    for p in _json.loads(pf.read_text()):
                        if p.get("enabled", True) and p.get("api_key") and p.get("models"):
                            provider = provider or p["id"]
                            model = p.get("default_model") or p["models"][0]
                            break
            except Exception:
                pass

    provider = provider or "ollama"
    if not model:
        # Auto-pick best available Ollama model from installed list
        _PREFS = ["qwen2.5:7b","qwen3.5:4b","mistral:7b-instruct","phi4-mini:latest",
                  "granite4.1:3b","qwen2.5:3b","qwen3.5:2b","qwen2.5:1.5b","llama3.2:1b",
                  "qwen2.5-coder:7b","qwen2.5:0.5b-instruct"]
        try:
            import httpx as _hx
            r = _hx.get("http://localhost:11434/api/tags", timeout=2)
            installed = [m["name"] for m in r.json().get("models", [])]
            for pref in _PREFS:
                if any(m == pref or m.startswith(pref.split(":")[0]+":") for m in installed):
                    model = next(m for m in installed if m==pref or m.startswith(pref.split(":")[0]+":"))
                    break
            if not model and installed:
                model = installed[0]
        except Exception:
            pass
        model = model or "qwen2.5:7b"

    cli = ICECodeCLI(model=model, provider=provider, server=args.server,
                     enable_computer=args.autonomous,
                     autopilot=args.autopilot)
    if args.skills:
        cli.active_skills = list(args.skills)
    if args.auto_skills:
        cli.auto_skills = True

    if args.list_models:
        cli._model_items()
        items = cli._model_items()
        t = Table(show_header=True, header_style="bold cyan", box=None, padding=(0,2), expand=True)
        t.add_column("#", width=4, style="dim")
        t.add_column("Model", min_width=30)
        t.add_column("Provider", width=14)
        t.add_column("Type", width=12)
        t.add_column("", width=10)
        curr = f"{provider}/{model}"
        for i, m in enumerate(items, 1):
            cur = "← active" if m["value"] == curr else ""
            s = "bold cyan" if cur else "white"
            prov = m.get("provider", "")
            desc = "local" if prov == "ollama" else "cloud"
            t.add_row(str(i), f"[{s}]{m['model']}[/{s}]",
                      m["provider"], desc,
                      f"[green]{cur}[/green]" if cur else "")
        console.print(Panel(t, title=f"[bold]Models ({len(items)})[/bold]",
                            border_style="cyan", padding=(1,1)))
        console.print("  [dim]Use: [yellow]./icecode --model qwen2.5:7b[/yellow]  "
                       "or [yellow]/models[/yellow] inside REPL[/dim]")
        return

    asyncio.run(cli.run(single_shot=args.message))


if __name__ == "__main__":
    main()
