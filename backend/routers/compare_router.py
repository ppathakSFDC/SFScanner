"""Org-to-org comparison endpoint."""
import asyncio
from fastapi import APIRouter, Request, HTTPException
from ..auth.org_store import get_org
from ..salesforce.client import SalesforceClient

router = APIRouter(prefix="/compare", tags=["compare"])


def _session_id(request: Request) -> str:
    return request.session.get("_sid") or ""


async def _fetch_org_stats(token: str, url: str) -> dict:
    sf = SalesforceClient(token, url)
    stats: dict = {"instance_url": url, "error": None}

    async def safe(coro, default):
        try:
            return await coro
        except Exception:
            return default

    info = await safe(sf.get_org_info(), {})
    stats["org_name"] = info.get("Name", "")
    stats["org_id"] = info.get("Id", "")
    stats["edition"] = info.get("OrganizationType", "")

    apex = await safe(sf.tooling_query("SELECT COUNT() FROM ApexClass WHERE Status = 'Active'"), {"size": 0})
    stats["apex_classes"] = apex.get("size", 0) if isinstance(apex, dict) else 0

    flows = await safe(sf.query("SELECT COUNT() FROM Flow WHERE Status = 'Active'"), {"totalSize": 0})
    stats["active_flows"] = flows.get("totalSize", 0) if isinstance(flows, dict) else 0

    objs = await safe(
        sf.query("SELECT COUNT() FROM EntityDefinition WHERE IsCustomizable = true AND IsCustomSetting = false"),
        {"totalSize": 0}
    )
    stats["custom_objects"] = objs.get("totalSize", 0) if isinstance(objs, dict) else 0

    limits = await safe(sf.get_limits(), {})
    if limits:
        dl = limits.get("DataStorageMB", {})
        fl = limits.get("FileStorageMB", {})
        al = limits.get("DailyApiRequests", {})
        stats["data_storage_used_mb"] = dl.get("Max", 0) - dl.get("Remaining", dl.get("Max", 0))
        stats["data_storage_max_mb"] = dl.get("Max", 0)
        stats["file_storage_used_mb"] = fl.get("Max", 0) - fl.get("Remaining", fl.get("Max", 0))
        stats["file_storage_max_mb"] = fl.get("Max", 0)
        stats["api_calls_used"] = al.get("Max", 0) - al.get("Remaining", al.get("Max", 0))
        stats["api_calls_max"] = al.get("Max", 0)
    else:
        stats.update({
            "data_storage_used_mb": 0, "data_storage_max_mb": 0,
            "file_storage_used_mb": 0, "file_storage_max_mb": 0,
            "api_calls_used": 0, "api_calls_max": 0,
        })

    users = await safe(sf.query("SELECT COUNT() FROM User WHERE IsActive = true"), {"totalSize": 0})
    stats["active_users"] = users.get("totalSize", 0) if isinstance(users, dict) else 0

    cov = await safe(sf.tooling_query(
        "SELECT SUM(NumLinesCovered) covered, SUM(NumLinesUncovered) uncovered "
        "FROM ApexCodeCoverageAggregate"
    ), {})
    if cov and isinstance(cov, dict):
        recs = cov.get("records", [{}])
        c = int((recs[0].get("covered") or 0)) if recs else 0
        u = int((recs[0].get("uncovered") or 0)) if recs else 0
        stats["apex_coverage_pct"] = round(c / (c + u) * 100) if (c + u) > 0 else 0
    else:
        stats["apex_coverage_pct"] = 0

    return stats


@router.post("/orgs")
async def compare_orgs(request: Request, body: dict):
    sid = _session_id(request)
    if not sid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    key_a = body.get("org_key_a")
    key_b = body.get("org_key_b")
    if not key_a or not key_b:
        raise HTTPException(status_code=400, detail="org_key_a and org_key_b are required")

    entry_a = get_org(sid, key_a)
    entry_b = get_org(sid, key_b)

    if not entry_a:
        raise HTTPException(status_code=404, detail=f"Org {key_a} not found")
    if not entry_b:
        raise HTTPException(status_code=404, detail=f"Org {key_b} not found")

    stats_a, stats_b = await asyncio.gather(
        _fetch_org_stats(entry_a["access_token"], entry_a["instance_url"]),
        _fetch_org_stats(entry_b["access_token"], entry_b["instance_url"]),
    )

    stats_a["label"] = entry_a.get("label") or entry_a.get("alias") or key_a
    stats_b["label"] = entry_b.get("label") or entry_b.get("alias") or key_b

    return {"org_a": stats_a, "org_b": stats_b}
