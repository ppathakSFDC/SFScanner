import json
import re
import asyncio
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import anthropic

from ..agents.definitions import get_agents_list, get_agent
from ..agents.skills import skill_for_message
from ..agents.tools import TOOL_DEFINITIONS, TOOL_DEFINITIONS_OPENAI, execute_tool
from ..config import settings
from ..salesforce.client import SalesforceClient


def _read_file_key(path: Path) -> str:
    """Read an API key from a file (opencode key-file convention). Returns '' on failure."""
    try:
        return path.read_text().strip()
    except Exception:
        return ""
from ..scanners.soql_scanner import SOQLScanner as _SOQLScanner

router = APIRouter(tags=["agents"])


async def _fetch_omniscript_context(sf: SalesforceClient, user_message: str) -> str:
    """Fetch actual OmniScript data from Salesforce and return as context string."""
    records, err = await sf.get_omniscripts()
    if err and not records:
        return f"[Could not fetch OmniScript list: {err}]"

    if not records:
        return "[No active OmniScripts found in this org.]"

    names = [r.get("Name", "") for r in records]
    msg_lower = user_message.lower()

    # Find the most relevant OmniScript mentioned in the user's message.
    # OmniProcess.Name is typically "SubType/Language" or just a label; also check SubType__c.
    matched = None
    for r in records:
        record_name = r.get("Name", "").lower()
        sub_type = (r.get("SubType__c") or r.get("vlocity_cmt__SubType__c") or "").lower()
        # Match if the record's Name or SubType appears in the message, or vice versa
        if (record_name and record_name in msg_lower) or (sub_type and sub_type in msg_lower):
            matched = r
            break
    # If still no match, try word-by-word: split message into tokens and check each
    if not matched:
        tokens = [t.strip("'\".,?!") for t in msg_lower.split() if len(t) > 3]
        for r in records:
            record_name = r.get("Name", "").lower()
            sub_type = (r.get("SubType__c") or r.get("vlocity_cmt__SubType__c") or "").lower()
            for tok in tokens:
                if tok in record_name or tok in sub_type:
                    matched = r
                    break
            if matched:
                break

    lines = [f"Active OmniScripts in org ({len(records)} total): {', '.join(names[:30])}"]

    if matched:
        name = matched.get("Name", "")
        lines.append(f"\n--- Full definition of '{name}' ---")
        lines.append(f"Id: {matched.get('Id', '')}")
        lines.append(f"Type/SubType: {matched.get('Type__c') or matched.get('vlocity_cmt__Type__c', '')} / {matched.get('SubType__c') or matched.get('vlocity_cmt__SubType__c', '')}")
        lines.append(f"Language: {matched.get('Language__c', 'default')}")
        lines.append(f"Active: {matched.get('IsActive__c', True)}")

        prop_raw = matched.get("PropertySet__c") or matched.get("vlocity_cmt__PropertySet__c", "")
        if prop_raw:
            try:
                prop = json.loads(prop_raw) if isinstance(prop_raw, str) else prop_raw
                # Summarise elements for performance analysis
                elements = prop.get("element", [])
                lines.append(f"\nTotal elements: {len(elements)}")
                # Group by type
                type_counts: dict = {}
                server_calls = []
                for el in elements:
                    el_type = el.get("type", "Unknown")
                    type_counts[el_type] = type_counts.get(el_type, 0) + 1
                    if el_type in ("DataRaptor Extract", "DataRaptor Transform", "DataRaptor Load",
                                   "DataRaptor Turbo Extract", "Integration Procedure",
                                   "Remote Action", "HTTP Action", "Calculation Procedure"):
                        server_calls.append({
                            "name": el.get("name", ""),
                            "type": el_type,
                            "label": el.get("label", ""),
                            "pre_cache": el.get("preCache", False),
                            "caching": el.get("caching", False),
                            "on_load": el.get("onLoad", False),
                            "conditional": bool(el.get("condition")),
                        })
                lines.append(f"Element types: {json.dumps(type_counts, indent=2)}")
                lines.append(f"\nServer calls ({len(server_calls)} total):")
                for sc in server_calls:
                    cache_info = []
                    if sc["pre_cache"]:
                        cache_info.append("pre-cached")
                    if sc["caching"]:
                        cache_info.append("result-cached")
                    if sc["on_load"]:
                        cache_info.append("on-load")
                    if sc["conditional"]:
                        cache_info.append("conditional")
                    lines.append(f"  - [{sc['type']}] {sc['name'] or sc['label']} {('(' + ', '.join(cache_info) + ')') if cache_info else '(no caching)'}")
                # Include full PropertySet for deep analysis (truncated)
                full_json = json.dumps(prop, indent=2)
                lines.append(f"\nFull PropertySet (first 8000 chars):\n{full_json[:8000]}")
            except Exception as ex:
                lines.append(f"\nPropertySet (raw, first 6000 chars):\n{str(prop_raw)[:6000]}")
    else:
        lines.append("\n[No specific OmniScript name found in the message. Ask about a specific one from the list above for detailed analysis.]")

    return "\n".join(lines)


async def _fetch_dataraptor_context(sf: SalesforceClient, user_message: str) -> str:
    records, err = await sf.get_dataraptors()
    if err and not records:
        return f"[Could not fetch DataRaptors: {err}]"
    if not records:
        return "[No DataRaptors found in this org.]"
    names = [r.get("Name", "") for r in records]
    lines = [f"DataRaptors in org ({len(records)} total): {', '.join(names[:30])}"]
    msg_lower = user_message.lower()
    for r in records:
        if r.get("Name", "").lower() in msg_lower:
            lines.append(f"\nMatched DataRaptor: {json.dumps(r, indent=2)[:4000]}")
            break
    return "\n".join(lines)


async def _fetch_integration_context(sf: SalesforceClient, user_message: str) -> str:
    records, err = await sf.get_integration_procedures()
    if err and not records:
        return f"[Could not fetch Integration Procedures: {err}]"
    if not records:
        return "[No Integration Procedures found in this org.]"
    names = [r.get("Name", "") for r in records]
    lines = [f"Integration Procedures in org ({len(records)} total): {', '.join(names[:30])}"]
    msg_lower = user_message.lower()
    for r in records:
        if r.get("Name", "").lower() in msg_lower:
            lines.append(f"\nMatched IP: {json.dumps(r, indent=2)[:4000]}")
            break
    return "\n".join(lines)


