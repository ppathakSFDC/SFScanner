import React, { useState, useEffect, useMemo } from 'react'

const C = {
  bg: 'var(--bg)', surface: 'var(--surface)', surfaceHi: 'var(--surface-hi)',
  border: 'var(--border)',
  cyan: '#06b6d4', green: '#22c55e', orange: '#f97316', red: '#ef4444',
  purple: '#a855f7', yellow: '#eab308', blue: '#3b82f6', teal: '#14b8a6',
  pink: '#f472b6', lime: '#a3e635', indigo: '#818cf8', rose: '#fb7185',
  text: 'var(--text)', textMid: 'var(--text-mid)', textLo: 'var(--text-lo)',
}

const PALETTE = [
  C.cyan, C.purple, C.green, C.orange, C.red,
  C.yellow, C.blue, C.teal, C.pink, C.lime, C.indigo, C.rose,
]

const COL_LABELS = {
  QualifiedApiName:'API Name', DeveloperName:'Developer Name', TableEnumOrId:'SObject',
  LengthWithoutComments:'Lines', ValidationName:'Rule Name', IsCustom:'Custom',
  IsActive:'Active', UserType:'User Type', MasterLabel:'Name', ProcessType:'Flow Type',
  EventType:'Event Type', ApiVersion:'API Ver', SiteName:'Site Name', SiteURL:'URL',
  PrincipalType:'Auth Type', ProviderType:'Provider', FriendlyName:'Display Name',
  LastLoginDate:'Last Login', 'Profile.Name':'Profile',
}
function fmtCol(name) {
  return COL_LABELS[name] || name.replace(/([A-Z])/g, ' $1').replace(/\./g, ' ').trim()
}
function fmtVal(val) {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'boolean') return val ? 'Yes' : 'No'
  if (typeof val === 'number') return val.toLocaleString()
  if (typeof val === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(val))
    return new Date(val).toLocaleDateString(undefined, { year:'numeric', month:'short', day:'numeric' })
  return String(val)
}
function cellStyle(col, val) {
  if (typeof val === 'boolean' || val === 'true' || val === 'false')
    return { color: (val === true || val === 'true') ? C.green : C.red }
  if (col === 'Status')
    return { color: String(val).toLowerCase() === 'active' ? C.green : C.red }
  return {}
}

// ─── Donut Chart ──────────────────────────────────────────────────────────────

function DonutChart({ segments, size = 150, thickness = 26, centerLabel, centerSub }) {
  const cx = size / 2, cy = size / 2
  const r  = (size - thickness) / 2
  const circ = 2 * Math.PI * r
  const total = segments.reduce((s, seg) => s + seg.value, 0)
  let accumulated = 0

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}
      style={{ display:'block', overflow:'visible', flexShrink:0 }}>
      {/* background track */}
      <circle cx={cx} cy={cy} r={r} fill="none"
        stroke="rgba(255,255,255,0.05)" strokeWidth={thickness} />

      {segments.filter(s => s.value > 0).map((seg, i) => {
        const pct   = total > 0 ? seg.value / total : 0
        const dash  = pct * circ
        const start = -90 + accumulated * 360   // degrees; -90 = 12 o'clock
        accumulated += pct
        return (
          <circle key={i} cx={cx} cy={cy} r={r} fill="none"
            stroke={seg.color} strokeWidth={thickness}
            strokeDasharray={`${dash} ${circ - dash}`}
            style={{
              transform: `rotate(${start}deg)`,
              transformOrigin: `${cx}px ${cy}px`,
              transition: 'stroke-dasharray 0.8s cubic-bezier(.4,0,.2,1)',
            }}
          />
        )
      })}

      {/* center text */}
      {centerLabel && (
        <text x={cx} y={cy - 5} textAnchor="middle"
          fill="white" fontSize="20" fontWeight="800"
          fontFamily="system-ui,sans-serif">{centerLabel}</text>
      )}
      {centerSub && (
        <text x={cx} y={cy + 13} textAnchor="middle"
          fill="var(--text-lo)" fontSize="9" fontWeight="700"
          letterSpacing="0.09em" fontFamily="system-ui,sans-serif">{centerSub}</text>
      )}
    </svg>
  )
}

// ─── Donut + Legend block ─────────────────────────────────────────────────────

