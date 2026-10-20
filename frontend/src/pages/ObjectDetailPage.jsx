import React, { useState, useEffect, useMemo } from 'react'

const C = {
  bg:       'var(--bg)',
  surface:  'var(--surface)',
  surfaceHi:'var(--surface-hi)',
  border:   'var(--border)',
  borderHi: 'var(--border-hi)',
  cyan:     '#06b6d4',
  green:    '#22c55e',
  orange:   '#f97316',
  red:      '#ef4444',
  purple:   '#a855f7',
  yellow:   '#eab308',
  text:     'var(--text)',
  textMid:  'var(--text-mid)',
  textLo:   'var(--text-lo)',
}

const TYPE_COLOR = {
  string:      '#60a5fa', textarea:   '#60a5fa', email:      '#60a5fa', phone:    '#60a5fa', url: '#60a5fa',
  reference:   '#a78bfa', picklist:   '#34d399', multipicklist: '#34d399',
  boolean:     '#86efac', int:        '#fcd34d', double:     '#fcd34d', currency: '#fcd34d', percent: '#fcd34d',
  date:        '#f9a8d4', datetime:   '#f9a8d4', time:       '#f9a8d4',
  id:          '#94a3b8', base64:     '#94a3b8',
}
function typeColor(t) { return TYPE_COLOR[t?.toLowerCase()] || '#94a3b8' }

function Badge({ label, color }) {
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 20,
      background: `${color}18`, border: `1px solid ${color}40`, color,
      letterSpacing: '0.05em',
    }}>{label}</span>
  )
}

function StatCard({ label, value, color }) {
  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10,
      padding: '12px 18px', minWidth: 100, textAlign: 'center',
    }}>
      <div style={{ fontSize: 26, fontWeight: 800, color: color || C.text, letterSpacing: '-0.02em', lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 10, color: C.textLo, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: 4 }}>{label}</div>
    </div>
  )
}