_APEX_NAME_RE = re.compile(r'\b([A-Z][A-Za-z0-9_]{3,}(?:Test|Handler|Service|Controller|Helper|Trigger|Batch|Scheduler|Util|Utils|Manager)?)\b')


async def _fetch_apex_class_by_name(sf: SalesforceClient, name: str) -> Optional[dict]:
    """Direct targeted fetch for a single Apex class by exact name."""
    try:
        result = await sf.tooling_query(
            f"SELECT Id, Name, Body, ApiVersion, Status, LengthWithoutComments "
            f"FROM ApexClass WHERE Name = '{name}' LIMIT 1"
        )
        records = result.get("records", [])
        if not records:
            return None
        r = records[0]
        body = r.get("Body", "") or ""
        if not body:
            detail = await sf.tooling_get(f"sobjects/ApexClass/{r['Id']}")
            body = detail.get("Body", "") or ""
            r["Body"] = body
        return r
    except Exception:
        return None


async def _fetch_apex_context(sf: SalesforceClient, user_message: str) -> str:
    records, err = await sf.get_apex_classes()
    if err and not records:
        return f"[Could not fetch Apex classes: {err}]"
    if not records:
        return "[No Apex classes found in this org.]"

    names_in_org = {r.get("Name", ""): r for r in records}
    msg_lower = user_message.lower()
    lines = [f"Apex classes in org ({len(records)} total): {', '.join(list(names_in_org.keys())[:60])}"]

    # Extract candidate class names from the message (CamelCase / PascalCase identifiers)
    candidate_names = [m for m in _APEX_NAME_RE.findall(user_message) if len(m) > 4]

    # Direct-fetch any mentioned class names, even if not in the bulk-300 list
    directly_fetched: list[dict] = []
    for cname in candidate_names[:4]:
        if cname in names_in_org:
            # Already in bulk list — grab it
            directly_fetched.append(names_in_org[cname])
        else:
            # Not in bulk results (org may have >300 classes) — query directly
            fetched = await _fetch_apex_class_by_name(sf, cname)
            if fetched:
                directly_fetched.append(fetched)
                lines.append(f"[Note: '{cname}' was not in the first-300 bulk results; fetched directly]")
            else:
                lines.append(f"[Note: Apex class '{cname}' was NOT found in this org (checked via direct query)]")

    # Partial-match from bulk list for any remaining tokens
    matched_bulk = [
        r for r in records
        if r.get("Name", "").lower() in msg_lower
        or any(tok in r.get("Name", "").lower() for tok in msg_lower.split() if len(tok) > 3)
    ]

    # Combine: direct-fetched first, then bulk matches, deduplicated by Id
    seen_ids: set = set()
    targets: list[dict] = []
    for r in directly_fetched + matched_bulk:
        rid = r.get("Id", "")
        if rid not in seen_ids:
            seen_ids.add(rid)
            targets.append(r)
        if len(targets) >= 5:
            break

    # When nothing specific matched, show first 5 for general context
    if not targets:
        targets = records[:5]

    for r in targets:
        body = (r.get("Body", "") or "")
        if not body:
            try:
                detail = await sf.tooling_get(f"sobjects/ApexClass/{r['Id']}")
                body = detail.get("Body", "") or ""
            except Exception:
                body = ""
        lines.append(f"\n--- Apex Class: {r.get('Name')} (API v{r.get('ApiVersion','?')}) ---\n{body[:8000]}")

    if not directly_fetched and not matched_bulk and len(records) > 5:
        lines.append(f"\n[Showing first 5 of {len(records)} classes. Mention a specific class name to fetch its full code.]")

    return "\n".join(lines)


async def _fetch_general_context(sf: SalesforceClient, user_message: str) -> str:
    """Smart dispatcher for the general/architect agent — picks the right fetcher based on message content."""
    msg_lower = user_message.lower()

    # Detect intent from keywords and dispatch to the right specialist fetcher
    apex_keywords = ("apex", "class", "trigger", "test", "soql", "dml", "governor", "batch", "queueable",
                     "future", "invocable", "schedulable", "exception", ".cls", "rlm_", "sfdc_", "_apex")
    omni_keywords = ("omniscript", "omni script", "omniprocess", "vlocity", "omnistudio")
    ip_keywords = ("integration procedure", "integrationprocedure", "omniip", "ip action")
    dr_keywords = ("dataraptor", "data raptor", "drextract", "drload", "drtransform")
    flow_keywords = ("flow", "process builder", "workflow rule", "autolaunched", "record-triggered")

    # Check for specific class names (strongest signal)
    has_class_name = bool(_APEX_NAME_RE.search(user_message))

    if has_class_name or any(k in msg_lower for k in apex_keywords):
        return await _fetch_apex_context(sf, user_message)
    if any(k in msg_lower for k in omni_keywords):
        return await _fetch_omniscript_context(sf, user_message)
    if any(k in msg_lower for k in ip_keywords):
        return await _fetch_integration_context(sf, user_message)
    if any(k in msg_lower for k in dr_keywords):
        return await _fetch_dataraptor_context(sf, user_message)

    # Default: return apex class list as general context
    return await _fetch_apex_context(sf, user_message)


_ORG_FETCHERS = {
    "omniscript_expert": _fetch_omniscript_context,
    "dataraptor_expert": _fetch_dataraptor_context,
    "integration_expert": _fetch_integration_context,
    "apex_expert": _fetch_apex_context,
    "general_expert": _fetch_general_context,
}


def _require_auth(request: Request):
    token = request.session.get("access_token")
    instance_url = request.session.get("instance_url")
    if not token or not instance_url:
        raise HTTPException(status_code=401, detail="Not authenticated — connect your Salesforce org first")
    return token, instance_url


