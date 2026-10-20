import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

_PERSIST_DIR = os.path.expanduser("~/.sf-scanner")
_JOBS_FILE = os.path.join(_PERSIST_DIR, "migration_jobs.json")


@dataclass
class ObjectMigrationResult:
    object_name: str
    status: str = "waiting"        # waiting | running | done | done_with_errors | failed | skipped
    queried: int = 0
    inserted: int = 0
    updated: int = 0
    failed: int = 0
    skipped_dry_run: int = 0       # records that would be written in a real run
    error: str = ""
    error_categories: dict = field(default_factory=dict)  # error_code → count
    inserted_ids: list = field(default_factory=list)  # target IDs for rollback


@dataclass
class MigrationJob:
    job_id: str
    source_url: str
    target_url: str
    mode: str                      # upsert | insert
    selected_objects: list
    dep_order: list
    migration_owner_id: str = ""
    status: str = "running"        # running | completed | failed | rolling_back | rolled_back
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    current_object: str = ""
    progress_pct: int = 0
    message: str = "Initializing…"
    object_results: dict = field(default_factory=dict)   # object_name → ObjectMigrationResult
    object_filters: dict = field(default_factory=dict)  # object_name → WHERE clause string
    product_scoped: bool = False
    total_queried: int = 0
    total_inserted: int = 0
    total_updated: int = 0
    total_failed: int = 0
    error: str = ""
    log_path: str = ""
    cancelled: bool = False
    dry_run: bool = False           # validate-only; no records are written to target
    failure_threshold_pct: int = 0  # abort when failed% exceeds this (0 = fail on any error)


# In-memory stores (mirrors the scan pattern in store.py)
_jobs: dict[str, MigrationJob] = {}
_job_progress: dict[str, dict] = {}
_job_logs: dict[str, list] = {}  # job_id → list of log line strings


def append_log(job_id: str, line: str):
    if job_id not in _job_logs:
        _job_logs[job_id] = []
    _job_logs[job_id].append(line)


def get_log_delta(job_id: str, offset: int) -> tuple:
    lines = _job_logs.get(job_id, [])
    return lines[offset:], len(lines)


def _save_jobs():
    """Persist terminal jobs and jobs with inserts needed for rollback."""
    try:
        os.makedirs(_PERSIST_DIR, exist_ok=True)
        data = {}
        for job_id, job in _jobs.items():
            if job.status in ("completed", "failed", "stopped", "rolled_back", "rolling_back") or any(
                result.inserted_ids for result in job.object_results.values()
            ):
                job_dict = asdict(job)
                data[job_id] = job_dict
        tmp = _JOBS_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, default=str)
        os.replace(tmp, _JOBS_FILE)
    except Exception:
        pass


def _load_jobs():
    """Load previously persisted jobs from disk at startup."""
    try:
        if not os.path.exists(_JOBS_FILE):
            return
        with open(_JOBS_FILE) as f:
            data = json.load(f)
        for job_id, job_dict in data.items():
            raw_results = job_dict.pop("object_results", {})
            known_job_fields = {f for f in MigrationJob.__dataclass_fields__}
            safe_dict = {k: v for k, v in job_dict.items() if k in known_job_fields}
            job = MigrationJob(**safe_dict)
            if job.status == 'running':
                job.status = 'stopped'
                job.error = 'Migration interrupted by server restart; tracked inserts can be rolled back.'
                job.completed_at = datetime.now(timezone.utc).isoformat()
            known_res_fields = {f for f in ObjectMigrationResult.__dataclass_fields__}
            for k, v in raw_results.items():
                job.object_results[k] = ObjectMigrationResult(
                    **{kk: vv for kk, vv in v.items() if kk in known_res_fields}
                )
            _jobs[job_id] = job
    except Exception:
        pass


# Load persisted jobs at import time
_load_jobs()


def get_job(job_id: str) -> Optional[MigrationJob]:
    return _jobs.get(job_id)


def cancel_job(job_id: str) -> bool:
    """Mark a running job for cancellation. Returns True if the job existed and was running."""
    job = _jobs.get(job_id)
    if not job or job.status not in ("running",):
        return False
    job.cancelled = True
    return True


def set_job(job: MigrationJob):
    _jobs[job.job_id] = job
    if job.status in ("completed", "failed", "stopped", "rolled_back", "rolling_back") or any(
        result.inserted_ids for result in job.object_results.values()
    ):
        _save_jobs()


def get_progress(job_id: str) -> dict:
    return _job_progress.get(job_id, {})


def set_progress(job_id: str, pct: int, message: str, status: str = "running",
                 current_object: str = "", object_results: dict = None):
    _job_progress[job_id] = {
        "status": status,
        "progress_pct": pct,
        "message": message,
        "current_object": current_object,
        "object_results": {
            k: {
                "object_name": v.object_name,
                "status": v.status,
                "queried": v.queried,
                "inserted": v.inserted,
                "updated": v.updated,
                "failed": v.failed,
                "skipped_dry_run": v.skipped_dry_run,
                "error": v.error,
                "error_categories": v.error_categories,
            }
            for k, v in (object_results or {}).items()
        },
    }
