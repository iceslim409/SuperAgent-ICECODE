"""
ICECODE Skills API
Built-in skills + full SKILL.md library (166 skills from skills/builtin + skills/optional)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Root of the skills/ directory (4 levels up from this file)
_SKILLS_ROOT = Path(__file__).parents[4] / "skills"

router = APIRouter(prefix="/api/skills", tags=["skills"])

# ── Built-in skills ───────────────────────────────────────────────────────────

BUILTIN_SKILLS = [
    {
        "id": "code_execution",
        "name": "Code Execution",
        "description": "Run Python, bash, JS code in terminal. Returns output and errors.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["run_terminal"],
        "tags": ["code", "terminal"],
    },
    {
        "id": "file_operations",
        "name": "File Operations",
        "description": "Read, write, list files and directories on disk.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["read_file", "write_file", "list_dir"],
        "tags": ["files", "storage"],
    },
    {
        "id": "web_search",
        "name": "Web Search",
        "description": "Search the web with DuckDuckGo. Returns relevant results.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["search_web", "web_fetch"],
        "tags": ["web", "search"],
    },
    {
        "id": "memory",
        "name": "Persistent Memory",
        "description": "Save and retrieve information between sessions.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["remember", "recall"],
        "tags": ["memory", "learning"],
    },
    {
        "id": "computer_control",
        "name": "Computer Control",
        "description": "Control desktop: screenshot, click, typing, open applications.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["screenshot", "click", "type_text", "hotkey", "open_app",
                  "move_mouse", "scroll", "get_screen_size"],
        "tags": ["autonomous", "desktop"],
    },
    {
        "id": "git_operations",
        "name": "Git Operations",
        "description": "Clone, commit, push, pull via terminal. Lucru cu repository-uri git.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["run_terminal"],
        "tags": ["git", "code"],
    },
    {
        "id": "api_calls",
        "name": "API Calls",
        "description": "Make HTTP requests to external APIs. Parses JSON/XML.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["web_fetch"],
        "tags": ["api", "web"],
    },
    {
        "id": "data_analysis",
        "name": "Data Analysis",
        "description": "Analyze CSV, JSON data. Generate statistics and charts with Python.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["run_terminal", "read_file", "write_file"],
        "tags": ["data", "analysis"],
    },
    {
        "id": "project_scaffold",
        "name": "Project Scaffold",
        "description": "Create project scaffolding (Python, Node.js, React, FastAPI etc.)",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["write_file", "run_terminal", "list_dir"],
        "tags": ["code", "scaffold"],
    },
    {
        "id": "self_learning",
        "name": "Self Learning",
        "description": "Agent learns from interactions and saves new knowledge.",
        "version": "1.0.0",
        "enabled": True,
        "builtin": True,
        "tools": ["remember", "recall"],
        "tags": ["learning", "memory"],
    },
]


class SkillToggle(BaseModel):
    enabled: bool


def _skills_file():
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    return cfg.home_dir / "data" / "skills_config.json"


def _load_overrides() -> dict:
    """Load enable/disable overrides for skills."""
    f = _skills_file()
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return {}


def _save_overrides(overrides: dict):
    f = _skills_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(overrides, indent=2))


def _build_skill_list():
    """Return built-in skills + any user skills from ~/.icecode/skills/."""
    overrides = _load_overrides()
    result = []

    # Built-in skills with override support
    for s in BUILTIN_SKILLS:
        skill = dict(s)
        if skill["id"] in overrides:
            skill["enabled"] = overrides[skill["id"]]
        result.append(skill)

    # User-created skills from markdown files
    try:
        from icecode.config.settings import ICECodeSettings
        cfg = ICECodeSettings()
        skills_dir = cfg.home_dir / "skills"
        if skills_dir.exists():
            for md_file in sorted(skills_dir.glob("**/*.md")):
                skill_id = md_file.stem
                if any(s["id"] == skill_id for s in result):
                    continue
                result.append({
                    "id": skill_id,
                    "name": skill_id.replace("_", " ").title(),
                    "description": f"Custom skill from {md_file.name}",
                    "version": "1.0.0",
                    "enabled": overrides.get(skill_id, True),
                    "builtin": False,
                    "tools": [],
                    "tags": ["custom"],
                    "path": str(md_file),
                })
    except Exception:
        pass

    return result


# ── SKILL.md library ─────────────────────────────────────────────────────────

def _parse_skill_md(path: Path) -> dict:
    """Parse a SKILL.md file and return metadata + content."""
    try:
        txt = path.read_text(errors="ignore")
    except Exception:
        return {}
    name = desc = author = version = ""
    tags: List[str] = []
    # parse YAML frontmatter
    m = re.match(r"^---\n(.*?)\n---\n?", txt, re.DOTALL)
    if m:
        fm = m.group(1)
        nm = re.search(r"^name:\s*(.+)", fm, re.MULTILINE)
        dm = re.search(r"^description:\s*[\"']?(.*?)[\"']?\s*$", fm, re.MULTILINE)
        am = re.search(r"^author:\s*(.+)", fm, re.MULTILINE)
        vm = re.search(r"^version:\s*(.+)", fm, re.MULTILINE)
        tm = re.search(r"tags:\s*\[([^\]]+)\]", fm)
        name    = nm.group(1).strip() if nm else ""
        desc    = dm.group(1).strip().strip('"\'') if dm else ""
        author  = am.group(1).strip() if am else ""
        version = vm.group(1).strip() if vm else "1.0.0"
        if tm:
            tags = [t.strip().strip('"\'') for t in tm.group(1).split(",")]
        body = txt[m.end():]
    else:
        body = txt

    # derive skill_id from directory name
    skill_id   = path.parent.name
    # category = parent of parent relative to skills root
    parts = path.parts
    try:
        idx = parts.index("skills")
        tier     = parts[idx + 1] if idx + 1 < len(parts) else ""   # builtin/optional
        category = parts[idx + 2] if idx + 2 < len(parts) else ""   # software-development/…
    except ValueError:
        tier = category = ""

    return {
        "id":          f"{tier}/{category}/{skill_id}",
        "slug":        skill_id,
        "name":        name or skill_id.replace("-", " ").title(),
        "description": desc,
        "category":    category,
        "tier":        tier,          # "builtin" | "optional"
        "tags":        tags,
        "author":      author,
        "version":     version,
        "path":        str(path),
        "content_size": len(body),
    }


_LIBRARY_CACHE: Optional[List[dict]] = None

def _load_library(force: bool = False) -> List[dict]:
    """Scan all SKILL.md files and return parsed list (cached)."""
    global _LIBRARY_CACHE
    if _LIBRARY_CACHE is not None and not force:
        return _LIBRARY_CACHE
    skills = []
    if _SKILLS_ROOT.exists():
        for md in sorted(_SKILLS_ROOT.rglob("SKILL.md")):
            parsed = _parse_skill_md(md)
            if parsed:
                skills.append(parsed)
    _LIBRARY_CACHE = skills
    return skills


def load_skill_content(skill_id_or_slug: str) -> str:
    """Return full SKILL.md body text for a skill (without frontmatter).
    Accepts full id like 'builtin/software-development/tdd' or just slug 'tdd'."""
    library = _load_library()
    skill = None
    for s in library:
        if s["id"] == skill_id_or_slug or s["slug"] == skill_id_or_slug:
            skill = s
            break
    if not skill:
        return ""
    try:
        txt = Path(skill["path"]).read_text(errors="ignore")
        m = re.match(r"^---\n.*?\n---\n?", txt, re.DOTALL)
        return txt[m.end():].strip() if m else txt.strip()
    except Exception:
        return ""


# ── Auto-skill detection ─────────────────────────────────────────────────────

# keyword → skill slugs mapping for high-precision fast matching
_KEYWORD_MAP: dict = {
    # software development
    "test": ["test-driven-development", "systematic-debugging"],
    "tdd": ["test-driven-development"],
    "debug": ["systematic-debugging", "python-debugpy", "node-inspect-debugger"],
    "debugging": ["systematic-debugging"],
    "git": ["github-pr-workflow", "github-auth", "github-issues", "codebase-inspection"],
    "github": ["github-pr-workflow", "github-auth", "github-issues", "github-code-review"],
    "pull request": ["github-pr-workflow", "requesting-code-review"],
    "pr": ["github-pr-workflow", "requesting-code-review"],
    "code review": ["github-code-review", "requesting-code-review"],
    "plan": ["plan", "writing-plans"],
    "refactor": ["test-driven-development", "systematic-debugging"],
    "docker": ["docker-management"],
    "container": ["docker-management"],
    "deploy": ["docker-management", "watchers"],
    "ci": ["github-pr-workflow"],
    "pipeline": ["kanban-orchestrator", "kanban-worker"],
    # research
    "research": ["blogwatcher", "domain-intel", "llm-wiki"],
    "paper": ["research-paper-writing", "arxiv"],
    "arxiv": ["arxiv"],
    "academic": ["arxiv", "research-paper-writing"],
    "article": ["arxiv", "blogwatcher"],
    "literature": ["arxiv", "research-paper-writing"],
    # data
    "data": ["jupyter-live-kernel"],
    "jupyter": ["jupyter-live-kernel"],
    "notebook": ["jupyter-live-kernel"],
    "csv": ["jupyter-live-kernel"],
    "pandas": ["jupyter-live-kernel"],
    "chart": ["jupyter-live-kernel"],
    "plot": ["jupyter-live-kernel"],
    "analysis": ["jupyter-live-kernel"],
    # ml / ai
    "train": ["trl-fine-tuning", "axolotl", "unsloth"],
    "fine-tune": ["trl-fine-tuning", "axolotl", "unsloth"],
    "finetune": ["trl-fine-tuning", "unsloth"],
    "lora": ["trl-fine-tuning", "unsloth"],
    "vllm": ["vllm"],
    "llama": ["llama-cpp"],
    "embedding": ["faiss", "chroma"],
    "vector": ["faiss", "chroma"],
    "rag": ["faiss", "chroma"],
    "faiss": ["faiss"],
    "chroma": ["chroma"],
    "clip": ["clip"],
    # creative
    "image": ["comfyui", "clip"],
    "generate image": ["comfyui"],
    "comfyui": ["comfyui"],
    "video": ["ascii-video", "manim-video", "youtube-content"],
    "animation": ["manim-video", "ascii-video"],
    "diagram": ["architecture-diagram", "concept-diagrams"],
    "ascii": ["ascii-art", "ascii-video"],
    "sketch": ["sketch"],
    "comic": ["baoyu-comic"],
    "meme": ["meme-generation"],
    "music": ["spotify"],
    "gif": ["gif-search"],
    # productivity
    "google": ["google-workspace"],
    "spreadsheet": ["google-workspace", "excel-author"],
    "email": ["himalaya", "agentmail"],
    "calendar": ["google-workspace"],
    "obsidian": ["obsidian"],
    "notion": ["canvas"],
    "airtable": ["airtable"],
    "linear": ["linear"],
    "shopify": ["shopify"],
    # finance
    "finance": ["dcf-model", "comps-analysis", "3-statement-model"],
    "stock": ["dcf-model", "comps-analysis"],
    "valuation": ["dcf-model", "lbo-model"],
    "excel": ["excel-author"],
    "financial model": ["dcf-model", "3-statement-model"],
    # security
    "security": ["oss-forensics", "1password"],
    "vulnerability": ["oss-forensics"],
    "osint": ["sherlock", "domain-intel"],
    "password": ["1password"],
    # blockchain
    "blockchain": ["evm", "solana"],
    "crypto": ["evm", "solana", "hyperliquid"],
    "solana": ["solana"],
    "ethereum": ["evm"],
    # health
    "fitness": ["fitness-nutrition"],
    "nutrition": ["fitness-nutrition"],
    "workout": ["fitness-nutrition"],
    # mcp
    "mcp": ["fastmcp", "native-mcp", "mcporter"],
    "mcp server": ["fastmcp", "native-mcp"],
    # social / media
    "youtube": ["youtube-content"],
    "spotify": ["spotify"],
    "twitter": ["xurl"],
    "x.com": ["xurl"],
    # smart home
    "hue": ["openhue"],
    "smart home": ["openhue"],
    "lights": ["openhue"],
    # devops misc
    "cron": ["watchers"],
    "monitor": ["watchers"],
    "scheduler": ["watchers"],
    # web
    "web scrape": ["page-agent"],
    "scrape": ["page-agent"],
    "crawl": ["page-agent"],
    "web page": ["page-agent"],
    # agents
    "agent": ["hermes-agent", "claude-code", "codex"],
    "subagent": ["hermes-agent"],
    "codex": ["codex"],
    "claude": ["claude-code"],
}


def auto_detect_skills(message: str, limit: int = 5) -> List[str]:
    """Score all library skills against a message and return top-N slugs.

    Two-pass approach:
    1. Fast keyword/phrase map for high-confidence hits
    2. TF-style scoring against skill name + description + tags for coverage
    """
    library = _load_library()
    slug_index = {s["slug"]: s for s in library}
    msg_lower = message.lower()
    msg_words = set(re.findall(r"[a-z]{3,}", msg_lower))

    scores: dict[str, float] = {}

    # Pass 1 — keyword map (high precision)
    for phrase, slugs in _KEYWORD_MAP.items():
        if phrase in msg_lower:
            for slug in slugs:
                scores[slug] = scores.get(slug, 0) + 5.0

    # Pass 2 — TF scoring against skill metadata
    for skill in library:
        slug = skill["slug"]
        score = scores.get(slug, 0.0)

        # skill name words
        for w in re.findall(r"[a-z]{3,}", skill["name"].lower()):
            if w in msg_words:
                score += 3.0

        # category match
        cat_words = re.findall(r"[a-z]{3,}", skill["category"].replace("-", " "))
        for w in cat_words:
            if w in msg_words:
                score += 2.0

        # tags
        for tag in skill["tags"]:
            if tag.lower() in msg_lower:
                score += 2.5
            elif any(w in msg_words for w in re.findall(r"[a-z]{3,}", tag.lower())):
                score += 1.0

        # description words (lower weight)
        for w in re.findall(r"[a-z]{4,}", (skill["description"] or "").lower()):
            if w in msg_words:
                score += 0.5

        if score > 0:
            scores[slug] = score

    # Sort and return top-N that actually exist in library
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    result = []
    for slug, _ in ranked:
        if slug in slug_index:
            result.append(slug)
        if len(result) >= limit:
            break
    return result


@router.get("/library")
async def list_skill_library(category: str = "", tier: str = "", q: str = ""):
    """Return all SKILL.md skills with optional filter by category, tier, or search query."""
    library = _load_library()
    if tier:
        library = [s for s in library if s["tier"] == tier]
    if category:
        library = [s for s in library if s["category"] == category]
    if q:
        ql = q.lower()
        library = [s for s in library if
                   ql in s["name"].lower() or
                   ql in s["description"].lower() or
                   any(ql in t.lower() for t in s["tags"]) or
                   ql in s["category"].lower()]
    return library


@router.get("/library/categories")
async def list_categories():
    """Return distinct categories with skill counts."""
    from collections import Counter
    library = _load_library()
    counts = Counter(s["category"] for s in library)
    return [{"category": k, "count": v} for k, v in sorted(counts.items())]


@router.get("/library/{skill_id:path}/content")
async def get_skill_content(skill_id: str):
    """Return full SKILL.md text for agent injection."""
    content = load_skill_content(skill_id)
    if not content:
        raise HTTPException(404, f"Skill not found: {skill_id}")
    return {"skill_id": skill_id, "content": content}


@router.post("/library/refresh")
async def refresh_library():
    """Rescan SKILL.md files and clear cache."""
    skills = _load_library(force=True)
    return {"ok": True, "count": len(skills)}


class AutoDetectRequest(BaseModel):
    message: str
    limit: int = 5


@router.post("/auto-detect")
async def auto_detect(req: AutoDetectRequest):
    """Analyze a message and return the most relevant skill slugs."""
    slugs = auto_detect_skills(req.message, limit=req.limit)
    library = _load_library()
    slug_index = {s["slug"]: s for s in library}
    skills_info = [
        {"slug": s, "name": slug_index[s]["name"], "category": slug_index[s]["category"]}
        for s in slugs if s in slug_index
    ]
    return {"detected": slugs, "skills": skills_info, "count": len(slugs)}


@router.get("/")
@router.get("")
async def list_skills():
    return _build_skill_list()


@router.get("/stats")
async def skill_stats():
    skills = _build_skill_list()
    return {
        "total": len(skills),
        "enabled": sum(1 for s in skills if s.get("enabled")),
        "builtin": sum(1 for s in skills if s.get("builtin")),
        "custom": sum(1 for s in skills if not s.get("builtin")),
    }


@router.put("/{skill_id}/toggle")
async def toggle_skill(skill_id: str, req: SkillToggle):
    overrides = _load_overrides()
    overrides[skill_id] = req.enabled
    _save_overrides(overrides)
    return {"ok": True, "skill_id": skill_id, "enabled": req.enabled}


@router.post("/discover")
async def discover_skills():
    """Scan for skills and return the full list."""
    skills = _build_skill_list()
    return {
        "ok": True,
        "count": len(skills),
        "discovered": [s["id"] for s in skills],
        "message": f"Found {len(skills)} skills ({sum(1 for s in skills if s.get('builtin'))} built-in)",
    }


@router.post("/")
async def create_skill(body: dict):
    """Create a custom skill (saves as markdown to ~/.icecode/skills/)."""
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    skills_dir = cfg.home_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "name is required")

    skill_id = name.lower().replace(" ", "_")
    content = f"# {name}\n\n{body.get('description', '')}\n\n## Tools\n{', '.join(body.get('tools', []))}\n"
    (skills_dir / f"{skill_id}.md").write_text(content)

    return {"ok": True, "id": skill_id, "name": name}


# ── Curator ──────────────────────────────────────────────────────────────────

def _curator_file():
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    return cfg.home_dir / "data" / "skills_curator.json"


def _load_curator() -> dict:
    f = _curator_file()
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return {"pinned": [], "archived": [], "usage_counts": {}}


def _save_curator(data: dict):
    f = _curator_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2))


@router.get("/curator/status")
async def curator_status():
    """Skill curator status — usage, pinned, archived."""
    curator = _load_curator()
    skills = _build_skill_list()
    return {
        "total_skills": len(skills),
        "pinned": curator.get("pinned", []),
        "archived": curator.get("archived", []),
        "usage_counts": curator.get("usage_counts", {}),
        "enabled": True,
    }


@router.post("/curator/pin/{skill_id}")
async def pin_skill(skill_id: str):
    """Pin a skill so curator never archives it."""
    curator = _load_curator()
    if skill_id not in curator["pinned"]:
        curator["pinned"].append(skill_id)
    if skill_id in curator.get("archived", []):
        curator["archived"].remove(skill_id)
    _save_curator(curator)
    return {"ok": True, "pinned": skill_id}


@router.post("/curator/unpin/{skill_id}")
async def unpin_skill(skill_id: str):
    curator = _load_curator()
    curator["pinned"] = [s for s in curator.get("pinned", []) if s != skill_id]
    _save_curator(curator)
    return {"ok": True, "unpinned": skill_id}


@router.post("/curator/archive/{skill_id}")
async def archive_skill(skill_id: str):
    """Archive a skill (disables it and marks for review)."""
    curator = _load_curator()
    overrides = _load_overrides()

    if skill_id not in curator.get("archived", []):
        curator.setdefault("archived", []).append(skill_id)
    overrides[skill_id] = False  # disable
    _save_curator(curator)
    _save_overrides(overrides)
    return {"ok": True, "archived": skill_id}


@router.post("/curator/restore/{skill_id}")
async def restore_skill(skill_id: str):
    """Restore an archived skill."""
    curator = _load_curator()
    overrides = _load_overrides()
    curator["archived"] = [s for s in curator.get("archived", []) if s != skill_id]
    overrides[skill_id] = True
    _save_curator(curator)
    _save_overrides(overrides)
    return {"ok": True, "restored": skill_id}


@router.post("/curator/run")
async def curator_run():
    """Run curator: report usage stats and suggest which to archive."""
    curator = _load_curator()
    skills = _build_skill_list()
    pinned = set(curator.get("pinned", []))
    archived = set(curator.get("archived", []))
    usage = curator.get("usage_counts", {})

    suggestions = []
    for s in skills:
        sid = s["id"]
        if sid in pinned or sid in archived or s.get("builtin"):
            continue
        if usage.get(sid, 0) == 0:
            suggestions.append({"skill_id": sid, "reason": "never used", "action": "archive"})

    return {
        "ok": True,
        "skills_reviewed": len(skills),
        "archive_suggestions": suggestions,
        "pinned_count": len(pinned),
        "archived_count": len(archived),
    }