@router.get("/agents/org/apex-class/{class_name}")
async def fetch_apex_class(request: Request, class_name: str):
    """Return full source body of a single Apex class by name."""
    token, instance_url = _require_auth(request)
    sf = SalesforceClient(token, instance_url)
    result = await sf.tooling_query(
        f"SELECT Id, Name, Body, ApiVersion, Status, LengthWithoutComments "
        f"FROM ApexClass WHERE Name = '{class_name}' LIMIT 1"
    )
    records = result.get("records", [])
    if not records:
        raise HTTPException(status_code=404, detail=f"Apex class '{class_name}' not found")
    r = records[0]
    body = r.get("Body", "") or ""
    if not body:
        detail = await sf.tooling_get(f"sobjects/ApexClass/{r['Id']}")
        body = detail.get("Body", "") or ""
    return {
        "name": r.get("Name"),
        "id": r.get("Id"),
        "api_version": r.get("ApiVersion"),
        "status": r.get("Status"),
        "length": r.get("LengthWithoutComments"),
        "body": body,
    }


@router.get("/agents/org/omniscripts")
async def fetch_omniscripts(request: Request):
    token, instance_url = _require_auth(request)
    sf = SalesforceClient(token, instance_url)
    records, err = await sf.get_omniscripts()
    return {"total": len(records), "records": records, "error": err}


@router.get("/agents/org/data")
async def fetch_org_data(request: Request):
    token, instance_url = _require_auth(request)
    sf = SalesforceClient(token, instance_url)
    raw = await asyncio.gather(
        sf.get_omniscripts(),
        sf.get_integration_procedures(),
        sf.get_dataraptors(),
    )
    keys = ["omniscripts", "integration_procedures", "dataraptors"]
    records = {k: raw[i][0] for i, k in enumerate(keys)}
    errors = {k: raw[i][1] for i, k in enumerate(keys) if raw[i][1]}
    return {
        "instance_url": instance_url,
        "counts": {k: len(v) for k, v in records.items()},
        "records": records,
        "errors": errors,
    }


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    org_context: bool = False
    model: str = ""  # optional model override; falls back to settings default


_SERVER_CALL_TYPES = {
    "DataRaptor Extract", "DataRaptor Transform", "DataRaptor Load",
    "DataRaptor Turbo Extract", "Integration Procedure",
    "Remote Action", "HTTP Action", "Calculation Procedure",
    "Response Action", "OmniScript",
}


def _analyze_omniscript(record: dict) -> list:
    issues = []
    name = record.get("Name", "?")
    prop_raw = record.get("PropertySet__c") or record.get("vlocity_cmt__PropertySet__c", "")
    if not prop_raw:
        return issues
    try:
        prop = json.loads(prop_raw) if isinstance(prop_raw, str) else prop_raw
    except Exception:
        return issues

    elements = prop.get("element", [])
    server_calls = [e for e in elements if e.get("type") in _SERVER_CALL_TYPES]

    uncached = [e for e in server_calls if not e.get("preCache") and not e.get("caching")]
    for e in uncached:
        el_name = e.get("name") or e.get("label") or "(unnamed)"
        issues.append({
            "component": name, "component_type": "OmniScript",
            "severity": "high",
            "issue": f"Uncached {e.get('type', 'server call')}: '{el_name}'",
            "fix": "Enable preCache or result caching to reduce repeated server round-trips.",
        })

    if len(server_calls) > 6:
        issues.append({
            "component": name, "component_type": "OmniScript",
            "severity": "medium",
            "issue": f"High server-call count ({len(server_calls)} calls)",
            "fix": "Consolidate calls into a single Integration Procedure or add caching.",
        })

    always_on = [e for e in server_calls if not e.get("condition") and e.get("onLoad")]
    if len(always_on) > 3:
        issues.append({
            "component": name, "component_type": "OmniScript",
            "severity": "medium",
            "issue": f"{len(always_on)} on-load server calls fire unconditionally at startup",
            "fix": "Use conditional loading or preCache to defer calls the user may never need.",
        })
    return issues


def _analyze_integration_procedure(record: dict) -> list:
    issues = []
    name = record.get("Name", "?")
    prop_raw = record.get("PropertySet__c") or record.get("vlocity_cmt__PropertySet__c", "")
    if not prop_raw:
        return issues
    try:
        prop = json.loads(prop_raw) if isinstance(prop_raw, str) else prop_raw
    except Exception:
        return issues

    elements = prop.get("element", [])
    http_no_timeout = [
        e for e in elements
        if e.get("type") in ("HTTP Action", "Remote Action")
        and not e.get("timeout") and not e.get("timeoutMs")
    ]
    for e in http_no_timeout:
        el_name = e.get("name") or e.get("label") or "(unnamed)"
        issues.append({
            "component": name, "component_type": "Integration Procedure",
            "severity": "high",
            "issue": f"HTTP/Remote action '{el_name}' has no timeout configured",
            "fix": "Set a timeout (e.g. 5000 ms) to prevent hanging on slow external calls.",
        })

    sequential = [e for e in elements if not e.get("isParallel") and e.get("type") in ("HTTP Action", "DataRaptor Extract", "DataRaptor Turbo Extract")]
    if len(sequential) > 2:
        issues.append({
            "component": name, "component_type": "Integration Procedure",
            "severity": "medium",
            "issue": f"{len(sequential)} sequential server actions (none marked parallel)",
            "fix": "Enable parallel execution for independent actions to reduce total latency.",
        })
    return issues


def _detect_loop_violations(body: str, name: str, comp_type: str) -> list:
    issues = []
    if not body:
        return issues
    lines = body.split('\n')
    brace_stack = []
    in_block_comment = False
    soql_reported = False
    dml_reported = False

    for line_num, raw_line in enumerate(lines, 1):
        line = raw_line
        if '/*' in line and not in_block_comment:
            in_block_comment = True
        if '*/' in line and in_block_comment:
            in_block_comment = False
            continue
        if in_block_comment:
            continue
        if '//' in line:
            line = line[:line.index('//')]

        opens = line.count('{')
        closes = line.count('}')
        is_loop = bool(re.search(r'\b(for|while)\s*\(', line, re.IGNORECASE))

        for _ in range(opens):
            brace_stack.append(is_loop)

        in_loop = any(brace_stack)

        if in_loop:
            if not soql_reported and re.search(r'\[\s*SELECT\b|\[\s*FIND\b', line, re.IGNORECASE):
                issues.append({
                    "component": name, "component_type": comp_type, "severity": "high",
                    "issue": f"SOQL query inside loop (line {line_num})",
                    "fix": "Move the SOQL outside the loop. Build a List of IDs first, query once, then use a Map for lookups inside the loop.",
                })
                soql_reported = True
            if not dml_reported and re.search(r'\b(insert|update|delete|upsert|merge|undelete)\s+\w', line, re.IGNORECASE):
                issues.append({
                    "component": name, "component_type": comp_type, "severity": "high",
                    "issue": f"DML statement inside loop (line {line_num})",
                    "fix": "Collect records into a List, then perform a single DML operation outside the loop.",
                })
                dml_reported = True

        for _ in range(closes):
            if brace_stack:
                brace_stack.pop()

    return issues


