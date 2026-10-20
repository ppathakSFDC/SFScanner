import json
from .base import BaseScanner
from ..models.findings import Finding, ComponentType, Severity


class FlowScanner(BaseScanner):
    component_type = ComponentType.FLOW

    async def scan(self, components: list[dict]) -> list[Finding]:
        findings = []
        for flow in components:
            name = flow.get("FullName") or flow.get("Name", "Unknown")
            cid = flow.get("Id")
            meta = flow.get("Metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            findings.extend(self._check_flow(name, meta, cid))
        return findings

    def _check_flow(self, name: str, meta: dict, cid: str) -> list[Finding]:
        findings = []
        process_type = meta.get("processType", "")
        elements = self._all_elements(meta)
        loops = [e for e in elements if e.get("elementType") == "Loop" or "loop" in e.get("elementType", "").lower()]
        decisions = [e for e in elements if "decision" in e.get("elementType", "").lower()]
        record_lookups = [e for e in elements if "recordlookup" in e.get("elementType", "").lower()]
        record_creates = [e for e in elements if "recordcreate" in e.get("elementType", "").lower()]
        record_updates = [e for e in elements if "recordupdate" in e.get("elementType", "").lower()]
        record_deletes = [e for e in elements if "recorddelete" in e.get("elementType", "").lower()]

        # DML / SOQL inside loops
        if loops:
            dml_inside = self._dml_inside_loops(meta)
            if dml_inside:
                findings.append(self._finding(
                    name, "FLOW-001", "DML/SOQL Inside Loop", Severity.CRITICAL,
                    f"Flow has record operations ({', '.join(dml_inside)}) inside a loop. "
                    "This runs a query or DML per iteration, hitting governor limits.",
                    component_id=cid,
                    suggested_fix=(
                        "Use a 'Get Records' element BEFORE the loop to collect all needed records. "
                        "Store records in a collection variable inside the loop, then use a single "
                        "'Create/Update Records' element AFTER the loop with the collection."
                    ),
                    impact="100 SOQL or 150 DML limit hit for bulk record operations.",
                    effort="medium",
                ))

        # Too many elements — complexity
        if len(elements) > 50:
            findings.append(self._finding(
                name, "FLOW-002", "Overly Complex Flow", Severity.MEDIUM,
                f"Flow has {len(elements)} elements. Flows over 50 elements are hard to maintain "
                "and slow to load in Flow Builder.",
                component_id=cid,
                suggested_fix=(
                    "Split into sub-flows using the 'Subflow' element. "
                    "Group related logic into reusable child flows."
                ),
                impact="Maintenance difficulty, slower debugging, higher chance of errors.",
                effort="high",
            ))

        # No fault paths on DML operations
        dml_elements = record_creates + record_updates + record_deletes
        for elem in dml_elements:
            if not elem.get("faultConnector") and not elem.get("faultPath"):
                findings.append(self._finding(
                    name, "FLOW-003", "Missing Fault Path on DML Element", Severity.HIGH,
                    f"Element '{elem.get('label', elem.get('name', '?'))}' performs DML but "
                    "has no fault connector. Errors will surface as unhandled exceptions.",
                    component_id=cid,
                    suggested_fix=(
                        "Add a Fault Connector from every record-write element to a fault-handling "
                        "path that displays an error message to the user or logs the failure."
                    ),
                    impact="Unhandled DML errors crash the flow with a generic error for the user.",
                    effort="low",
                ))
            break  # one finding per flow to avoid noise

        # Hardcoded record IDs in filter conditions
        if self._has_hardcoded_ids(meta):
            findings.append(self._finding(
                name, "FLOW-004", "Hardcoded Record ID in Filter", Severity.HIGH,
                "Flow contains hardcoded Salesforce record IDs in filter conditions.",
                component_id=cid,
                suggested_fix=(
                    "Replace hardcoded IDs with flow variables populated at runtime, "
                    "or use Custom Metadata values."
                ),
                impact="Flow breaks when deployed to another org or sandbox.",
                effort="low",
            ))

        # Unconnected/dead elements
        unreachable = self._find_unreachable_elements(meta, elements)
        if unreachable:
            findings.append(self._finding(
                name, "FLOW-005", "Unreachable Flow Elements", Severity.LOW,
                f"Elements not connected to the flow: {', '.join(unreachable[:5])}",
                component_id=cid,
                suggested_fix="Remove unused elements to reduce complexity and improve readability.",
                impact="Clutter makes the flow harder to debug and maintain.",
                effort="low",
            ))

        # Too many Get Record calls without limits
        for lookup in record_lookups:
            filters = lookup.get("filters", [])
            if not filters and not lookup.get("filterLogic"):
                findings.append(self._finding(
                    name, "FLOW-006", "Get Records Without Filters", Severity.HIGH,
                    f"Get Records element '{lookup.get('label', '?')}' has no filter conditions. "
                    "This queries ALL records of the object.",
                    component_id=cid,
                    suggested_fix=(
                        "Add filter conditions to limit the records returned. "
                        "At minimum filter by active/relevant status."
                    ),
                    impact="Fetches potentially millions of records, exhausting heap and SOQL row limits.",
                    effort="low",
                ))
            break  # one per flow

        # Auto-launched flows without bulkification
        if process_type in ("AutoLaunchedFlow", "Workflow") and loops:
            findings.append(self._finding(
                name, "FLOW-007", "Auto-Launched Flow With Loops", Severity.HIGH,
                "Auto-launched flow uses loops, risking governor limit failures in bulk operations.",
                component_id=cid,
                suggested_fix=(
                    "Ensure all record operations use collections rather than individual "
                    "records inside loops. Test with 200+ records to validate bulkification."
                ),
                impact="Batch apex or data imports triggering this flow will hit governor limits.",
                effort="medium",
            ))

        # FLOW-008: Decision fan-out (too many outcomes)
        for dec in decisions:
            rules = dec.get("rules", [])
            if isinstance(rules, dict):
                rules = [rules]
            if len(rules) > 5:
                findings.append(self._finding(
                    name, "FLOW-008", "Decision Element Fan-Out", Severity.MEDIUM,
                    f"Decision '{dec.get('label', dec.get('name', '?'))}' has {len(rules)} outcome branches. "
                    "Decisions with many branches are difficult to read, test, and maintain.",
                    component_id=cid,
                    suggested_fix=(
                        "Split complex decisions into multiple smaller decisions or use a custom label/picklist "
                        "with a single decision element using Equals checks on a collection variable."
                    ),
                    impact="High branch count increases risk of missing a path during testing and makes maintenance error-prone.",
                    effort="medium",
                ))
                break  # one per flow

        # FLOW-009: Screen flow missing error screen when it has DML
        screens = [e for e in elements if "screen" in e.get("elementType", "").lower()]
        if screens and process_type in ("Flow", "ScreenFlow"):
            has_fault_screen = any(
                "error" in (e.get("label", "") + e.get("name", "")).lower()
                for e in elements
                if "screen" in e.get("elementType", "").lower()
            )
            if not has_fault_screen and (record_creates or record_updates or record_deletes):
                findings.append(self._finding(
                    name, "FLOW-009", "Screen Flow Missing Error Screen", Severity.HIGH,
                    "Screen flow performs DML operations but has no dedicated error/fault screen. "
                    "Users see a generic Salesforce error page when DML fails.",
                    component_id=cid,
                    suggested_fix=(
                        "Add a Screen element named 'Error_Screen' with a display text showing the error message. "
                        "Connect all DML fault paths to this error screen:\n"
                        "Fault Path → Error Screen (display {!$Flow.FaultMessage})"
                    ),
                    impact="Users see a raw unformatted error page instead of a friendly message, breaking the UX.",
                    effort="low",
                ))

        # FLOW-010: Scheduled path with DML (async bulkification risk)
        scheduled_paths = meta.get("scheduledPaths", [])
        if isinstance(scheduled_paths, dict):
            scheduled_paths = [scheduled_paths]
        if scheduled_paths and (record_creates or record_updates or record_deletes):
            findings.append(self._finding(
                name, "FLOW-010", "Scheduled Path with DML — Async Bulkification Risk", Severity.HIGH,
                "Flow has scheduled paths that perform DML. Scheduled paths run asynchronously per record, "
                "not in bulk — each scheduled interview consumes separate governor limit allocations.",
                component_id=cid,
                suggested_fix=(
                    "Avoid DML inside scheduled paths when processing large volumes. "
                    "Consider a Scheduled Apex job that processes records in bulk using a SOQL query + DML batch."
                ),
                impact="Scheduled paths on high-volume objects can generate thousands of separate Apex transactions.",
                effort="high",
            ))

        return findings

    def _all_elements(self, meta: dict) -> list[dict]:
        element_keys = [
            "loops", "decisions", "recordLookups", "recordCreates",
            "recordUpdates", "recordDeletes", "assignments", "screens",
            "subflows", "actionCalls", "customErrors",
        ]
        elements = []
        for key in element_keys:
            items = meta.get(key, [])
            if isinstance(items, dict):
                items = [items]
            for item in (items or []):
                item["elementType"] = key
                elements.append(item)
        return elements

    def _dml_inside_loops(self, meta: dict) -> list[str]:
        loops = meta.get("loops", [])
        if isinstance(loops, dict):
            loops = [loops]
        if not loops:
            return []
        # Simplified check: look for any DML connector names matching loop targets
        dml_types = []
        for loop in (loops or []):
            next_value = loop.get("nextValueConnector", {})
            target = next_value.get("targetReference", "")
            # Check if target matches a record DML element
            for dml_key in ("recordCreates", "recordUpdates", "recordDeletes", "recordLookups"):
                items = meta.get(dml_key, [])
                if isinstance(items, dict):
                    items = [items]
                for item in (items or []):
                    if item.get("name") == target:
                        dml_types.append(dml_key)
        return list(set(dml_types))

    def _has_hardcoded_ids(self, meta: dict) -> bool:
        import re
        meta_str = json.dumps(meta)
        pattern = re.compile(r'"(00[A-Za-z0-9]{13,16})"')
        return bool(pattern.search(meta_str))

    def _find_unreachable_elements(self, meta: dict, elements: list[dict]) -> list[str]:
        # Collect all referenced targets from connectors
        meta_str = json.dumps(meta)
        referenced = set()
        import re
        for match in re.finditer(r'"targetReference"\s*:\s*"([^"]+)"', meta_str):
            referenced.add(match.group(1))
        start = meta.get("startElementReference", "")
        if start:
            referenced.add(start)
        unreachable = []
        for elem in elements:
            elem_name = elem.get("name", "")
            if elem_name and elem_name not in referenced:
                unreachable.append(elem.get("label") or elem_name)
        return unreachable
