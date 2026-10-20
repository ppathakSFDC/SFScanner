import anthropic
import json
from typing import Optional
from ..models.findings import Finding
from ..config import settings


_client: Optional[anthropic.AsyncAnthropic] = None


def _make_client() -> anthropic.AsyncAnthropic:
    kwargs = {"api_key": settings.ANTHROPIC_API_KEY or "placeholder"}
    if settings.ANTHROPIC_BASE_URL:
        kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
    if settings.ANTHROPIC_CUSTOM_HEADERS:
        headers = {}
        for part in settings.ANTHROPIC_CUSTOM_HEADERS.split(","):
            part = part.strip()
            if ": " in part:
                k, v = part.split(": ", 1)
                headers[k.strip()] = v.strip()
        if headers:
            kwargs["default_headers"] = headers
    return anthropic.AsyncAnthropic(**kwargs)


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = _make_client()
    return _client


async def enrich_finding_with_ai(finding: Finding) -> Finding:
    """Use Claude to add a detailed explanation and concrete fix diff to a finding."""
    if not settings.ANTHROPIC_API_KEY:
        return finding

    code_block = f"**Current Code/Config**:\n```\n{finding.current_code}\n```" if finding.current_code else ""
    fix_block = f"**Initial Suggested Fix**: {finding.suggested_fix}" if finding.suggested_fix else ""

    prompt = f"""You are a Salesforce best-practices expert. A code scanner found the following issue:

**Component Type**: {finding.component_type}
**Component Name**: {finding.component_name}
**Rule**: {finding.rule_name} ({finding.rule_id})
**Severity**: {finding.severity}
**Description**: {finding.description}

{code_block}
{fix_block}

Please provide:
1. A clear 2-3 sentence explanation of WHY this is a problem and what can go wrong
2. A concrete code/config fix showing BEFORE and AFTER (use diff format: - for removed, + for added lines)
3. An estimated performance improvement or risk reduction

Be concise and practical. Focus on actionable advice.

Respond in this exact JSON format:
{{
  "explanation": "...",
  "fix_diff": "...",
  "impact_summary": "..."
}}"""

    try:
        client = get_client()
        msg = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        finding.ai_explanation = data.get("explanation")
        finding.ai_fix_diff = data.get("fix_diff")
        if data.get("impact_summary"):
            finding.impact = data["impact_summary"]
    except Exception as e:
        finding.ai_explanation = f"AI enrichment unavailable: {e}"

    return finding


async def enrich_findings_batch(findings: list[Finding], max_enrich: int = 20) -> list[Finding]:
    """Enrich the top N most severe findings with AI analysis."""
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.severity, 99))
    to_enrich = sorted_findings[:max_enrich]
    rest = sorted_findings[max_enrich:]

    import asyncio
    enriched = await asyncio.gather(*[enrich_finding_with_ai(f) for f in to_enrich])
    return list(enriched) + rest


async def generate_executive_summary(scan_result) -> str:
    """Generate an AI-written executive summary of the scan."""
    if not settings.ANTHROPIC_API_KEY:
        return ""

    top_findings = sorted(
        scan_result.findings,
        key=lambda f: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(f.severity, 4),
    )[:10]

    summary_data = {
        "org": scan_result.org_name,
        "total_components": scan_result.total_components,
        "total_findings": scan_result.total_findings,
        "critical": scan_result.critical_count,
        "high": scan_result.high_count,
        "medium": scan_result.medium_count,
        "low": scan_result.low_count,
        "top_issues": [
            {"rule": f.rule_name, "component": f.component_name, "severity": f.severity}
            for f in top_findings
        ],
        "component_summary": scan_result.component_summary,
    }

    prompt = f"""You are a Salesforce technical lead writing a scan report executive summary.

Scan data:
{json.dumps(summary_data, indent=2)}

Write a concise (3-4 paragraph) executive summary that:
1. States the overall health/risk level of the org
2. Highlights the most critical issues and their business impact
3. Prioritizes what to fix first (quick wins vs. large efforts)
4. Ends with a positive, actionable recommendation

Write in professional but accessible language. No bullet points — prose only."""

    try:
        client = get_client()
        msg = await client.messages.create(
            model=settings.ANTHROPIC_DEFAULT_SONNET_MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return ""


async def generate_recommendations(findings: list[Finding]) -> list[dict]:
    """Generate a prioritized remediation roadmap from findings."""
    if not settings.ANTHROPIC_API_KEY or not findings:
        return _fallback_recommendations(findings)

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    top = sorted(findings, key=lambda f: severity_order.get(f.severity, 99))[:30]

    summary = [
        {"rule": f.rule_name, "component": f.component_name,
         "type": f.component_type, "severity": f.severity, "effort": f.effort}
        for f in top
    ]

    prompt = f"""You are a Salesforce architect. Based on these scan findings, create a prioritized remediation roadmap.

Findings:
{json.dumps(summary, indent=2)}

Return a JSON array of 5-8 recommendation objects, each with:
- "phase": "immediate" | "this_sprint" | "next_quarter" | "quick_win"
- "title": short action title (max 60 chars)
- "description": 1-2 sentence explanation of what to fix and why
- "component_types": array of affected component types
- "finding_count": estimated number of findings addressed
- "effort": "low" | "medium" | "high"
- "impact": "low" | "medium" | "high" | "critical"

"quick_win" phase = low effort, meaningful impact.
Order by phase: immediate first, then this_sprint, then quick_win, then next_quarter.

Return ONLY the JSON array, no markdown wrapping."""

    try:
        client = get_client()
        msg = await client.messages.create(
            model=settings.ANTHROPIC_DEFAULT_SONNET_MODEL,
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
            if raw.endswith("```"):
                raw = raw[:-3]
        return json.loads(raw)
    except Exception:
        return _fallback_recommendations(findings)


def _fallback_recommendations(findings: list[Finding]) -> list[dict]:
    """Rule-based recommendations when AI is unavailable."""
    recs = []
    criticals = [f for f in findings if f.severity == "critical"]
    highs = [f for f in findings if f.severity == "high"]
    quick_wins = [f for f in findings if f.effort == "low"]

    if criticals:
        recs.append({
            "phase": "immediate",
            "title": f"Fix {len(criticals)} critical issue{'s' if len(criticals) > 1 else ''}",
            "description": "Critical findings pose immediate risk to org stability and governor limits.",
            "component_types": list({f.component_type for f in criticals}),
            "finding_count": len(criticals),
            "effort": "high",
            "impact": "critical",
        })
    if highs:
        recs.append({
            "phase": "this_sprint",
            "title": f"Address {len(highs)} high-severity finding{'s' if len(highs) > 1 else ''}",
            "description": "High severity issues should be resolved within the current sprint to reduce org risk.",
            "component_types": list({f.component_type for f in highs}),
            "finding_count": len(highs),
            "effort": "medium",
            "impact": "high",
        })
    if quick_wins:
        recs.append({
            "phase": "quick_win",
            "title": f"{len(quick_wins)} low-effort improvement{'s' if len(quick_wins) > 1 else ''} available",
            "description": "These findings can be fixed quickly with minimal risk and deliver immediate value.",
            "component_types": list({f.component_type for f in quick_wins}),
            "finding_count": len(quick_wins),
            "effort": "low",
            "impact": "medium",
        })
    return recs