def _analyze_apex_class(record: dict) -> list:
    issues = []
    name = record.get("Name", "?")
    body = record.get("Body", "") or ""

    issues.extend(_detect_loop_violations(body, name, "Apex Class"))

    class_decl = re.search(r'\bclass\s+\w+', body, re.IGNORECASE)
    if class_decl and not re.search(r'\b(with|without|inherited)\s+sharing\b', body[:2000], re.IGNORECASE):
        issues.append({
            "component": name, "component_type": "Apex Class", "severity": "medium",
            "issue": "Class has no sharing declaration (with sharing / without sharing / inherited sharing)",
            "fix": "Add 'with sharing' unless you explicitly need elevated access. Omitting it defaults to 'without sharing' in many contexts, which can expose data.",
        })

    ids = re.findall(r"['\"]([a-zA-Z0-9]{15}|[a-zA-Z0-9]{18})['\"]", body)
    if ids:
        issues.append({
            "component": name, "component_type": "Apex Class", "severity": "medium",
            "issue": f"Hardcoded Salesforce ID(s) detected ({len(ids)} found)",
            "fix": "Replace hardcoded IDs with Custom Labels, Custom Metadata, or SOQL lookups. IDs differ between orgs.",
        })

    if re.search(r'@future\s*\(\s*callout\s*=\s*true', body, re.IGNORECASE) and re.search(r'\b(insert|update|delete|upsert)\b', body, re.IGNORECASE):
        issues.append({
            "component": name, "component_type": "Apex Class", "severity": "medium",
            "issue": "@future(callout=true) method contains DML — governor limits apply in async context",
            "fix": "Review async DML usage. Prefer Queueable Apex for more control over async execution.",
        })

    return issues


def _analyze_apex_triggers(records: list) -> list:
    issues = []
    by_object: dict = {}
    for r in records:
        obj = r.get("TableEnumOrId", "Unknown")
        by_object.setdefault(obj, []).append(r.get("Name", "?"))

    for obj, names in by_object.items():
        if len(names) > 1:
            issues.append({
                "component": ", ".join(names), "component_type": "Apex Trigger", "severity": "high",
                "issue": f"Multiple triggers on {obj}: {', '.join(names)}",
                "fix": "Consolidate into a single trigger per object using a handler/dispatcher pattern (e.g. TriggerHandler framework).",
            })

    for r in records:
        name = r.get("Name", "?")
        body = r.get("Body", "") or ""

        issues.extend(_detect_loop_violations(body, name, "Apex Trigger"))

        non_empty = [l.strip() for l in body.split('\n') if l.strip() and not l.strip().startswith('//')]
        meaningful = [l for l in non_empty if l not in ('{', '}') and not l.startswith('trigger ')]
        if len(meaningful) > 15:
            issues.append({
                "component": name, "component_type": "Apex Trigger", "severity": "medium",
                "issue": f"Trigger contains {len(meaningful)} lines of logic — business logic in trigger body",
                "fix": "Move logic to a dedicated handler class (e.g. AccountTriggerHandler). Trigger should only dispatch to handler methods.",
            })

        if re.search(r'Trigger\.(new|old)\s*\[\s*0\s*\]', body):
            issues.append({
                "component": name, "component_type": "Apex Trigger", "severity": "high",
                "issue": "Non-bulkified pattern: Trigger.new[0] or Trigger.old[0]",
                "fix": "Iterate over Trigger.new with a for loop. Triggers must handle bulk operations (up to 200 records per transaction).",
            })

    return issues


def _analyze_flow(record: dict) -> list:
    issues = []
    name = record.get("MasterLabel", "?")
    process_type = record.get("ProcessType", "")

    if process_type in ("AutoLaunchedFlow", "Flow") and record.get("TriggerType") == "RecordAfterSave":
        issues.append({
            "component": name, "component_type": "Flow", "severity": "medium",
            "issue": "Record-triggered (after-save) flow — verify recursion prevention",
            "fix": "Add a recursion prevention mechanism (e.g. a static variable in Apex or a custom field flag) if this flow updates the triggering record.",
        })

    if process_type == "Workflow":
        issues.append({
            "component": name, "component_type": "Flow", "severity": "medium",
            "issue": "Legacy Process Builder flow — scheduled for retirement",
            "fix": "Migrate to a Record-Triggered Flow. Salesforce retired Process Builder; it will stop working in future releases.",
        })

    if process_type == "CustomEvent":
        issues.append({
            "component": name, "component_type": "Flow", "severity": "medium",
            "issue": "Platform Event triggered flow — verify governor limit handling",
            "fix": "Platform event flows share the async governor limits. Ensure DML operations are batched and errors are handled gracefully.",
        })

    return issues


_LIMIT_THRESHOLDS = {
    "DataStorageMB": (75, "Data storage"),
    "FileStorageMB": (75, "File storage"),
    "DailyApiRequests": (80, "Daily API requests"),
    "DailyAsyncApexExecutions": (80, "Daily async Apex executions"),
    "DailyBulkApiBatches": (80, "Daily Bulk API batches"),
    "ActiveScratchOrgs": (90, "Active scratch orgs"),
    "DailyScratchOrgs": (90, "Daily scratch org allocations"),
    "PermissionSets": (85, "Permission sets"),
    "CustomApps": (85, "Custom apps"),
    "CustomObjects": (85, "Custom objects"),
    "CustomTabs": (80, "Custom tabs"),
    "DailyWorkflowEmails": (80, "Daily workflow emails"),
    "HourlyPublishedPlatformEvents": (80, "Hourly platform events published"),
    "DailyDurableGenericStreamingApiEvents": (80, "Daily streaming events"),
}


