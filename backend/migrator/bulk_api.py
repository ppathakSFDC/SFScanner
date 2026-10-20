"""
Salesforce Bulk API 2.0 wrapper.

Lifecycle:
  1. create_ingest_job()  → job_id
  2. upload_job_data()    → stream CSV batches
  3. close_job()          → tell Salesforce processing can start
  4. wait_for_completion()→ poll until JobComplete / Failed
  5. get_successful_results() / get_failed_results()
  6. (optional) abort_job() or create a delete job for rollback
"""

import asyncio
import csv
import io
import httpx
from typing import Optional


BATCH_SIZE_RECORDS = 10_000   # records per CSV batch


def _sf_error(resp) -> str:
    """Extract Salesforce error message from a failed Bulk API response."""
    try:
        body = resp.json()
        if isinstance(body, list) and body:
            return "; ".join(
                f"{e.get('errorCode', 'ERROR')}: {e.get('message', '')}" for e in body
            )
        return str(body)
    except Exception:
        return resp.text[:400] or f"HTTP {resp.status_code}"


class BulkAPI2:
    def __init__(self, access_token: str, instance_url: str, api_version: str = "v62.0", log_fn=None):
        self.access_token = access_token
        self.instance_url = instance_url.rstrip("/")
        self.api_version = api_version
        self._base = f"{instance_url}/services/data/{api_version}/jobs/ingest"
        self._log = log_fn or (lambda msg: None)

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def create_ingest_job(
        self,
        object_name: str,
        operation: str,                        # upsert | insert | delete
        external_id_field: Optional[str] = None,
        line_ending: str = "LF",
    ) -> str:
        payload: dict = {
            "object": object_name,
            "operation": operation,
            "contentType": "CSV",
            "lineEnding": line_ending,
        }
        if operation == "upsert" and external_id_field:
            payload["externalIdFieldName"] = external_id_field

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(self._base, json=payload, headers=self._headers)
            if not resp.is_success:
                raise Exception(f"Bulk API error ({resp.status_code}): {_sf_error(resp)}")
            return resp.json()["id"]

    async def upload_job_data(self, job_id: str, csv_data: str):
        """Upload a CSV string as a batch. For large datasets call this multiple times."""
        url = f"{self._base}/{job_id}/batches"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "text/csv",
        }
        self._log(f"    → Job {job_id}: uploading CSV")
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.put(url, content=csv_data.encode("utf-8"), headers=headers)
            if not resp.is_success:
                raise Exception(f"Bulk API error ({resp.status_code}): {_sf_error(resp)}")

    async def close_job(self, job_id: str):
        """Signal that all data has been uploaded; Salesforce starts processing."""
        url = f"{self._base}/{job_id}"
        self._log(f"    → Job {job_id}: marking UploadComplete")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                url, json={"state": "UploadComplete"}, headers=self._headers
            )
            if not resp.is_success:
                raise Exception(f"Bulk API error ({resp.status_code}): {_sf_error(resp)}")

    async def abort_job(self, job_id: str):
        url = f"{self._base}/{job_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            await client.patch(url, json={"state": "Aborted"}, headers=self._headers)

    async def get_job_status(self, job_id: str) -> dict:
        url = f"{self._base}/{job_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers)
            if not resp.is_success:
                raise Exception(f"Bulk API error ({resp.status_code}): {_sf_error(resp)}")
            return resp.json()

    async def wait_for_completion(self, job_id: str, poll_interval: float = 3.0, timeout: float = 600.0) -> str:
        """Poll until the job reaches a terminal state. Returns the final state string."""
        elapsed = 0.0
        _transient_retries = 0
        while elapsed < timeout:
            try:
                status = await self.get_job_status(job_id)
                _transient_retries = 0
            except Exception as exc:
                _transient_retries += 1
                if _transient_retries > 5:
                    raise
                backoff = min(2 ** _transient_retries, 30)
                self._log(f"    → {job_id}: transient poll error ({exc}), retry in {backoff}s")
                await asyncio.sleep(backoff)
                elapsed += backoff
                continue
            state = status.get("state", "")
            processed = status.get("numberRecordsProcessed", 0)
            failed = status.get("numberRecordsFailed", 0)
            self._log(f"    → {job_id}: state={state}, processed={processed}, failed={failed}")
            if state in ("JobComplete", "Failed", "Aborted"):
                self._log(f"    → Job {job_id}: completed with state={state}")
                return state
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f"Bulk job {job_id} did not complete within {timeout}s")

    async def _get_results_csv(self, job_id: str, result_type: str) -> list[dict]:
        """result_type: successfulResults | failedResults | unprocessedrecords"""
        url = f"{self._base}/{job_id}/{result_type}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "text/csv",
        }
        for attempt in range(4):
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(url, headers=headers)
            if resp.status_code == 404 or not resp.text.strip():
                return []
            if resp.status_code in (429, 503) and attempt < 3:
                backoff = 2 ** (attempt + 1)
                self._log(f"    → {result_type} {resp.status_code} retry in {backoff}s")
                await asyncio.sleep(backoff)
                continue
            if not resp.is_success:
                raise Exception(f"Bulk API error ({resp.status_code}): {_sf_error(resp)}")
            reader = csv.DictReader(io.StringIO(resp.text))
            return list(reader)
        raise Exception(f"Bulk API {result_type} failed after retries")

    async def get_successful_results(self, job_id: str) -> list[dict]:
        return await self._get_results_csv(job_id, "successfulResults")

    async def get_failed_results(self, job_id: str) -> list[dict]:
        return await self._get_results_csv(job_id, "failedResults")

    async def get_unprocessed_records(self, job_id: str) -> list[dict]:
        return await self._get_results_csv(job_id, "unprocessedrecords")


# ──────────────────────────────────────────────────────────────────────────────
# CSV helpers
# ──────────────────────────────────────────────────────────────────────────────

def records_to_csv(records: list[dict], fields: list[str]) -> str:
    """Serialise a list of record dicts to a Bulk API 2.0 compatible CSV string."""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=fields,
        extrasaction="ignore",
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for rec in records:
        row = {f: ("" if rec.get(f) is None else rec[f]) for f in fields}
        writer.writerow(row)
    return buf.getvalue()


def chunk_records(records: list, batch_size: int = BATCH_SIZE_RECORDS):
    """Yield successive batches of records."""
    for i in range(0, len(records), batch_size):
        yield records[i: i + batch_size]
