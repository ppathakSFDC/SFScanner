import asyncio
from fastapi import APIRouter, Request, HTTPException

from ..salesforce.client import SalesforceClient

router = APIRouter()


def _score(findings: list) -> int:
    deductions = {"critical": 20, "high": 12, "medium": 6, "low": 2}
    return max(0, 100 - sum(deductions.get(f.get("severity", "low").lower(), 2) for f in findings))


def _f(rule_id, name, severity, description, fix="", component=""):
    return {"rule_id": rule_id, "rule_name": name, "severity": severity,
            "description": description, "suggested_fix": fix, "component": component}


async def _safe(coro):
    try:
        return await coro
    except Exception:
        return None


# ── DATA QUALITY ─────────────────────────────────────────────────────────────

async def check_data_quality(sf: SalesforceClient) -> dict:
    findings = []

    checks = await asyncio.gather(
        _safe(sf.query("SELECT COUNT() FROM Contact WHERE Email = null AND IsDeleted = false")),
        _safe(sf.query("SELECT COUNT() FROM Contact WHERE AccountId = null AND IsDeleted = false")),
        _safe(sf.query("SELECT COUNT() FROM Account WHERE Phone = null AND IsDeleted = false")),
        _safe(sf.query("SELECT COUNT() FROM Case WHERE IsClosed = false AND CreatedDate < LAST_N_DAYS:30 AND IsDeleted = false")),
        _safe(sf.query("SELECT COUNT() FROM Lead WHERE IsConverted = false AND CreatedDate < LAST_N_DAYS:90 AND IsDeleted = false")),
        _safe(sf.query("SELECT COUNT() FROM Account WHERE Id NOT IN (SELECT AccountId FROM Contact WHERE AccountId != null) AND IsDeleted = false")),
    )

    contact_no_email, contact_no_acct, acct_no_phone, old_cases, stale_leads, acct_no_contact = checks

    if contact_no_email and (n := contact_no_email.get("totalSize", 0)) > 0:
        findings.append(_f("DQ-001", "Contacts missing Email",
            "high" if n > 500 else "medium" if n > 100 else "low",
            f"{n:,} Contact records have no Email address.",
            "Run a data cleanse or add a validation rule to require Email on new Contacts."))

    if contact_no_acct and (n := contact_no_acct.get("totalSize", 0)) > 0:
        findings.append(_f("DQ-002", "Contacts not linked to an Account",
            "medium" if n > 100 else "low",
            f"{n:,} Contacts have no AccountId.",
            "Associate orphaned Contacts to Accounts or archive if stale."))

    if acct_no_contact and (n := acct_no_contact.get("totalSize", 0)) > 0:
        findings.append(_f("DQ-003", "Accounts with no Contacts",
            "medium" if n > 200 else "low",
            f"{n:,} Account records have no associated Contacts.",
            "Review whether these accounts are stale candidates for archiving."))

    if old_cases and (n := old_cases.get("totalSize", 0)) > 0:
        findings.append(_f("DQ-004", "Cases open longer than 30 days",
            "high" if n > 100 else "medium",
            f"{n:,} Cases have been open for more than 30 days.",
            "Review SLA policies and escalation rules for long-running cases."))

    if stale_leads and (n := stale_leads.get("totalSize", 0)) > 0:
        findings.append(_f("DQ-005", "Unconverted Leads older than 90 days",
            "medium" if n > 500 else "low",
            f"{n:,} Leads older than 90 days have never been converted.",
            "Add an automated lead recycling or archiving process."))

    if acct_no_phone and (n := acct_no_phone.get("totalSize", 0)) > 0:
        findings.append(_f("DQ-006", "Accounts missing Phone",
            "low",
            f"{n:,} Account records have no Phone number.",
            "Consider a validation rule or data enrichment to populate Phone on Accounts."))

    return {"domain": "Data Quality", "score": _score(findings), "findings": findings}


# ── USER ADOPTION ─────────────────────────────────────────────────────────────

