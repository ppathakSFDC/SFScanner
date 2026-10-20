import json
from .base import BaseScanner
from ..models.findings import Finding, ComponentType, Severity


class FlexCardScanner(BaseScanner):
    component_type = ComponentType.OMNISCRIPT  # reuse until a dedicated type is added

    async def scan(self, components: list[dict]) -> list[Finding]:
        findings = []
        for fc in components:
            name = fc.get("Name") or fc.get("FlexcardName", "Unknown")
            cid = fc.get("Id")
            prop_raw = fc.get("PropertySet__c") or fc.get("PropertySet") or ""
            try:
                props = json.loads(prop_raw) if isinstance(prop_raw, str) and prop_raw else {}
            except Exception:
                props = {}
            findings.extend(self._check_flexcard(name, props, fc, cid))
        return findings

    def _check_flexcard(self, name: str, props: dict, raw: dict, cid: str) -> list[Finding]:
        findings = []

        # Count data sources (actions, datasources keys)
        data_sources = props.get("dataSources", []) or props.get("dataSource", [])
        if isinstance(data_sources, dict):
            data_sources = list(data_sources.values())
        if len(data_sources) > 4:
            findings.append(self._finding(
                name, "FC-001", "Too Many Data Sources", Severity.MEDIUM,
                f"FlexCard has {len(data_sources)} data sources. Multiple data sources increase "
                "render time and complicate cache invalidation.",
                component_id=cid,
                suggested_fix=(
                    "Consolidate data fetching into a single Integration Procedure that returns "
                    "all required data in one call."
                ),
                impact="Slower card load, higher API consumption, harder to debug.",
                effort="medium",
            ))

        # Check for child cards (embedded FlexCards)
        children = props.get("children", []) or props.get("childCards", [])
        if len(children) > 3:
            findings.append(self._finding(
                name, "FC-002", "Many Nested Child Cards", Severity.MEDIUM,
                f"FlexCard embeds {len(children)} child cards. Deep nesting causes repeated "
                "data fetches and complex re-render chains.",
                component_id=cid,
                suggested_fix=(
                    "Limit child card nesting to 2 levels. Use a parent Integration Procedure to "
                    "pre-fetch and pass data down instead of letting each child query independently."
                ),
                impact="Cascading data loads, multiple API calls on a single page render.",
                effort="high",
            ))

        # Actions without error handling
        actions = props.get("actions", []) or []
        if isinstance(actions, dict):
            actions = list(actions.values())
        has_error_handler = any(
            a.get("type", "").lower() in ("error", "toast")
            or "error" in (a.get("name") or "").lower()
            for a in actions
        )
        if actions and not has_error_handler:
            findings.append(self._finding(
                name, "FC-003", "No Error Handler on Actions", Severity.HIGH,
                "FlexCard defines actions but has no error handling action configured.",
                component_id=cid,
                suggested_fix=(
                    "Add an 'Error' action type or a Toast notification for failure paths "
                    "so users receive feedback when an action fails."
                ),
                impact="Silent failures, users unaware of errors, no retry path.",
                effort="low",
            ))

        # Version check — many versions indicates no cleanup
        version_count = raw.get("VersionCount", 0)
        if isinstance(version_count, (int, float)) and version_count > 20:
            findings.append(self._finding(
                name, "FC-004", "High Version Count", Severity.LOW,
                f"FlexCard has {int(version_count)} saved versions. Excess versions consume "
                "storage and make rollback auditing difficult.",
                component_id=cid,
                suggested_fix="Archive or delete unused versions via OmniStudio FlexCard editor.",
                impact="Storage bloat, slower load in the designer, confusing version history.",
                effort="low",
            ))

        return findings
