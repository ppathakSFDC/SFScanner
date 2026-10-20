"""Self-contained HTML and CSV export for scan results."""
from __future__ import annotations

import csv
import html
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from ..models.findings import ScanResult
from ..store import _scans

router = APIRouter(prefix="/scan", tags=["export"])

# ── Phase metadata ────────────────────────────────────────────────────────────
_PHASE = {
    "immediate":    {"label": "Fix Immediately", "border": "#7f1d1d", "color": "#fca5a5", "bg": "rgba(252,165,165,0.06)"},
    "this_sprint":  {"label": "This Sprint",     "border": "#9a3412", "color": "#fdba74", "bg": "rgba(253,186,116,0.06)"},
    "quick_win":    {"label": "Quick Win",        "border": "#166534", "color": "#86efac", "bg": "rgba(134,239,172,0.06)"},
    "next_quarter": {"label": "Next Quarter",     "border": "#1e40af", "color": "#93c5fd", "bg": "rgba(147,197,253,0.06)"},
}
_SEV_COLOR = {
    "critical": "#fca5a5",
    "high":     "#fdba74",
    "medium":   "#fcd34d",
    "low":      "#86efac",
    "info":     "#94a3b8",
}
_SEV_BG = {
    "critical": "#450a0a",
    "high":     "#431407",
    "medium":   "#422006",
    "low":      "#14532d",
    "info":     "#1e293b",
}
_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


# ── Health score helper ───────────────────────────────────────────────────────
def _health_score(findings) -> int:
    score = 100
    for f in findings:
        sev = f.severity if isinstance(f.severity, str) else f.severity.value
        score -= {"critical": 15, "high": 8, "medium": 4, "low": 1}.get(sev, 0)
    return max(0, score)


def _grade(score: int) -> tuple[str, str]:
    if score >= 90: return "A", "#86efac"
    if score >= 75: return "B", "#a3e635"
    if score >= 60: return "C", "#fcd34d"
    if score >= 45: return "D", "#fdba74"
    return "F", "#fca5a5"


# ── HTML builder ──────────────────────────────────────────────────────────────
def _h(text: str) -> str:
    return html.escape(str(text or ""), quote=True)


