"""Org-level security configuration scanner."""
from .base import BaseScanner
from ..models.findings import ComponentType, Severity


class SecurityScanner(BaseScanner):
    component_type = ComponentType.SECURITY

    async def scan(self, org_settings: dict) -> list:
        """
        org_settings keys:
          - "security_settings": dict from GET /services/data/v62.0/settings/Security
          - "connected_apps": list of connected app dicts
          - "entity_sharing": list of {QualifiedApiName, InternalSharingModel, ExternalSharingModel}
          - "guest_profile": dict with guest profile permissions (or None)
        """
        findings = []

        sec = org_settings.get("security_settings", {})
        apps = org_settings.get("connected_apps", [])
        sharing = org_settings.get("entity_sharing", [])

        # SORG-001: HTTPS not enforced
        if sec.get("enableHttpsRequirement") is False or sec.get("enforceHttps") is False:
            findings.append(self._finding(
                "Org Security", "SORG-001", "HTTPS Not Enforced",
                Severity.CRITICAL,
                "The org does not enforce HTTPS for all connections. Data can be transmitted in plaintext.",
                suggested_fix="Enable 'Require HTTPS' in Setup > Session Settings.",
                impact="Session tokens and data exposed to network eavesdropping/man-in-the-middle attacks.",
            ))

        # SORG-002: Login as any user enabled (admin privilege escalation)
        if sec.get("enableAdminLoginAsAny") is True:
            findings.append(self._finding(
                "Org Security", "SORG-002", "Login-As-Any-User Enabled",
                Severity.HIGH,
                "Administrators can log in as any user without that user's credentials.",
                suggested_fix="Disable in Setup > Session Settings > 'Allow Admins to Log in as Any User' unless legally required.",
                impact="Complicates audit trails and enables admins to bypass per-user access controls.",
            ))

        # SORG-003: Clickjack protection disabled
        if sec.get("enableClickjackNonsetupUserHeaderless") is False or sec.get("enableClickjackNonsetupUser") is False:
            findings.append(self._finding(
                "Org Security", "SORG-003", "Clickjack Protection Disabled",
                Severity.HIGH,
                "X-Frame-Options is not set, leaving Visualforce pages vulnerable to clickjacking attacks.",
                suggested_fix="Enable clickjack protection for all pages in Setup > Session Settings.",
                impact="Attackers can embed Salesforce pages in malicious iframes to trick users into unintended actions.",
            ))

        # SORG-004: CSRF protection disabled on GET requests
        if sec.get("enableCsrfOnGet") is False:
            findings.append(self._finding(
                "Org Security", "SORG-004", "CSRF Protection Disabled on GET Requests",
                Severity.MEDIUM,
                "CSRF token validation is disabled for GET requests, increasing CSRF attack surface.",
                suggested_fix="Enable CSRF protection for GET requests in Setup > Session Settings.",
                impact="Cross-site request forgery attacks possible on read-heavy operations.",
            ))

        # SORG-005: Connected apps with all-user access
        for app in apps:
            if app.get("OptionsAllowAllProfiles") is True:
                findings.append(self._finding(
                    f"Connected App: {app.get('Name', 'Unknown')}",
                    "SORG-005", "Connected App Grants Access to All Profiles",
                    Severity.HIGH,
                    f"Connected App '{app.get('Name')}' is configured to allow ALL profiles — any user can authorize it.",
                    suggested_fix="Restrict the connected app to specific profiles or permission sets in Setup > Connected Apps.",
                    impact="A compromised or malicious connected app can impersonate any user in the org.",
                ))

        # SORG-006: Public Read/Write OWD on custom objects
        for entity in sharing:
            name = entity.get("QualifiedApiName", "")
            if not name.endswith("__c"):
                continue
            internal = entity.get("InternalSharingModel", "")
            if internal in ("ReadWrite", "Read", "ControlledByLeadOrContact"):
                findings.append(self._finding(
                    f"Object: {name}",
                    "SORG-006", "Org-Wide Default Too Permissive (Internal)",
                    Severity.MEDIUM,
                    f"Custom object '{name}' has internal OWD of '{internal}', granting broad access without explicit sharing.",
                    suggested_fix="Set OWD to Private and use sharing rules, role hierarchy, or manual sharing for controlled access.",
                    impact="All internal users can read (or write) records they should not have access to.",
                ))

        # SORG-007: Guest users have record access on custom objects
        for entity in sharing:
            name = entity.get("QualifiedApiName", "")
            external = entity.get("ExternalSharingModel", "")
            if external in ("ReadWrite", "Read") and name.endswith("__c"):
                findings.append(self._finding(
                    f"Object: {name}",
                    "SORG-007", "Guest Users Have Record Access",
                    Severity.HIGH,
                    f"Custom object '{name}' has ExternalSharingModel='{external}', granting unauthenticated guest users record access.",
                    suggested_fix="Set External OWD to Private. Use authenticated sites or explicitly grant access to specific records.",
                    impact="Unauthenticated users can access or modify CRM data via Experience Cloud sites.",
                ))

        return findings
