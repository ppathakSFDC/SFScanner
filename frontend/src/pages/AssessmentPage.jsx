import React, { useState } from 'react'

const C = {
  bg: 'var(--bg)', surface: 'var(--surface)', border: 'var(--border)',
  text: 'var(--text)', textLo: 'var(--text-dim)', textMid: 'var(--text-mid)',
  cyan: '#06b6d4', green: '#22c55e', red: '#ef4444',
  orange: '#f97316', amber: '#f59e0b',
}

const SEV_COLOR = { critical: '#ef4444', high: '#f97316', medium: '#f59e0b', low: '#22c55e' }
const SEV_BG    = { critical: 'rgba(239,68,68,0.1)', high: 'rgba(249,115,22,0.1)', medium: 'rgba(245,158,11,0.1)', low: 'rgba(34,197,94,0.1)' }

const DOMAIN_META = {
  'Data Quality':       { icon: '🗃️', color: '#818cf8', desc: 'Records, duplicates & completeness' },
  'User Adoption':      { icon: '👥', color: '#34d399', desc: 'Logins, licences & feature usage'   },
  'Integration Health': { icon: '🔌', color: '#f472b6', desc: 'Connected apps, callouts & APIs'    },
  'DevOps & Release':   { icon: '🚀', color: '#fb923c', desc: 'Coverage, flows & automation debt'  },
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
  const meta  = DOMAIN_META[domain.domain] || { icon: '📊', color: C.cyan, desc: '' }
  const critCount = domain.findings.filter(f => f.severity === 'critical').length
  const highCount = domain.findings.filter(f => f.severity === 'high').length
  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderTop: `3px solid ${meta.color}`,
      borderRadius: 14, padding: '18px 16px',
      display: 'flex', flexDirection: 'column', gap: 12,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{
          fontSize: 22, background: meta.color + '18',
          borderRadius: 10, padding: '6px 8px', lineHeight: 1,
        }}>{meta.icon}</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{domain.domain}</div>
          <div style={{ fontSize: 11, color: C.textLo, marginTop: 1 }}>{meta.desc}</div>
        </div>
      </div>
      <ScoreRing score={domain.score} label="score" size={80} />
      <div style={{ display: 'flex', gap: 6, justifyContent: 'center', flexWrap: 'wrap' }}>
        {critCount > 0 && (
          <span style={{ fontSize: 10, background: SEV_BG.critical, color: SEV_COLOR.critical,
            border: `1px solid ${SEV_COLOR.critical}44`, borderRadius: 4, padding: '1px 6px', fontWeight: 700 }}>
            {critCount} Critical
          </span>
        )}
        {highCount > 0 && (
          <span style={{ fontSize: 10, background: SEV_BG.high, color: SEV_COLOR.high,
            border: `1px solid ${SEV_COLOR.high}44`, borderRadius: 4, padding: '1px 6px', fontWeight: 700 }}>
            {highCount} High
          </span>
        )}
        {critCount === 0 && highCount === 0 && (
          <span style={{ fontSize: 10, background: SEV_BG.low, color: SEV_COLOR.low,
            border: `1px solid ${SEV_COLOR.low}44`, borderRadius: 4, padding: '1px 6px', fontWeight: 700 }}>
            {domain.findings.length === 0 ? '✓ All clear' : `${domain.findings.length} Low/Med`}
          </span>
        )}
      </div>
      {domain.error && <div style={{ fontSize: 10, color: C.red, textAlign: 'center' }}>⚠ Error loading</div>}
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{
            width: 48, height: 48, borderRadius: 14,
            background: 'linear-gradient(135deg, rgba(6,182,212,0.15), rgba(99,102,241,0.15))',
            border: '1px solid rgba(6,182,212,0.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" stroke="#06b6d4" strokeWidth="2.2"
                strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, margin: 0 }}>Org Assessment</h1>
            <p style={{ color: C.textLo, fontSize: 13, margin: '3px 0 0' }}>
              Data Quality · User Adoption · Integration Health · DevOps
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {data && (
            <button onClick={exportCsv} style={{ ...btnStyle(false), display: 'flex', alignItems: 'center', gap: 5 }}>
              ⬇ Export CSV
            </button>
          )}
          <button onClick={runAssessment} disabled={loading || !auth} style={{
            padding: '9px 22px',
            background: !auth ? C.surface : loading ? 'rgba(6,182,212,0.2)' : `linear-gradient(135deg, ${C.cyan}, #0891b2)`,
            border: !auth ? `1px solid ${C.border}` : loading ? `1px solid ${C.cyan}44` : 'none',
            borderRadius: 10, color: !auth ? C.textMid : loading ? C.cyan : '#000',
            fontSize: 13, fontWeight: 700, cursor: !auth || loading ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            {loading ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ animation: 'spin 1s linear infinite' }}>
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31 63" strokeLinecap="round"/>
                </svg>
                Scanning…
              </>
            ) : data ? '↺ Re-run' : '▶ Run Assessment'}
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
        <div style={{ background: C.surface, border: `1px solid rgba(6,182,212,0.2)`,
          borderRadius: 14, padding: '48px 32px', textAlign: 'center', marginBottom: 24 }}>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" style={{ marginBottom: 16 }}>
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" stroke="#06b6d4" strokeWidth="2"
              strokeLinecap="round" strokeLinejoin="round"
              style={{ animation: 'pulse 1.5s ease-in-out infinite' }}/>
          </svg>
          <div style={{ fontSize: 15, color: C.text, fontWeight: 700 }}>Running assessment…</div>
          <div style={{ fontSize: 13, color: C.textLo, marginTop: 6, marginBottom: 20 }}>
            All 4 domains are running in parallel
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 16, flexWrap: 'wrap' }}>
            {Object.entries(DOMAIN_META).map(([name, meta]) => (
              <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 6,
                background: meta.color + '12', border: `1px solid ${meta.color}30`,
                borderRadius: 8, padding: '6px 12px', fontSize: 12, color: C.textMid }}>
                <span>{meta.icon}</span> {name}
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: meta.color,
                  animation: 'pulse 1.2s ease-in-out infinite', display: 'inline-block' }}/>
              </div>
            ))}
          </div>
        </div>
      )}
      <style>{`
        @keyframes spin { to { transform: rotate(360deg) } }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
      `}</style>

      {/* Empty state */}
      {!loading && !data && !error && auth && (
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 14,
          padding: '56px 32px', textAlign: 'center' }}>
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" style={{ marginBottom: 16, opacity: 0.4 }}>
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" stroke={C.cyan} strokeWidth="2"
              strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <div style={{ fontSize: 16, color: C.text, fontWeight: 700, marginBottom: 8 }}>
            Ready to assess your org
          </div>
          <div style={{ fontSize: 13, color: C.textLo, maxWidth: 440, margin: '0 auto 24px' }}>
            Runs 20+ checks across Data Quality, User Adoption, Integration Health and DevOps in under 5 seconds.
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 28 }}>
            {Object.entries(DOMAIN_META).map(([name, meta]) => (
              <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 6,
                background: meta.color + '12', border: `1px solid ${meta.color}30`,
                borderRadius: 8, padding: '6px 14px', fontSize: 12, color: C.textMid }}>
                <span>{meta.icon}</span> {name}
              </div>
            ))}
          </div>
          <button onClick={runAssessment} style={{
            padding: '10px 28px', background: `linear-gradient(135deg, ${C.cyan}, #0891b2)`,
            border: 'none', borderRadius: 10, color: '#000', fontSize: 14, fontWeight: 700, cursor: 'pointer',
          }}>▶ Run Assessment</button>
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
