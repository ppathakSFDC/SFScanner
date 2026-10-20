import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

// ── Severity config ───────────────────────────────────────────────────────────
const SEV = {
  critical: { bg: '#450a0a', color: '#fca5a5', border: '#7f1d1d', order: 0 },
  high:     { bg: '#431407', color: '#fdba74', border: '#9a3412', order: 1 },
  medium:   { bg: '#422006', color: '#fcd34d', border: '#92400e', order: 2 },
  low:      { bg: '#14532d', color: '#86efac', border: '#166534', order: 3 },
  info:     { bg: '#0d1e1e', color: '#94a3b8', border: '#0f2e2e', order: 4 },
}

const PHASE = {
  immediate:    { color: '#fca5a5', border: '#7f1d1d', label: 'Fix Immediately' },
  this_sprint:  { color: '#fdba74', border: '#9a3412', label: 'This Sprint' },
  quick_win:    { color: '#86efac', border: '#166534', label: 'Quick Win' },
  next_quarter: { color: '#93c5fd', border: '#1e40af', label: 'Next Quarter' },
}

const IMPACT_COLOR = { critical: '#fca5a5', high: '#fdba74', medium: '#fcd34d', low: '#86efac' }

// ── Health score ──────────────────────────────────────────────────────────────
function calcHealth(findings) {
  let score = 100
  for (const f of findings) {
    if (f.severity === 'critical') score -= 15
    else if (f.severity === 'high')     score -= 8
    else if (f.severity === 'medium')   score -= 4
    else if (f.severity === 'low')      score -= 1
  }
  return Math.max(0, score)
}

function grade(score) {
  if (score >= 90) return { letter: 'A', color: '#86efac' }
  if (score >= 75) return { letter: 'B', color: '#a3e635' }
  if (score >= 60) return { letter: 'C', color: '#fcd34d' }
  if (score >= 45) return { letter: 'D', color: '#fdba74' }
  return { letter: 'F', color: '#fca5a5' }
}

// ── Tiny components ───────────────────────────────────────────────────────────
function SevBadge({ s }) {
  const c = SEV[s] || SEV.info
  return (
    <span style={{
      padding: '3px 9px', borderRadius: 5, fontSize: 11, fontWeight: 700,
      background: c.bg, color: c.color, border: `1px solid ${c.border}`,
      textTransform: 'uppercase', letterSpacing: '0.05em', whiteSpace: 'nowrap',
    }}>{s}</span>
  )
}

function DiffBlock({ diff }) {
  if (!diff) return null
  return (
    <div style={{
      background: '#000000', borderRadius: 8, padding: '12px 16px', marginTop: 8,
      fontSize: 12, fontFamily: 'monospace', lineHeight: 1.7,
      border: '1px solid #1e3a5f', overflowX: 'auto',
    }}>
      {diff.split('\n').map((line, i) => (
        <div key={i} style={{
          color: line.startsWith('+') ? '#86efac' : line.startsWith('-') ? '#fca5a5'
               : line.startsWith('@@') ? '#93c5fd' : '#94a3b8',
          background: line.startsWith('+') ? 'rgba(134,239,172,0.06)'
                     : line.startsWith('-') ? 'rgba(252,165,165,0.06)' : 'transparent',
        }}>{line || ' '}</div>
      ))}
    </div>
  )
}

function ProgressBar({ value, color }) {
  return (
    <div style={{ height: 6, background: '#050c0c', borderRadius: 3, overflow: 'hidden', flex: 1 }}>
      <div style={{
        height: '100%', width: `${Math.min(100, value)}%`,
        background: color, borderRadius: 3, transition: 'width 0.6s ease',
      }} />
    </div>
  )
}