def _build_html_report(result: ScanResult) -> str:
    scan_date = result.started_at[:10] if result.started_at else "unknown"
    export_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    health = _health_score(result.findings)
    g_letter, g_color = _grade(health)

    findings_sorted = sorted(
        result.findings,
        key=lambda f: _SEV_ORDER.get(f.severity if isinstance(f.severity, str) else f.severity.value, 99),
    )

    # ── Summary tiles ─────────────────────────────────────────────────────────
    tiles_html = "".join(
        f'<div class="tile"><div class="tile-num" style="color:{color}">{num}</div>'
        f'<div class="tile-label">{_h(label)}</div></div>'
        for num, label, color in [
            (result.total_components, "Components Scanned", "#c4b5fd"),
            (result.total_findings,   "Total Findings",     "#94a3b8"),
            (result.critical_count,   "Critical",           "#fca5a5"),
            (result.high_count,       "High",               "#fdba74"),
            (result.medium_count,     "Medium",             "#fcd34d"),
            (health,                  "Health Score",       g_color),
        ]
    )

    # ── Executive summary ─────────────────────────────────────────────────────
    exec_html = ""
    if result.executive_summary:
        paras = "".join(f"<p>{_h(p)}</p>" for p in result.executive_summary.split("\n\n") if p.strip())
        exec_html = f"""
<section class="section">
  <h2 class="section-title">Executive Summary</h2>
  <div class="exec-box">{paras}</div>
</section>"""

    # ── Recommendations ───────────────────────────────────────────────────────
    rec_cards = ""
    if result.recommendations:
        for rec in result.recommendations:
            ph = _PHASE.get(rec.get("phase", ""), _PHASE["next_quarter"])
            types_str = ", ".join(rec.get("component_types") or [])
            effort = rec.get("effort", "")
            impact = rec.get("impact", "")
            finding_count = rec.get("finding_count", "")
            rec_cards += f"""
<div class="rec-card" style="border-left:3px solid {ph['border']};background:{ph['bg']}">
  <div class="rec-header">
    <span class="rec-phase" style="color:{ph['color']};border-color:{ph['border']}">{_h(ph['label'])}</span>
    <span class="rec-title">{_h(rec.get('title',''))}</span>
  </div>
  <div class="rec-desc">{_h(rec.get('description',''))}</div>
  <div class="rec-meta">
    {f'<span class="meta-chip">Addresses {_h(finding_count)} findings</span>' if finding_count else ''}
    {f'<span class="meta-chip">Effort: {_h(effort)}</span>' if effort else ''}
    {f'<span class="meta-chip">Impact: {_h(impact)}</span>' if impact else ''}
    {f'<span class="meta-chip">{_h(types_str)}</span>' if types_str else ''}
  </div>
</div>"""
        exec_html += f"""
<section class="section">
  <h2 class="section-title">Remediation Roadmap</h2>
  <div class="rec-grid">{rec_cards}</div>
</section>"""

    # ── Component scorecard ───────────────────────────────────────────────────
    scorecard_rows = ""
    for comp_type, count in sorted(result.component_summary.items()):
        comp_findings = [
            f for f in result.findings
            if (f.component_type if isinstance(f.component_type, str) else f.component_type.value) == comp_type
        ]
        comp_health = _health_score(comp_findings)
        g_l, g_c = _grade(comp_health)
        crit = sum(1 for f in comp_findings if (f.severity if isinstance(f.severity, str) else f.severity.value) == "critical")
        high = sum(1 for f in comp_findings if (f.severity if isinstance(f.severity, str) else f.severity.value) == "high")
        bar_pct = comp_health
        bar_color = g_c
        scorecard_rows += f"""
<tr>
  <td class="sc-name">{_h(comp_type)}</td>
  <td class="sc-count">{count}</td>
  <td class="sc-bar-cell">
    <div class="bar-track"><div class="bar-fill" style="width:{bar_pct}%;background:{bar_color}"></div></div>
  </td>
  <td><span class="grade-badge" style="color:{g_c};border-color:{g_c}40">{g_l} {comp_health}</span></td>
  <td class="sc-findings">
    {f'<span class="sev-mini" style="color:#fca5a5">{crit} critical</span>' if crit else ''}
    {f'<span class="sev-mini" style="color:#fdba74">{high} high</span>' if high else ''}
    {f'<span class="sev-mini" style="color:#94a3b8">{len(comp_findings) - crit - high} other</span>' if len(comp_findings) - crit - high else ''}
    {f'<span class="sev-mini" style="color:#475569">clean</span>' if not comp_findings else ''}
  </td>
</tr>"""

    scorecard_html = f"""
<section class="section">
  <h2 class="section-title">Component Health Scorecard</h2>
  <table class="scorecard">
    <thead><tr>
      <th>Component Type</th><th>Scanned</th><th style="width:180px">Health</th>
      <th>Grade</th><th>Findings</th>
    </tr></thead>
    <tbody>{scorecard_rows}</tbody>
  </table>
</section>"""

    # ── Findings by severity ──────────────────────────────────────────────────
    findings_sections = ""
    for sev in ["critical", "high", "medium", "low", "info"]:
        sev_findings = [
            f for f in findings_sorted
            if (f.severity if isinstance(f.severity, str) else f.severity.value) == sev
        ]
        if not sev_findings:
            continue
        sc = _SEV_COLOR[sev]
        sb = _SEV_BG[sev]
        cards = ""
        for f in sev_findings:
            f_sev = f.severity if isinstance(f.severity, str) else f.severity.value
            f_type = f.component_type if isinstance(f.component_type, str) else f.component_type.value
            diff_html = ""
            if f.ai_fix_diff:
                lines = ""
                for line in f.ai_fix_diff.split("\n"):
                    lc = "#86efac" if line.startswith("+") else "#fca5a5" if line.startswith("-") else "#93c5fd" if line.startswith("@@") else "#94a3b8"
                    bg = "rgba(134,239,172,0.06)" if line.startswith("+") else "rgba(252,165,165,0.06)" if line.startswith("-") else "transparent"
                    lines += f'<div style="color:{lc};background:{bg}">{_h(line) or "&nbsp;"}</div>'
                diff_html = f'<div class="label-sm" style="color:#86efac">Suggested Fix</div><div class="code-block diff-block">{lines}</div>'
            elif f.suggested_fix:
                diff_html = f'<div class="label-sm" style="color:#86efac">Suggested Fix</div><div class="code-block" style="color:#86efac">{_h(f.suggested_fix)}</div>'

            cards += f"""
<div class="finding-card" style="border-left:3px solid {sc}">
  <div class="finding-head">
    <span class="sev-badge" style="background:{sb};color:{sc}">{_h(f_sev.upper())}</span>
    <span class="finding-rule">{_h(f.rule_name)}</span>
    {f'<span class="effort-chip">{_h(f.effort)} effort</span>' if f.effort else ''}
  </div>
  <div class="finding-meta">{_h(f_type)} · <strong>{_h(f.component_name)}</strong>{(' · ' + _h(f.location)) if f.location else ''}</div>
  <div class="finding-desc">{_h(f.description)}</div>
  {f'<div class="impact-box"><span class="label-sm" style="color:#fbbf24">Business Impact</span><div style="color:#fcd34d;font-size:13px">{_h(f.impact)}</div></div>' if f.impact else ''}
  {f'<div class="ai-box"><div class="label-sm" style="color:#818cf8">AI Analysis</div><div style="color:#c7d2fe;font-size:13px;line-height:1.7">{_h(f.ai_explanation)}</div></div>' if f.ai_explanation else ''}
  {f'<div class="label-sm" style="color:#94a3b8;margin-top:12px">Current Code</div><div class="code-block">{_h(f.current_code)}</div>' if f.current_code else ''}
  {diff_html}
</div>"""

        findings_sections += f"""
<section class="section">
  <h2 class="section-title" style="color:{sc}">{sev.upper()} — {len(sev_findings)} finding{'s' if len(sev_findings) != 1 else ''}</h2>
  {cards}
</section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SF Scanner Report — {_h(result.org_name)}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f172a;color:#e2e8f0;line-height:1.5;font-size:14px}}
a{{color:#818cf8}}
.wrap{{max-width:1100px;margin:0 auto;padding:32px 24px}}
.header{{margin-bottom:32px;padding-bottom:20px;border-bottom:1px solid #334155}}
.org-name{{font-size:28px;font-weight:700;color:#f1f5f9;margin-bottom:6px}}
.scan-meta{{color:#64748b;font-size:13px}}
.tiles{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:32px}}
.tile{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:18px 16px;text-align:center}}
.tile-num{{font-size:30px;font-weight:700;line-height:1}}
.tile-label{{color:#64748b;font-size:11px;margin-top:6px;font-weight:500;text-transform:uppercase;letter-spacing:.04em}}
.section{{margin-bottom:36px}}
.section-title{{font-size:16px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid #1e293b}}
.exec-box{{background:linear-gradient(135deg,#1e1b4b,#1e293b);border:1px solid #3730a3;border-radius:12px;padding:24px 28px;color:#c7d2fe;font-size:14px;line-height:1.8}}
.exec-box p{{margin-bottom:12px}}.exec-box p:last-child{{margin-bottom:0}}
.rec-grid{{display:flex;flex-direction:column;gap:12px}}
.rec-card{{padding:16px 20px;border-radius:10px;border:1px solid #334155}}
.rec-header{{display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-wrap:wrap}}
.rec-phase{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;border:1px solid;border-radius:4px;padding:2px 8px}}
.rec-title{{font-size:15px;font-weight:600;color:#f1f5f9}}
.rec-desc{{color:#94a3b8;font-size:13px;margin-bottom:10px;line-height:1.6}}
.rec-meta{{display:flex;gap:8px;flex-wrap:wrap}}
.meta-chip{{background:#0f172a;border:1px solid #334155;border-radius:4px;padding:3px 10px;font-size:11px;color:#64748b}}
.scorecard{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden}}
.scorecard th{{background:#0f172a;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding:10px 14px;text-align:left}}
.scorecard td{{padding:12px 14px;border-bottom:1px solid #0f172a;vertical-align:middle}}
.scorecard tr:last-child td{{border-bottom:none}}
.sc-name{{font-weight:600;color:#f1f5f9}}
.sc-count{{color:#64748b;text-align:center}}
.sc-bar-cell{{min-width:140px}}
.bar-track{{height:6px;background:#0f172a;border-radius:3px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:3px}}
.grade-badge{{font-weight:700;font-size:13px;border:1px solid;border-radius:6px;padding:2px 10px}}
.sev-mini{{font-size:11px;margin-right:6px}}
.sc-findings{{font-size:12px}}
.finding-card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px 20px;margin-bottom:10px}}
.finding-head{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px}}
.sev-badge{{font-size:11px;font-weight:700;padding:3px 9px;border-radius:5px;text-transform:uppercase;letter-spacing:.05em}}
.finding-rule{{font-size:14px;font-weight:600;color:#f1f5f9}}
.effort-chip{{font-size:11px;color:#475569;border:1px solid #334155;border-radius:4px;padding:2px 7px;margin-left:auto}}
.finding-meta{{color:#64748b;font-size:12px;margin-bottom:8px}}
.finding-meta strong{{color:#c4b5fd}}
.finding-desc{{color:#94a3b8;font-size:13px;line-height:1.6}}
.impact-box{{margin-top:12px}}
.label-sm{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;display:block}}
.ai-box{{background:linear-gradient(135deg,#0f172a,#1e1b4b);border:1px solid #3730a3;border-radius:8px;padding:12px 16px;margin-top:12px}}
.code-block{{background:#0a0f1a;border:1px solid #1e3a5f;border-radius:8px;padding:12px 16px;font-family:monospace;font-size:12px;line-height:1.7;color:#e2e8f0;white-space:pre-wrap;overflow-x:auto;margin-top:6px}}
.diff-block{{}}
.footer{{margin-top:48px;padding-top:20px;border-top:1px solid #1e293b;color:#334155;font-size:12px;text-align:center}}
@media print{{
  body{{background:#fff;color:#1e293b}}
  .tile{{background:#f8fafc;border-color:#e2e8f0}}
  .finding-card{{background:#f8fafc;border-color:#e2e8f0;break-inside:avoid}}
  .scorecard{{background:#f8fafc}}
  .scorecard th{{background:#f1f5f9}}
  .exec-box{{background:#f0f4ff;border-color:#c7d2fe}}
  .rec-card{{background:#fafafa}}
  .code-block{{background:#f1f5f9;border-color:#e2e8f0;color:#1e293b}}
  .ai-box{{background:#f0f4ff;border-color:#c7d2fe}}
}}
@media(max-width:700px){{
  .tiles{{grid-template-columns:repeat(3,1fr)}}
}}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div class="org-name">{_h(result.org_name)}</div>
    <div class="scan-meta">
      Scan date: {_h(scan_date)}
      {f" · Completed in {round((datetime.fromisoformat(result.completed_at.replace('Z','+00:00')) - datetime.fromisoformat(result.started_at.replace('Z','+00:00'))).total_seconds())}s" if result.completed_at else ""}
      · Exported: {_h(export_ts)}
    </div>
  </div>

  <div class="tiles">{tiles_html}</div>

  {exec_html}
  {scorecard_html}
  {findings_sections}

  <div class="footer">
    Generated by SF Scanner &nbsp;·&nbsp; {_h(export_ts)}
  </div>
</div>
</body>
</html>"""