function DonutBlock({ title, segments, size = 150, centerLabel, centerSub }) {
  const total = segments.reduce((s, seg) => s + seg.value, 0)
  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: '16px 18px',
    }}>
      {title && (
        <div style={{ fontSize: 10, fontWeight: 800, color: C.textLo, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 14 }}>
          {title}
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <DonutChart
          segments={segments}
          size={size}
          thickness={Math.round(size * 0.17)}
          centerLabel={centerLabel ?? total.toLocaleString()}
          centerSub={centerSub ?? 'TOTAL'}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          {segments.map(({ label, value, color }) => {
            const pct = total > 0 ? Math.round((value / total) * 100) : 0
            return (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: color, flexShrink: 0 }} />
                <span style={{ flex: 1, fontSize: 12, color: C.textMid, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
                <span style={{ fontSize: 13, fontWeight: 700, color }}>{value.toLocaleString()}</span>
                <span style={{ fontSize: 10, color: C.textLo, minWidth: 32, textAlign: 'right' }}>{pct}%</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ─── Stat Card ────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color = C.cyan }) {
  return (
    <div style={{
      background: C.surfaceHi, border: `1px solid ${C.border}`,
      borderRadius: 10, padding: '14px 18px', flex: 1, minWidth: 0,
    }}>
      <div style={{ fontSize: 10, color: C.textLo, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 900, color, letterSpacing: '-0.02em', lineHeight: 1 }}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      {sub && <div style={{ fontSize: 11, color: C.textLo, marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

// ─── User Summary ─────────────────────────────────────────────────────────────

function UserSummary() {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')

  useEffect(() => {
    const p = new URLSearchParams({
      object_name: 'User', fields: 'UserType,IsActive,LastLoginDate,Profile.Name',
      filter_clause: '', tooling: 'false', limit: '2000',
    })
    fetch(`/auth/list-records?${p}`, { credentials: 'include' })
      .then(r => r.text())
      .then(t => {
        const j = JSON.parse(t)
        const users = j.records || []

        const isInternal = u => !u.UserType || u.UserType === 'Standard'
        const isActive   = u => u.IsActive === true  || u.IsActive === 'true'
        const isInactive = u => u.IsActive === false || u.IsActive === 'false'
        const neverIn    = u => !u.LastLoginDate || u.LastLoginDate === null

        const internal = users.filter(isInternal)
        const external = users.filter(u => !isInternal(u) && u.UserType !== 'Guest')
        const guests   = users.filter(u => u.UserType === 'Guest')

        // UserType donut (top 10)
        const typeMap = {}
        users.forEach(u => { const t = u.UserType || 'Standard'; typeMap[t] = (typeMap[t] || 0) + 1 })
        const typeSegs = Object.entries(typeMap).sort((a,b)=>b[1]-a[1])
          .map(([label, value], i) => ({ label, value, color: PALETTE[i] }))

        // Profile donut (top 10 + Others)
        const profMap = {}
        users.forEach(u => { const n = u['Profile.Name'] || 'Unknown'; profMap[n] = (profMap[n] || 0) + 1 })
        const sorted = Object.entries(profMap).sort((a,b)=>b[1]-a[1])
        const topN   = sorted.slice(0, 10)
        const others = sorted.slice(10).reduce((s,[,c])=>s+c, 0)
        const profSegs = [
          ...topN.map(([label, value], i) => ({ label, value, color: PALETTE[i] })),
          ...(others > 0 ? [{ label: 'Others', value: others, color: 'rgba(255,255,255,0.18)' }] : []),
        ]

        const mkGroup = arr => ({
          total:        arr.length,
          active:       arr.filter(isActive).length,
          inactive:     arr.filter(isInactive).length,
          neverLoggedIn:arr.filter(neverIn).length,
        })

        setData({ total: users.length, internal: mkGroup(internal), external: mkGroup(external), guests: guests.length, typeSegs, profSegs })
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:240, flexDirection:'column', gap:10 }}>
      <div style={{ fontSize:22 }}>⏳</div>
      <div style={{ color:C.textLo, fontSize:13 }}>Loading user analytics…</div>
    </div>
  )
  if (error) return <div style={{ color:C.red, padding:24, fontSize:13 }}>⚠ {error}</div>
  if (!data)  return null

  const intSegs  = [
    { label:'Active',          value: data.internal.active,        color: C.green  },
    { label:'Inactive',        value: data.internal.inactive,      color: C.red    },
    { label:'Never Logged In', value: data.internal.neverLoggedIn, color: C.orange },
  ]
  const extSegs  = [
    { label:'Active',          value: data.external.active,        color: C.green  },
    { label:'Inactive',        value: data.external.inactive,      color: C.red    },
    { label:'Never Logged In', value: data.external.neverLoggedIn, color: C.orange },
  ]

  return (
    <div style={{ padding:'20px 24px', overflowY:'auto' }}>

      {/* Stat row */}
      <div style={{ display:'flex', gap:12, marginBottom:20 }}>
        <StatCard label="Total Users"          value={data.total}             color={C.cyan}   />
        <StatCard label="Internal"             value={data.internal.total}    color={C.blue}   sub={`${data.internal.active} active`} />
        <StatCard label="Community / External" value={data.external.total}    color={C.purple} sub={`${data.external.active} active`} />
        {data.guests > 0 && <StatCard label="Guest" value={data.guests} color={C.textLo} />}
      </div>

      {/* Internal + External donuts */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, marginBottom:20 }}>
        <DonutBlock
          title="Internal Users (Standard)"
          segments={intSegs}
          size={150}
          centerLabel={data.internal.total.toString()}
          centerSub="INTERNAL"
        />
        <DonutBlock
          title="Community / External Users"
          segments={data.external.total === 0
            ? [{ label:'No external users', value:1, color:'rgba(255,255,255,0.07)' }]
            : extSegs
          }
          size={150}
          centerLabel={data.external.total.toString()}
          centerSub="EXTERNAL"
        />
      </div>

      {/* User Type breakdown */}
      {data.typeSegs.length > 1 && (
        <div style={{ marginBottom:20 }}>
          <DonutBlock
            title="User Type Breakdown"
            segments={data.typeSegs}
            size={160}
            centerLabel={data.total.toString()}
            centerSub="USERS"
          />
        </div>
      )}

      {/* Users per Profile */}
      <DonutBlock
        title={`Users per Profile${data.profSegs.some(s=>s.label==='Others') ? ' (top 10 + others)' : ''}`}
        segments={data.profSegs}
        size={180}
        centerLabel={data.total.toString()}
        centerSub="USERS"
      />
    </div>
  )
}

// ─── Permission Set Summary ────────────────────────────────────────────────────

function PermSetSummary({ records }) {
  const custom  = records.filter(r => r.IsCustom === true  || r.IsCustom === 'true').length
  const managed = records.filter(r => r.IsCustom === false || r.IsCustom === 'false').length

  return (
    <div style={{ padding:'20px 24px' }}>
      <div style={{ display:'flex', gap:12, marginBottom:20 }}>
        <StatCard label="Total Permission Sets" value={records.length} color={C.cyan} />
        <StatCard label="Custom"   value={custom}  color={C.yellow} sub="Created in org" />
        <StatCard label="Managed"  value={managed} color={C.purple} sub="From packages"  />
      </div>
      <DonutBlock
        title="Custom vs Managed"
        segments={[
          { label:'Custom',  value:custom,  color:C.yellow },
          { label:'Managed', value:managed, color:C.purple },
        ]}
        size={160}
        centerLabel={records.length.toString()}
        centerSub="TOTAL"
      />
    </div>
  )
}

// ─── Generic Summary ──────────────────────────────────────────────────────────

function GenericSummary({ records, columns, label }) {
  const charts = useMemo(() => {
    if (!records.length) return []
    const skipCols = new Set(['Id', 'Description', 'Endpoint', 'SiteURL', 'Username', 'DeveloperName', 'QualifiedApiName'])
    return columns
      .filter(col => !skipCols.has(col) && col !== 'Name')
      .map(col => {
        const dist = {}
        records.forEach(r => { const k = fmtVal(r[col]); dist[k] = (dist[k] || 0) + 1 })
        const entries = Object.entries(dist).sort((a,b) => b[1]-a[1])
        return { col, entries, unique: entries.length }
      })
      .filter(d => d.unique >= 2 && d.unique <= 20)
      .slice(0, 4)
      .map(({ col, entries }) => ({
        col,
        segments: entries.map(([label, value], i) => ({ label, value, color: PALETTE[i % PALETTE.length] })),
      }))
  }, [records, columns])

  return (
    <div style={{ padding:'20px 24px' }}>
      <div style={{ display:'flex', gap:12, marginBottom:20 }}>
        <StatCard label={`Total ${label}`} value={records.length} color={C.cyan} />
      </div>
      {charts.length === 0 ? (
        <div style={{ color:C.textLo, fontSize:13, textAlign:'center', padding:'32px 0' }}>
          No distribution data available for the loaded fields.
        </div>
      ) : (
        <div style={{ display:'grid', gridTemplateColumns: charts.length === 1 ? '1fr' : '1fr 1fr', gap:16 }}>
          {charts.map(({ col, segments }) => (
            <DonutBlock
              key={col}
              title={fmtCol(col)}
              segments={segments}
              size={140}
              centerLabel={records.length.toString()}
              centerSub="TOTAL"
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function RecordsListPage({ config, onBack }) {
  const [records, setRecords] = useState([])
  const [columns, setColumns] = useState([])
  const [total,   setTotal]   = useState(0)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')
  const [search,  setSearch]  = useState('')
  const [sortCol, setSortCol] = useState(null)
  const [sortAsc, setSortAsc] = useState(true)
  const [tab,     setTab]     = useState('records')

  useEffect(() => {
    if (!config?.object) return
    setLoading(true); setError(''); setRecords([]); setColumns([]); setSearch(''); setTab('records')

    const p = new URLSearchParams({
      object_name:   config.object,
      fields:        config.fields || 'Id,Name',
      filter_clause: config.filter || '',
      tooling:       config.tooling ? 'true' : 'false',
      limit:         '500',
    })
    fetch(`/auth/list-records?${p}`, { credentials:'include' })
      .then(r => r.text())
      .then(t => {
        try {
          const j = JSON.parse(t)
          if (!j.records) return setError(j.detail || 'Unexpected response')
          setRecords(j.records); setColumns(j.columns); setTotal(j.total)
          if (j.columns?.length) setSortCol(j.columns[0])
        } catch { setError('Could not parse response') }
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [config])

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    const base = q
      ? records.filter(r => Object.values(r).some(v => String(v ?? '').toLowerCase().includes(q)))
      : records
    if (!sortCol) return base
    return [...base].sort((a, b) => {
      const va = String(a[sortCol] ?? ''), vb = String(b[sortCol] ?? '')
      return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va)
    })
  }, [records, search, sortCol, sortAsc])

  function toggleSort(col) {
    if (sortCol === col) setSortAsc(a => !a)
    else { setSortCol(col); setSortAsc(true) }
  }

  function renderSummary() {
    const obj = config?.object
    if (!loading && !error) {
      if (obj === 'User')          return <UserSummary />
      if (obj === 'PermissionSet') return <PermSetSummary records={records} />
      return <GenericSummary records={records} columns={columns} label={config?.label || obj} />
    }
    return null
  }

  return (
    <div style={{
      flex:1, display:'flex', flexDirection:'column', overflow:'hidden',
      background:C.bg, fontFamily:'system-ui,-apple-system,sans-serif',
    }}>
      {/* ── HEADER ── */}
      <div style={{
        display:'flex', alignItems:'center', gap:14,
        padding:'12px 24px', borderBottom:`1px solid ${C.border}`,
        background:C.surface, flexShrink:0,
      }}>
        <button onClick={onBack} style={{
          background:'none', border:`1px solid ${C.border}`, borderRadius:8,
          color:C.textMid, padding:'6px 14px', cursor:'pointer', fontSize:12, fontWeight:600,
        }}>← Back</button>

        <div style={{ flex:1 }}>
          <div style={{ display:'flex', alignItems:'center', gap:10 }}>
            <h2 style={{ margin:0, fontSize:17, fontWeight:800, color:C.text, letterSpacing:'-0.02em' }}>
              {config?.label || config?.object}
            </h2>
            {!loading && (
              <span style={{
                fontSize:11, fontWeight:700, padding:'2px 10px', borderRadius:20,
                background:'rgba(6,182,212,0.12)', border:'1px solid rgba(6,182,212,0.25)', color:C.cyan,
              }}>
                {total > records.length ? `${records.length} of ${total.toLocaleString()}` : total.toLocaleString()} records
              </span>
            )}
          </div>
          <div style={{ fontSize:11, color:C.textLo, marginTop:1 }}>
            {config?.object}{config?.filter ? ` · where ${config.filter}` : ''}
          </div>
        </div>

        {/* Tab switcher */}
        <div style={{ display:'flex', gap:2, background:C.surfaceHi, borderRadius:8, padding:3, border:`1px solid ${C.border}` }}>
          {['records','summary'].map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding:'5px 14px', border:'none', borderRadius:6,
              background: tab===t ? C.surface : 'transparent',
              color: tab===t ? C.text : C.textLo,
              fontSize:12, fontWeight: tab===t ? 700 : 500, cursor:'pointer',
              boxShadow: tab===t ? '0 1px 3px rgba(0,0,0,0.2)' : 'none',
              transition:'all 0.12s',
            }}>
              {t === 'records' ? '📋 Records' : '📊 Summary'}
            </button>
          ))}
        </div>

        {/* Search (records tab only) */}
        {tab === 'records' && (
          <div style={{ position:'relative', width:210 }}>
            <span style={{ position:'absolute', left:9, top:'50%', transform:'translateY(-50%)', fontSize:12, pointerEvents:'none' }}>🔍</span>
            <input
              placeholder="Search…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                width:'100%', boxSizing:'border-box', padding:'7px 26px 7px 28px',
                background:C.bg, border:`1px solid ${C.border}`,
                borderRadius:8, color:C.text, fontSize:12, outline:'none',
              }}
            />
            {search && (
              <button onClick={() => setSearch('')} style={{
                position:'absolute', right:7, top:'50%', transform:'translateY(-50%)',
                background:'none', border:'none', color:C.textLo, cursor:'pointer', fontSize:13,
              }}>×</button>
            )}
          </div>
        )}
      </div>

      {/* ── BODY ── */}
      <div style={{ flex:1, overflow:'auto' }}>
        {loading && (
          <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100%', flexDirection:'column', gap:12 }}>
            <div style={{ fontSize:28 }}>⏳</div>
            <div style={{ color:C.textLo, fontSize:13 }}>Loading {config?.label}…</div>
          </div>
        )}

        {!loading && error && (
          <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100%', flexDirection:'column', gap:12 }}>
            <div style={{ fontSize:28 }}>⚠️</div>
            <div style={{ color:C.red, fontSize:13, maxWidth:500, textAlign:'center' }}>{error}</div>
            <button onClick={onBack} style={{ padding:'8px 18px', background:C.surfaceHi, border:`1px solid ${C.border}`, borderRadius:8, color:C.text, cursor:'pointer', fontSize:13 }}>← Back</button>
          </div>
        )}

        {!loading && !error && tab === 'records' && (
          <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>
            <thead>
              <tr style={{ background:C.surfaceHi, position:'sticky', top:0, zIndex:2 }}>
                <th style={{ padding:'9px 14px', textAlign:'left', fontWeight:700, fontSize:9, color:C.textLo, textTransform:'uppercase', letterSpacing:'0.08em', borderBottom:`1px solid ${C.border}`, width:40 }}>#</th>
                {columns.map(col => (
                  <th key={col} onClick={() => toggleSort(col)} style={{
                    padding:'9px 14px', textAlign:'left', fontWeight:700, fontSize:9,
                    color: sortCol===col ? C.cyan : C.textLo,
                    textTransform:'uppercase', letterSpacing:'0.08em',
                    borderBottom:`1px solid ${C.border}`,
                    cursor:'pointer', userSelect:'none', whiteSpace:'nowrap',
                  }}>
                    {fmtCol(col)}
                    <span style={{ marginLeft:3, opacity: sortCol===col ? 1 : 0.3 }}>
                      {sortCol===col ? (sortAsc ? '▲' : '▼') : '⇅'}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={columns.length + 1} style={{ padding:'48px 16px', textAlign:'center', color:C.textLo, fontStyle:'italic', fontSize:13 }}>
                    {search ? `No records match "${search}"` : 'No records found'}
                  </td>
                </tr>
              ) : filtered.map((rec, i) => (
                <tr key={rec.Id || i} style={{
                  borderBottom:`1px solid ${C.border}`,
                  background: i % 2 === 0 ? 'transparent' : `${C.surfaceHi}55`,
                }}>
                  <td style={{ padding:'8px 14px', color:C.textLo, fontSize:10 }}>{i+1}</td>
                  {columns.map(col => (
                    <td key={col} style={{
                      padding:'8px 14px', color:C.text,
                      maxWidth:240, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap',
                      ...cellStyle(col, rec[col]),
                    }}>
                      {fmtVal(rec[col])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {!loading && !error && tab === 'summary' && renderSummary()}
      </div>

      {/* ── FOOTER ── */}
      {!loading && !error && tab === 'records' && filtered.length > 0 && (
        <div style={{
          padding:'6px 24px', borderTop:`1px solid ${C.border}`,
          background:C.surfaceHi, fontSize:11, color:C.textLo,
          display:'flex', justifyContent:'space-between', flexShrink:0,
        }}>
          <span>
            {search
              ? `${filtered.length} match${filtered.length !== 1 ? 'es' : ''} for "${search}" of ${records.length}`
              : `${records.length} record${records.length !== 1 ? 's' : ''} loaded`}
          </span>
          {total > records.length && (
            <span style={{ color:C.orange }}>⚠ Showing first {records.length} — refine filter to see more</span>
          )}
        </div>
      )}
    </div>
  )
}