async def check_user_adoption(sf: SalesforceClient) -> dict:
    findings = []

    checks = await asyncio.gather(
        _safe(sf.query("SELECT COUNT() FROM User WHERE IsActive = true AND LastLoginDate < LAST_N_DAYS:90 AND UserType = 'Standard'")),
        _safe(sf.query("SELECT COUNT() FROM User WHERE IsActive = true AND LastLoginDate = null AND UserType = 'Standard'")),
        _safe(sf.query("SELECT COUNT() FROM Report WHERE LastRunDate < LAST_N_DAYS:180")),
        _safe(sf.query("SELECT COUNT() FROM Dashboard WHERE LastViewedDate < LAST_N_DAYS:90")),
        _safe(sf.query("SELECT COUNT() FROM User WHERE IsActive = true AND UserType = 'Standard'")),
    )

    inactive, never_logged, stale_reports, stale_dashboards, total_active = checks

    if inactive and (n := inactive.get("totalSize", 0)) > 0:
        findings.append(_f("UA-001", "Inactive licensed users (no login >90 days)",
            "high" if n > 20 else "medium" if n > 5 else "low",
            f"{n:,} active licensed users have not logged in for 90+ days.",
            "Deactivate unused licences to free seats and reduce the org's attack surface."))

    if never_logged and (n := never_logged.get("totalSize", 0)) > 0:
        findings.append(_f("UA-002", "Active users who have never logged in",
            "medium" if n > 5 else "low",
            f"{n:,} active users have never logged in.",
            "Verify these accounts still need access; deactivate if not required."))

    if stale_reports and (n := stale_reports.get("totalSize", 0)) > 0:
        findings.append(_f("UA-003", "Reports not run in 180 days",
            "low",
            f"{n:,} reports have not been run in the last 180 days.",
            "Archive or delete unused reports to keep the org clean."))

    if stale_dashboards and (n := stale_dashboards.get("totalSize", 0)) > 0:
        findings.append(_f("UA-004", "Dashboards not viewed in 90 days",
            "low",
            f"{n:,} dashboards have not been viewed in 90 days.",
            "Review and archive dashboards that are no longer in use."))

    return {"domain": "User Adoption", "score": _score(findings), "findings": findings}


# ── INTEGRATION HEALTH ────────────────────────────────────────────────────────

async def check_integrations(sf: SalesforceClient) -> dict:
    findings = []

    checks = await asyncio.gather(
        _safe(sf.tooling_query("SELECT Id, Name, OptionsAllowAdminApprovedUsersOnly FROM ConnectedApplication")),
        _safe(sf.tooling_query("SELECT Id, EndpointUrl, IsActive FROM RemoteSiteSetting WHERE IsActive = true")),
        _safe(sf.tooling_query("SELECT COUNT() FROM NamedCredential")),
        _safe(sf.tooling_query("SELECT COUNT() FROM WorkflowOutboundMessage")),
    )

    connected_apps, remote_sites, named_creds, outbound_msgs = checks

    if connected_apps:
        unrestricted = [a["Name"] for a in connected_apps.get("records", [])
                        if not a.get("OptionsAllowAdminApprovedUsersOnly")]
        if unrestricted:
            findings.append(_f("INT-001", "Connected Apps without user restriction",
                "high" if len(unrestricted) > 3 else "medium",
                f"{len(unrestricted)} Connected App(s) not restricted to admin-approved users: {', '.join(unrestricted[:5])}.",
                "Enable 'Admin approved users are pre-authorised' on each Connected App."))

    if remote_sites:
        broad = [r["EndpointUrl"] for r in remote_sites.get("records", [])
                 if r.get("EndpointUrl", "").rstrip("/") in ("http://", "https://", "http://*", "https://*")]
        if broad:
            findings.append(_f("INT-002", "Overly broad Remote Site Settings",
                "high",
                "Remote Site Settings with wildcard or root-level URLs allow callouts to any endpoint.",
                "Restrict each Remote Site Setting to a specific hostname."))

    if named_creds and named_creds.get("totalSize", 0) == 0:
        findings.append(_f("INT-003", "No Named Credentials configured",
            "medium",
            "No Named Credentials found. External callouts may use hardcoded URLs or credentials in Apex.",
            "Migrate external endpoint URLs and credentials to Named Credentials."))

    if outbound_msgs and (n := outbound_msgs.get("totalSize", 0)) > 0:
        findings.append(_f("INT-004", "Legacy Outbound Messages in use",
            "low",
            f"{n} Outbound Message(s) found. These are legacy workflow actions being retired by Salesforce.",
            "Migrate outbound messages to Flow-based integrations or Platform Events."))

    return {"domain": "Integration Health", "score": _score(findings), "findings": findings}


# ── DEVOPS & RELEASE ──────────────────────────────────────────────────────────

