import uuid
import asyncio
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
import json

from ..salesforce.client import SalesforceClient
from ..scanners.apex_scanner import ApexScanner
from ..scanners.soql_scanner import SOQLScanner
from ..scanners.flow_scanner import FlowScanner
from ..scanners.omniscript_scanner import OmniScriptScanner
from ..scanners.dataraptor_scanner import DataRaptorScanner
from ..scanners.integration_procedure_scanner import IntegrationProcedureScanner
from ..scanners.pricing_procedure_scanner import PricingProcedureScanner
from ..scanners.business_rules_scanner import BusinessRulesScanner
from ..scanners.flexcard_scanner import FlexCardScanner
from ..scanners.permission_scanner import PermissionScanner
from ..scanners.security_scanner import SecurityScanner
from ..scanners.compliance_scanner import ComplianceScanner
from ..ai.analyzer import enrich_findings_batch, generate_executive_summary, generate_recommendations
from ..models.findings import ScanResult, Severity, ComponentType
from ..store import _scans, _scan_progress

router = APIRouter(prefix="/scan", tags=["scan"])


def _require_auth(request: Request) -> tuple[str, str]:
    token = request.session.get("access_token")
    instance_url = request.session.get("instance_url")
    if not token or not instance_url:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token, instance_url


@router.post("/start")
async def start_scan(request: Request, background_tasks=None):
    token, instance_url = _require_auth(request)
    scan_id = str(uuid.uuid4())
    _scan_progress[scan_id] = {"status": "running", "progress_pct": 0, "message": "Initializing..."}

    asyncio.create_task(_run_scan(scan_id, token, instance_url))
    return {"scan_id": scan_id}


