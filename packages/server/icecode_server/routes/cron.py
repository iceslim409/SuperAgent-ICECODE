"""
ICECODE Cron API
Scheduled tasks with delivery to any platform
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parents[4] / "core"))

router = APIRouter(prefix="/api/cron", tags=["cron"])


class CronJobCreate(BaseModel):
    name: str
    schedule: str  # cron expression, "every 5m", "daily at 9am", ISO datetime
    command: str
    model: Optional[str] = None
    provider: Optional[str] = None
    delivery_channel: Optional[str] = None
    enabled: bool = True


class CronJobUpdate(BaseModel):
    name: Optional[str] = None
    schedule: Optional[str] = None
    command: Optional[str] = None
    enabled: Optional[bool] = None


def _load_jobs():
    import json
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    f = cfg.home_dir / "data" / "cron_jobs.json"
    if f.exists():
        return json.loads(f.read_text())
    return []


def _save_jobs(jobs):
    import json
    from icecode.config.settings import ICECodeSettings
    cfg = ICECodeSettings()
    f = cfg.home_dir / "data" / "cron_jobs.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(jobs, indent=2))


@router.get("/")
async def list_jobs():
    return _load_jobs()


@router.post("/")
async def create_job(req: CronJobCreate):
    jobs = _load_jobs()
    job = {
        "id": f"cron_{uuid.uuid4().hex[:8]}",
        "name": req.name,
        "schedule": req.schedule,
        "command": req.command,
        "model": req.model,
        "provider": req.provider,
        "delivery_channel": req.delivery_channel,
        "enabled": req.enabled,
        "last_run": None,
        "next_run": None,
        "run_count": 0,
    }
    jobs.append(job)
    _save_jobs(jobs)

    # Register with scheduler
    try:
        from icecode.cron.scheduler import CronScheduler
        scheduler = CronScheduler()
        scheduler.add_job(job)
    except Exception:
        pass

    return job


@router.put("/{job_id}")
async def update_job(job_id: str, req: CronJobUpdate):
    jobs = _load_jobs()
    for job in jobs:
        if job["id"] == job_id:
            if req.name is not None:
                job["name"] = req.name
            if req.schedule is not None:
                job["schedule"] = req.schedule
            if req.command is not None:
                job["command"] = req.command
            if req.enabled is not None:
                job["enabled"] = req.enabled
            _save_jobs(jobs)
            return job
    raise HTTPException(404, "Job not found")


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    jobs = _load_jobs()
    jobs = [j for j in jobs if j["id"] != job_id]
    _save_jobs(jobs)
    return {"ok": True}


@router.post("/{job_id}/trigger")
async def trigger_job(job_id: str):
    """Manually trigger a cron job."""
    jobs = _load_jobs()
    for job in jobs:
        if job["id"] == job_id:
            try:
                from icecode.cron.scheduler import CronScheduler
                scheduler = CronScheduler()
                result = await scheduler.run_job(job)
                return {"ok": True, "result": result}
            except Exception as e:
                return {"ok": False, "error": str(e)}
    raise HTTPException(404, "Job not found")