// ── Finding card ──────────────────────────────────────────────────────────────
function FindingCard({ f }) {
  const [open, setOpen] = useState(false)
  const c = SEV[f.severity] || SEV.info
  return (
    <div
      style={{
        background: '#0d1e1e', borderRadius: 10, marginBottom: 10,
        border: `1px solid ${open ? c.border : '#0f2e2e'}`,
        borderLeft: `3px solid ${c.color}`, overflow: 'hidden',
        transition: 'border-color 0.15s',
      }}
      onClick={() => setOpen(o => !o)}
    >
      <div style={{ padding: '14px 18px', cursor: 'pointer', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 3 }}>
            <SevBadge s={f.severity} />
            <span style={{ color: '#f1f5f9', fontWeight: 600, fontSize: 14 }}>{f.rule_name}</span>
          </div>
          <div style={{ color: '#4a9a9a', fontSize: 12 }}>
            <span style={{ color: '#94a3b8' }}>{f.component_type}</span>
            {' · '}
            <span style={{ color: '#a5f3fc', fontWeight: 600 }}>{f.component_name}</span>
            {f.location && <span style={{ color: '#4a9a9a' }}> · {f.location}</span>}
          </div>
          <div style={{ color: '#94a3b8', fontSize: 13, lineHeight: 1.6, marginTop: 6 }}>{f.description}</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, flexShrink: 0 }}>
          {f.effort && (
            <span style={{ fontSize: 11, color: '#4a9a9a', border: '1px solid #0f2e2e', borderRadius: 4, padding: '2px 7px' }}>
              {f.effort} effort
            </span>
          )}
          <span style={{ color: '#4a9a9a', fontSize: 16 }}>{open ? '▲' : '▼'}</span>
        </div>
      </div>

      {open && (
        <div style={{ borderTop: '1px solid #0f2e2e', padding: '16px 18px', background: '#050c0c' }}
             onClick={e => e.stopPropagation()}>
          {f.impact && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ color: '#fbbf24', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', marginBottom: 4 }}>Business Impact</div>
              <div style={{ color: '#fcd34d', fontSize: 13, lineHeight: 1.6 }}>{f.impact}</div>
            </div>
          )}
          {f.ai_explanation && (
            <div style={{
              background: 'linear-gradient(135deg,#050c0c,#001c26)', borderRadius: 8,
              padding: '12px 16px', border: '1px solid #3730a3', marginBottom: 14,
            }}>
              <div style={{ color: '#22d3ee', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', marginBottom: 6 }}>AI Analysis</div>
              <div style={{ color: '#c7d2fe', fontSize: 13, lineHeight: 1.7 }}>{f.ai_explanation}</div>
            </div>
          )}
          {f.current_code && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ color: '#94a3b8', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', marginBottom: 6 }}>Current Code</div>
              <div style={{
                background: '#000000', borderRadius: 8, padding: '12px 16px',
                fontSize: 12, fontFamily: 'monospace', color: '#e2e8f0', lineHeight: 1.7,
                border: '1px solid #1e3a5f', whiteSpace: 'pre-wrap', overflowX: 'auto',
              }}>{f.current_code}</div>
            </div>
          )}
          {(f.ai_fix_diff || f.suggested_fix) && (
            <div>
              <div style={{ color: '#86efac', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', marginBottom: 6 }}>Suggested Fix</div>
              {f.ai_fix_diff
                ? <DiffBlock diff={f.ai_fix_diff} />
                : <div style={{
                    background: '#000000', borderRadius: 8, padding: '12px 16px',
                    fontSize: 12, fontFamily: 'monospace', color: '#86efac', lineHeight: 1.7,
                    border: '1px solid #166534', whiteSpace: 'pre-wrap',
                  }}>{f.suggested_fix}</div>
              }
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Recommendation card ───────────────────────────────────────────────────────
function RecCard({ rec }) {
  const ph = PHASE[rec.phase] || PHASE.next_quarter
  const imp = IMPACT_COLOR[rec.impact] || '#94a3b8'
  return (
    <div style={{
      background: '#0d1e1e', borderRadius: 10, padding: '16px 20px',
      border: '1px solid #0f2e2e', borderLeft: `4px solid ${ph.color}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 8 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
            <span style={{
              padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700,
              background: ph.color + '22', color: ph.color, textTransform: 'uppercase', letterSpacing: '0.06em',
            }}>{ph.label}</span>
            <span style={{ color: '#f1f5f9', fontWeight: 600, fontSize: 14 }}>{rec.title}</span>
          </div>
          <div style={{ color: '#94a3b8', fontSize: 13, lineHeight: 1.6 }}>{rec.description}</div>
        </div>
        <div style={{ flexShrink: 0, textAlign: 'right' }}>
          <div style={{ color: imp, fontWeight: 700, fontSize: 13 }}>{rec.finding_count} findings</div>
          <div style={{ color: '#4a9a9a', fontSize: 11, marginTop: 2 }}>{rec.effort} effort</div>
        </div>
      </div>
      {rec.component_types?.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
          {rec.component_types.map(t => (
            <span key={t} style={{
              fontSize: 11, padding: '2px 8px', borderRadius: 4,
              background: '#050c0c', color: '#4a9a9a', border: '1px solid #0f2e2e',
            }}>{t}</span>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Component health scorecard ────────────────────────────────────────────────
function HealthScorecard({ findings, componentSummary }) {
  const byType = {}
  for (const [type, count] of Object.entries(componentSummary || {})) {
    byType[type] = { count, findings: [] }
  }
  for (const f of findings) {
    if (!byType[f.component_type]) byType[f.component_type] = { count: 0, findings: [] }
    byType[f.component_type].findings.push(f)
  }

  const rows = Object.entries(byType).map(([type, data]) => {
    const score = calcHealth(data.findings)
    const g = grade(score)
    return { type, score, grade: g, count: data.count, issues: data.findings.length }
  }).sort((a, b) => a.score - b.score)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {rows.map(r => (
        <div key={r.type} style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ width: 160, color: '#94a3b8', fontSize: 13, flexShrink: 0 }}>{r.type}</div>
          <ProgressBar value={r.score} color={r.grade.color} />
          <div style={{ width: 36, textAlign: 'right', fontWeight: 700, fontSize: 14, color: r.grade.color, flexShrink: 0 }}>
            {r.grade.letter}
          </div>
          <div style={{ width: 70, textAlign: 'right', color: '#4a9a9a', fontSize: 12, flexShrink: 0 }}>
            {r.issues} issue{r.issues !== 1 ? 's' : ''}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── PDF export ────────────────────────────────────────────────────────────────
function buildPrintHTML(result) {
  const overallScore = calcHealth(result.findings)
  const overallGrade = grade(overallScore)
  const SEV_PRINT = {
    critical: '#dc2626', high: '#ea580c', medium: '#d97706', low: '#16a34a', info: '#6b7280',
  }
  const PHASE_PRINT = {
    immediate: '#dc2626', this_sprint: '#ea580c', quick_win: '#16a34a', next_quarter: '#2563eb',
  }
  const PHASE_LABEL = {
    immediate: 'Fix Immediately', this_sprint: 'This Sprint',
    quick_win: 'Quick Win', next_quarter: 'Next Quarter',
  }

  const findingRows = [...result.findings]
    .sort((a, b) => (SEV[a.severity]?.order ?? 99) - (SEV[b.severity]?.order ?? 99))
    .map(f => `
      <div class="finding">
        <div class="finding-header">
          <span class="badge" style="color:${SEV_PRINT[f.severity]||'#6b7280'};border-color:${SEV_PRINT[f.severity]||'#6b7280'}">${f.severity.toUpperCase()}</span>
          <strong>${escH(f.rule_name)}</strong>
          <span class="muted">${escH(f.component_type)} · ${escH(f.component_name)}</span>
        </div>
        <div class="finding-desc">${escH(f.description)}</div>
        ${f.impact ? `<div class="impact"><strong>Impact:</strong> ${escH(f.impact)}</div>` : ''}
        ${f.suggested_fix ? `<div class="fix"><strong>Fix:</strong> ${escH(f.suggested_fix)}</div>` : ''}
        ${f.ai_explanation ? `<div class="ai"><strong>AI Analysis:</strong> ${escH(f.ai_explanation)}</div>` : ''}
      </div>`).join('')

  const recRows = [...(result.recommendations || [])]
    .sort((a, b) => ['immediate','this_sprint','quick_win','next_quarter'].indexOf(a.phase) - ['immediate','this_sprint','quick_win','next_quarter'].indexOf(b.phase))
    .map(r => `
      <div class="rec">
        <div class="rec-header">
          <span class="phase-badge" style="color:${PHASE_PRINT[r.phase]||'#2563eb'};border-color:${PHASE_PRINT[r.phase]||'#2563eb'}">${PHASE_LABEL[r.phase]||r.phase}</span>
          <strong>${escH(r.title)}</strong>
          <span class="muted">${r.finding_count} findings · ${r.effort} effort</span>
        </div>
        <div class="rec-desc">${escH(r.description)}</div>
      </div>`).join('')

  const byType = {}
  for (const [type, count] of Object.entries(result.component_summary || {}))
    byType[type] = { count, findings: [] }
  for (const f of result.findings) {
    if (!byType[f.component_type]) byType[f.component_type] = { count: 0, findings: [] }
    byType[f.component_type].findings.push(f)
  }
  const scorecardRows = Object.entries(byType).map(([type, data]) => {
    const s = calcHealth(data.findings)
    const g = grade(s)
    return `<tr><td>${escH(type)}</td><td style="color:${g.color};font-weight:700">${g.letter}</td><td>${s}</td><td>${data.findings.length}</td><td>${data.count}</td></tr>`
  }).join('')

  const scanDuration = result.completed_at
    ? Math.round((new Date(result.completed_at) - new Date(result.started_at)) / 1000)
    : null

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>ProWorker Report — ${escH(result.org_name)}</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:12px;color:#111;background:#fff;padding:20px 28px}
  h1{font-size:22px;font-weight:800;margin-bottom:4px}
  h2{font-size:15px;font-weight:700;color:#1e40af;border-bottom:2px solid #1e40af;padding-bottom:4px;margin:24px 0 12px}
  h3{font-size:13px;font-weight:700;margin:16px 0 8px;color:#374151}
  .meta{color:#6b7280;font-size:11px;margin-bottom:12px}
  .grade{font-size:40px;font-weight:800;color:${overallGrade.color};line-height:1}
  .tiles{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:16px 0 24px}
  .tile{border:1px solid #e5e7eb;border-radius:8px;padding:12px 14px}
  .tile-num{font-size:24px;font-weight:700}
  .tile-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em}
  .tile-sub{font-size:10px;color:#9ca3af}
  .exec{background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:16px 20px;margin:16px 0 24px}
  .exec-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#1d4ed8;margin-bottom:8px}
  .exec-body{color:#1e3a8a;font-size:12px;line-height:1.8;white-space:pre-line}
  .finding{border:1px solid #e5e7eb;border-radius:7px;padding:12px 14px;margin-bottom:8px;page-break-inside:avoid}
  .finding-header{display:flex;align-items:baseline;gap:8px;margin-bottom:4px;flex-wrap:wrap}
  .badge{font-size:10px;font-weight:700;text-transform:uppercase;border:1px solid;border-radius:4px;padding:1px 7px}
  .finding-desc{color:#374151;line-height:1.6;margin-bottom:4px}
  .impact{color:#92400e;font-size:11px;margin-top:4px}
  .fix{color:#14532d;font-size:11px;margin-top:4px;font-family:monospace}
  .ai{color:#312e81;font-size:11px;margin-top:6px;background:#eef2ff;padding:6px 10px;border-radius:5px}
  .muted{color:#6b7280;font-size:11px}
  .rec{border:1px solid #e5e7eb;border-radius:7px;padding:12px 14px;margin-bottom:8px;page-break-inside:avoid}
  .rec-header{display:flex;align-items:baseline;gap:8px;margin-bottom:4px;flex-wrap:wrap}
  .phase-badge{font-size:10px;font-weight:700;text-transform:uppercase;border:1px solid;border-radius:4px;padding:1px 7px}
  .rec-desc{color:#374151;font-size:11px;line-height:1.6}
  table{border-collapse:collapse;width:100%;font-size:12px}
  th{background:#f3f4f6;text-align:left;padding:8px 10px;font-weight:700;border:1px solid #e5e7eb}
  td{padding:7px 10px;border:1px solid #e5e7eb}
  .header-row{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:4px}
  @media print{
    body{padding:10px 16px}
    @page{margin:.5in;size:A4}
    h2{page-break-after:avoid}
  }
</style>
</head>
<body>
<div class="header-row">
  <div>
    <h1>${escH(result.org_name)}</h1>
    <div class="meta">Salesforce Org Health Report · Generated ${new Date().toLocaleString()}${scanDuration ? ` · Scan duration: ${scanDuration}s` : ''}</div>
  </div>
  <div style="text-align:center">
    <div class="grade">${overallGrade.letter}</div>
    <div class="meta">Org Health</div>
  </div>
</div>

<div class="tiles">
  <div class="tile"><div class="tile-num" style="color:#0284c7">${result.total_components}</div><div class="tile-label" style="color:#0284c7">Scanned</div><div class="tile-sub">components</div></div>
  <div class="tile"><div class="tile-num" style="color:#374151">${result.total_findings}</div><div class="tile-label" style="color:#374151">Total</div><div class="tile-sub">findings</div></div>
  <div class="tile"><div class="tile-num" style="color:#dc2626">${result.critical_count}</div><div class="tile-label" style="color:#dc2626">Critical</div><div class="tile-sub">severity</div></div>
  <div class="tile"><div class="tile-num" style="color:#ea580c">${result.high_count}</div><div class="tile-label" style="color:#ea580c">High</div><div class="tile-sub">severity</div></div>
  <div class="tile"><div class="tile-num" style="color:#d97706">${result.medium_count}</div><div class="tile-label" style="color:#d97706">Medium</div><div class="tile-sub">severity</div></div>
  <div class="tile"><div class="tile-num" style="color:#16a34a">${result.low_count}</div><div class="tile-label" style="color:#16a34a">Low</div><div class="tile-sub">severity</div></div>
</div>

${result.executive_summary ? `
<div class="exec">
  <div class="exec-label">AI Executive Summary</div>
  <div class="exec-body">${escH(result.executive_summary)}</div>
</div>` : ''}

<h2>Findings (${result.total_findings})</h2>
${findingRows || '<p style="color:#6b7280">No findings.</p>'}

${recRows ? `<h2>Recommendations</h2>${recRows}` : ''}

<h2>Component Health Scorecard</h2>
<table>
  <thead><tr><th>Component Type</th><th>Grade</th><th>Score</th><th>Issues</th><th>Total</th></tr></thead>
  <tbody>${scorecardRows}</tbody>
</table>

<div style="margin-top:24px;color:#9ca3af;font-size:10px;text-align:center">
  Generated by ProWorker · ${new Date().toLocaleDateString()}
</div>
</body></html>`
}

function escH(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')
}

function exportPDF(result) {
  const html = buildPrintHTML(result)
  const win = window.open('', '_blank', 'width=900,height=700')
  win.document.write(html)
  win.document.close()
  win.onload = () => {
    win.focus()
    win.print()
  }
}

// ── Main page ─────────────────────────────────────────────────────────────────
const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info']

export default function ScanReport() {
  const { scanId } = useParams()
  const navigate = useNavigate()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sevFilter, setSevFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState('findings')

  useEffect(() => {
    fetch(`/scan/result/${scanId}`, { credentials: 'include' })
      .then(r => r.json())
      .then(data => { setResult(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [scanId])

  if (loading) return (
    <div style={{ minHeight: '100vh', background: '#050c0c', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ color: '#94a3b8' }}>Loading report...</div>
    </div>
  )
  if (!result) return (
    <div style={{ minHeight: '100vh', background: '#050c0c', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ color: '#fca5a5' }}>Report not found.</div>
    </div>
  )

  const componentTypes = [...new Set(result.findings.map(f => f.component_type))]

  const filtered = result.findings.filter(f => {
    if (sevFilter !== 'all' && f.severity !== sevFilter) return false
    if (typeFilter !== 'all' && f.component_type !== typeFilter) return false
    if (search) {
      const q = search.toLowerCase()
      if (!f.component_name.toLowerCase().includes(q) &&
          !f.rule_name.toLowerCase().includes(q) &&
          !f.description.toLowerCase().includes(q)) return false
    }
    return true
  })

  const sortedFindings = [...filtered].sort((a, b) =>
    (SEV[a.severity]?.order ?? 99) - (SEV[b.severity]?.order ?? 99)
  )

  const scanDuration = result.completed_at
    ? Math.round((new Date(result.completed_at) - new Date(result.started_at)) / 1000)
    : null

  const overallScore = calcHealth(result.findings)
  const overallGrade = grade(overallScore)

  const tiles = [
    { num: result.total_components, label: 'Scanned', sub: 'components', color: '#a5f3fc' },
    { num: result.total_findings,   label: 'Total',    sub: 'findings',   color: '#94a3b8' },
    { num: result.critical_count,   label: 'Critical', sub: 'severity',   color: SEV.critical.color },
    { num: result.high_count,       label: 'High',     sub: 'severity',   color: SEV.high.color },
    { num: result.medium_count,     label: 'Medium',   sub: 'severity',   color: SEV.medium.color },
    { num: result.low_count,        label: 'Low',      sub: 'severity',   color: SEV.low.color },
  ]

  const recommendations = result.recommendations || []
  const PHASE_ORDER = ['immediate', 'this_sprint', 'quick_win', 'next_quarter']
  const sortedRecs = [...recommendations].sort(
    (a, b) => PHASE_ORDER.indexOf(a.phase) - PHASE_ORDER.indexOf(b.phase)
  )

  const base = `/scan/export/${scanId}`

  return (
    <div style={{ minHeight: '100vh', background: '#050c0c', padding: '24px 24px 60px' }}>
      <div style={{ maxWidth: 1240, margin: '0 auto' }}>

        {/* Top bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
          <button
            onClick={() => navigate('/')}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, padding: 0 }}
          >
            ← Back
          </button>
          <div style={{ display: 'flex', gap: 8 }}>
            <a
              href={`${base}?format=csv`}
              download
              style={{
                padding: '8px 16px', background: '#0d1e1e', border: '1px solid #0f2e2e',
                borderRadius: 8, color: '#94a3b8', fontSize: 13, fontWeight: 600,
                textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              ↓ CSV
            </a>
            <button
              onClick={() => exportPDF(result)}
              style={{
                padding: '8px 16px', background: '#0d1e1e', border: '1px solid #0f2e2e',
                borderRadius: 8, color: '#f87171', fontSize: 13, fontWeight: 600,
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              ↓ PDF
            </button>
            <a
              href={`${base}?format=html`}
              download
              style={{
                padding: '8px 16px', background: 'linear-gradient(135deg,#06b6d4,#0891b2)',
                border: 'none', borderRadius: 8, color: 'white', fontSize: 13, fontWeight: 600,
                textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              ↓ Export Report
            </a>
          </div>
        </div>

        {/* Header */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#f1f5f9' }}>{result.org_name}</div>
              <div style={{ color: '#4a9a9a', fontSize: 13, marginTop: 4 }}>
                Scanned {new Date(result.started_at).toLocaleString()}
                {scanDuration && ` · ${scanDuration}s`}
              </div>
            </div>
            <div style={{
              marginLeft: 'auto', textAlign: 'center',
              background: '#0d1e1e', borderRadius: 12, padding: '10px 20px',
              border: `2px solid ${overallGrade.color}22`,
            }}>
              <div style={{ fontSize: 36, fontWeight: 800, color: overallGrade.color, lineHeight: 1 }}>{overallGrade.letter}</div>
              <div style={{ color: '#4a9a9a', fontSize: 11, marginTop: 2 }}>Org Health</div>
            </div>
          </div>
        </div>

        {/* Summary tiles */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginBottom: 28 }}>
          {tiles.map(t => (
            <div key={t.label} style={{
              background: '#0d1e1e', borderRadius: 10, padding: '16px 18px',
              border: '1px solid #0f2e2e',
            }}>
              <div style={{ fontSize: 28, fontWeight: 700, color: t.color }}>{t.num}</div>
              <div style={{ color: t.color, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{t.label}</div>
              <div style={{ color: '#4a9a9a', fontSize: 11, marginTop: 1 }}>{t.sub}</div>
            </div>
          ))}
        </div>

        {/* Executive summary */}
        {result.executive_summary && (
          <div style={{
            background: 'linear-gradient(135deg,#050c0c,#001c26)', borderRadius: 12,
            padding: '22px 26px', border: '1px solid #3730a3', marginBottom: 24,
          }}>
            <div style={{ color: '#22d3ee', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
              AI Executive Summary
            </div>
            <div style={{ color: '#c7d2fe', fontSize: 14, lineHeight: 1.8, whiteSpace: 'pre-line' }}>
              {result.executive_summary}
            </div>
          </div>
        )}

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 0, marginBottom: 20, background: '#0d1e1e', borderRadius: 10, padding: 4, width: 'fit-content' }}>
          {[
            ['findings', `Findings (${result.total_findings})`],
            ['soql', `SOQL Analysis (${result.findings.filter(f => f.component_type === 'SOQL').length})`],
            ['recommendations', `Recommendations (${recommendations.length})`],
            ['scorecard', 'Health Scorecard'],
            ['performance', 'Performance'],
          ].map(([tab, label]) => (
            <button key={tab} onClick={() => setActiveTab(tab)} style={{
              padding: '8px 18px', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600,
              cursor: 'pointer', transition: 'all 0.15s',
              background: activeTab === tab ? 'linear-gradient(135deg,#06b6d4,#0891b2)' : 'transparent',
              color: activeTab === tab ? 'white' : '#1e4a4a',
            }}>{label}</button>
          ))}
        </div>

        {/* ── Findings tab ── */}
        {activeTab === 'findings' && (
          <div style={{ display: 'flex', gap: 20 }}>
            {/* Sidebar */}
            <div style={{ width: 210, flexShrink: 0 }}>
              <div style={{ background: '#0d1e1e', borderRadius: 10, padding: 16, border: '1px solid #0f2e2e', marginBottom: 12 }}>
                <div style={{ color: '#94a3b8', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>Severity</div>
                {['all', ...SEVERITIES].map(s => {
                  const active = sevFilter === s
                  const c = SEV[s]
                  return (
                    <button key={s} onClick={() => setSevFilter(s)} style={{
                      display: 'block', width: '100%', padding: '7px 10px', borderRadius: 7,
                      border: '1px solid transparent', cursor: 'pointer', fontSize: 13,
                      textAlign: 'left', marginBottom: 3, transition: 'all 0.12s',
                      background: active ? (c?.bg || '#0f2e2e') : 'transparent',
                      color: active ? (c?.color || '#f1f5f9') : '#94a3b8',
                      borderColor: active ? (c?.border || '#06b6d4') : 'transparent',
                    }}>
                      {s === 'all' ? 'All Severities' : s.charAt(0).toUpperCase() + s.slice(1)}
                      {s !== 'all' && (
                        <span style={{ float: 'right', color: '#4a9a9a' }}>
                          {result.findings.filter(f => f.severity === s).length}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>

              <div style={{ background: '#0d1e1e', borderRadius: 10, padding: 16, border: '1px solid #0f2e2e' }}>
                <div style={{ color: '#94a3b8', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>Component</div>
                {['all', ...componentTypes].map(t => (
                  <button key={t} onClick={() => setTypeFilter(t)} style={{
                    display: 'block', width: '100%', padding: '7px 10px', borderRadius: 7,
                    border: '1px solid transparent', cursor: 'pointer', fontSize: 13,
                    textAlign: 'left', marginBottom: 3,
                    background: typeFilter === t ? '#1e3a5f' : 'transparent',
                    color: typeFilter === t ? '#93c5fd' : '#94a3b8',
                    borderColor: typeFilter === t ? '#3b82f644' : 'transparent',
                  }}>
                    {t === 'all' ? 'All Types' : t}
                    {t !== 'all' && (
                      <span style={{ float: 'right', color: '#4a9a9a' }}>
                        {result.findings.filter(f => f.component_type === t).length}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Findings list */}
            <div style={{ flex: 1 }}>
              <input
                placeholder="Search findings by component, rule, or description…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                style={{
                  width: '100%', background: '#0d1e1e', border: '1px solid #0f2e2e',
                  borderRadius: 10, padding: '11px 16px', color: '#f1f5f9', fontSize: 14,
                  marginBottom: 14, outline: 'none', boxSizing: 'border-box',
                }}
              />
              {sortedFindings.length === 0
                ? <div style={{ textAlign: 'center', color: '#4a9a9a', padding: '48px 0', fontSize: 15 }}>
                    No findings match your filters.
                  </div>
                : sortedFindings.map(f => <FindingCard key={f.id} f={f} />)
              }
            </div>
          </div>
        )}

        {/* ── SOQL Analysis tab ── */}
        {activeTab === 'soql' && (() => {
          const soqlFindings = result.findings.filter(f => f.component_type === 'SOQL')
          const byRule = {}
          for (const f of soqlFindings) {
            if (!byRule[f.rule_id]) byRule[f.rule_id] = { name: f.rule_name, sev: f.severity, findings: [] }
            byRule[f.rule_id].findings.push(f)
          }
          const RULE_ICONS = {
            'SOQL-001': '⏱', 'SOQL-002': '🔍', 'SOQL-003': '🃏', 'SOQL-004': '🚫',
            'SOQL-005': '≠',  'SOQL-006': '∨',  'SOQL-007': '📄', 'SOQL-008': '📦',
            'SOQL-009': '🔗', 'SOQL-010': '📇',
          }
          return (
            <div>
              {soqlFindings.length === 0 ? (
                <div style={{ textAlign: 'center', color: '#4a9a9a', padding: '60px 0', fontSize: 15 }}>
                  <div style={{ fontSize: 32, marginBottom: 12 }}>✓</div>
                  No SOQL anti-patterns detected in scanned Apex classes.
                </div>
              ) : (
                <>
                  {/* Summary strip */}
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 24 }}>
                    {['critical','high','medium','low'].map(s => {
                      const n = soqlFindings.filter(f => f.severity === s).length
                      if (!n) return null
                      const c = SEV[s]
                      return (
                        <div key={s} style={{
                          background: c.bg, border: `1px solid ${c.border}`, borderRadius: 8,
                          padding: '10px 18px', display: 'flex', alignItems: 'center', gap: 10,
                        }}>
                          <span style={{ fontSize: 22, fontWeight: 800, color: c.color }}>{n}</span>
                          <span style={{ color: c.color, fontSize: 12, fontWeight: 700, textTransform: 'uppercase' }}>{s}</span>
                        </div>
                      )
                    })}
                    <div style={{ background: '#0d1e1e', border: '1px solid #0f2e2e', borderRadius: 8, padding: '10px 18px', display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ fontSize: 22, fontWeight: 800, color: '#a5f3fc' }}>
                        {new Set(soqlFindings.map(f => f.component_name)).size}
                      </span>
                      <span style={{ color: '#a5f3fc', fontSize: 12, fontWeight: 700, textTransform: 'uppercase' }}>Apex Classes</span>
                    </div>
                  </div>

                  {/* Issues grouped by rule */}
                  {Object.entries(byRule).sort((a,b) => (SEV[a[1].sev]?.order??99) - (SEV[b[1].sev]?.order??99)).map(([ruleId, group]) => (
                    <div key={ruleId} style={{ marginBottom: 24 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                        <span style={{ fontSize: 18 }}>{RULE_ICONS[ruleId] || '⚠'}</span>
                        <SevBadge s={group.sev} />
                        <span style={{ color: '#f1f5f9', fontWeight: 700, fontSize: 15 }}>{group.name}</span>
                        <span style={{ color: '#4a9a9a', fontSize: 13 }}>— {group.findings.length} class{group.findings.length !== 1 ? 'es' : ''}</span>
                        <span style={{ marginLeft: 'auto', color: '#06b6d4', fontSize: 12, background: '#001c26', padding: '2px 8px', borderRadius: 4 }}>{ruleId}</span>
                      </div>

                      {group.findings.map((f, i) => (
                        <div key={i} style={{
                          background: '#0d1e1e', borderRadius: 10, padding: '16px 18px', marginBottom: 8,
                          border: '1px solid #0f2e2e', borderLeft: `3px solid ${SEV[f.severity]?.color || '#94a3b8'}`,
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, flexWrap: 'wrap' }}>
                            <span style={{ color: '#a5f3fc', fontWeight: 700, fontSize: 14 }}>{f.component_name}</span>
                            {f.location && <span style={{ color: '#4a9a9a', fontSize: 12 }}>{f.location}</span>}
                          </div>
                          <div style={{ color: '#94a3b8', fontSize: 13, lineHeight: 1.6, marginBottom: 12 }}>{f.description}</div>

                          {f.current_code && (
                            <div style={{ marginBottom: 12 }}>
                              <div style={{ color: '#fca5a5', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', marginBottom: 6 }}>
                                Problematic Query
                              </div>
                              <div style={{
                                background: '#000000', borderRadius: 8, padding: '10px 14px',
                                fontSize: 12, fontFamily: 'monospace', color: '#fca5a5',
                                border: '1px solid #7f1d1d', whiteSpace: 'pre-wrap', overflowX: 'auto',
                              }}>{f.current_code}</div>
                            </div>
                          )}

                          {f.impact && (
                            <div style={{ marginBottom: 12, padding: '8px 12px', background: '#422006', borderRadius: 6, border: '1px solid #92400e' }}>
                              <span style={{ color: '#fbbf24', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', marginRight: 8 }}>Performance Impact</span>
                              <span style={{ color: '#fcd34d', fontSize: 12 }}>{f.impact}</span>
                            </div>
                          )}

                          {f.suggested_fix && (
                            <div>
                              <div style={{ color: '#86efac', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', marginBottom: 6 }}>Fix</div>
                              <div style={{
                                background: '#000000', borderRadius: 8, padding: '10px 14px',
                                fontSize: 12, fontFamily: 'monospace', color: '#86efac',
                                border: '1px solid #166534', whiteSpace: 'pre-wrap', overflowX: 'auto',
                              }}>{f.suggested_fix}</div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ))}
                </>
              )}
            </div>
          )
        })()}

        {/* ── Recommendations tab ── */}
        {activeTab === 'recommendations' && (
          <div>
            {sortedRecs.length === 0 ? (
              <div style={{ textAlign: 'center', color: '#4a9a9a', padding: '48px 0', fontSize: 15 }}>
                No recommendations available — run a scan with an Anthropic API key to generate them.
              </div>
            ) : (
              <>
                <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 20, lineHeight: 1.6 }}>
                  AI-generated remediation roadmap based on {result.total_findings} findings across {result.total_components} components.
                </div>
                {/* Phase groups */}
                {PHASE_ORDER.map(phase => {
                  const recs = sortedRecs.filter(r => r.phase === phase)
                  if (!recs.length) return null
                  const ph = PHASE[phase]
                  return (
                    <div key={phase} style={{ marginBottom: 28 }}>
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14,
                      }}>
                        <div style={{ width: 4, height: 20, borderRadius: 2, background: ph.color }} />
                        <div style={{ color: ph.color, fontSize: 13, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                          {ph.label}
                        </div>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {recs.map((r, i) => <RecCard key={i} rec={r} />)}
                      </div>
                    </div>
                  )
                })}

                {/* Quick stats */}
                <div style={{
                  background: '#0d1e1e', borderRadius: 10, padding: '18px 22px',
                  border: '1px solid #0f2e2e', marginTop: 8,
                }}>
                  <div style={{ color: '#94a3b8', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 14 }}>
                    Effort Breakdown
                  </div>
                  <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
                    {['low', 'medium', 'high'].map(e => {
                      const recs = result.findings.filter(f => f.effort === e)
                      return (
                        <div key={e}>
                          <div style={{ fontSize: 22, fontWeight: 700, color: e === 'low' ? '#86efac' : e === 'medium' ? '#fcd34d' : '#fca5a5' }}>
                            {recs.length}
                          </div>
                          <div style={{ color: '#4a9a9a', fontSize: 12 }}>{e} effort</div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Health scorecard tab ── */}
        {activeTab === 'scorecard' && (
          <div>
            <div style={{ background: '#0d1e1e', borderRadius: 12, padding: '22px 26px', border: '1px solid #0f2e2e', marginBottom: 20 }}>
              <div style={{ color: '#94a3b8', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 20 }}>
                Component Health Scores
              </div>
              <HealthScorecard findings={result.findings} componentSummary={result.component_summary} />
              <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid #0f2e2e', display: 'flex', gap: 24, flexWrap: 'wrap' }}>
                {[['A', '90–100', '#86efac'], ['B', '75–89', '#a3e635'], ['C', '60–74', '#fcd34d'], ['D', '45–59', '#fdba74'], ['F', '0–44', '#fca5a5']].map(([g, range, col]) => (
                  <div key={g} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontWeight: 700, color: col, fontSize: 14, width: 14 }}>{g}</span>
                    <span style={{ color: '#4a9a9a', fontSize: 12 }}>{range}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Findings by component grouped */}
            {componentTypes.map(type => {
              const typeFindings = result.findings.filter(f => f.component_type === type)
              const score = calcHealth(typeFindings)
              const g = grade(score)
              if (!typeFindings.length) return null
              return (
                <div key={type} style={{ background: '#0d1e1e', borderRadius: 10, padding: '18px 22px', border: '1px solid #0f2e2e', marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                    <span style={{ fontSize: 20, fontWeight: 800, color: g.color }}>{g.letter}</span>
                    <span style={{ color: '#f1f5f9', fontWeight: 600, fontSize: 15 }}>{type}</span>
                    <span style={{ color: '#4a9a9a', fontSize: 13 }}>— {typeFindings.length} finding{typeFindings.length !== 1 ? 's' : ''}</span>
                  </div>
                  {typeFindings.slice(0, 5).map(f => (
                    <div key={f.id} style={{
                      display: 'flex', alignItems: 'flex-start', gap: 10,
                      padding: '8px 0', borderTop: '1px solid #0f2e2e',
                    }}>
                      <SevBadge s={f.severity} />
                      <div>
                        <div style={{ color: '#f1f5f9', fontSize: 13, fontWeight: 500 }}>{f.rule_name}</div>
                        <div style={{ color: '#4a9a9a', fontSize: 12 }}>{f.component_name}</div>
                      </div>
                    </div>
                  ))}
                  {typeFindings.length > 5 && (
                    <div
                      style={{ color: '#06b6d4', fontSize: 13, cursor: 'pointer', marginTop: 8, paddingTop: 8, borderTop: '1px solid #0f2e2e' }}
                      onClick={() => { setTypeFilter(type); setActiveTab('findings') }}
                    >
                      + {typeFindings.length - 5} more — view all →
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* ── Performance tab ── */}
        {activeTab === 'performance' && (() => {
          const timing = result.scanner_timing || {}
          const totalMs = result.scan_duration_ms ||
            (result.completed_at ? Math.round(new Date(result.completed_at) - new Date(result.started_at)) : 0)
          const rows = Object.entries(timing)
            .map(([scanner, ms]) => ({
              scanner,
              ms,
              components: result.component_summary[scanner] || 0,
              findings: result.findings.filter(f => f.component_type === scanner).length,
            }))
            .sort((a, b) => b.ms - a.ms)
          const maxMs = Math.max(...rows.map(r => r.ms), 1)
          const avgMs = rows.length ? Math.round(rows.reduce((s, r) => s + r.ms, 0) / rows.length) : 0
          const slowest = rows[0]
          const msColor = ms => ms > 2000 ? '#fca5a5' : ms > 500 ? '#fcd34d' : '#86efac'
          const fmtMs = ms => ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms}ms`

          return (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
                {[
                  { num: fmtMs(totalMs), label: 'Total Scan', sub: 'elapsed time', color: '#a5f3fc' },
                  { num: rows.length, label: 'Scanners', sub: 'component types', color: '#86efac' },
                  { num: fmtMs(avgMs), label: 'Avg / Scanner', sub: 'mean elapsed', color: '#fcd34d' },
                  ...(slowest ? [{ num: slowest.scanner, label: 'Slowest', sub: fmtMs(slowest.ms), color: '#fca5a5' }] : []),
                ].map(t => (
                  <div key={t.label} style={{ background: '#0d1e1e', borderRadius: 10, padding: '16px 20px', border: '1px solid #0f2e2e' }}>
                    <div style={{ fontSize: 22, fontWeight: 700, color: t.color, wordBreak: 'break-word' }}>{t.num}</div>
                    <div style={{ color: t.color, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 2 }}>{t.label}</div>
                    <div style={{ color: '#4a9a9a', fontSize: 11, marginTop: 1 }}>{t.sub}</div>
                  </div>
                ))}
              </div>

              {rows.length > 0 ? (
                <>
                  <div style={{ background: '#0d1e1e', borderRadius: 12, padding: '22px 26px', border: '1px solid #0f2e2e', marginBottom: 20 }}>
                    <div style={{ color: '#94a3b8', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 20 }}>
                      Elapsed Time per Scanner
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                      {rows.map(r => (
                        <div key={r.scanner} style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                          <div style={{ width: 180, color: '#94a3b8', fontSize: 13, flexShrink: 0 }}>{r.scanner}</div>
                          <div style={{ flex: 1, height: 20, background: '#050c0c', borderRadius: 4, overflow: 'hidden' }}>
                            <div style={{
                              height: '100%', width: `${(r.ms / maxMs) * 100}%`,
                              background: `linear-gradient(90deg,${msColor(r.ms)}33,${msColor(r.ms)}88)`,
                              borderRadius: 4, borderRight: `2px solid ${msColor(r.ms)}`,
                              transition: 'width 0.6s ease',
                            }} />
                          </div>
                          <div style={{ width: 72, textAlign: 'right', fontWeight: 700, fontSize: 13, color: msColor(r.ms), flexShrink: 0 }}>
                            {fmtMs(r.ms)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div style={{ background: '#0d1e1e', borderRadius: 12, padding: '22px 26px', border: '1px solid #0f2e2e' }}>
                    <div style={{ color: '#94a3b8', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 16 }}>
                      Scanner Breakdown
                    </div>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                      <thead>
                        <tr>
                          {['Scanner', 'Components', 'Findings', 'Elapsed', 'Finding Rate'].map(h => (
                            <th key={h} style={{ textAlign: 'left', color: '#4a9a9a', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em', paddingBottom: 10, borderBottom: '1px solid #0f2e2e', paddingRight: 16 }}>
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((r, i) => {
                          const rate = r.components > 0 ? Math.round(r.findings / r.components * 100) : 0
                          return (
                            <tr key={r.scanner} style={{ borderBottom: i < rows.length - 1 ? '1px solid #050c0c' : 'none' }}>
                              <td style={{ padding: '10px 16px 10px 0', color: '#f1f5f9', fontWeight: 600 }}>{r.scanner}</td>
                              <td style={{ padding: '10px 16px 10px 0', color: '#a5f3fc' }}>{r.components}</td>
                              <td style={{ padding: '10px 16px 10px 0', color: '#94a3b8' }}>{r.findings}</td>
                              <td style={{ padding: '10px 16px 10px 0', color: msColor(r.ms), fontWeight: 700 }}>{fmtMs(r.ms)}</td>
                              <td style={{ padding: '10px 0', color: rate > 50 ? '#fca5a5' : rate > 20 ? '#fcd34d' : '#86efac' }}>{rate}%</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <div style={{ textAlign: 'center', color: '#4a9a9a', padding: '60px 0', fontSize: 15 }}>
                  No timing data — re-run a scan to see performance metrics.
                </div>
              )}
            </div>
          )
        })()}

      </div>
    </div>
  )
}
