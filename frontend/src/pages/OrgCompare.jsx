import React, { useState, useEffect } from 'react'

const C = {
  bg: '#050c0c', surface: '#0d1e1e', border: '#0f2e2e',
  text: '#e2e8f0', textLo: '#4a9a9a', textMid: '#94a3b8',
  cyan: '#06b6d4', green: '#22c55e', red: '#ef4444', orange: '#f97316',
}

function StatCard({ label, a, b, unit = '', higherIsBetter = true }) {
  const numA = typeof a === 'number' ? a : 0
  const numB = typeof b === 'number' ? b : 0
  const diff = numA - numB
  const aWins = higherIsBetter ? diff > 0 : diff < 0
  const bWins = higherIsBetter ? diff < 0 : diff > 0
  const tie = diff === 0

  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderRadius: 12, padding: '16px 20px', marginBottom: 10,
    }}>
      <div style={{ fontSize: 11, color: C.textLo, fontWeight: 600,
        textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          flex: 1, textAlign: 'center', padding: '12px 8px', borderRadius: 10,
          background: aWins ? 'rgba(34,197,94,0.08)' : bWins ? 'rgba(239,68,68,0.06)' : 'rgba(148,163,184,0.05)',
          border: `1px solid ${aWins ? 'rgba(34,197,94,0.25)' : bWins ? 'rgba(239,68,68,0.2)' : C.border}`,
        }}>
          <div style={{ fontSize: 22, fontWeight: 700,
            color: aWins ? C.green : bWins ? '#fca5a5' : C.text }}>
            {typeof a === 'number' ? a.toLocaleString() : (a ?? '—')}{unit}
          </div>
          {aWins && <div style={{ fontSize: 10, color: C.green, marginTop: 2 }}>▲ Better</div>}
          {bWins && <div style={{ fontSize: 10, color: '#fca5a5', marginTop: 2 }}>▼ Lower</div>}
          {tie && <div style={{ fontSize: 10, color: C.textLo, marginTop: 2 }}>Equal</div>}
        </div>
        <div style={{ color: C.textLo, fontSize: 18, fontWeight: 700 }}>vs</div>
        <div style={{
          flex: 1, textAlign: 'center', padding: '12px 8px', borderRadius: 10,
          background: bWins ? 'rgba(34,197,94,0.08)' : aWins ? 'rgba(239,68,68,0.06)' : 'rgba(148,163,184,0.05)',
          border: `1px solid ${bWins ? 'rgba(34,197,94,0.25)' : aWins ? 'rgba(239,68,68,0.2)' : C.border}`,
        }}>
          <div style={{ fontSize: 22, fontWeight: 700,
            color: bWins ? C.green : aWins ? '#fca5a5' : C.text }}>
            {typeof b === 'number' ? b.toLocaleString() : (b ?? '—')}{unit}
          </div>
          {bWins && <div style={{ fontSize: 10, color: C.green, marginTop: 2 }}>▲ Better</div>}
          {aWins && <div style={{ fontSize: 10, color: '#fca5a5', marginTop: 2 }}>▼ Lower</div>}
          {tie && <div style={{ fontSize: 10, color: C.textLo, marginTop: 2 }}>Equal</div>}
        </div>
      </div>
    </div>
  )
}

function StorageBar({ used, max, label }) {
  const pct = max > 0 ? Math.round(used / max * 100) : 0
  const color = pct > 80 ? C.red : pct > 60 ? C.orange : C.cyan
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12,
        color: C.textMid, marginBottom: 4 }}>
        <span>{label}</span>
        <span style={{ color }}>{pct}% ({used} / {max} MB)</span>
      </div>
      <div style={{ background: '#0a1a1a', borderRadius: 4, height: 6, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color,
          borderRadius: 4, transition: 'width 0.8s ease' }} />
      </div>
    </div>
  )
}