def _analyze_org_limits(limits: dict) -> list:
    issues = []
    for key, (threshold_pct, label) in _LIMIT_THRESHOLDS.items():
        entry = limits.get(key)
        if not entry:
            continue
        max_val = entry.get("Max", 0)
        remaining = entry.get("Remaining", max_val)
        if max_val <= 0:
            continue
        used_pct = ((max_val - remaining) / max_val) * 100
        if used_pct >= threshold_pct:
            severity = "high" if used_pct >= 90 else "medium"
            issues.append({
                "component": key, "component_type": "Org Limit", "severity": severity,
                "issue": f"{label}: {used_pct:.0f}% used ({max_val - remaining:,} / {max_val:,})",
                "fix": f"Review usage of {label.lower()}. Consider archiving data, optimising API call patterns, or requesting a limit increase from Salesforce.",
            })
    return issues


def _analyze_custom_object(record: dict) -> list:
    issues = []
    name = record.get("DeveloperName", "?")
    sharing = record.get("SharingModel", "")
    ext_sharing = record.get("ExternalSharingModel", "")

    if sharing == "ReadWrite":
        issues.append({
            "component": name, "component_type": "Custom Object", "severity": "medium",
            "issue": "Object uses Public Read/Write sharing — overly permissive",
            "fix": "Review whether Public Read/Write is required. Consider Private or Public Read Only sharing and use sharing rules to grant access selectively.",
        })

    if ext_sharing and ext_sharing not in ("Private", "None") and sharing != ext_sharing:
        issues.append({
            "component": name, "component_type": "Custom Object", "severity": "medium",
            "issue": f"External sharing model ({ext_sharing}) differs from internal ({sharing})",
            "fix": "Ensure external (Experience Cloud) sharing is intentionally more restrictive than internal access.",
        })

    return issues


def _analyze_dataraptor(record: dict) -> list:
    issues = []
    name = record.get("Name", "?")
    itype = record.get("InterfaceType__c") or record.get("vlocity_cmt__InterfaceType__c", "")
    prop_raw = record.get("PropertySet__c") or record.get("vlocity_cmt__PropertySet__c", "")

    if itype and "extract" in itype.lower() and "turbo" not in itype.lower():
        if prop_raw:
            try:
                prop = json.loads(prop_raw) if isinstance(prop_raw, str) else prop_raw
                bundles = prop.get("bundles") or prop.get("queryItems", [])
                has_filters = any(
                    b.get("filter") or b.get("filters") or b.get("whereClause")
                    for b in (bundles if isinstance(bundles, list) else [])
                )
                if bundles and not has_filters:
                    issues.append({
                        "component": name, "component_type": "DataRaptor",
                        "severity": "high",
                        "issue": "DataRaptor Extract has no query filters — risks full table scan",
                        "fix": "Add WHERE filters and consider migrating to Turbo Extract for simpler queries.",
                    })
            except Exception:
                pass
    return issues


def _analyze_business_rule(record: dict) -> list:
    import re as _re
    issues = []
    name = record.get("Name", "?")
    bre_type = record.get("_bre_type", "BusinessRule")

    # ExpressionSetDefinition — check status
    if bre_type == "ExpressionSetDefinition":
        status = record.get("Status", "")
        if status not in ("Active", "Draft", ""):
            issues.append({
                "component": name, "component_type": "Business Rule",
                "severity": "medium",
                "issue": f"Expression Set has status '{status}' — may not be active",
                "fix": "Verify the Expression Set is activated and assigned to the appropriate context.",
            })
        return issues

    # Native / vlocity BusinessRule — inspect PropertySet
    is_active = record.get("IsActive") or record.get("vlocity_cmt__IsActive__c")
    prop_raw = record.get("PropertySet__c") or record.get("vlocity_cmt__PropertySet__c", "")

    if not is_active:
        issues.append({
            "component": name, "component_type": "Business Rule",
            "severity": "medium",
            "issue": "Business Rule is inactive — verify it is intentionally disabled",
            "fix": "Activate the rule if it should be running, or remove/archive it to reduce clutter.",
        })

    if not prop_raw:
        issues.append({
            "component": name, "component_type": "Business Rule",
            "severity": "medium",
            "issue": "Business Rule has no PropertySet / condition configuration",
            "fix": "Open the rule in the BRE editor and define conditions and actions.",
        })
        return issues

    try:
        props = json.loads(prop_raw) if isinstance(prop_raw, str) else prop_raw
    except Exception:
        props = {}

    conditions = props.get("conditions") or props.get("Conditions") or []
    actions    = props.get("actions")    or props.get("Actions")    or []
    rules      = props.get("rules")      or props.get("Rules")      or []

    if len(conditions) > 15:
        issues.append({
            "component": name, "component_type": "Business Rule",
            "severity": "medium",
            "issue": f"Rule has {len(conditions)} conditions — complex rules are hard to maintain",
            "fix": "Break into multiple focused rules or use a decision table for matrix-style logic.",
        })

    if len(actions) > 10:
        issues.append({
            "component": name, "component_type": "Business Rule",
            "severity": "medium",
            "issue": f"Rule triggers {len(actions)} actions — single-responsibility rule recommended",
            "fix": "Split into multiple rules or orchestrate complex action sequences via an Integration Procedure.",
        })

    hardcoded_ids = _re.findall(r'"(00[A-Za-z0-9]{13,16})"', json.dumps(props))
    if hardcoded_ids:
        issues.append({
            "component": name, "component_type": "Business Rule",
            "severity": "high",
            "issue": f"Hardcoded Salesforce IDs found in rule conditions ({len(hardcoded_ids)} instances)",
            "fix": "Replace hardcoded IDs with Custom Labels, Custom Metadata, or dynamic variable references.",
        })

    if len(rules) > 3:
        has_priority = any(
            r.get("priority") or r.get("Priority") or r.get("order")
            for r in rules if isinstance(r, dict)
        )
        if not has_priority:
            issues.append({
                "component": name, "component_type": "Business Rule",
                "severity": "medium",
                "issue": f"Rule group has {len(rules)} rules with no explicit priority ordering",
                "fix": "Set explicit priority numbers on each rule to ensure deterministic execution order.",
            })

    return issues


