import React, { useState, useEffect } from 'react'

const C = {
  bg: 'var(--bg)', surface: 'var(--surface)', border: 'var(--border)',
  text: 'var(--text)', textLo: 'var(--text-dim)', textMid: 'var(--text-mid)',
  cyan: '#06b6d4', green: '#22c55e', red: '#ef4444',
  orange: '#f97316', amber: '#f59e0b', purple: '#a855f7',
}

const SEV_COLOR = {
  critical: '#ef4444', high: '#f97316', medium: '#f59e0b', low: '#22c55e',
}
const SEV_BG = {
  critical: 'rgba(239,68,68,0.1)', high: 'rgba(249,115,22,0.1)',
  medium: 'rgba(245,158,11,0.1)', low: 'rgba(34,197,94,0.1)',
}
const TYPE_LABELS = {
  Security: 'Org Settings', Compliance: 'Compliance', Permission: 'Permissions',
  Apex: 'Apex Code', SOQL: 'SOQL',
}

const COMPLIANCE_CHECKS = [
  { label: 'No ViewAllData in non-admin profiles',  rule: 'PERM-001', category: 'SOC2 / GDPR' },
  { label: 'No ModifyAllData in non-admin profiles', rule: 'PERM-002', category: 'SOC2 / GDPR' },
  { label: 'No PII fields without encryption',       rule: 'COMP-001', category: 'GDPR / HIPAA' },
  { label: 'PII fields have audit trail tracking',   rule: 'COMP-002', category: 'GDPR Art. 5(2)' },
  { label: 'HTTPS enforced',                         rule: 'SORG-001', category: 'SOC2 / PCI' },
  { label: 'No Guest User record access',            rule: 'SORG-007', category: 'GDPR / SOC2' },
  { label: 'Connected apps access restricted',       rule: 'SORG-005', category: 'SOC2' },
  { label: 'No weak crypto hash algorithms',         rule: 'APEX-016', category: 'FIPS / SOC2' },
  { label: 'No dynamic SOQL injection risk',         rule: 'APEX-015', category: 'OWASP A03' },
  { label: 'BulkApiHardDelete restricted',           rule: 'PERM-007', category: 'GDPR Art. 17' },
]

