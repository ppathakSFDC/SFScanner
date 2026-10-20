"""Security & compliance summary endpoint."""
from fastapi import APIRouter, Request, HTTPException
from ..store import _scans
from ..models.findings import ComponentType, Severity

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/summary")
async def security_summary(request: Request):
    """Return security & compliance summary from the most recent scan."""
    if not request.session.get("access_token"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not _scans:
        return {"findings": [], "scores": {}, "scan_id": None, "severity_counts": {}, "by_category": {}, "total": 0}

    latest = max(_scans.values(), key=lambda s: s.started_at)

    sec_types = {
        ComponentType.SECURITY, ComponentType.COMPLIANCE,
        ComponentType.PERMISSION, ComponentType.APEX, ComponentType.SOQL,
    }

    findings = [
        {
            "id": f.id,
            "rule_id": f.rule_id,
            "rule_name": f.rule_name,
            "component_type": f.component_type.value,
            "component_name": f.component_name,
            "severity": f.severity.value,
            "description": f.description,
            "suggested_fix": f.suggested_fix,
            "impact": f.impact,
        }
        for f in latest.findings
        if f.component_type in sec_types
    ]

    sev_counts = {sev.value: sum(1 for f in findings if f["severity"] == sev.value) for sev in Severity}

    by_category: dict[str, int] = {}
    for f in findings:
        cat = f["component_type"]
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "scan_id": latest.scan_id,
        "findings": findings,
        "severity_counts": sev_counts,
        "by_category": by_category,
        "scores": latest.health_scores,
        "total": len(findings),
    }