@router.get("/agents/org/scan")
async def org_scan(request: Request):
    token, instance_url = _require_auth(request)
    sf = SalesforceClient(token, instance_url)

    raw = await asyncio.gather(
        sf.get_omniscripts(),
        sf.get_dataraptors(),
        sf.get_integration_procedures(),
        sf.get_apex_classes(),
        sf.get_apex_triggers(),
        sf.get_flows_active(),
        sf.get_org_limits(),
        sf.get_custom_objects_summary(),
        sf.get_flexcards(),
        sf.get_business_rules(),
        sf.get_cml_rules(),
        sf.get_data_mappers(),
        return_exceptions=True,
    )

    def _unpack(result, default):
        if isinstance(result, Exception):
            return default, str(result)
        if isinstance(result, tuple):
            return result
        return result, ""

    omniscripts, os_err    = _unpack(raw[0], [])
    dataraptors, dr_err    = _unpack(raw[1], [])
    integrations, ip_err   = _unpack(raw[2], [])
    apex_classes, ac_err   = _unpack(raw[3], [])
    apex_triggers, at_err  = _unpack(raw[4], [])
    flows, fl_err          = _unpack(raw[5], [])
    org_limits, ol_err     = _unpack(raw[6], {})
    custom_objs, co_err    = _unpack(raw[7], [])
    flexcards, fc_err      = _unpack(raw[8], [])
    business_rules, br_err = _unpack(raw[9], [])
    cml_rules, cml_err     = _unpack(raw[10], [])
    data_mappers, dm_err   = _unpack(raw[11], [])

    def _is_not_installed(err: str) -> bool:
        """True when the error just means the sObject doesn't exist in this org."""
        if not err:
            return False
        low = err.lower()
        return ("400" in low or "invalid_type" in low or "sObject type" in low.lower()
                or "not supported" in low or "does not support" in low)

    fetch_errors = {k: v for k, v in {
        "omniscripts": os_err, "dataraptors": dr_err,
        "integration_procedures": ip_err, "apex_classes": ac_err,
        "apex_triggers": at_err, "flows": fl_err,
        "org_limits": ol_err, "custom_objects": co_err,
        "flexcards": fc_err, "business_rules": br_err,
        "cml_rules": cml_err, "data_mappers": dm_err,
    }.items() if v and not _is_not_installed(v)}

    all_issues: list = []
    for r in omniscripts:    all_issues.extend(_analyze_omniscript(r))
    for r in dataraptors:    all_issues.extend(_analyze_dataraptor(r))
    for r in integrations:   all_issues.extend(_analyze_integration_procedure(r))
    for r in apex_classes:   all_issues.extend(_analyze_apex_class(r))
    all_issues.extend(_analyze_apex_triggers(apex_triggers))
    for r in flows:          all_issues.extend(_analyze_flow(r))
    all_issues.extend(_analyze_org_limits(org_limits))
    for r in custom_objs:    all_issues.extend(_analyze_custom_object(r))
    for r in business_rules: all_issues.extend(_analyze_business_rule(r))

    # SOQL analysis across all apex classes
    soql_findings = await _SOQLScanner().scan(apex_classes)
    for f in soql_findings:
        all_issues.append({
            "component": f.component_name,
            "component_type": "SOQL",
            "severity": f.severity.value,
            "issue": f"{f.rule_name}: {f.description}",
            "fix": f.suggested_fix or "",
            "current_code": f.current_code or "",
            "location": f.location or "",
            "impact": f.impact or "",
            "rule_id": f.rule_id,
        })

    attention_map: dict = {}
    for issue in all_issues:
        if issue["severity"] == "high":
            key = (issue["component"], issue["component_type"])
            attention_map.setdefault(key, []).append(issue["issue"])
    attention = [{"name": k[0], "type": k[1], "issues": v} for k, v in attention_map.items()]

    soql_count = len({i["component"] for i in all_issues if i.get("component_type") == "SOQL"})
    total = (len(omniscripts) + len(dataraptors) + len(integrations) +
             len(apex_classes) + len(apex_triggers) + len(flows) + len(custom_objs) +
             len(flexcards) + len(business_rules) + len(cml_rules) + len(data_mappers))

    limits_summary = {}
    for key, entry in (org_limits or {}).items():
        if isinstance(entry, dict) and entry.get("Max", 0) > 0:
            max_v = entry["Max"]
            remaining = entry.get("Remaining", max_v)
            limits_summary[key] = {
                "max": max_v, "remaining": remaining,
                "used": max_v - remaining,
                "pct": round(((max_v - remaining) / max_v) * 100, 1),
            }

    return {
        "instance_url": instance_url,
        "fetch_errors": fetch_errors,
        "summary": {
            "total_components": total,
            "omniscripts": len(omniscripts),
            "dataraptors": len(dataraptors),
            "integration_procedures": len(integrations),
            "flexcards": len(flexcards),
            "business_rules": len(business_rules),
            "cml_rules": len(cml_rules),
            "data_mappers": len(data_mappers),
            "soql_issues": soql_count,
            "apex_classes": len(apex_classes),
            "apex_triggers": len(apex_triggers),
            "flows": len(flows),
            "custom_objects": len(custom_objs),
            "total_issues": len(all_issues),
            "high": sum(1 for i in all_issues if i["severity"] == "high"),
            "medium": sum(1 for i in all_issues if i["severity"] == "medium"),
            "attention_required": len(attention),
        },
        "issues": all_issues,
        "attention": attention,
        "org_limits": limits_summary,
        "components": {
            "omniscripts":            [{"name": r.get("Name", ""), "id": r.get("Id", ""), "sub_type": r.get("SubType__c") or r.get("vlocity_cmt__SubType__c", "")} for r in omniscripts],
            "dataraptors":            [{"name": r.get("Name", ""), "id": r.get("Id", ""), "interface_type": r.get("InterfaceType__c") or r.get("vlocity_cmt__InterfaceType__c", "")} for r in dataraptors],
            "integration_procedures": [{"name": r.get("Name", ""), "id": r.get("Id", "")} for r in integrations],
            "apex_classes":           [{"name": r.get("Name", ""), "id": r.get("Id", ""), "api_version": r.get("ApiVersion", "")} for r in apex_classes],
            "apex_triggers":          [{"name": r.get("Name", ""), "id": r.get("Id", ""), "sub_type": r.get("TableEnumOrId", "")} for r in apex_triggers],
            "flows":                  [{"name": r.get("MasterLabel", ""), "id": r.get("Id", ""), "sub_type": r.get("ProcessType", "")} for r in flows],
            "custom_objects":         [{"name": r.get("DeveloperName", ""), "id": r.get("Id", ""), "sub_type": r.get("SharingModel", "")} for r in custom_objs],
            "flexcards":       [{"name": r.get("Name") or r.get("FlexcardName", ""), "id": r.get("Id", ""), "author": r.get("Author", "")} for r in flexcards],
            "business_rules":  [{"name": r.get("Name", ""), "id": r.get("Id", ""), "is_active": bool(r.get("IsActive") or r.get("vlocity_cmt__IsActive__c")), "sub_type": r.get("_bre_type", "BusinessRule"), "status": r.get("Status", "")} for r in business_rules],
            "cml_rules":       [{"name": r.get("Name", ""), "id": r.get("Id", "")} for r in cml_rules],
            "data_mappers":    [{"name": r.get("Name", ""), "id": r.get("Id", ""), "sub_type": r.get("sub_type", "DataMapping")} for r in data_mappers],
        },
    }


