import React, { useState } from 'react'

const C = {
  bg: 'var(--bg)', surface: 'var(--surface)', border: 'var(--border)',
  text: 'var(--text)', textLo: 'var(--text-dim)', textMid: 'var(--text-mid)',
  cyan: '#06b6d4', green: '#22c55e', red: '#ef4444',
  orange: '#f97316', amber: '#f59e0b',
}

const SEV_COLOR = { critical: '#ef4444', high: '#f97316', medium: '#f59e0b', low: '#22c55e' }
const SEV_BG    = { critical: 'rgba(239,68,68,0.1)', high: 'rgba(249,115,22,0.1)', medium: 'rgba(245,158,11,0.1)', low: 'rgba(34,197,94,0.1)' }

const DOMAIN_ICONS = {
  'Data Quality':       '🗄️',
  'User Adoption':      '👥',
  'Integration Health': '🔗',
  'DevOps & Release':   '🚀',
}

function ScoreRing({ score, label, size = 90 }) {
  const r = (size - 14) / 2
  const circ = 2 * Math.PI * r
  const color = score >= 80 ? C.green : score >= 60 ? C.amber : C.red
  return (
    <div style={{ textAlign: 'center', position: 'relative' }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={12}/>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={12}
          strokeDasharray={circ} strokeDashoffset={circ * (1 - (score || 0) / 100)}
          strokeLinecap="round" style={{ transition: 'stroke-dashoffset 1.2s ease' }}/>
      </svg>
      <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', textAlign: 'center' }}>
        <div style={{ fontSize: size > 100 ? 28 : 18, fontWeight: 800, color, lineHeight: 1 }}>{score ?? '—'}</div>
      </div>
      <div style={{ fontSize: 11, color: C.textLo, marginTop: 4 }}>{label}</div>
    </div>
  )
}

function SevBadge({ sev }) {
  const k = (sev || '').toLowerCase()
  return (
    <span style={{ background: SEV_BG[k] || 'rgba(148,163,184,0.1)', color: SEV_COLOR[k] || C.textMid,
      border: `1px solid ${(SEV_COLOR[k] || C.textMid)}44`, borderRadius: 6,
      padding: '2px 8px', fontSize: 11, fontWeight: 700, flexShrink: 0 }}>{sev}</span>
  )
}

function FindingRow({ f }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ borderBottom: `1px solid ${C.border}` }}>
      <div onClick={() => setOpen(o => !o)} style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 16px', cursor: 'pointer',
        background: open ? 'rgba(6,182,212,0.03)' : 'transparent',
      }}>
        <SevBadge sev={f.severity} />
        <span style={{ fontSize: 11, color: C.textLo, minWidth: 80, fontFamily: 'monospace' }}>{f.rule_id}</span>
        <span style={{ flex: 1, fontSize: 13, color: C.text, fontWeight: 500 }}>{f.rule_name}</span>
        <span style={{ fontSize: 11, color: C.cyan, background: 'rgba(6,182,212,0.1)',
          border: '1px solid rgba(6,182,212,0.2)', borderRadius: 4, padding: '1px 6px', flexShrink: 0 }}>
          {f.domain}
        </span>
        <span style={{ color: C.textLo, fontSize: 12 }}>{open ? '▲' : '▼'}</span>
      </div>
      {open && (
        <div style={{ padding: '0 16px 14px 106px', background: 'rgba(6,182,212,0.02)' }}>
          <div style={{ fontSize: 13, color: C.textMid, lineHeight: 1.6, marginBottom: 6 }}>{f.description}</div>
          {f.suggested_fix && (
            <div style={{ fontSize: 12, color: C.green }}>
              <span style={{ fontWeight: 700 }}>Fix: </span>{f.suggested_fix}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DomainCard({ domain }) {
  const icon = DOMAIN_ICONS[domain.domain] || '📊'
  const scoreColor = domain.score >= 80 ? C.green : domain.score >= 60 ? C.amber : C.red
  return (
    <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 14,
      padding: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
      <div style={{ fontSize: 28 }}>{icon}</div>
      <ScoreRing score={domain.score} label="" size={90} />
      <div style={{ fontSize: 13, fontWeight: 700, color: C.text, textAlign: 'center' }}>{domain.domain}</div>
      <div style={{ fontSize: 11, color: C.textMid }}>
        {domain.findings.length} finding{domain.findings.length !== 1 ? 's' : ''}
      </div>
      {domain.error && <div style={{ fontSize: 10, color: C.red }}>Error loading</div>}
    </div>
  )
}

export default function AssessmentPage({ auth, onConnectOrg }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sevFilter, setSevFilter] = useState('ALL')
  const [domainFilter, setDomainFilter] = useState('ALL')

  async function runAssessment() {
    setLoading(true)
    setError('')
    setData(null)
    try {
      const res = await fetch('/assessment/full', { credentials: 'include' })
      if (res.status === 401) { setError('Connect your Salesforce org first.'); setLoading(false); return }
      if (!res.ok) { setError('Assessment failed — check your org connection.'); setLoading(false); return }
      setData(await res.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function exportCsv() {
    if (!data) return
    const rows = [['Rule ID', 'Severity', 'Domain', 'Finding', 'Fix']]
    for (const f of data.all_findings) {
      rows.push([f.rule_id, f.severity, f.domain, f.rule_name, f.suggested_fix])
    }
    const csv = rows.map(r => r.map(c => `"${(c||'').replace(/"/g,'""')}"`).join(',')).join('\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
    Object.assign(document.createElement('a'), { href: url, download: 'sf-assessment.csv' }).click()
    URL.revokeObjectURL(url)
  }

  const allFindings = data?.all_findings || []
  const domains = data?.domains?.map(d => d.domain) || []

  const displayed = allFindings.filter(f => {
    if (sevFilter !== 'ALL' && f.severity?.toLowerCase() !== sevFilter.toLowerCase()) return false
    if (domainFilter !== 'ALL' && f.domain !== domainFilter) return false
    return true
  })

  const btnStyle = active => ({
    padding: '4px 12px', borderRadius: 6, fontSize: 12, fontWeight: active ? 700 : 400,
    background: active ? 'rgba(6,182,212,0.15)' : 'transparent',
    border: active ? '1px solid rgba(6,182,212,0.4)' : `1px solid ${C.border}`,
    color: active ? C.cyan : C.textMid, cursor: 'pointer',
  })

  return (
    <div style={{ height: '100%', background: C.bg, overflowY: 'auto', padding: '28px 32px' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, margin: 0 }}>Org Assessment</h1>
          <p style={{ color: C.textLo, fontSize: 13, margin: '4px 0 0' }}>
            Full health check across Data Quality · User Adoption · Integrations · DevOps
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          {data && (
            <button onClick={exportCsv} style={{ ...btnStyle(false), display: 'flex', alignItems: 'center', gap: 5 }}>
              ⬇ Export CSV
            </button>
          )}
          <button onClick={runAssessment} disabled={loading || !auth} style={{
            padding: '8px 20px', background: !auth ? C.surface : `linear-gradient(135deg, ${C.cyan}, #0891b2)`,
            border: !auth ? `1px solid ${C.border}` : 'none',
            borderRadius: 10, color: !auth ? C.textMid : '#000',
            fontSize: 13, fontWeight: 700, cursor: !auth ? 'not-allowed' : 'pointer',
          }}>
            {loading ? 'Running…' : data ? 'Re-run Assessment' : 'Run Assessment'}
          </button>
        </div>
      </div>

      {/* Not connected banner */}
      {!auth && (
        <div style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)',
          borderRadius: 10, padding: '14px 18px', color: C.amber, fontSize: 14, marginBottom: 20,
          display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ flex: 1 }}>Connect your Salesforce org to run the assessment.</span>
          <button onClick={onConnectOrg} style={{ background: C.amber, color: '#000', border: 'none',
            borderRadius: 8, padding: '6px 16px', fontWeight: 700, cursor: 'pointer', fontSize: 13 }}>
            Connect Org
          </button>
        </div>
      )}

      {error && (
        <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 10, padding: '12px 18px', color: '#fca5a5', fontSize: 13, marginBottom: 20 }}>
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 14,
          padding: '48px', textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
          <div style={{ fontSize: 15, color: C.text, fontWeight: 600 }}>Running assessment…</div>
          <div style={{ fontSize: 13, color: C.textLo, marginTop: 6 }}>
            Checking data quality, users, integrations and devops in parallel
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && !data && !error && auth && (
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 14,
          padding: '56px', textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🏥</div>
          <div style={{ fontSize: 16, color: C.text, fontWeight: 700, marginBottom: 8 }}>
            Ready to assess your org
          </div>
          <div style={{ fontSize: 13, color: C.textLo, maxWidth: 420, margin: '0 auto' }}>
            Click <strong style={{ color: C.text }}>Run Assessment</strong> to check data quality,
            user adoption, integration health, and DevOps maturity across your Salesforce org.
          </div>
        </div>
      )}

      {/* Results */}
      {data && !loading && (
        <>
          {/* Overall score + summary bar */}
          <div style={{ background: C.surface, border: `1px solid ${C.border}`,
            borderRadius: 14, padding: '24px 28px', marginBottom: 20,
            display: 'flex', alignItems: 'center', gap: 32, flexWrap: 'wrap' }}>
            <ScoreRing score={data.overall_score} label="Overall" size={120} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: C.text, marginBottom: 4 }}>
                {data.overall_score >= 80 ? 'Healthy Org' : data.overall_score >= 60 ? 'Needs Attention' : 'Action Required'}
              </div>
              <div style={{ fontSize: 13, color: C.textLo, marginBottom: 16 }}>
                {data.instance_url} · {data.total_findings} finding{data.total_findings !== 1 ? 's' : ''}
              </div>
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {[
                  { label: 'Critical', count: data.critical_count, color: SEV_COLOR.critical, bg: SEV_BG.critical },
                  { label: 'High',     count: data.high_count,     color: SEV_COLOR.high,     bg: SEV_BG.high },
                  { label: 'Medium',   count: allFindings.filter(f => f.severity === 'medium').length, color: SEV_COLOR.medium, bg: SEV_BG.medium },
                  { label: 'Low',      count: allFindings.filter(f => f.severity === 'low').length,    color: SEV_COLOR.low,    bg: SEV_BG.low },
                ].map(s => (
                  <div key={s.label} style={{ background: s.bg, border: `1px solid ${s.color}44`,
                    borderRadius: 10, padding: '10px 18px', textAlign: 'center', minWidth: 80 }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: s.color }}>{s.count}</div>
                    <div style={{ fontSize: 11, color: C.textLo, marginTop: 2 }}>{s.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Domain score cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 14, marginBottom: 20 }}>
            {data.domains.map(d => <DomainCard key={d.domain} domain={d} />)}
          </div>

          {/* Findings table */}
          <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 14 }}>
            <div style={{ padding: '14px 16px', borderBottom: `1px solid ${C.border}`,
              display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: C.text, marginRight: 4 }}>
                Findings ({displayed.length})
              </span>
              {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(s => (
                <button key={s} onClick={() => setSevFilter(s)} style={btnStyle(sevFilter === s)}>{s}</button>
              ))}
              <div style={{ width: 1, height: 20, background: C.border, margin: '0 4px' }} />
              {['ALL', ...domains].map(d => (
                <button key={d} onClick={() => setDomainFilter(d)} style={btnStyle(domainFilter === d)}>
                  {d === 'ALL' ? 'ALL DOMAINS' : d}
                </button>
              ))}
            </div>

            {displayed.length === 0 ? (
              <div style={{ padding: '32px', textAlign: 'center', color: C.textLo, fontSize: 13 }}>
                No findings match the current filter.
              </div>
            ) : (
              displayed.map((f, i) => <FindingRow key={i} f={f} />)
            )}
          </div>
        </>
      )}
    </div>
  )
}