async def check_devops(sf: SalesforceClient) -> dict:
    findings = []

    checks = await asyncio.gather(
        _safe(sf.tooling_query("SELECT PercentCovered FROM ApexOrgWideCoverage")),
        _safe(sf.query("SELECT COUNT() FROM FlowDefinitionView WHERE ActiveVersionId = null AND IsTemplate = false")),
        _safe(sf.query("SELECT COUNT() FROM FlowVersionView WHERE Status = 'Obsolete'")),
        _safe(sf.query("SELECT COUNT() FROM PackageLicense WHERE Status = 'Active'")),
        _safe(sf.query("SELECT COUNT() FROM FlowDefinitionView WHERE ProcessType = 'Workflow' AND ActiveVersionId != null")),
    )

    coverage, inactive_flows, obsolete_versions, packages, process_builders = checks

    if coverage and coverage.get("records"):
        pct = coverage["records"][0].get("PercentCovered", 0)
        if pct < 75:
            findings.append(_f("DO-001", f"Apex test coverage critically low ({pct}%)",
                "critical" if pct < 50 else "high",
                f"Org-wide Apex test coverage is {pct}%, below Salesforce's 75% deployment requirement.",
                "Add test methods to classes with low coverage; use ApexCodeCoverageAggregate to identify them."))
        elif pct < 85:
            findings.append(_f("DO-001", f"Apex test coverage below recommended ({pct}%)",
                "low",
                f"Coverage is {pct}%. Best practice is 85%+.",
                "Add assertions to existing test methods and cover edge cases."))

    if inactive_flows and (n := inactive_flows.get("totalSize", 0)) > 0:
        findings.append(_f("DO-002", "Flows with no active version",
            "low",
            f"{n} Flow definition(s) have never been activated.",
            "Activate or delete unused Flow definitions."))

    if obsolete_versions and (n := obsolete_versions.get("totalSize", 0)) > 50:
        findings.append(_f("DO-003", f"{n} obsolete Flow versions accumulating",
            "low",
            f"{n} obsolete Flow versions are consuming metadata storage.",
            "Delete old versions in Setup → Flows → Manage Versions."))

    if packages and (n := packages.get("totalSize", 0)) > 0:
        findings.append(_f("DO-004", f"{n} managed package(s) — verify versions",
            "low",
            f"{n} active managed package licence(s). Outdated packages may contain security vulnerabilities.",
            "Review each package in Setup → Installed Packages and check AppExchange for updates."))

    if process_builders and (n := process_builders.get("totalSize", 0)) > 0:
        findings.append(_f("DO-005", "Active Process Builder automations",
            "medium" if n > 10 else "low",
            f"{n} active Process Builder flow(s) found. Salesforce is retiring Process Builder.",
            "Migrate Process Builder automations to Flow before the retirement deadline."))

    return {"domain": "DevOps & Release", "score": _score(findings), "findings": findings}


# ── FULL ASSESSMENT ───────────────────────────────────────────────────────────

@router.get("/assessment/full")
async def full_assessment(request: Request):
    access_token = request.session.get("access_token")
    instance_url = request.session.get("instance_url")
    if not access_token or not instance_url:
        raise HTTPException(status_code=401, detail="Not authenticated — connect your Salesforce org first")

    sf = SalesforceClient(access_token, instance_url)

    results = await asyncio.gather(
        check_data_quality(sf),
        check_user_adoption(sf),
        check_integrations(sf),
        check_devops(sf),
        return_exceptions=True,
    )

    domains = []
    for r in results:
        if isinstance(r, Exception):
            domains.append({"domain": "Error", "score": 0, "findings": [], "error": str(r)})
        else:
            domains.append(r)

    scores = [d["score"] for d in domains if "score" in d]
    overall = round(sum(scores) / len(scores)) if scores else 0

    all_findings = []
    for d in domains:
        for f in d.get("findings", []):
            all_findings.append({**f, "domain": d["domain"]})

    # Sort findings by severity
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_findings.sort(key=lambda f: sev_order.get(f.get("severity", "low").lower(), 4))

    return {
        "overall_score": overall,
        "instance_url": instance_url,
        "domains": domains,
        "all_findings": all_findings,
        "total_findings": len(all_findings),
        "critical_count": sum(1 for f in all_findings if f.get("severity") == "critical"),
        "high_count": sum(1 for f in all_findings if f.get("severity") == "high"),
    }
