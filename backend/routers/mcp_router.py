"""
MCP bridge router — exposes scan, security, and metadata endpoints for the
MCP stdio server. Auth is via X-MCP-API-Key header; Salesforce credentials
are forwarded in X-SF-Access-Token / X-SF-Instance-URL headers.
"""

import asyncio
import uuid

from fastapi import APIRouter, Header, HTTPException, Request

from ..config import settings
from ..models.findings import ComponentType, Severity
from ..salesforce.client import SalesforceClient
from ..store import _scan_progress, _scans
from ..routers.scan_router import _run_scan
from ..routers.info_router import (
    _soap_describe_metadata,
    _STATIC_METADATA_TYPES,
    _list_with_folders,
    _soap_list_one,
    _FOLDER_PARENT_TYPE,
    _TOOLING_QUERIES,
    _API_VERSION,
)

import httpx

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _require_mcp_auth(x_mcp_api_key: str = Header(default="")) -> None:
    if not settings.MCP_API_KEY:
        raise HTTPException(status_code=403, detail="MCP_API_KEY not configured")
    if x_mcp_api_key != settings.MCP_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid MCP API key")


def _require_sf_client(
    x_sf_access_token: str = Header(default=""),
    x_sf_instance_url: str = Header(default=""),
) -> SalesforceClient:
    if not x_sf_access_token or not x_sf_instance_url:
        raise HTTPException(
            status_code=400,
            detail="X-SF-Access-Token and X-SF-Instance-URL headers are required",
        )
    return SalesforceClient(x_sf_access_token, x_sf_instance_url)


# ── Scan endpoints ────────────────────────────────────────────────────────────

@router.get("/scan/start")
async def mcp_scan_start(
    x_mcp_api_key: str = Header(default=""),
    x_sf_access_token: str = Header(default=""),
    x_sf_instance_url: str = Header(default=""),
):
    _require_mcp_auth(x_mcp_api_key)
    client = _require_sf_client(x_sf_access_token, x_sf_instance_url)

    scan_id = str(uuid.uuid4())
    _scan_progress[scan_id] = {"status": "running", "progress_pct": 0, "message": "Initializing..."}
    asyncio.create_task(_run_scan(scan_id, client.access_token, client.instance_url))
    return {"scan_id": scan_id}