export default function OrgCompare() {
  const [orgs, setOrgs] = useState([])
  const [orgKeyA, setOrgKeyA] = useState('')
  const [orgKeyB, setOrgKeyB] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/auth/orgs', { credentials: 'include' })
      .then(r => r.ok ? r.json() : { orgs: [] })
      .then(d => {
        setOrgs(d.orgs || [])
        if (d.orgs?.length >= 1) setOrgKeyA(d.orgs[0].org_key)
        if (d.orgs?.length >= 2) setOrgKeyB(d.orgs[1].org_key)
      })
      .catch(() => {})
  }, [])

  async function runComparison() {
    if (!orgKeyA || !orgKeyB || orgKeyA === orgKeyB) return
    setLoading(true); setError(''); setResult(null)
    try {
      const res = await fetch('/compare/orgs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ org_key_a: orgKeyA, org_key_b: orgKeyB }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Comparison failed')
      setResult(data)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const a = result?.org_a
  const b = result?.org_b

  const inputStyle = {
    padding: '9px 12px', borderRadius: 8, background: '#0a1a1a',
    border: `1px solid ${C.border}`, color: C.text, fontSize: 13,
    outline: 'none', minWidth: 200,
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', background: C.bg,
      padding: '24px 28px', fontFamily: 'system-ui,-apple-system,sans-serif' }}>

      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, margin: 0 }}>
          Org Comparison
        </h1>
        <p style={{ color: C.textLo, fontSize: 13, margin: '4px 0 0' }}>
          Select two connected orgs to compare side-by-side
        </p>
      </div>

      <div style={{
        background: C.surface, border: `1px solid ${C.border}`,
        borderRadius: 14, padding: '20px 24px', marginBottom: 24,
        display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
      }}>
        <div>
          <div style={{ fontSize: 11, color: C.textLo, fontWeight: 600, marginBottom: 6 }}>ORG A</div>
          <select value={orgKeyA} onChange={e => setOrgKeyA(e.target.value)} style={inputStyle}>
            <option value="">— Select org —</option>
            {orgs.map(o => (
              <option key={o.org_key} value={o.org_key}>{o.label || o.alias || o.instance_url}</option>
            ))}
          </select>
        </div>
        <div style={{ fontSize: 22, color: C.textLo, marginTop: 18 }}>⇄</div>
        <div>
          <div style={{ fontSize: 11, color: C.textLo, fontWeight: 600, marginBottom: 6 }}>ORG B</div>
          <select value={orgKeyB} onChange={e => setOrgKeyB(e.target.value)} style={inputStyle}>
            <option value="">— Select org —</option>
            {orgs.map(o => (
              <option key={o.org_key} value={o.org_key}>{o.label || o.alias || o.instance_url}</option>
            ))}
          </select>
        </div>
        <button
          onClick={runComparison}
          disabled={!orgKeyA || !orgKeyB || orgKeyA === orgKeyB || loading}
          style={{
            marginTop: 18, padding: '10px 24px', borderRadius: 9, fontSize: 14,
            fontWeight: 700, border: 'none', cursor: 'pointer',
            background: (!orgKeyA || !orgKeyB || orgKeyA === orgKeyB || loading)
              ? '#0f2e2e' : 'linear-gradient(135deg,#06b6d4,#0891b2)',
            color: (!orgKeyA || !orgKeyB || orgKeyA === orgKeyB || loading)
              ? C.textLo : 'white',
          }}
        >
          {loading ? 'Comparing…' : 'Compare Orgs'}
        </button>

        {orgs.length < 2 && (
          <div style={{ fontSize: 13, color: C.orange, marginTop: 18 }}>
            Connect at least 2 orgs to compare. Use the Connections page to add another.
          </div>
        )}
      </div>

      {error && (
        <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 10, padding: '12px 16px', color: '#fca5a5', fontSize: 13, marginBottom: 20 }}>
          {error}
        </div>
      )}

      {result && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 60px 1fr', gap: 12, marginBottom: 20 }}>
            {[a, b].map((org, i) => (
              <div key={i} style={{
                background: C.surface, border: `1px solid ${C.border}`,
                borderRadius: 12, padding: '16px 20px',
              }}>
                <div style={{ fontSize: 16, fontWeight: 700, color: C.text }}>{org?.label}</div>
                <div style={{ fontSize: 12, color: C.textLo, marginTop: 4 }}>{org?.instance_url}</div>
                <div style={{ fontSize: 12, color: C.textMid, marginTop: 2 }}>{org?.edition}</div>
              </div>
            ))}
            <div />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            <div>
              <div style={{ fontSize: 12, color: C.cyan, fontWeight: 700, textTransform: 'uppercase',
                letterSpacing: '0.08em', marginBottom: 12 }}>Code & Metadata</div>
              <StatCard label="Apex Classes" a={a?.apex_classes} b={b?.apex_classes} />
              <StatCard label="Active Flows" a={a?.active_flows} b={b?.active_flows} />
              <StatCard label="Custom Objects" a={a?.custom_objects} b={b?.custom_objects} />
              <StatCard label="Active Users" a={a?.active_users} b={b?.active_users} />
              <StatCard label="Apex Test Coverage" a={a?.apex_coverage_pct} b={b?.apex_coverage_pct} unit="%" />
            </div>
            <div>
              <div style={{ fontSize: 12, color: C.cyan, fontWeight: 700, textTransform: 'uppercase',
                letterSpacing: '0.08em', marginBottom: 12 }}>Capacity & Usage</div>

              <div style={{ background: C.surface, border: `1px solid ${C.border}`,
                borderRadius: 12, padding: '16px 20px', marginBottom: 10 }}>
                <div style={{ fontSize: 11, color: C.textLo, fontWeight: 600, marginBottom: 12 }}>
                  {a?.label} — Storage
                </div>
                <StorageBar label="Data Storage" used={a?.data_storage_used_mb || 0} max={a?.data_storage_max_mb || 1} />
                <StorageBar label="File Storage" used={a?.file_storage_used_mb || 0} max={a?.file_storage_max_mb || 1} />
              </div>

              <div style={{ background: C.surface, border: `1px solid ${C.border}`,
                borderRadius: 12, padding: '16px 20px', marginBottom: 10 }}>
                <div style={{ fontSize: 11, color: C.textLo, fontWeight: 600, marginBottom: 12 }}>
                  {b?.label} — Storage
                </div>
                <StorageBar label="Data Storage" used={b?.data_storage_used_mb || 0} max={b?.data_storage_max_mb || 1} />
                <StorageBar label="File Storage" used={b?.file_storage_used_mb || 0} max={b?.file_storage_max_mb || 1} />
              </div>

              <StatCard label="Daily API Calls Used" a={a?.api_calls_used} b={b?.api_calls_used} higherIsBetter={false} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
