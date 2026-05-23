"""Stub for cron.jobs — full API surface."""
import json, uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

_FILE = Path.home() / ".icecode" / "data" / "cronjobs.json"

def _load() -> List[Dict]:
    try:
        if _FILE.exists(): return json.loads(_FILE.read_text())
    except Exception: pass
    return []

def _save(jobs: List[Dict]) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(jobs, indent=2))

def parse_schedule(expr: str) -> Dict:
    return {"expression": expr, "valid": True}

def create_job(name: str, schedule: str, task: str, **kw) -> Dict:
    job = {"id": f"cron_{uuid.uuid4().hex[:8]}", "name": name,
           "schedule": schedule, "task": task, "enabled": True,
           "created_at": datetime.now().isoformat(), **kw}
    jobs = _load(); jobs.append(job); _save(jobs)
    return job

def get_job(job_id: str) -> Optional[Dict]:
    return next((j for j in _load() if j.get("id") == job_id), None)

def list_jobs() -> List[Dict]: return _load()

def update_job(job_id: str, **kw) -> Optional[Dict]:
    jobs = _load()
    for j in jobs:
        if j.get("id") == job_id:
            j.update(kw); j["updated_at"] = datetime.now().isoformat()
            _save(jobs); return j
    return None

def remove_job(job_id: str) -> bool:
    jobs = _load(); new = [j for j in jobs if j.get("id") != job_id]
    if len(new) < len(jobs): _save(new); return True
    return False

def pause_job(job_id: str) -> Optional[Dict]: return update_job(job_id, enabled=False)
def resume_job(job_id: str) -> Optional[Dict]: return update_job(job_id, enabled=True)
def trigger_job(job_id: str) -> Dict: return {"triggered": job_id, "status": "ok"}
