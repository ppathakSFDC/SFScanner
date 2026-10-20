import json
from .base import BaseScanner
from ..models.findings import Finding, ComponentType, Severity


class DataRaptorScanner(BaseScanner):
    component_type = ComponentType.DATARAPTOR

    async def scan(self, components: list[dict]) -> list[Finding]:
        findings = []
        for dr in components:
            name = dr.get("Name", "Unknown")
            cid = dr.get("Id")
            dr_type = (
                dr.get("InterfaceType__c")
                or dr.get("vlocity_cmt__InterfaceType__c")
                or "Unknown"
            )
            prop_set = (
                dr.get("PropertySet__c")
                or dr.get("vlocity_cmt__PropertySet__c")
                or ""
            )
            try:
                props = json.loads(prop_set) if isinstance(prop_set, str) and prop_set else {}
            except Exception:
                props = {}
            findings.extend(self._check_dr(name, dr_type, props, cid))
        return findings

    def _check_dr(self, name: str, dr_type: str, props: dict, cid: str) -> list[Finding]:
        findings = []
        mappings = props.get("mappings", []) or props.get("Extract Mappings", []) or []
        objects = props.get("objects", []) or []

        # SELECT * equivalent — no field restrictions
        for obj in objects:
            fields = obj.get("fields", [])
            if not fields and obj.get("objectName"):
                findings.append(self._finding(
                    name, "DR-001", "No Field Restrictions (SELECT *)", Severity.HIGH,
                    f"Object '{obj.get('objectName')}' has no field restrictions defined. "
                    "This retrieves all fields, consuming unnecessary heap.",
                    component_id=cid,
                    suggested_fix=(
                        "Specify only the fields you need in the DataRaptor mapping. "
                        "Remove unused field mappings."
                    ),
                    impact="Excessive heap usage, slower queries, risk of field-level security bypass.",
                    effort="medium",
                ))
            break

        # Too many mappings
        if len(mappings) > 50:
            findings.append(self._finding(
                name, "DR-002", "Excessive Field Mappings", Severity.MEDIUM,
                f"DataRaptor has {len(mappings)} field mappings. "
                "Large mapping sets slow down transformation.",
                component_id=cid,
                suggested_fix=(
                    "Split into multiple DataRaptors by functional area, or use a single "
                    "Integration Procedure to orchestrate smaller, focused DataRaptors."
                ),
                impact="Increased transformation time, harder to debug and maintain.",
                effort="high",
            ))

        # No SOQL filter (load all records)
        extract_filters = props.get("filters", []) or props.get("condition", [])
        if dr_type in ("Extract", "Turbo Extract") and not extract_filters:
            findings.append(self._finding(
                name, "DR-003", "Extract Without Filters", Severity.HIGH,
                "DataRaptor Extract has no filter conditions, potentially loading all records.",
                component_id=cid,
                suggested_fix=(
                    "Add input-parameter-based filter conditions. At minimum, filter by Id "
                    "or a contextual field passed from the OmniScript or Integration Procedure."
                ),
                impact="Loads all records of the object, hitting SOQL row limits (50,000 rows).",
                effort="low",
            ))

        # Use Turbo Extract instead of Extract for simple lookups
        if dr_type == "Extract":
            findings.append(self._finding(
                name, "DR-004", "Consider Using Turbo Extract", Severity.LOW,
                "Standard Extract DataRaptors are slower than Turbo Extract for simple lookups.",
                component_id=cid,
                suggested_fix=(
                    "If this DataRaptor only reads from a single object with direct field mappings, "
                    "convert it to a Turbo Extract for better performance."
                ),
                impact="Turbo Extract can be 3-5x faster than standard Extract for simple reads.",
                effort="low",
            ))

        # Complex JSONPath expressions
        import re
        prop_str = json.dumps(props)
        complex_jsonpath = re.findall(r'"(\$\.[^"]{50,})"', prop_str)
        if complex_jsonpath:
            findings.append(self._finding(
                name, "DR-005", "Complex JSONPath Expression", Severity.MEDIUM,
                f"Found complex JSONPath expression: {complex_jsonpath[0][:80]}...",
                component_id=cid,
                suggested_fix=(
                    "Simplify JSONPath expressions. Complex paths with multiple filters "
                    "or recursive descent ('..') are slow to evaluate."
                ),
                impact="Slow JSON transformation, especially on large payloads.",
                effort="medium",
            ))

        # Load DataRaptor used in write path
        if dr_type == "Load" and "props" in (name or "").lower():
            findings.append(self._finding(
                name, "DR-006", "Load DataRaptor May Lack Error Handling", Severity.MEDIUM,
                "Load DataRaptor should have error handling for DML failures.",
                component_id=cid,
                suggested_fix=(
                    "Wrap Load DataRaptor calls in an Integration Procedure with try/catch "
                    "handling using a Conditional Block to check for errors in the response."
                ),
                impact="Silent data write failures with no user feedback.",
                effort="medium",
            ))

        return findings
