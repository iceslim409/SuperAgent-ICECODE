"""Stub for agent.file_safety."""
from pathlib import Path
from typing import List, Optional

def get_read_block_error(path: str, task_id: str = "default") -> Optional[str]: return None
def get_write_block_error(path: str, task_id: str = "default") -> Optional[str]: return None
def build_write_denied_paths(home: Path) -> List[Path]: return []
def build_write_denied_prefixes(home: Path) -> List[str]: return []
def get_safe_write_root(task_id: str = "default") -> Optional[str]: return None
def is_write_denied(path: str, task_id: str = "default") -> bool: return False
def is_safe_path(path: str) -> bool: return True
