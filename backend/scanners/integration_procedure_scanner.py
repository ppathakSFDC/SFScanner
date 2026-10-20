import json
from .base import BaseScanner
from ..models.findings import Finding, ComponentType, Severity


class IntegrationProcedureScanner(BaseScanner):
    component_type = ComponentType.INTEGRATION_PROCEDURE

    async def scan(self, components: list[dict]) -> list[Finding]:
        findings = []
        for ip in components:
            name = ip.get("Name", "Unknown")
            cid = ip.get("Id")
            prop_set = (
                ip.get("PropertySet__c")
                or ip.get("vlocity_cmt__PropertySet__c")
                or ""
            )
            try:
                props = json.loads(prop_set) if isinstance(prop_set, str) and prop_set else {}
            except Exception:
                props = {}
            findings.extend(self._check_ip(name, props, cid))
        return findings

    def _check_ip(self, name: str, props: dict, cid: str) -> list[Finding]:
        findings = []
        elements = self._get_elements(props)

        http_elements = [e for e in elements if e.get("Type") in ("HTTPAction", "HTTP")]
        set_values = [e for e in elements if e.get("Type") in ("SetValues", "Set Values")]
        loops = [e for e in elements if e.get("Type") in ("Loop", "ForEach")]
        conditionals = [e for e in elements if e.get("Type") in ("Conditional", "ConditionalBlock")]
        all_actions = [e for e in elements if e.get("Type") in ("DataRaptor", "DataRaptorAction")]

        # HTTP actions without timeout
        for http in http_elements:
            timeout = (
                http.get("propSetMap", {}).get("timeout")
                or http.get("timeout")
                or http.get("Timeout")
            )
            if not timeout:
                findings.append(self._finding(
                    name, "IP-001", "HTTP Action Without Timeout", Severity.HIGH,
                    f"HTTP action '{http.get('name', '?')}' has no timeout configured. "
                    "A hanging external call will block the entire transaction.",
                    component_id=cid,
                    suggested_fix=(
                        "Set a timeout value (recommended: 10-30 seconds) on all HTTP actions. "
                        "Add a Conditional Block after to handle timeout/error responses."
                    ),
                    impact="Single hanging API call can tie up a transaction for up to 120 seconds.",
                    effort="low",
                ))
            break

        # No error handling for HTTP calls
        if http_elements and not conditionals:
            findings.append(self._finding(
                name, "IP-002", "HTTP Calls Without Error Handling", Severity.HIGH,
                "Integration Procedure makes HTTP calls but has no Conditional Block to handle errors.",
                component_id=cid,
                suggested_fix=(
                    "After each HTTP action, add a Conditional Block that checks "
                    "the HTTP status code and routes to an error-handling path for non-200 responses."
                ),
                impact="API failures propagate silently or crash the calling component.",
                effort="low",
            ))

        # Loops with DataRaptor calls inside
        if loops:
            dr_in_loop = self._dr_inside_loops(props)
            if dr_in_loop:
                findings.append(self._finding(
                    name, "IP-003", "DataRaptor Inside Loop", Severity.CRITICAL,
                    f"DataRaptor action found inside a loop in '{name}'. "
                    "Each iteration triggers a separate SOQL query or DML.",
                    component_id=cid,
                    suggested_fix=(
                        "Move the DataRaptor call outside the loop. Pass the full collection "
                        "to a Load DataRaptor that handles bulk insert/update."
                    ),
                    impact="SOQL/DML governor limits hit rapidly under moderate data volumes.",
                    effort="medium",
                ))

        # Too many sequential elements (no parallelism)
        sequential_http = [e for e in http_elements if not e.get("parallel") and not e.get("isParallel")]
        if len(sequential_http) > 3:
            findings.append(self._finding(
                name, "IP-004", "Sequential HTTP Calls — Consider Parallelism", Severity.MEDIUM,
                f"Found {len(sequential_http)} sequential HTTP actions. "
                "Running them sequentially adds their latencies.",
                component_id=cid,
                suggested_fix=(
                    "Group independent HTTP calls into a 'Parallel' execution block "
                    "in the Integration Procedure to reduce total latency."
                ),
                impact=f"Total latency = sum of all call times. 3x500ms calls = 1.5s vs 500ms parallel.",
                effort="medium",
            ))

        # Missing response caching
        cache_enabled = props.get("cacheData") or props.get("cacheable")
        if not cache_enabled and all_actions and not http_elements:
            findings.append(self._finding(
                name, "IP-005", "Caching Not Enabled", Severity.LOW,
                "Integration Procedure is read-only but caching is not enabled. "
                "Repeated calls will re-execute all steps.",
                component_id=cid,
                suggested_fix=(
                    "Enable response caching on the Integration Procedure if the data "
                    "is not user-specific or doesn't change frequently."
                ),
                impact="Unnecessary repeated computation and API calls for the same data.",
                effort="low",
            ))

        # Overly complex — too many elements
        if len(elements) > 30:
            findings.append(self._finding(
                name, "IP-006", "Overly Complex Integration Procedure", Severity.MEDIUM,
                f"Integration Procedure has {len(elements)} elements. "
                "Procedures over 30 elements are hard to maintain.",
                component_id=cid,
                suggested_fix=(
                    "Extract reusable logic into sub-Integration Procedures "
                    "called via a 'Remote Procedure' action."
                ),
                impact="Difficult to debug, test, and modify without introducing regressions.",
                effort="high",
            ))

        return findings

    def _get_elements(self, props: dict) -> list[dict]:
        elements = props.get("elements", []) or props.get("children", []) or []
        if isinstance(elements, dict):
            elements = [elements]
        return elements

    def _dr_inside_loops(self, props: dict) -> bool:
        elements = self._get_elements(props)
        loops = [e for e in elements if e.get("Type") in ("Loop", "ForEach")]
        for loop in loops:
            loop_children = loop.get("children", []) or []
            for child in loop_children:
                if child.get("Type") in ("DataRaptor", "DataRaptorAction"):
                    return True
        return False