@router.get("/agents/org/debug")
async def org_debug(request: Request):
    """Returns which OmniStudio-related sObjects exist in this org — useful for diagnosing empty scans."""
    token, instance_url = _require_auth(request)
    sf = SalesforceClient(token, instance_url)
    targets = [
        "OmniProcess", "OmniDataTransform", "OmniIntegrationProcedure",
        "vlocity_cmt__OmniScript__c", "vlocity_cmt__DRBundle__c",
        "vlocity_cmt__IntegrationProcedure__c",
    ]
    found = []
    missing = []
    for name in targets:
        exists = await sf.sobject_exists(name)
        (found if exists else missing).append(name)
    # Also try a quick count query on OmniProcess
    counts = {}
    for obj in found:
        try:
            result = await sf.query(f"SELECT COUNT() FROM {obj}")
            counts[obj] = result.get("totalSize", 0)
        except Exception as e:
            counts[obj] = f"query error: {e}"
    return {"found": found, "missing": missing, "counts": counts}


@router.get("/agents/model-info")
async def model_info():
    """Returns the active AI provider and model so the UI can display it."""
    llmgw_key = (
        settings.LLMGW_API_KEY
        or os.environ.get("LLMGW_API_KEY", "")
        or _read_file_key(Path.home() / ".config/opencode/.llmgw-key")
    )
    if llmgw_key:
        return {"provider": "llmgw", "model": settings.LLMGW_MODEL, "base_url": settings.LLMGW_BASE_URL}
    return {"provider": "anthropic", "model": settings.ANTHROPIC_DEFAULT_SONNET_MODEL}


@router.get("/agents/available-models")
async def available_models():
    """Returns selectable models for the active provider."""
    llmgw_key = (
        settings.LLMGW_API_KEY
        or os.environ.get("LLMGW_API_KEY", "")
        or _read_file_key(Path.home() / ".config/opencode/.llmgw-key")
    )
    if llmgw_key:
        return {
            "provider": "llmgw",
            "active": settings.LLMGW_MODEL,
            "models": [{"id": settings.LLMGW_MODEL, "label": settings.LLMGW_MODEL}],
        }
    return {
        "provider": "anthropic",
        "active": settings.ANTHROPIC_DEFAULT_SONNET_MODEL,
        "models": [
            {"id": "claude-opus-4-5-20250929",   "label": "Opus 4.5 — Most capable"},
            {"id": "claude-sonnet-4-5-20250929",  "label": "Sonnet 4.5 — Balanced"},
            {"id": "claude-haiku-4-5-20250929",   "label": "Haiku 4.5 — Fast"},
            {"id": "claude-sonnet-4-7-20250219",  "label": "Sonnet 4.7"},
            {"id": "claude-opus-4-0",             "label": "Opus 4.0"},
        ],
    }


@router.get("/agents")
async def list_agents() -> List[Dict[str, Any]]:
    return get_agents_list()