@router.get("/scan/progress/{scan_id}")
async def mcp_scan_progress(
    scan_id: str,
    x_mcp_api_key: str = Header(default=""),
):
    _require_mcp_auth(x_mcp_api_key)
    progress = _scan_progress.get(scan_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Scan not found")
    return progress


@router.get("/scan/result/{scan_id}")
async def mcp_scan_result(
    scan_id: str,
    x_mcp_api_key: str = Header(default=""),
):
    _require_mcp_auth(x_mcp_api_key)
    result = _scans.get(scan_id)
    if not result:
        raise HTTPException(status_code=404, detail="Scan result not found")

    findings_summary = [
        {
            "id":             f.id,
            "rule_id":        f.rule_id,
            "rule_name":      f.rule_name,
            "component_type": f.component_type.value,
            "component_name": f.component_name,
            "severity":       f.severity.value,
            "description":    f.description,
            "suggested_fix":  f.suggested_fix,
            "impact":         f.impact,
        }
        for f in result.findings[:50]
    ]

    return {
        "scan_id":           result.scan_id,
        "org_name":          result.org_name,
        "total_findings":    result.total_findings,
        "critical_count":    result.critical_count,
        "high_count":        result.high_count,
        "medium_count":      result.medium_count,
        "low_count":         result.low_count,
        "health_scores":     result.health_scores,
        "executive_summary": result.executive_summary,
        "recommendations":   result.recommendations,
        "component_summary": result.component_summary,
        "started_at":        result.started_at,
        "completed_at":      result.completed_at,
        "findings":          findings_summary,
    }


@router.get("/scan/health")
async def mcp_scan_health(x_mcp_api_key: str = Header(default="")):
    _require_mcp_auth(x_mcp_api_key)
    if not _scans:
        return {"health_scores": None, "scan_id": None, "org_name": None}
    latest = max(_scans.values(), key=lambda s: s.started_at)
    return {
        "scan_id":        latest.scan_id,
        "org_name":       latest.org_name,
        "health_scores":  latest.health_scores,
        "total_findings": latest.total_findings,
        "critical_count": latest.critical_count,
        "completed_at":   latest.completed_at,
    }


# ── Security endpoint ─────────────────────────────────────────────────────────

@router.get("/security/summary")
async def mcp_security_summary(x_mcp_api_key: str = Header(default="")):
    _require_mcp_auth(x_mcp_api_key)

    if not _scans:
        return {"findings": [], "scores": {}, "scan_id": None, "severity_counts": {}, "by_category": {}, "total": 0}

    latest = max(_scans.values(), key=lambda s: s.started_at)

    sec_types = {
        ComponentType.SECURITY, ComponentType.COMPLIANCE,
        ComponentType.PERMISSION, ComponentType.APEX, ComponentType.SOQL,
    }

    findings = [
        {
            "id":             f.id,
            "rule_id":        f.rule_id,
            "rule_name":      f.rule_name,
            "component_type": f.component_type.value,
            "component_name": f.component_name,
            "severity":       f.severity.value,
            "description":    f.description,
            "suggested_fix":  f.suggested_fix,
            "impact":         f.impact,
        }
        for f in latest.findings
        if f.component_type in sec_types
    ]

    sev_counts = {sev.value: sum(1 for f in findings if f["severity"] == sev.value) for sev in Severity}

    by_category: dict = {}
    for f in findings:
        cat = f["component_type"]
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "scan_id":        latest.scan_id,
        "findings":       findings,
        "severity_counts": sev_counts,
        "by_category":    by_category,
        "scores":         latest.health_scores,
        "total":          len(findings),
    }


# ── Metadata endpoints ────────────────────────────────────────────────────────

@router.get("/info/metadata-types")
async def mcp_metadata_types(
    x_mcp_api_key: str = Header(default=""),
    x_sf_access_token: str = Header(default=""),
    x_sf_instance_url: str = Header(default=""),
):
    _require_mcp_auth(x_mcp_api_key)
    client = _require_sf_client(x_sf_access_token, x_sf_instance_url)

    types = await _soap_describe_metadata(client.access_token, client.instance_url)
    if types:
        return {"metadata_types": types, "total": len(types), "source": "soap"}
    return {
        "metadata_types": _STATIC_METADATA_TYPES,
        "total": len(_STATIC_METADATA_TYPES),
        "source": "static",
    }


@router.get("/info/metadata-components/{type_name}")
async def mcp_metadata_components(
    type_name: str,
    x_mcp_api_key: str = Header(default=""),
    x_sf_access_token: str = Header(default=""),
    x_sf_instance_url: str = Header(default=""),
):
    _require_mcp_auth(x_mcp_api_key)
    client = _require_sf_client(x_sf_access_token, x_sf_instance_url)

    token        = client.access_token
    instance_url = client.instance_url

    # 1. Tooling API for dev-centric types
    soql = _TOOLING_QUERIES.get(type_name)
    if soql:
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as http:
                resp = await http.get(
                    f"{instance_url}/services/data/v{_API_VERSION}/tooling/query",
                    params={"q": soql},
                    headers={"Authorization": f"Bearer {token}"},
                )
            if resp.is_success:
                records = resp.json().get("records", [])
                clean = [{k: v for k, v in r.items() if k != "attributes"} for r in records]
                if clean:
                    return {"type": type_name, "components": clean, "count": len(clean), "source": "tooling"}
        except Exception:
            pass

    # 2. SOAP listMetadata
    if type_name in _FOLDER_PARENT_TYPE:
        components = await _list_with_folders(token, instance_url, type_name)
    else:
        components = await _soap_list_one(token, instance_url, type_name)

    if components:
        return {"type": type_name, "components": components, "count": len(components), "source": "soap"}

    return {"type": type_name, "components": [], "count": 0, "source": "none"}
