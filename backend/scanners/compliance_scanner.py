"""PII and data compliance scanner."""
import re
from .base import BaseScanner
from ..models.findings import ComponentType, Severity


_PII_PATTERNS = re.compile(
    r"(?:ssn|social.?sec|passport|date.?of.?birth|dob|tax.?id|national.?id|"
    r"credit.?card|card.?number|cvv|routing.?num|bank.?account|"
    r"health|diagnosis|medical|patient|phi|hipaa|"
    r"driver.?lic|driv.?lic|gender|ethnic|race|religion|biometric)",
    re.IGNORECASE,
)

_SENSITIVE_OBJ_PATTERNS = re.compile(
    r"(?:patient|medical|health|clinical|phi|hipaa|payment|financial|"
    r"credit|banking|personal|pii|sensitive|ssn|confidential)",
    re.IGNORECASE,
)


class ComplianceScanner(BaseScanner):
    component_type = ComponentType.COMPLIANCE

    async def scan(self, field_data: dict) -> list:
        """
        field_data keys:
          - "custom_fields": list of {QualifiedApiName, Label, DataType, IsEncrypted,
                              EntityDefinitionId, EntityDefinition.QualifiedApiName}
          - "tracked_fields": list of {ParentId, FieldName}
          - "object_names": list of custom object ApiNames
        """
        findings = []

        fields = field_data.get("custom_fields", [])
        tracked = {f.get("FieldName", "").lower() for f in field_data.get("tracked_fields", [])}

        # COMP-001: PII field not encrypted
        for f in fields:
            api_name = f.get("QualifiedApiName", "")
            label = f.get("Label", "")
            encrypted = f.get("IsEncrypted", False)
            obj_name = (f.get("EntityDefinition") or {}).get("QualifiedApiName", "")

            if _PII_PATTERNS.search(api_name) or _PII_PATTERNS.search(label):
                if not encrypted:
                    findings.append(self._finding(
                        f"{obj_name}.{api_name}",
                        "COMP-001", "PII Field Without Encryption",
                        Severity.HIGH,
                        f"Field '{api_name}' on '{obj_name}' appears to contain PII but is not encrypted.",
                        suggested_fix="Enable Shield Platform Encryption for this field, or mask it using a formula field for display.",
                        impact="PII data stored in plaintext is exposed in backups, data exports, and admin tooling.",
                    ))

        # COMP-002: PII field without field history tracking
        for f in fields:
            api_name = f.get("QualifiedApiName", "")
            label = f.get("Label", "")
            obj_name = (f.get("EntityDefinition") or {}).get("QualifiedApiName", "")

            if _PII_PATTERNS.search(api_name) or _PII_PATTERNS.search(label):
                if api_name.lower() not in tracked:
                    findings.append(self._finding(
                        f"{obj_name}.{api_name}",
                        "COMP-002", "PII Field Without Audit Trail",
                        Severity.MEDIUM,
                        f"PII field '{api_name}' on '{obj_name}' does not have field history tracking enabled.",
                        suggested_fix="Enable Field History Tracking for this field to maintain a GDPR-compliant audit trail of changes.",
                        impact="Cannot demonstrate data modification audit trail, required for GDPR Article 5(2) accountability.",
                    ))

        # COMP-003: Sensitive custom object detected by name
        for obj_name in field_data.get("object_names", []):
            if _SENSITIVE_OBJ_PATTERNS.search(obj_name):
                findings.append(self._finding(
                    obj_name,
                    "COMP-003", "Sensitive Custom Object Detected",
                    Severity.MEDIUM,
                    f"Custom object '{obj_name}' appears to hold sensitive/personal data based on its name.",
                    suggested_fix="Review this object's sharing model, field-level security, and encryption configuration. Ensure a data retention policy is in place.",
                    impact="Sensitive data objects require stricter access controls, retention policies, and encryption under GDPR/HIPAA/SOC2.",
                ))

        return findings
