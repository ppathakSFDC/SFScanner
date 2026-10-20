import json
from .base import BaseScanner
from ..models.findings import Finding, ComponentType, Severity


class OmniScriptScanner(BaseScanner):
    component_type = ComponentType.OMNISCRIPT

    async def scan(self, components: list[dict]) -> list[Finding]:
        findings = []
        for os_comp in components:
            name = os_comp.get("Name", "Unknown")
            cid = os_comp.get("Id")
            prop_set = os_comp.get("PropertySet__c") or os_comp.get("vlocity_cmt__PropertySet__c") or ""
            try:
                props = json.loads(prop_set) if isinstance(prop_set, str) and prop_set else {}
            except Exception:
                props = {}
            findings.extend(self._check_omniscript(name, props, os_comp, cid))
        return findings

    def _check_omniscript(self, name: str, props: dict, raw: dict, cid: str) -> list[Finding]:
        findings = []
        children = props.get("children", [])
        all_elements = self._flatten_elements(children)

        # Too many steps
        steps = [e for e in all_elements if e.get("type") == "Step"]
        if len(steps) > 10:
            findings.append(self._finding(
                name, "OS-001", "Too Many Steps", Severity.MEDIUM,
                f"OmniScript has {len(steps)} steps. Scripts with more than 10 steps degrade "
                "user experience and loading performance.",
                component_id=cid,
                suggested_fix=(
                    "Split into multiple OmniScripts linked via a parent orchestration script, "
                    "or use Conditional Views to show/hide step content dynamically."
                ),
                impact="Slow initial load, complex state management, poor UX on mobile.",
                effort="high",
            ))

        # Remote Actions without caching
        remote_actions = [e for e in all_elements if e.get("type") in ("RemoteAction", "DataJSON", "DataRaptor")]
        for ra in remote_actions:
            ra_props = ra.get("propSetMap", {})
            if not ra_props.get("cacheData") and not ra_props.get("cacheable"):
                findings.append(self._finding(
                    name, "OS-002", "Remote Action Without Caching", Severity.MEDIUM,
                    f"Element '{ra.get('name', '?')}' ({ra.get('type')}) does not have caching enabled. "
                    "Every user navigation triggers a fresh call.",
                    component_id=cid,
                    suggested_fix=(
                        "Enable 'Cache Data' on the element if the data doesn't change per session. "
                        "Set an appropriate cache expiry (e.g., 30 minutes)."
                    ),
                    impact="Unnecessary server calls, increased response times, higher API usage.",
                    effort="low",
                ))
            break  # one per script

        # Hardcoded org-specific values
        prop_str = json.dumps(props)
        import re
        if re.search(r'"00[A-Za-z0-9]{13,16}"', prop_str):
            findings.append(self._finding(
                name, "OS-003", "Hardcoded Salesforce ID", Severity.HIGH,
                "OmniScript contains hardcoded Salesforce record IDs.",
                component_id=cid,
                suggested_fix="Use Custom Labels, Custom Settings, or dynamic variables instead of hardcoded IDs.",
                impact="Breaks when deployed to other orgs or sandboxes.",
                effort="low",
            ))

        # No error handling block
        has_error_block = any(
            e.get("type") in ("Message", "Error", "NavigationAction")
            and "error" in (e.get("name") or "").lower()
            for e in all_elements
        )
        if remote_actions and not has_error_block:
            findings.append(self._finding(
                name, "OS-004", "Missing Error Handling", Severity.HIGH,
                "OmniScript makes remote calls but has no visible error handling element.",
                component_id=cid,
                suggested_fix=(
                    "Add a 'Message' element connected to remote action error paths "
                    "to display user-friendly error messages."
                ),
                impact="API failures show generic errors or crash the script silently.",
                effort="low",
            ))

        # Deeply nested OmniScripts (sub-scripts)
        sub_scripts = [e for e in all_elements if e.get("type") == "OmniScript"]
        if len(sub_scripts) > 3:
            findings.append(self._finding(
                name, "OS-005", "Too Many Nested Sub-Scripts", Severity.MEDIUM,
                f"OmniScript embeds {len(sub_scripts)} sub-scripts. Deep nesting causes "
                "state management complexity and performance issues.",
                component_id=cid,
                suggested_fix="Flatten the flow — use Navigation Actions to chain scripts instead of embedding.",
                impact="Increased load time, complex debugging, state variable conflicts.",
                effort="high",
            ))

        # Custom LWC components without lazy loading
        lwc_elements = [e for e in all_elements if e.get("type") == "Custom LWC"]
        if len(lwc_elements) > 5:
            findings.append(self._finding(
                name, "OS-006", "Many Custom LWC Components", Severity.LOW,
                f"OmniScript loads {len(lwc_elements)} custom LWC components. "
                "All are loaded upfront, increasing initial render time.",
                component_id=cid,
                suggested_fix="Use conditional visibility to only load LWC components when their step is active.",
                impact="Slow initial page load, especially on mobile or slow connections.",
                effort="medium",
            ))

        # Check for pre-populate not using lazy loading
        pre_pop = [e for e in all_elements if e.get("type") == "DataRaptor Extract"]
        if len(pre_pop) > 3:
            findings.append(self._finding(
                name, "OS-007", "Multiple Pre-Populate DataRaptors", Severity.MEDIUM,
                f"OmniScript runs {len(pre_pop)} DataRaptor Extract actions on load. "
                "These execute sequentially before the first step renders.",
                component_id=cid,
                suggested_fix=(
                    "Consolidate pre-populate DataRaptors into one, or move non-critical "
                    "data loads to be triggered lazily on step entry."
                ),
                impact="Slow first-paint time, poor perceived performance.",
                effort="medium",
            ))

        return findings

    def _flatten_elements(self, children: list, depth: int = 0) -> list[dict]:
        if depth > 10:
            return []
        result = []
        for child in (children or []):
            result.append(child)
            result.extend(self._flatten_elements(child.get("children", []), depth + 1))
        return result