# ── CSV builder ───────────────────────────────────────────────────────────────
def _build_csv(result: ScanResult) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Severity", "Component Type", "Component Name", "Rule ID", "Rule Name",
        "Description", "Location", "Impact", "Effort", "AI Explanation", "Suggested Fix",
    ])
    for f in sorted(result.findings, key=lambda x: _SEV_ORDER.get(
        x.severity if isinstance(x.severity, str) else x.severity.value, 99
    )):
        f_sev = f.severity if isinstance(f.severity, str) else f.severity.value
        f_type = f.component_type if isinstance(f.component_type, str) else f.component_type.value
        fix = f.ai_fix_diff or f.suggested_fix or ""
        writer.writerow([
            f_sev, f_type, f.component_name, f.rule_id, f.rule_name,
            f.description, f.location or "", f.impact or "", f.effort or "",
            f.ai_explanation or "", fix,
        ])
    return buf.getvalue()


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.get("/export/{scan_id}")
async def export_scan(scan_id: str, format: str = Query("html", regex="^(html|csv)$")):
    result = _scans.get(scan_id)
    if not result:
        raise HTTPException(status_code=404, detail="Scan result not found")

    safe_org = "".join(c if c.isalnum() or c in "-_" else "_" for c in result.org_name)
    date_str = (result.started_at or "")[:10].replace("-", "")

    if format == "csv":
        content = _build_csv(result)
        filename = f"SFScanner_{safe_org}_{date_str}.csv"
        return Response(
            content=content.encode("utf-8"),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    content = _build_html_report(result)
    filename = f"SFScanner_{safe_org}_{date_str}.html"
    return Response(
        content=content.encode("utf-8"),
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
