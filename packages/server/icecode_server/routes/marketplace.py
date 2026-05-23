"""
ICECODE Agent Marketplace — share and import skills between users.
Skills are stored locally (~/.icecode/marketplace/) and exported as base64 codes.
"""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

_MARKET_DIR = Path(os.getenv("ICECODE_HOME", str(Path.home() / ".icecode"))) / "marketplace"
_MARKET_DIR.mkdir(parents=True, exist_ok=True)

# Built-in featured skills for the marketplace
_FEATURED = [
    {
        "id": "code_reviewer",
        "name": "Code Reviewer",
        "description": "Analyzes code, finds bugs, suggests refactoring. Uses static analysis skills.",
        "author": "ICECODE",
        "tags": ["code", "review", "debugging"],
        "downloads": 142,
        "rating": 4.8,
        "tools": ["read_file", "code_search", "run_terminal"],
        "system_extra": "You are an expert code reviewer. Focus on: correctness, security, performance, readability. Be specific with line numbers and actionable suggestions.",
    },
    {
        "id": "research_writer",
        "name": "Research & Write",
        "description": "Searches the web, synthesizes information, and writes structured articles or reports.",
        "author": "ICECODE",
        "tags": ["research", "writing", "web"],
        "downloads": 98,
        "rating": 4.6,
        "tools": ["web_search", "web_extract", "write_file"],
        "system_extra": "You are a research assistant. Search thoroughly, verify facts from multiple sources, then write a well-structured document with citations.",
    },
    {
        "id": "devops_helper",
        "name": "DevOps Helper",
        "description": "Docker, CI/CD, deployment, monitoring. Expert in infrastructure and automation.",
        "author": "ICECODE",
        "tags": ["devops", "docker", "ci-cd"],
        "downloads": 87,
        "rating": 4.7,
        "tools": ["run_terminal", "read_file", "write_file", "http_request"],
        "system_extra": "You are a DevOps engineer. Help with containers, pipelines, servers. Always explain what each command does. Prefer idempotent solutions.",
    },
    {
        "id": "data_analyst",
        "name": "Data Analyst",
        "description": "Analyzes CSV/JSON files, produces statistics, visualizations and insights.",
        "author": "ICECODE",
        "tags": ["data", "analysis", "csv"],
        "downloads": 76,
        "rating": 4.5,
        "tools": ["read_file", "execute_code", "write_file"],
        "system_extra": "You are a data analyst. Load data files, compute statistics, find patterns, and explain findings in plain language. Use Python for analysis.",
    },
    {
        "id": "security_auditor",
        "name": "Security Auditor",
        "description": "Audits code and configurations for OWASP vulnerabilities and known CVEs.",
        "author": "ICECODE",
        "tags": ["security", "audit", "owasp"],
        "downloads": 64,
        "rating": 4.9,
        "tools": ["read_file", "code_search", "web_search"],
        "system_extra": "You are a security auditor. Check for OWASP Top 10, hardcoded secrets, injection vulnerabilities, insecure dependencies. Be thorough and specific.",
    },
    {
        "id": "git_assistant",
        "name": "Git Assistant",
        "description": "Commit messages, PR descriptions, code diffs, branch management.",
        "author": "ICECODE",
        "tags": ["git", "version-control"],
        "downloads": 58,
        "rating": 4.4,
        "tools": ["git_command", "read_file", "run_terminal"],
        "system_extra": "You are a Git expert. Help with commits, branches, merges, and history. Write clear conventional commit messages. Always explain git operations before running them.",
    },
]


class PublishRequest(BaseModel):
    skill: Dict[str, Any]


class ImportRequest(BaseModel):
    code: str


def _encode_skill(skill: Dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(skill, ensure_ascii=False).encode()).decode()


def _decode_skill(code: str) -> Dict:
    return json.loads(base64.urlsafe_b64decode(code.encode()).decode())


@router.get("/skills")
async def list_skills(search: str = ""):
    """List marketplace skills — featured + locally published."""
    skills = list(_FEATURED)

    # Add locally published skills
    for f in sorted(_MARKET_DIR.glob("*.json")):
        try:
            skills.append(json.loads(f.read_text()))
        except Exception:
            pass

    if search:
        q = search.lower()
        skills = [s for s in skills if q in s.get("name", "").lower()
                  or q in s.get("description", "").lower()
                  or any(q in t for t in s.get("tags", []))]

    return skills


@router.post("/publish")
async def publish_skill(req: PublishRequest):
    """Encode a skill as a shareable base64 code."""
    skill = req.skill
    if not skill.get("name"):
        raise HTTPException(400, "Skill must have a name")

    skill.setdefault("id", skill["name"].lower().replace(" ", "_"))
    skill.setdefault("author", "community")
    skill.setdefault("downloads", 0)
    skill.setdefault("rating", 0)
    skill["published_at"] = int(time.time())

    code = _encode_skill(skill)

    # Save locally
    dest = _MARKET_DIR / f"{skill['id']}.json"
    dest.write_text(json.dumps(skill, ensure_ascii=False, indent=2))

    return {"code": code, "id": skill["id"], "share_url": f"?import={code}"}


@router.post("/import")
async def import_skill(req: ImportRequest):
    """Import a skill from a base64 code."""
    try:
        skill = _decode_skill(req.code)
    except Exception:
        raise HTTPException(400, "Invalid skill code")

    if not skill.get("name"):
        raise HTTPException(400, "Skill data is invalid — missing name")

    skill.setdefault("id", skill["name"].lower().replace(" ", "_"))
    skill["imported_at"] = int(time.time())

    dest = _MARKET_DIR / f"{skill['id']}.json"
    dest.write_text(json.dumps(skill, ensure_ascii=False, indent=2))

    # Also install into active skills directory
    try:
        _skills_dir = Path(os.getenv("ICECODE_HOME", str(Path.home() / ".icecode"))) / "skills"
        _skills_dir.mkdir(parents=True, exist_ok=True)
        skill_dest = _skills_dir / f"{skill['id']}.json"
        skill_dest.write_text(json.dumps(skill, ensure_ascii=False, indent=2))
    except Exception:
        pass

    return {"ok": True, "skill": skill}


@router.delete("/skills/{skill_id}")
async def delete_published_skill(skill_id: str):
    dest = _MARKET_DIR / f"{skill_id}.json"
    if dest.exists():
        dest.unlink()
        return {"ok": True}
    raise HTTPException(404, "Skill not found in local marketplace")
