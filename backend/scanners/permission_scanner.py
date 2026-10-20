from .base import BaseScanner
from ..models.findings import Finding, ComponentType, Severity


_DANGEROUS_SYSTEM_PERMS = {
    "ViewAllData": (
        "PERM-001", "ViewAllData Permission Granted", Severity.CRITICAL,
        "Profile/PermSet grants ViewAllData — user can read ALL records in the org regardless of sharing rules.",
        "Revoke ViewAllData and use sharing rules, permission sets scoped to specific objects, "
        "or territory management to limit record access appropriately.",
        "Violates principle of least privilege. Any compromise of this user exposes ALL org data.",
    ),
    "ModifyAllData": (
        "PERM-002", "ModifyAllData Permission Granted", Severity.CRITICAL,
        "Profile/PermSet grants ModifyAllData — user can edit/delete ALL records bypassing all sharing.",
        "Revoke ModifyAllData. Grant object-level CRUD + sharing rules instead.",
        "A compromised account with ModifyAllData can destroy or corrupt the entire org's data.",
    ),
    "ManageUsers": (
        "PERM-003", "ManageUsers Permission Granted", Severity.HIGH,
        "Profile/PermSet grants ManageUsers — user can create/edit other users, change profiles, and reset passwords.",
        "Restrict ManageUsers to dedicated admin profiles. Audit all users with this permission quarterly.",
        "Allows privilege escalation: a user with ManageUsers can grant themselves ViewAllData.",
    ),
    "AuthorApex": (
        "PERM-004", "Author Apex Permission Granted", Severity.HIGH,
        "Profile/PermSet grants Author Apex — user can write and execute arbitrary Apex code in production.",
        "Restrict to developers in sandboxes. Use deployment processes (CI/CD) for production Apex changes.",
        "Allows complete bypass of all security controls via Execute Anonymous.",
    ),
    "InstallPackaging": (
        "PERM-005", "InstallPackaging Permission Granted", Severity.MEDIUM,
        "Profile/PermSet grants permission to install packages. Malicious packages can execute arbitrary code.",
        "Restrict package installation to System Administrators only.",
        "Rogue package installation can compromise org integrity and data.",
    ),
    "ApiEnabled": (
        "PERM-006", "API Access Granted to Non-Admin Profile", Severity.MEDIUM,
        "Profile/PermSet grants API access — enables external system integration and bulk data extraction.",
        "Review which profiles genuinely need API access. Restrict to integration users and developers only.",
        "Broad API access enables large-scale data extraction bypassing record-level sharing rules.",
    ),
    "BulkApiHardDelete": (
        "PERM-007", "Bulk API Hard Delete Permission Granted", Severity.HIGH,
        "Profile/PermSet grants BulkApiHardDelete — enables permanent, unrecoverable deletion of records via Bulk API.",
        "Revoke BulkApiHardDelete from all profiles except dedicated admin/ETL service accounts.",
        "Hard delete bypasses the recycle bin, making accidental or malicious mass-deletion unrecoverable.",
    ),
    "ManageEncryptionKeys": (
        "PERM-008", "Manage Encryption Keys Permission Granted", Severity.CRITICAL,
        "Profile/PermSet grants ManageEncryptionKeys — user can export, rotate, or destroy platform encryption keys.",
        "Restrict to a single break-glass admin account with MFA enforced. Audit quarterly.",
        "Compromise of this permission allows decryption of all Shield Platform Encryption protected data.",
    ),
}


class PermissionScanner(BaseScanner):
    component_type = ComponentType.PERMISSION

    async def scan(self, components: list[dict]) -> list[Finding]:
        findings = []
        for perm in components:
            name = perm.get("Name") or perm.get("Label", "Unknown")
            cid = perm.get("Id")
            ptype = perm.get("_type", "PermissionSet")
            findings.extend(self._check_permissions(name, perm, cid, ptype))
        return findings

    def _check_permissions(self, name: str, perm: dict, cid: str, ptype: str) -> list[Finding]:
        findings = []
        for perm_name, rule in _DANGEROUS_SYSTEM_PERMS.items():
            field_key = f"Permissions{perm_name}"
            if perm.get(field_key) is True:
                rule_id, rule_name, severity, description, fix, impact = rule
                findings.append(self._finding(
                    f"{ptype}: {name}", rule_id, rule_name, severity,
                    description,
                    component_id=cid,
                    suggested_fix=fix,
                    impact=impact,
                    effort="low",
                ))
        return findings
