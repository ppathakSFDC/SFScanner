import os
from pathlib import Path
from datetime import datetime, timezone

_LOG_DIR = Path(os.path.expanduser("~/.sf-scanner/logs"))


class MigrationLogger:
    def __init__(self, job_id: str):
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.path = _LOG_DIR / f"migration_{job_id}.log"
        self._f = self.path.open("w", encoding="utf-8")
        self._write("INFO", f"Job started job_id={job_id}")

    def _write(self, level: str, msg: str):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self._f.write(f"[{ts}] [{level}] {msg}\n")
        self._f.flush()

    def info(self, msg: str):
        self._write("INFO", msg)

    def warn(self, msg: str):
        self._write("WARN", msg)

    def error(self, msg: str):
        self._write("ERROR", msg)

    def object_start(self, obj: str):
        self._write("INFO", f"OBJECT_START object={obj}")

    def object_done(self, obj: str, queried: int, inserted: int, updated: int, failed: int, error: str = ""):
        self._write(
            "WARN" if failed or error else "INFO",
            f"OBJECT_DONE object={obj} queried={queried} inserted={inserted} updated={updated} failed={failed}"
            + (f" error={error!r}" if error else ""),
        )

    def bulk_job(self, obj: str, bulk_job_id: str, operation: str, records: int, successes: int, failures: int):
        level = "WARN" if failures else "INFO"
        self._write(level, f"BULK_JOB object={obj} bulk_job_id={bulk_job_id} op={operation} records={records} ok={successes} fail={failures}")

    def failed_records(self, obj: str, failures: list):
        for row in failures[:50]:  # cap log size
            sf_err = row.get("sf__Error", "")
            ref = row.get("sf__Id") or row.get("Id", "")
            self._write("ERROR", f"RECORD_FAIL object={obj} id={ref!r} error={sf_err!r}")

    def close(self, status: str):
        self._write("INFO", f"Job finished status={status}")
        self._f.close()