export default function ObjectDetailPage({ objectName, onBack }) {
  const [describe, setDescribe]   = useState(null)
  const [triggers, setTriggers]   = useState([])
  const [recCount, setRecCount]   = useState(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')
  const [tab, setTab]             = useState('fields')
  const [fieldSearch, setFieldSearch] = useState('')

  useEffect(() => {
    if (!objectName) return
    setLoading(true); setError(''); setDescribe(null); setTriggers([]); setRecCount(null)

    const descP = fetch(`/auth/describe-object/${objectName}`, { credentials: 'include' })
      .then(r => r.text()).then(t => { try { return JSON.parse(t) } catch { return null } })

    const trigP = fetch(
      `/auth/list-records?object_name=ApexTrigger&fields=Name%2CStatus%2CApiVersion&tooling=true&filter=TableEnumOrId+%3D+'${encodeURIComponent(objectName)}'&limit=50`,
      { credentials: 'include' }
    ).then(r => r.ok ? r.json() : { records: [] }).catch(() => ({ records: [] }))

    const countP = fetch(
      `/auth/list-records?object_name=${encodeURIComponent(objectName)}&fields=Id&limit=1`,
      { credentials: 'include' }
    ).then(r => r.ok ? r.json() : null).catch(() => null)

    Promise.all([descP, trigP, countP]).then(([desc, trig, cnt]) => {
      if (!desc || desc.detail) { setError(desc?.detail || 'Could not load object'); setLoading(false); return }
      setDescribe(desc)
      setTriggers(trig?.records || [])
      setRecCount(cnt?.total ?? null)
      setLoading(false)
    }).catch(e => { setError(String(e)); setLoading(false) })
  }, [objectName])

  const fields = useMemo(() => describe?.fields || [], [describe])

  const filteredFields = useMemo(() => {
    const q = fieldSearch.toLowerCase()
    if (!q) return fields
    return fields.filter(f =>
      f.name?.toLowerCase().includes(q) || f.label?.toLowerCase().includes(q) || f.type?.toLowerCase().includes(q)
    )
  }, [fields, fieldSearch])

  const customFields   = fields.filter(f => f.custom)
  const requiredFields = fields.filter(f => !f.nillable && f.createable)
  const typeSummary    = fields.reduce((acc, f) => { acc[f.type] = (acc[f.type] || 0) + 1; return acc }, {})

  if (loading) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: C.bg, flexDirection: 'column', gap: 12 }}>
      <div style={{ fontSize: 32 }}>⏳</div>
      <div style={{ color: C.textLo, fontSize: 14 }}>Loading {objectName}…</div>
    </div>
  )

  if (error) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: C.bg, flexDirection: 'column', gap: 12 }}>
      <div style={{ fontSize: 32 }}>⚠️</div>
      <div style={{ color: C.red, fontSize: 14 }}>{error}</div>
      <button onClick={onBack} style={{ padding: '8px 18px', background: C.surfaceHi, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text, cursor: 'pointer', fontSize: 13 }}>← Back</button>
    </div>
  )

  return (
    <div style={{ flex: 1, overflowY: 'auto', background: C.bg, padding: '20px 28px 60px', fontFamily: 'system-ui,-apple-system,sans-serif' }}>

      {/* ── HEADER ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, marginBottom: 20 }}>
        <button onClick={onBack} style={{
          background: 'none', border: `1px solid ${C.border}`, borderRadius: 8,
          color: C.textMid, padding: '6px 12px', cursor: 'pointer', fontSize: 12, fontWeight: 600,
          display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0, marginTop: 2,
        }}>← Back</button>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, margin: 0, letterSpacing: '-0.02em' }}>
              {describe.label || objectName}
            </h1>
            <span style={{ fontSize: 13, color: C.textLo, fontWeight: 500 }}>{describe.name}</span>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {describe.custom       && <Badge label="Custom"      color={C.purple} />}
              {describe.queryable    && <Badge label="Queryable"   color={C.cyan}   />}
              {describe.createable   && <Badge label="Createable"  color={C.green}  />}
              {describe.updateable   && <Badge label="Updateable"  color={C.green}  />}
              {describe.searchable   && <Badge label="Searchable"  color={C.orange} />}
            </div>
          </div>
          {describe.labelPlural && (
            <div style={{ fontSize: 12, color: C.textLo, marginTop: 4 }}>
              Plural: <span style={{ color: C.textMid }}>{describe.labelPlural}</span>
              {describe.keyPrefix && <> · Key prefix: <span style={{ color: C.textMid }}>{describe.keyPrefix}</span></>}
            </div>
          )}
        </div>
      </div>

      {/* ── STAT CARDS ── */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
        <StatCard label="Total Fields"    value={fields.length}        color={C.cyan}   />
        <StatCard label="Custom Fields"   value={customFields.length}  color={C.purple} />
        <StatCard label="Required Fields" value={requiredFields.length} color={C.orange} />
        <StatCard label="Apex Triggers"   value={triggers.length}      color={C.red}    />
        {recCount != null && <StatCard label="Records" value={recCount.toLocaleString()} color={C.green} />}
      </div>

      {/* ── TABS ── */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: `1px solid ${C.border}`, paddingBottom: 0 }}>
        {[
          { id: 'fields',   label: `Fields (${fields.length})`,     icon: '📝' },
          { id: 'triggers', label: `Triggers (${triggers.length})`, icon: '⚡' },
          { id: 'summary',  label: 'Summary',                       icon: '📊' },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '8px 16px', background: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
            border: 'none', borderBottom: `2px solid ${tab === t.id ? C.cyan : 'transparent'}`,
            color: tab === t.id ? C.cyan : C.textLo, transition: 'all 0.15s',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span>{t.icon}</span>{t.label}
          </button>
        ))}
      </div>

      {/* ── FIELDS TAB ── */}
      {tab === 'fields' && (
        <div>
          <input
            placeholder="Search fields by name, label or type…"
            value={fieldSearch}
            onChange={e => setFieldSearch(e.target.value)}
            style={{
              width: '100%', boxSizing: 'border-box', marginBottom: 12,
              padding: '9px 14px', background: C.surface, border: `1px solid ${C.border}`,
              borderRadius: 8, color: C.text, fontSize: 13, outline: 'none',
            }}
          />
          <div style={{ border: `1px solid ${C.border}`, borderRadius: 10, overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto', maxHeight: 'calc(100vh - 380px)', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ background: C.surfaceHi, position: 'sticky', top: 0, zIndex: 1 }}>
                    {['Label', 'API Name', 'Type', 'Required', 'Custom', 'Unique', 'Length'].map(col => (
                      <th key={col} style={{
                        padding: '8px 12px', textAlign: 'left', fontWeight: 700, fontSize: 10,
                        color: C.textLo, textTransform: 'uppercase', letterSpacing: '0.07em',
                        borderBottom: `1px solid ${C.border}`, whiteSpace: 'nowrap',
                      }}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredFields.length === 0 ? (
                    <tr><td colSpan={7} style={{ padding: '20px', textAlign: 'center', color: C.textLo, fontStyle: 'italic' }}>No fields match</td></tr>
                  ) : filteredFields.map((f, i) => (
                    <tr key={f.name} style={{ borderBottom: `1px solid ${C.border}`, background: i % 2 === 0 ? 'transparent' : `${C.surfaceHi}66` }}>
                      <td style={{ padding: '7px 12px', color: C.text, fontWeight: 500 }}>{f.label}</td>
                      <td style={{ padding: '7px 12px', color: C.textMid, fontFamily: 'monospace', fontSize: 11 }}>{f.name}</td>
                      <td style={{ padding: '7px 12px' }}>
                        <span style={{
                          fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4,
                          background: `${typeColor(f.type)}20`, color: typeColor(f.type),
                          border: `1px solid ${typeColor(f.type)}40`,
                        }}>{f.type}</span>
                      </td>
                      <td style={{ padding: '7px 12px', color: !f.nillable && f.createable ? C.orange : C.textLo }}>
                        {!f.nillable && f.createable ? '✓' : '—'}
                      </td>
                      <td style={{ padding: '7px 12px', color: f.custom ? C.purple : C.textLo }}>
                        {f.custom ? '✓' : '—'}
                      </td>
                      <td style={{ padding: '7px 12px', color: f.unique ? C.cyan : C.textLo }}>
                        {f.unique ? '✓' : '—'}
                      </td>
                      <td style={{ padding: '7px 12px', color: C.textLo, fontFamily: 'monospace', fontSize: 11 }}>
                        {f.length || f.precision || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ padding: '7px 12px', fontSize: 11, color: C.textLo, borderTop: `1px solid ${C.border}`, background: C.surfaceHi }}>
              {filteredFields.length} of {fields.length} fields
              {fieldSearch && <> matching "<span style={{ color: C.cyan }}>{fieldSearch}</span>"</>}
            </div>
          </div>
        </div>
      )}

      {/* ── TRIGGERS TAB ── */}
      {tab === 'triggers' && (
        <div>
          {triggers.length === 0 ? (
            <div style={{
              background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10,
              padding: '40px 20px', textAlign: 'center',
            }}>
              <div style={{ fontSize: 28, marginBottom: 8 }}>⚡</div>
              <div style={{ color: C.textLo, fontSize: 14 }}>No Apex triggers on {objectName}</div>
            </div>
          ) : (
            <div style={{ border: `1px solid ${C.border}`, borderRadius: 10, overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: C.surfaceHi }}>
                    {['Trigger Name', 'Status', 'API Version'].map(col => (
                      <th key={col} style={{
                        padding: '9px 14px', textAlign: 'left', fontWeight: 700, fontSize: 10,
                        color: C.textLo, textTransform: 'uppercase', letterSpacing: '0.07em',
                        borderBottom: `1px solid ${C.border}`,
                      }}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {triggers.map((t, i) => (
                    <tr key={t.Id || i} style={{ borderBottom: `1px solid ${C.border}`, background: i % 2 === 0 ? 'transparent' : `${C.surfaceHi}66` }}>
                      <td style={{ padding: '9px 14px', color: C.text, fontWeight: 600 }}>{t.Name}</td>
                      <td style={{ padding: '9px 14px' }}>
                        <span style={{
                          fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                          background: t.Status === 'Active' ? `${C.green}18` : `${C.red}18`,
                          color: t.Status === 'Active' ? C.green : C.red,
                          border: `1px solid ${t.Status === 'Active' ? C.green : C.red}30`,
                        }}>{t.Status}</span>
                      </td>
                      <td style={{ padding: '9px 14px', color: C.textLo }}>{t.ApiVersion}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── SUMMARY TAB ── */}
      {tab === 'summary' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

          {/* Field type breakdown */}
          <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: '18px 20px' }}>
            <div style={{ fontSize: 11, fontWeight: 800, color: C.textLo, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 14 }}>Field Types</div>
            {Object.entries(typeSummary).sort((a, b) => b[1] - a[1]).map(([type, count]) => {
              const pct = Math.round((count / fields.length) * 100)
              return (
                <div key={type} style={{ marginBottom: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                    <span style={{ fontSize: 12, color: typeColor(type), fontWeight: 600 }}>{type}</span>
                    <span style={{ fontSize: 12, color: C.textLo }}>{count} ({pct}%)</span>
                  </div>
                  <div style={{ height: 4, background: C.surfaceHi, borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${pct}%`, background: typeColor(type), borderRadius: 2, transition: 'width 0.8s ease' }} />
                  </div>
                </div>
              )
            })}
          </div>

          {/* Object capabilities */}
          <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: '18px 20px' }}>
            <div style={{ fontSize: 11, fontWeight: 800, color: C.textLo, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 14 }}>Capabilities</div>
            {[
              ['Queryable',    describe.queryable],
              ['Searchable',   describe.searchable],
              ['Createable',   describe.createable],
              ['Updateable',   describe.updateable],
              ['Deletable',    describe.deletable],
              ['Feed Enabled', describe.feedEnabled],
              ['History Tracked', describe.historyEnabled],
              ['Undeletable',  describe.undeletable],
              ['Mergeable',    describe.mergeable],
              ['Replicateable',describe.replicateable],
            ].map(([label, val]) => val !== undefined && (
              <div key={label} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '6px 0', borderBottom: `1px solid ${C.border}`,
              }}>
                <span style={{ fontSize: 12, color: C.textMid }}>{label}</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: val ? C.green : C.textLo }}>{val ? '✓ Yes' : '✗ No'}</span>
              </div>
            ))}
          </div>

          {/* Custom field stats */}
          <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: '18px 20px' }}>
            <div style={{ fontSize: 11, fontWeight: 800, color: C.textLo, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 14 }}>Field Breakdown</div>
            {[
              ['Standard fields', fields.length - customFields.length, C.cyan],
              ['Custom fields',   customFields.length,                  C.purple],
              ['Required fields', requiredFields.length,                C.orange],
              ['Unique fields',   fields.filter(f => f.unique).length,  C.green],
              ['External IDs',    fields.filter(f => f.externalId).length, C.yellow],
              ['Encrypted',       fields.filter(f => f.encrypted).length, C.red],
            ].map(([label, count, color]) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: `1px solid ${C.border}` }}>
                <span style={{ fontSize: 12, color: C.textMid }}>{label}</span>
                <span style={{ fontSize: 14, fontWeight: 700, color }}>{count}</span>
              </div>
            ))}
          </div>

          {/* Reference fields */}
          {fields.filter(f => f.type === 'reference').length > 0 && (
            <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: '18px 20px' }}>
              <div style={{ fontSize: 11, fontWeight: 800, color: C.textLo, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 14 }}>Relationships</div>
              <div style={{ maxHeight: 240, overflowY: 'auto' }}>
                {fields.filter(f => f.type === 'reference').map(f => (
                  <div key={f.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: `1px solid ${C.border}` }}>
                    <span style={{ fontSize: 12, color: C.textMid }}>{f.label}</span>
                    <span style={{ fontSize: 11, color: '#a78bfa', fontFamily: 'monospace' }}>
                      → {f.referenceTo?.join(', ') || '?'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
