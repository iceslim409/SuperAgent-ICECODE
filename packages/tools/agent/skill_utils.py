"""Stub for agent.skill_utils."""
from pathlib import Path
from typing import List, Iterator, Optional

EXCLUDED_SKILL_DIRS: List[str] = []

def get_all_skills_dirs() -> List[Path]: return []
def get_external_skills_dirs() -> List[Path]: return []
def get_disabled_skill_names() -> List[str]: return []
def iter_skill_index_files() -> Iterator[Path]:
    return iter([])
def parse_frontmatter(text: str) -> dict: return {}
def is_valid_namespace(ns: str) -> bool: return True
def parse_qualified_name(name: str): return name, None
def skill_matches_platform(skill, platform: str = "") -> bool: return True
