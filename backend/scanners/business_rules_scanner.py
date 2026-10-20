import json
from .base import BaseScanner
from ..models.findings import Finding, ComponentType, Severity


class BusinessRulesScanner(BaseScanner):
    component_type = ComponentType.BUSINESS_RULES

    async def scan(self, components: list[dict]) -> list[Finding]:
        findings = []
        for rule in components:
            name = rule.get("Name", "Unknown")
            cid = rule.get("Id")
            prop_set = (
                rule.get("PropertySet__c")
                or rule.get("vlocity_cmt__PropertySet__c")
                or ""
            )
            try:
                props = json.loads(prop_set) if isinstance(prop_set, str) and prop_set else {}
            except Exception:
                props = {}
            findings.extend(self._check_rule(name, props, cid))
        return findings

    def _check_rule(self, name: str, props: dict, cid: str) -> list[Finding]:
        findings = []
        conditions = props.get("conditions", []) or props.get("Conditions", []) or []
        actions = props.get("actions", []) or props.get("Actions", []) or []
        rules = props.get("rules", []) or props.get("Rules", []) or []

        # Too many conditions per rule
        if len(conditions) > 15:
            findings.append(self._finding(
                name, "BRE-001", "Too Many Conditions", Severity.MEDIUM,
                f"Business rule has {len(conditions)} conditions. "
                "Rules with many conditions are hard to read and test.",
                component_id=cid,
                suggested_fix=(
                    "Split into multiple focused rules using rule groups. "
                    "Use a decision table for matrix-style conditions."
                ),
                impact="Hard to maintain, high chance of logic errors in complex condition trees.",
                effort="high",
            ))

        # Too many actions per rule
        if len(actions) > 10:
            findings.append(self._finding(
                name, "BRE-002", "Too Many Actions per Rule", Severity.MEDIUM,
                f"Business rule triggers {len(actions)} actions. "
                "Rules should have focused, limited actions.",
                component_id=cid,
                suggested_fix=(
                    "Split into multiple rules with single-responsibility. "
                    "Consider an Integration Procedure to orchestrate complex action sequences."
                ),
                impact="Hard to debug which action caused an issue; blast radius of a change is large.",
                effort="medium",
            ))

        # Redundant rules (duplicate condition patterns)
        if len(rules) > 5:
            rule_conditions = [json.dumps(r.get("conditions", ""), sort_keys=True) for r in rules if isinstance(r, dict)]
            seen = set()
            duplicates = []
            for rc in rule_conditions:
                if rc in seen:
                    duplicates.append(rc)
                seen.add(rc)
            if duplicates:
                findings.append(self._finding(
                    name, "BRE-003", "Duplicate Rule Conditions", Severity.LOW,
                    "Multiple rules appear to have identical condition sets. "
                    "This may lead to conflicting or redundant rule execution.",
                    component_id=cid,
                    suggested_fix=(
                        "Consolidate rules with the same conditions. "
                        "Use actions within a single rule instead of separate rules."
                    ),
                    impact="Unpredictable behavior when both rules fire; hard to determine which takes precedence.",
                    effort="medium",
                ))

        # Hardcoded values in conditions
        import re
        prop_str = json.dumps(props)
        hardcoded_ids = re.findall(r'"(00[A-Za-z0-9]{13,16})"', prop_str)
        if hardcoded_ids:
            findings.append(self._finding(
                name, "BRE-004", "Hardcoded IDs in Rule Conditions", Severity.HIGH,
                f"Found {len(hardcoded_ids)} hardcoded Salesforce IDs in rule conditions.",
                component_id=cid,
                suggested_fix=(
                    "Replace hardcoded IDs with Custom Labels, Custom Metadata, "
                    "or dynamic variable references."
                ),
                impact="Rules break when deployed to other orgs or sandboxes.",
                effort="low",
            ))

        # No priority ordering
        if len(rules) > 3:
            has_priority = any(
                r.get("priority") or r.get("Priority") or r.get("order")
                for r in rules if isinstance(r, dict)
            )
            if not has_priority:
                findings.append(self._finding(
                    name, "BRE-005", "Rules Have No Priority Order", Severity.MEDIUM,
                    f"Rule group has {len(rules)} rules with no explicit priority ordering.",
                    component_id=cid,
                    suggested_fix=(
                        "Set explicit priority numbers on each rule. "
                        "Document the intended execution order in rule descriptions."
                    ),
                    impact="Rule execution order is non-deterministic, leading to inconsistent outcomes.",
                    effort="low",
                ))

        return findings