function ScoreRing({ score, label, size = 80 }) {
  const r = (size - 12) / 2
  const circ = 2 * Math.PI * r
  const color = score >= 80 ? C.green : score >= 60 ? C.amber : C.red
  return (
    <div style={{ textAlign: 'center' }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={10} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={10}
          strokeDasharray={circ} strokeDashoffset={circ * (1 - (score || 0) / 100)}
          strokeLinecap="round" style={{ transition: 'stroke-dashoffset 1s ease' }} />
      </svg>
      <div style={{ marginTop: 6, fontSize: 20, fontWeight: 800, color }}>{score ?? '—'}</div>
      <div style={{ fontSize: 11, color: C.textLo, marginTop: 2 }}>{label}</div>
    </div>
  )
}

function SeverityBadge({ sev }) {
  const key = (sev || '').toLowerCase()
  return (
    <span style={{
      background: SEV_BG[key] || 'rgba(148,163,184,0.1)',
      color: SEV_COLOR[key] || C.textMid,
      border: `1px solid ${(SEV_COLOR[key] || C.textMid)}44`,
      borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 700,
    }}>{sev}</span>
  )
}

function FindingRow({ f, expanded, onToggle }) {
  return (
    <div style={{ borderBottom: `1px solid ${C.border}` }}>
      <div onClick={onToggle} style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 16px', cursor: 'pointer',
        background: expanded ? 'rgba(6,182,212,0.03)' : 'transparent',
      }}>
        <SeverityBadge sev={f.severity} />
        <span style={{ fontSize: 12, color: C.textLo, minWidth: 90, fontFamily: 'monospace' }}>
          {f.rule_id}
        </span>
        <span style={{ flex: 1, fontSize: 13, color: C.text, fontWeight: 500 }}>{f.rule_name}</span>
        <span style={{ fontSize: 12, color: C.textMid, background: 'rgba(148,163,184,0.08)',
          borderRadius: 6, padding: '2px 8px' }}>
          {TYPE_LABELS[f.component_type] || f.component_type}
        </span>
        <span style={{ fontSize: 12, color: C.textLo, maxWidth: 200,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {f.component_name}
        </span>
        <span style={{ color: C.textLo, fontSize: 14 }}>{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <div style={{ padding: '0 16px 14px 16px', background: 'rgba(6,182,212,0.02)' }}>
          <div style={{ fontSize: 13, color: C.textMid, lineHeight: 1.6, marginBottom: 8 }}>
            {f.description}
          </div>
          {f.suggested_fix && (
            <div style={{ fontSize: 12, color: C.green, marginBottom: 6 }}>
              <span style={{ fontWeight: 700 }}>Fix: </span>{f.suggested_fix}
            </div>
          )}
          {f.impact && (
            <div style={{ fontSize: 12, color: C.orange }}>
              <span style={{ fontWeight: 700 }}>Impact: </span>{f.impact}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function downloadCSV(findings) {
  const headers = ['Rule ID', 'Rule Name', 'Severity', 'Category', 'Component', 'Description']
  const rows = findings.map(f => [
    f.rule_id, f.rule_name, f.severity,
    TYPE_LABELS[f.component_type] || f.component_type,
    f.component_name,
    (f.description || '').replace(/,/g, ';'),
  ])
  const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `security-findings-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
}

export default function SecurityPage({ auth, onNavigate }) {
  const [data,      setData]      = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [filter,    setFilter]    = useState('ALL')
  const [catFilter, setCatFilter] = useState('ALL')
  const [expanded,  setExpanded]  = useState(null)
  const [error,     setError]     = useState('')

  useEffect(() => {
    fetch('/security/summary', { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject('Failed'))
      .then(d => { setData(d); setLoading(false) })
      .catch(() => { setError('Run a scan first to see security findings.'); setLoading(false) })
  }, [])

  const findings = data?.findings || []
  const scores   = data?.scores   || {}
  const sevCounts = data?.severity_counts || {}

  const sevFiltered = filter === 'ALL' ? findings : findings.filter(f => f.severity === filter.toLowerCase())
  const displayed   = catFilter === 'ALL' ? sevFiltered
    : sevFiltered.filter(f => (TYPE_LABELS[f.component_type] || f.component_type) === catFilter)

  const ruleSet = new Set(findings.map(f => f.rule_id))
  const passCount = COMPLIANCE_CHECKS.filter(c => !ruleSet.has(c.rule)).length
  const compliancePct = Math.round(passCount / COMPLIANCE_CHECKS.length * 100)

  const categories = [...new Set(findings.map(f => TYPE_LABELS[f.component_type] || f.component_type))]

  const btnStyle = (active) => ({
    padding: '5px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600,
    border: `1px solid ${active ? C.cyan : C.border}`,
    background: active ? 'rgba(6,182,212,0.12)' : 'transparent',
    color: active ? C.cyan : C.textMid, cursor: 'pointer',
  })

  if (loading) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: C.bg, color: C.textLo, fontSize: 14 }}>
      Loading security data…
    </div>
  )

  return (
    <div style={{ flex: 1, overflowY: 'auto', background: C.bg,
      padding: '24px 28px', fontFamily: 'system-ui,-apple-system,sans-serif' }}>

      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, margin: 0 }}>
          Security & Compliance
        </h1>
        <p style={{ color: C.textLo, fontSize: 13, margin: '4px 0 0' }}>
          Org security posture · GDPR / SOC2 / HIPAA compliance indicators
        </p>
      </div>

      {error && (
        <div style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)',
          borderRadius: 10, padding: '14px 18px', color: C.amber, fontSize: 14, marginBottom: 20,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{error}</span>
          {onNavigate && (
            <button onClick={() => onNavigate('scanner')} style={{
              background: C.amber, color: '#000', border: 'none', borderRadius: 8,
              padding: '6px 14px', fontWeight: 700, fontSize: 12, cursor: 'pointer',
            }}>Run Scan</button>
          )}
        </div>
      )}

      {data && (
        <>
          {/* Score rings */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24, background: 'var(--surface)',
            border: `1px solid ${C.border}`, borderRadius: 14,
            padding: '20px 28px', marginBottom: 20, alignItems: 'center' }}>
            <ScoreRing score={scores.security}   label="Org Security" />
            <ScoreRing score={scores.compliance} label="Compliance" />
            <ScoreRing score={scores.perms}      label="Permissions" />
            <ScoreRing score={scores.apex}       label="Apex Code" />
            <div style={{ marginLeft: 'auto', textAlign: 'center' }}>
              <div style={{ fontSize: 36, fontWeight: 900,
                color: compliancePct >= 80 ? C.green : compliancePct >= 50 ? C.amber : C.red }}>
                {compliancePct}%
              </div>
              <div style={{ fontSize: 12, color: C.textLo, marginTop: 4 }}>Compliance Checklist</div>
              <div style={{ fontSize: 11, color: C.textMid, marginTop: 2 }}>
                {passCount} / {COMPLIANCE_CHECKS.length} checks pass
              </div>
            </div>
          </div>

          {/* Severity counts */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 20 }}>
            {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(sev => (
              <div key={sev} onClick={() => setFilter(f => f === sev ? 'ALL' : sev)}
                style={{
                  background: 'var(--surface)',
                  border: `1px solid ${filter === sev ? SEV_COLOR[sev.toLowerCase()] : C.border}`,
                  borderRadius: 12, padding: '14px 18px', cursor: 'pointer', textAlign: 'center',
                }}>
                <div style={{ fontSize: 28, fontWeight: 800, color: SEV_COLOR[sev.toLowerCase()] }}>
                  {sevCounts[sev.toLowerCase()] || 0}
                </div>
                <div style={{ fontSize: 11, color: C.textLo, marginTop: 4, fontWeight: 700 }}>{sev}</div>
              </div>
            ))}
          </div>

          {/* Compliance checklist */}
          <div style={{ background: 'var(--surface)', border: `1px solid ${C.border}`,
            borderRadius: 14, padding: '16px 20px', marginBottom: 20 }}>
            <div style={{ fontSize: 12, color: C.cyan, fontWeight: 700,
              textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
              Compliance Checklist
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {COMPLIANCE_CHECKS.map(c => {
                const fail = ruleSet.has(c.rule)
                return (
                  <div key={c.rule} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 14, color: fail ? C.red : C.green }}>{fail ? '✕' : '✓'}</span>
                    <span style={{ fontSize: 12, color: fail ? C.textMid : C.text }}>{c.label}</span>
                    <span style={{ fontSize: 10, color: C.textLo,
                      background: 'rgba(148,163,184,0.08)', borderRadius: 4, padding: '1px 5px',
                      flexShrink: 0 }}>
                      {c.category}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Findings table */}
          <div style={{ background: 'var(--surface)', border: `1px solid ${C.border}`, borderRadius: 14 }}>
            <div style={{ padding: '14px 16px', borderBottom: `1px solid ${C.border}`,
              display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: C.text, marginRight: 4 }}>
                Findings ({displayed.length})
              </span>
              {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(s => (
                <button key={s} onClick={() => setFilter(s)} style={btnStyle(filter === s)}>{s}</button>
              ))}
              <div style={{ width: 1, height: 20, background: C.border, margin: '0 4px' }} />
              {['ALL', ...categories].map(cat => (
                <button key={cat} onClick={() => setCatFilter(cat)} style={btnStyle(catFilter === cat)}>
                  {cat}
                </button>
              ))}
              <button onClick={() => downloadCSV(findings)} style={{
                marginLeft: 'auto', padding: '5px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                background: 'rgba(6,182,212,0.1)', border: `1px solid rgba(6,182,212,0.3)`,
                color: C.cyan, cursor: 'pointer',
              }}>⬇ Export CSV</button>
            </div>
            {displayed.length === 0 ? (
              <div style={{ padding: '32px', textAlign: 'center', color: C.textLo, fontSize: 13 }}>
                {findings.length === 0
                  ? 'No security findings in latest scan.'
                  : 'No findings match the current filter.'}
              </div>
            ) : (
              displayed.map(f => (
                <FindingRow
                  key={f.id}
                  f={f}
                  expanded={expanded === f.id}
                  onToggle={() => setExpanded(x => x === f.id ? null : f.id)}
                />
              ))
            )}
          </div>
        </>
      )}
    </div>
  )
}