@router.get("/progress/{scan_id}")
async def get_progress(scan_id: str):
    progress = _scan_progress.get(scan_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Scan not found")
    return progress


@router.get("/result/{scan_id}")
async def get_result(scan_id: str):
    result = _scans.get(scan_id)
    if not result:
        raise HTTPException(status_code=404, detail="Scan result not found")
    return result


@router.get("/stream/{scan_id}")
async def stream_progress(scan_id: str):
    """Server-Sent Events endpoint for real-time scan progress."""
    async def event_generator():
        last_pct = -1
        for _ in range(600):  # max 10 minutes
            await asyncio.sleep(1)
            progress = _scan_progress.get(scan_id, {})
            pct = progress.get("progress_pct", 0)
            status = progress.get("status", "running")
            if pct != last_pct or status != "running":
                last_pct = pct
                yield f"data: {json.dumps(progress)}\n\n"
            if status in ("completed", "failed"):
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/discover")
async def discover_objects(request: Request):
    """Check which OmniStudio / Revenue Cloud objects exist in the connected org."""
    token, instance_url = _require_auth(request)
    client = SalesforceClient(token, instance_url)
    result = await client.discover_omnistudio_objects()
    return result


@router.get("/debug-omnistudio")
async def debug_omnistudio(request: Request):
    """Diagnose OmniStudio: tries every query approach and returns counts + exact errors."""
    token, instance_url = _require_auth(request)
    client = SalesforceClient(token, instance_url)

    async def try_query(label: str, soql: str):
        try:
            result = await client.query(soql)
            count = len(result.get("records", []))
            return {"label": label, "status": "ok", "count": count}
        except Exception as e:
            return {"label": label, "status": "error", "error": str(e)}

    probes = await asyncio.gather(
        try_query("OmniScriptView",          "SELECT OmniscriptName, Type, SubType, Language, IsActive FROM OmniScriptView WHERE IsActive = TRUE"),
        try_query("OmniIntegrationProcdView","SELECT IntegrationProcedureName, Type, SubType, IsActive FROM OmniIntegrationProcdView WHERE IsActive = TRUE"),
        try_query("OmniDataMapperView",      "SELECT DataMapperName, Type, VersionCount FROM OmniDataMapperView"),
        try_query("OmniFlexCardView",        "SELECT FlexcardName, Author, VersionCount FROM OmniFlexCardView"),
        try_query("OmniProcess(OmniScript)", "SELECT Id, Name, Type, SubType, IsActive FROM OmniProcess WHERE Type = 'OmniScript' AND IsActive = true"),
        try_query("OmniProcess(IP)",         "SELECT Id, Name, Type, SubType, IsActive FROM OmniProcess WHERE Type = 'IntegrationProcedure' AND IsActive = true"),
        try_query("OmniDataTransform",       "SELECT Id, Name, Type FROM OmniDataTransform"),
        try_query("OmniUiCard",              "SELECT Id, Name, IsActive FROM OmniUiCard WHERE IsActive = true"),
        try_query("vlocity OmniScript__c",   "SELECT Id, Name FROM vlocity_cmt__OmniScript__c WHERE vlocity_cmt__IsActive__c = true"),
        try_query("vlocity DRBundle__c",     "SELECT Id, Name FROM vlocity_cmt__DRBundle__c"),
        try_query("vlocity IntProc__c",      "SELECT Id, Name FROM vlocity_cmt__IntegrationProcedure__c WHERE vlocity_cmt__IsActive__c = true"),
        try_query("vlocity VlocityCard__c",  "SELECT Id, Name FROM vlocity_cmt__VlocityCard__c WHERE vlocity_cmt__IsActive__c = true"),
    )

    omniscripts, os_err   = await client.get_omniscripts()
    dataraptors, dr_err   = await client.get_dataraptors()
    ips, ip_err           = await client.get_integration_procedures()
    flexcards, fc_err     = await client.get_flexcards()

    return {
        "instance_url": instance_url,
        "probes": list(probes),
        "resolved": {
            "omniscripts":  {"count": len(omniscripts), "error": os_err},
            "dataraptors":  {"count": len(dataraptors), "error": dr_err},
            "int_procs":    {"count": len(ips),         "error": ip_err},
            "flexcards":    {"count": len(flexcards),   "error": fc_err},
        }
    }


@router.get("/list")
async def list_scans(request: Request):
    token = request.session.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    results = []
    for scan_id, result in _scans.items():
        results.append({
            "scan_id": scan_id,
            "org_name": result.org_name,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "total_findings": result.total_findings,
            "critical_count": result.critical_count,
            "high_count": result.high_count,
        })
    return sorted(results, key=lambda x: x["started_at"], reverse=True)


@router.get("/latest-health")
async def get_latest_health(request: Request):
    """Return health scores from the most recent completed scan."""
    token = request.session.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not _scans:
        return {"health_scores": None, "scan_id": None, "org_name": None}
    latest = max(_scans.values(), key=lambda s: s.started_at)
    return {
        "health_scores": latest.health_scores,
        "scan_id": latest.scan_id,
        "org_name": latest.org_name,
        "total_findings": latest.total_findings,
        "critical_count": latest.critical_count,
        "completed_at": latest.completed_at,
    }


async def _run_scan(scan_id: str, token: str, instance_url: str):
    def update(pct: int, msg: str, status: str = "running"):
        _scan_progress[scan_id] = {"status": status, "progress_pct": pct, "message": msg}

    try:
        client = SalesforceClient(token, instance_url)
        update(2, "Connecting to Salesforce org...")

        org_info = await client.get_org_info()
        org_name = org_info.get("Name", instance_url)
        org_id = org_info.get("Id", "")

        result = ScanResult(
            org_id=org_id,
            org_name=org_name,
            scan_id=scan_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        all_findings = []
        component_counts = {}
        scan_start = time.monotonic()

        # --- Apex ---
        update(5, "Scanning Apex classes...")
        _t = time.monotonic()
        try:
            apex_classes, _ = await client.get_apex_classes()
        except Exception:
            apex_classes = []
        component_counts["Apex"] = len(apex_classes)
        apex_findings = await ApexScanner().scan(apex_classes)
        result.scanner_timing["Apex"] = round((time.monotonic() - _t) * 1000)
        all_findings.extend(apex_findings)

        # --- SOQL Analysis ---
        update(13, "Analyzing SOQL queries for performance issues...")
        _t = time.monotonic()
        soql_findings = await SOQLScanner().scan(apex_classes)
        result.scanner_timing["SOQL"] = round((time.monotonic() - _t) * 1000)
        if soql_findings:
            component_counts["SOQL"] = len({f.component_name for f in soql_findings})
        all_findings.extend(soql_findings)

        # --- Flows ---
        update(18, "Scanning Flows...")
        _t = time.monotonic()
        try:
            flows = await client.get_flows()
        except Exception:
            flows = []
        component_counts["Flow"] = len(flows)
        flow_findings = await FlowScanner().scan(flows)
        result.scanner_timing["Flow"] = round((time.monotonic() - _t) * 1000)
        all_findings.extend(flow_findings)

        # --- OmniScript ---
        update(32, "Scanning OmniScripts...")
        _t = time.monotonic()
        omniscripts, os_err = await client.get_omniscripts()
        if omniscripts:
            component_counts["OmniScript"] = len(omniscripts)
            os_findings = await OmniScriptScanner().scan(omniscripts)
            all_findings.extend(os_findings)
        result.scanner_timing["OmniScript"] = round((time.monotonic() - _t) * 1000)

        # --- DataRaptor ---
        update(46, "Scanning DataRaptors...")
        _t = time.monotonic()
        dataraptors, dr_err = await client.get_dataraptors()
        if dataraptors:
            component_counts["DataRaptor"] = len(dataraptors)
            dr_findings = await DataRaptorScanner().scan(dataraptors)
            all_findings.extend(dr_findings)
        result.scanner_timing["DataRaptor"] = round((time.monotonic() - _t) * 1000)

        # --- Integration Procedures ---
        update(60, "Scanning Integration Procedures...")
        _t = time.monotonic()
        ips, ip_err = await client.get_integration_procedures()
        if ips:
            component_counts["Integration Procedure"] = len(ips)
            ip_findings = await IntegrationProcedureScanner().scan(ips)
            all_findings.extend(ip_findings)
        result.scanner_timing["Integration Procedure"] = round((time.monotonic() - _t) * 1000)

        # --- Pricing Procedures ---
        update(73, "Scanning Pricing Procedures...")
        _t = time.monotonic()
        pps, pp_err = await client.get_pricing_procedures()
        if pps:
            component_counts["Pricing Procedure"] = len(pps)
            pp_findings = await PricingProcedureScanner().scan(pps)
            all_findings.extend(pp_findings)
        result.scanner_timing["Pricing Procedure"] = round((time.monotonic() - _t) * 1000)

        # --- FlexCards ---
        update(75, "Scanning FlexCards...")
        _t = time.monotonic()
        flexcards, fc_err = await client.get_flexcards()
        if flexcards:
            component_counts["FlexCard"] = len(flexcards)
            fc_findings = await FlexCardScanner().scan(flexcards)
            all_findings.extend(fc_findings)
        result.scanner_timing["FlexCard"] = round((time.monotonic() - _t) * 1000)

        # --- Permissions ---
        update(79, "Scanning Profiles and Permission Sets...")
        _t = time.monotonic()
        perms_data, perm_err = await client.get_profiles_and_permsets()
        if perms_data:
            component_counts["Permission"] = len(perms_data)
            perm_findings = await PermissionScanner().scan(perms_data)
            all_findings.extend(perm_findings)
        result.scanner_timing["Permission"] = round((time.monotonic() - _t) * 1000)

        # --- Security Settings ---
        update(82, "Scanning org security settings...")
        _t = time.monotonic()
        try:
            sec_settings = await client.get_security_settings()
            connected_apps = await client.get_connected_apps()
            entity_sharing = await client.get_entity_sharing_models()
            security_data = {
                "security_settings": sec_settings,
                "connected_apps": connected_apps,
                "entity_sharing": entity_sharing,
                "guest_profile": None,
            }
            sec_findings = await SecurityScanner().scan(security_data)
        except Exception:
            sec_findings = []
            entity_sharing = []
        all_findings.extend(sec_findings)
        result.scanner_timing["Security"] = round((time.monotonic() - _t) * 1000)

        # --- Compliance (PII) ---
        update(85, "Scanning compliance & PII fields...")
        _t = time.monotonic()
        try:
            custom_fields = await client.get_custom_fields_with_pii()
            tracked_fields = await client.get_tracked_fields()
            obj_names = [r.get("QualifiedApiName", "") for r in entity_sharing]
            compliance_data = {
                "custom_fields": custom_fields,
                "tracked_fields": tracked_fields,
                "object_names": obj_names,
            }
            comp_findings = await ComplianceScanner().scan(compliance_data)
        except Exception:
            comp_findings = []
        all_findings.extend(comp_findings)
        result.scanner_timing["Compliance"] = round((time.monotonic() - _t) * 1000)

        # --- Business Rules ---
        update(88, "Scanning Business Rules...")
        _t = time.monotonic()
        brs, br_err = await client.get_business_rules()
        if brs:
            component_counts["Business Rules"] = len(brs)
            br_findings = await BusinessRulesScanner().scan(brs)
            all_findings.extend(br_findings)
        result.scanner_timing["Business Rules"] = round((time.monotonic() - _t) * 1000)

        # --- AI enrichment ---
        update(93, "Running AI analysis on top findings...")
        _t = time.monotonic()
        all_findings = await enrich_findings_batch(all_findings)
        result.scanner_timing["AI Enrichment"] = round((time.monotonic() - _t) * 1000)

        # Finalize counts and findings before AI summary (summary needs them)
        total = sum(component_counts.values())
        result.total_components = total
        result.total_findings = len(all_findings)
        result.critical_count = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
        result.high_count = sum(1 for f in all_findings if f.severity == Severity.HIGH)
        result.medium_count = sum(1 for f in all_findings if f.severity == Severity.MEDIUM)
        result.low_count = sum(1 for f in all_findings if f.severity == Severity.LOW)
        result.findings = all_findings
        result.component_summary = component_counts

        # Compute per-category health scores (100 = clean, 0 = worst)
        def _health(comp_types):
            relevant = [f for f in all_findings if f.component_type in comp_types]
            penalty = sum(
                15 if f.severity == Severity.CRITICAL else
                 8 if f.severity == Severity.HIGH else
                 3 if f.severity == Severity.MEDIUM else 1
                for f in relevant
            )
            return max(0, min(100, 100 - penalty))

        result.health_scores = {
            "apex":       _health([ComponentType.APEX, ComponentType.SOQL]),
            "flows":      _health([ComponentType.FLOW]),
            "perms":      _health([ComponentType.PERMISSION]),
            "integr":     _health([ComponentType.INTEGRATION_PROCEDURE]),
            "omni":       _health([ComponentType.OMNISCRIPT, ComponentType.DATARAPTOR]),
            "security":   _health([ComponentType.SECURITY]),
            "compliance": _health([ComponentType.COMPLIANCE]),
        }

        # --- Executive summary + recommendations (concurrent) ---
        update(94, "Generating executive summary and recommendations...")
        exec_summary, recs = await asyncio.gather(
            generate_executive_summary(result),
            generate_recommendations(all_findings),
        )
        result.executive_summary = exec_summary
        result.recommendations = recs

        result.scan_duration_ms = round((time.monotonic() - scan_start) * 1000)
        result.completed_at = datetime.now(timezone.utc).isoformat()
        _scans[scan_id] = result
        update(100, "Scan complete!", status="completed")

    except Exception as e:
        _scan_progress[scan_id] = {
            "status": "failed",
            "progress_pct": 0,
            "message": f"Scan failed: {str(e)}",
        }
