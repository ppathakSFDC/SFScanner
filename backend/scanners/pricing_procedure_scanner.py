import json
from .base import BaseScanner
from ..models.findings import Finding, ComponentType, Severity


class PricingProcedureScanner(BaseScanner):
    component_type = ComponentType.PRICING_PROCEDURE

    async def scan(self, components: list[dict]) -> list[Finding]:
        findings = []
        for pp in components:
            name = pp.get("Name", "Unknown")
            cid = pp.get("Id")
            prop_set = pp.get("PropertySet__c") or pp.get("vlocity_cmt__PropertySet__c") or ""
            try:
                props = json.loads(prop_set) if isinstance(prop_set, str) and prop_set else {}
            except Exception:
                props = {}
            findings.extend(self._check_pp(name, props, pp, cid))
        return findings

    def _check_pp(self, name: str, props: dict, raw: dict, cid: str) -> list[Finding]:
        findings = []
        steps = props.get("steps", []) or props.get("PricingSteps", []) or []
        variables = props.get("variables", []) or []
        conditions = props.get("conditions", []) or []

        # Too many pricing steps
        if len(steps) > 15:
            findings.append(self._finding(
                name, "PP-001", "Too Many Pricing Steps", Severity.MEDIUM,
                f"Pricing Procedure has {len(steps)} steps. "
                "Complex procedures slow quote calculation.",
                component_id=cid,
                suggested_fix=(
                    "Consolidate steps with similar logic. Use conditional execution "
                    "to skip irrelevant steps based on product/context."
                ),
                impact="Slow quote calculation; poor CPQ/configure-price-quote performance.",
                effort="high",
            ))

        # Hardcoded prices or rates
        import re
        prop_str = json.dumps(props)
        hardcoded_prices = re.findall(r'"price"\s*:\s*(\d+\.?\d*)', prop_str, re.IGNORECASE)
        if hardcoded_prices:
            findings.append(self._finding(
                name, "PP-002", "Hardcoded Prices in Procedure", Severity.HIGH,
                f"Found {len(hardcoded_prices)} hardcoded price values in the procedure.",
                component_id=cid,
                suggested_fix=(
                    "Replace hardcoded prices with Price List lookups or formula-driven "
                    "variables so pricing stays maintainable."
                ),
                impact="Price changes require code deployments; different orgs have different prices.",
                effort="medium",
            ))

        # No caching on calculation-heavy procedure
        if not props.get("cacheEnabled") and len(steps) > 5:
            findings.append(self._finding(
                name, "PP-003", "Caching Not Enabled on Complex Procedure", Severity.LOW,
                "Procedure has multiple steps but caching is disabled. "
                "Repeated calls recalculate from scratch.",
                component_id=cid,
                suggested_fix=(
                    "Enable response caching if the pricing output is deterministic "
                    "for the same inputs within a session."
                ),
                impact="Repeated quote recalculations add latency on quote pages.",
                effort="low",
            ))

        # Unused variables
        if variables:
            used_vars = set(re.findall(r'%([A-Za-z0-9_]+)%', prop_str))
            declared_vars = {v.get("name") or v.get("variableName") for v in variables if isinstance(v, dict)}
            unused = declared_vars - used_vars
            if unused:
                findings.append(self._finding(
                    name, "PP-004", "Unused Variables", Severity.LOW,
                    f"Variables declared but not used: {', '.join(list(unused)[:5])}",
                    component_id=cid,
                    suggested_fix="Remove unused variables to reduce complexity and memory footprint.",
                    impact="Clutter increases debugging time and risk of name collisions.",
                    effort="low",
                ))

        # Complex condition logic
        if len(conditions) > 20:
            findings.append(self._finding(
                name, "PP-005", "High Condition Count", Severity.MEDIUM,
                f"Procedure has {len(conditions)} conditions. "
                "Complex conditional logic is difficult to test and maintain.",
                component_id=cid,
                suggested_fix=(
                    "Group related conditions using a decision table or matrix-based approach. "
                    "Consider a Business Rules Engine for complex eligibility logic."
                ),
                impact="Hard to test all paths; logic errors in pricing directly impact revenue.",
                effort="high",
            ))

        return findings