@router.post("/chat/{agent_id}")
async def chat(agent_id: str, request: Request, body: ChatRequest):
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    llmgw_key_available = bool(
        settings.LLMGW_API_KEY
        or os.environ.get("LLMGW_API_KEY", "")
        or _read_file_key(Path.home() / ".config/opencode/.llmgw-key")
    )
    if not settings.ANTHROPIC_API_KEY and not llmgw_key_available:
        raise HTTPException(status_code=503, detail="No AI provider configured — set ANTHROPIC_API_KEY or ensure ~/.config/opencode/.llmgw-key exists")

    system_prompt = agent["system_prompt"]
    user_msg_text = body.messages[-1].content if body.messages else ""

    # For the general_expert (Professor), dynamically inject the matching skill(s)
    if agent_id == "general_expert" and user_msg_text:
        skill_content = skill_for_message(user_msg_text)
        if skill_content:
            system_prompt = (
                system_prompt
                + "\n\n=== REFERENCE KNOWLEDGE ===\n"
                + "Use the following best-practice knowledge to answer questions precisely.\n\n"
                + skill_content
            )

    if body.org_context:
        access_token = request.session.get("access_token")
        instance_url = request.session.get("instance_url")
        if access_token and instance_url:
            sf = SalesforceClient(access_token, instance_url)
            fetcher = _ORG_FETCHERS.get(agent_id)
            user_msg = user_msg_text
            if fetcher:
                try:
                    org_data = await fetcher(sf, user_msg)
                except Exception as ex:
                    org_data = f"[Error fetching org data: {ex}]"
            else:
                # Agent has no specialist fetcher — give it the apex class list as a baseline
                try:
                    org_data = await _fetch_apex_context(sf, user_msg)
                except Exception as ex:
                    org_data = f"[Org connected: {instance_url}. Could not load org data: {ex}]"
            system_prompt = (
                system_prompt
                + f"\n\n=== LIVE DATA FROM SALESFORCE ORG ({instance_url}) ===\n"
                + org_data
                + "\n\nUse the above REAL data from the org to answer the user's question. "
                "Do NOT generate hypothetical code to fetch data — you already have it above. "
                "Provide a concrete analysis based on what is actually in the org."
            )

    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    async def stream_response():
        try:
            # Resolve llmgw API key: settings → env var → key file used by opencode
            llmgw_key = (
                settings.LLMGW_API_KEY
                or os.environ.get("LLMGW_API_KEY", "")
                or _read_file_key(Path.home() / ".config/opencode/.llmgw-key")
            )

            if llmgw_key:
                # ── llmgw path (OpenAI-compatible) ────────────────────────────
                from openai import AsyncOpenAI
                llmgw_client = AsyncOpenAI(
                    api_key=llmgw_key,
                    base_url=settings.LLMGW_BASE_URL,
                )
                oai_messages = [{"role": "system", "content": system_prompt}] + messages
                active_model = body.model or settings.LLMGW_MODEL
                stream = await llmgw_client.chat.completions.create(
                    model=active_model,
                    messages=oai_messages,
                    max_tokens=4096,
                    stream=True,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        yield "data: " + json.dumps({"text": delta}) + "\n\n"
            else:
                # ── Anthropic fallback ────────────────────────────────────────
                client_kwargs = {"api_key": settings.ANTHROPIC_API_KEY or "placeholder"}
                if settings.ANTHROPIC_BASE_URL:
                    client_kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
                if settings.ANTHROPIC_CUSTOM_HEADERS:
                    headers = {}
                    for part in settings.ANTHROPIC_CUSTOM_HEADERS.split(","):
                        part = part.strip()
                        if ": " in part:
                            k, v = part.split(": ", 1)
                            headers[k.strip()] = v.strip()
                    if headers:
                        client_kwargs["default_headers"] = headers
                active_model = body.model or settings.ANTHROPIC_DEFAULT_SONNET_MODEL
                anth_client = anthropic.AsyncAnthropic(**client_kwargs)
                async with anth_client.messages.stream(
                    model=active_model,
                    max_tokens=2048,
                    system=system_prompt,
                    messages=messages,
                ) as stream:
                    async for text in stream.text_stream:
                        yield "data: " + json.dumps({"text": text}) + "\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            yield "data: " + json.dumps({"error": str(e)}) + "\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/tool/{agent_id}")
async def chat_with_tools(agent_id: str, request: Request, body: ChatRequest):
    """Agentic chat endpoint — Claude calls SF tools (query/create/describe) in a loop."""
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    access_token = request.session.get("access_token")
    instance_url = request.session.get("instance_url")
    if not access_token or not instance_url:
        raise HTTPException(status_code=401, detail="Not authenticated — connect your Salesforce org first")

    sf = SalesforceClient(access_token, instance_url)
    system_prompt = agent["system_prompt"]
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    llmgw_key = (
        settings.LLMGW_API_KEY
        or os.environ.get("LLMGW_API_KEY", "")
        or _read_file_key(Path.home() / ".config/opencode/.llmgw-key")
    )

    async def stream_response():
        try:
            loop_messages = list(messages)
            max_iterations = 6

            for _iteration in range(max_iterations):
                if llmgw_key:
                    # ── OpenAI-compatible (llmgw) tool-calling path ────────────
                    from openai import AsyncOpenAI
                    llmgw_client = AsyncOpenAI(api_key=llmgw_key, base_url=settings.LLMGW_BASE_URL)
                    oai_messages = [{"role": "system", "content": system_prompt}] + loop_messages
                    response = await llmgw_client.chat.completions.create(
                        model=body.model or settings.LLMGW_MODEL,
                        messages=oai_messages,
                        tools=TOOL_DEFINITIONS_OPENAI,
                        tool_choice="auto",
                        max_tokens=4096,
                    )
                    choice = response.choices[0]
                    finish_reason = choice.finish_reason
                    msg = choice.message

                    if finish_reason == "tool_calls" and msg.tool_calls:
                        tool_results = []
                        for tc in msg.tool_calls:
                            fn = tc.function
                            try:
                                inputs = json.loads(fn.arguments)
                            except Exception:
                                inputs = {}
                            yield "data: " + json.dumps({
                                "tool_call": {"name": fn.name, "input": inputs}
                            }) + "\n\n"
                            result = await execute_tool(fn.name, inputs, sf)
                            tool_results.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": json.dumps(result),
                            })

                        loop_messages.append({"role": "assistant", "tool_calls": [
                            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                            for tc in msg.tool_calls
                        ]})
                        loop_messages.extend(tool_results)

                    else:
                        text = msg.content or ""
                        chunk_size = 20
                        for i in range(0, len(text), chunk_size):
                            yield "data: " + json.dumps({"text": text[i:i + chunk_size]}) + "\n\n"
                        break

                else:
                    # ── Anthropic tool-calling path ────────────────────────────
                    client_kwargs: dict = {"api_key": settings.ANTHROPIC_API_KEY or "placeholder"}
                    if settings.ANTHROPIC_BASE_URL:
                        client_kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
                    if settings.ANTHROPIC_CUSTOM_HEADERS:
                        hdrs: dict = {}
                        for part in settings.ANTHROPIC_CUSTOM_HEADERS.split(","):
                            part = part.strip()
                            if ": " in part:
                                k, v = part.split(": ", 1)
                                hdrs[k.strip()] = v.strip()
                        if hdrs:
                            client_kwargs["default_headers"] = hdrs

                    anth_client = anthropic.AsyncAnthropic(**client_kwargs)
                    response = await anth_client.messages.create(
                        model=body.model or settings.ANTHROPIC_DEFAULT_SONNET_MODEL,
                        max_tokens=4096,
                        system=system_prompt,
                        tools=TOOL_DEFINITIONS,
                        messages=loop_messages,
                    )

                    if response.stop_reason == "tool_use":
                        tool_results = []
                        assistant_content = []

                        for block in response.content:
                            assistant_content.append(block)
                            if block.type == "tool_use":
                                yield "data: " + json.dumps({
                                    "tool_call": {"name": block.name, "input": block.input}
                                }) + "\n\n"
                                result = await execute_tool(block.name, block.input, sf)
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": json.dumps(result),
                                })

                        loop_messages.append({"role": "assistant", "content": assistant_content})
                        loop_messages.append({"role": "user", "content": tool_results})

                    else:
                        final_text = ""
                        for block in response.content:
                            if hasattr(block, "text"):
                                final_text += block.text
                        chunk_size = 20
                        for i in range(0, len(final_text), chunk_size):
                            yield "data: " + json.dumps({"text": final_text[i:i + chunk_size]}) + "\n\n"
                        break

            yield "data: [DONE]\n\n"

        except Exception as e:
            yield "data: " + json.dumps({"error": str(e)}) + "\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
