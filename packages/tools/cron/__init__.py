"""Stub for cron module used by cronjob_tools."""
import json
from pathlib import Path
from typing import List, Dict

_CRON_FILE = Path.home() / ".icecode" / "data" / "cronjobs.json"

def load_jobs() -> List[Dict]:
    try:
        if _CRON_FILE.exists():
            return json.loads(_CRON_FILE.read_text())
    except Exception: pass
    return []

def save_jobs(jobs: List[Dict]) -> None:
    _CRON_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CRON_FILE.write_text(json.dumps(jobs, indent=2))

def add_job(job: Dict) -> Dict:
    jobs = load_jobs()
    jobs.append(job)
    save_jobs(jobs)
    return job

def remove_job(job_id: str) -> bool:
    jobs = load_jobs()
    new = [j for j in jobs if j.get("id") != job_id]
    if len(new) < len(jobs):
        save_jobs(new)
        return True
    return False

def list_jobs() -> List[Dict]: return load_jobs()
