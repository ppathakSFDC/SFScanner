import React, { useState, useEffect, useCallback, useRef } from 'react'
import OrgAuthModal from '../components/OrgAuthModal.jsx'

const PRODUCT_BUNDLES = new Set(['revenue_product_bundle', 'rca_product_catalog'])

const STATUS_COLOR = {
  waiting:          { text: '#4a9a9a',  bg: 'transparent',              dot: 'var(--border-hi)' },
  running:          { text: '#67e8f9',  bg: 'rgba(6,182,212,0.08)',     dot: '#06b6d4' },
  done:             { text: '#86efac',  bg: 'rgba(34,197,94,0.06)',     dot: '#22c55e' },
  done_with_errors: { text: '#fde68a',  bg: 'rgba(234,179,8,0.06)',     dot: '#eab308' },
  failed:           { text: '#fca5a5',  bg: 'rgba(239,68,68,0.06)',     dot: '#ef4444' },
  skipped:          { text: '#4a9a9a',  bg: 'transparent',              dot: 'var(--border-hi)' },
}

const OBJ_PALETTE = ['#3b82f6','#8b5cf6','#ec4899','#f97316','#22c55e','#06b6d4','#eab308','#ef4444','#14b8a6','#a855f7']
function objColor(name) {
  let h = 0; for (let i = 0; i < name.length; i++) { h = ((h << 5) - h) + name.charCodeAt(i); h |= 0 }
  return OBJ_PALETTE[Math.abs(h) % OBJ_PALETTE.length]
}

const s = {
  page:     { height: '100%', background: 'var(--bg)', padding: '28px 24px 60px', overflowY: 'auto', overscrollBehavior: 'none' },
  inner:    { maxWidth: '100%' },
  section:  { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 14, padding: 24, marginBottom: 20 },
  label:    { display: 'block', fontSize: 12, color: 'var(--text-mid)', marginBottom: 5, fontWeight: 500 },
  input:    { width: '100%', padding: '9px 11px', background: 'var(--input-bg)', border: '1px solid var(--input-border)', borderRadius: 7, color: 'var(--input-color)', fontSize: 13, boxSizing: 'border-box', outline: 'none', fontFamily: 'inherit' },
  btn:      (v) => ({ padding: '9px 20px', background: v === 'primary' ? 'linear-gradient(135deg,#1e40af,#3b82f6)' : v === 'danger' ? 'transparent' : v === 'ghost' ? 'transparent' : 'var(--surface-hi)', border: v === 'danger' ? '1px solid rgba(239,68,68,0.4)' : v === 'primary' ? 'none' : '1px solid var(--border)', borderRadius: 8, color: v === 'primary' ? 'white' : v === 'danger' ? '#fca5a5' : 'var(--text-mid)', fontSize: 13, fontWeight: 600, cursor: 'pointer' }),
  err:      { background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 7, padding: '9px 13px', color: '#fca5a5', fontSize: 12, marginBottom: 10 },
  warn:     { background: 'rgba(234,179,8,0.06)', border: '1px solid rgba(234,179,8,0.2)', borderRadius: 7, padding: '9px 13px', color: '#fde68a', fontSize: 12, marginBottom: 10 },
  ok:       { background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 7, padding: '9px 13px', color: '#86efac', fontSize: 12, marginBottom: 10 },
  progBar:  () => ({ height: 4, borderRadius: 2, background: 'var(--border)', overflow: 'hidden', marginTop: 4 }),
  progFill: (pct, color) => ({ height: '100%', width: `${pct}%`, background: color || '#06b6d4', borderRadius: 2, transition: 'width 0.5s ease' }),
  objStatus: (status) => ({ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 8, background: STATUS_COLOR[status]?.bg || 'transparent', marginBottom: 6 }),
  statusDot: (status) => ({ width: 8, height: 8, borderRadius: '50%', background: STATUS_COLOR[status]?.dot || 'var(--border-hi)', flexShrink: 0 }),
  depBox:   { background: 'var(--surface-hi)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px', marginTop: 6 },
  depStep:  { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 },
  sectionTitle: { fontSize: 11, fontWeight: 700, color: 'var(--text-mid)', textTransform: 'uppercase', letterSpacing: '0.08em' },
}

// ─── Salesforce Cloud SVG Icon ────────────────────────────────────────────────
function SfCloudIcon({ size = 22, color = 'white' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M10.5 6.5C11.3 4.5 13.2 3 15.5 3c2.9 0 5.2 2.3 5.2 5.2 0 .3 0 .5-.1.8C22 9.6 23 11.1 23 12.8c0 2.4-2 4.4-4.4 4.4H6.8C4.2 17.2 2 15 2 12.4c0-2 1.2-3.7 3-4.4-.1-.4-.1-.8-.1-1.3 0-3 2.5-5.5 5.6-5.5.1 0 0 5.3 0 5.3" fill={color} opacity="0.9"/>
    </svg>
  )
}

// ─── Database Icon SVG ────────────────────────────────────────────────────────
function DbIcon({ size = 28, color = 'white' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M3 5v4c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
      <path d="M3 9v4c0 1.66 4.03 3 9 3s9-1.34 9-3V9" />
      <path d="M3 13v4c0 1.66 4.03 3 9 3s9-1.34 9-3v-4" />
    </svg>
  )
}

// ─── Record Picker Modal ──────────────────────────────────────────────────────
function RecordPickerModal({ availableObjects, initialObjectName, fixedObject, recordSelections, onClose, onConfirm }) {
  const resolvedInit = fixedObject || initialObjectName || (availableObjects[0]?.name ?? '')
  const [objName, setObjName] = React.useState(resolvedInit)
  const [search, setSearch] = React.useState('')
  const [records, setRecords] = React.useState([])
  const [loading, setLoading] = React.useState(false)
  const [chosen, setChosen] = React.useState(recordSelections[resolvedInit] || [])
  const timerRef = React.useRef(null)
  const isFixed = !!fixedObject

  async function fetchRecords(name, q) {
    if (!name) return
    setLoading(true)
    try {
      const res = await fetch(`/migrate/records/${encodeURIComponent(name)}?q=${encodeURIComponent(q)}`, { credentials: 'include' })
      const d = await res.json()
      setRecords(d.records || [])
    } catch { setRecords([]) }
    setLoading(false)
  }

  React.useEffect(() => {
    setSearch('')
    setChosen(recordSelections[objName] || [])
    fetchRecords(objName, '')
  }, [objName])  // eslint-disable-line

  function handleSearch(e) {
    const v = e.target.value
    setSearch(v)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => fetchRecords(objName, v), 350)
  }

  function toggleRecord(rec) {
    setChosen(prev => prev.some(r => r.id === rec.id) ? prev.filter(r => r.id !== rec.id) : [...prev, rec])
  }

  const chosenSet = new Set(chosen.map(r => r.id))
  const selectedObj = availableObjects.find(o => o.name === objName)
  const displayLabel = selectedObj?.label || objName

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 1100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 12, width: 760, maxWidth: '96vw', maxHeight: '84vh', display: 'flex', flexDirection: 'column', boxShadow: '0 24px 60px rgba(0,0,0,0.5)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', padding: '20px 24px 0' }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', marginBottom: 2 }}>Select {displayLabel}</div>
            <div style={{ width: 40, height: 3, background: '#3b82f6', borderRadius: 2, marginBottom: 16 }} />
          </div>
           <button onClick={onClose} aria-label="Close record picker" style={{ background: 'none', border: 'none', color: 'var(--text-lo)', cursor: 'pointer', fontSize: 22, lineHeight: 1, marginTop: -2 }}>×</button>
        </div>
        <div style={{ padding: '0 24px 14px', display: 'flex', gap: 10, flexShrink: 0 }}>
          {!isFixed && (
             <select value={objName} onChange={e => setObjName(e.target.value)} aria-label="Record type"
              style={{ flex: '0 0 200px', padding: '9px 10px', background: 'var(--input-bg)', border: '1px solid var(--input-border)', borderRadius: 8, color: 'var(--input-color)', fontSize: 13, outline: 'none', cursor: 'pointer' }}>
              {availableObjects.map(o => (
                <option key={o.name} value={o.name}>{o.label !== o.name ? `${o.label} (${o.name})` : o.name}</option>
              ))}
            </select>
          )}
          <input
            style={{ flex: 1, padding: '9px 14px', background: 'var(--input-bg)', border: '1px solid var(--input-border)', borderRadius: 8, color: 'var(--input-color)', fontSize: 13, outline: 'none', fontFamily: 'inherit' }}
             value={search} onChange={handleSearch} aria-label={`Search ${displayLabel} records`}
            placeholder={`Search by Name or ${selectedObj?.name || objName}…`}
            autoFocus
          />
        </div>
        <div style={{ display: 'flex', flex: 1, minHeight: 0, borderTop: '1px solid var(--border)' }}>
          <div style={{ flex: 1, overflowY: 'auto', minWidth: 0 }}>
            {loading && <div style={{ fontSize: 12, color: 'var(--text-lo)', padding: '16px 20px' }}>Loading…</div>}
            {!loading && records.length === 0 && <div style={{ fontSize: 13, color: 'var(--text-lo)', padding: '32px 20px', textAlign: 'center' }}>No records found</div>}
            {records.map(rec => {
              const isChosen = chosenSet.has(rec.id)
              return (
                <div key={rec.id} onClick={() => toggleRecord(rec)}
                  style={{ padding: '12px 20px', cursor: 'pointer', borderBottom: '1px solid var(--border)', background: isChosen ? 'rgba(59,130,246,0.06)' : 'transparent' }}
                  onMouseEnter={e => { if (!isChosen) e.currentTarget.style.background = 'var(--surface-hi)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = isChosen ? 'rgba(59,130,246,0.06)' : 'transparent' }}
                >
                  <div style={{ fontSize: 14, fontWeight: 600, color: isChosen ? '#93c5fd' : 'var(--text)', marginBottom: rec.sub ? 3 : 0 }}>{rec.name}</div>
                  {rec.sub && <div style={{ fontSize: 12, color: 'var(--text-lo)' }}>{rec.sub}</div>}
                </div>
              )
            })}
          </div>
          <div style={{ width: 210, borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', padding: '12px 14px 8px', borderBottom: '1px solid var(--border)', gap: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: '#3b82f6', textTransform: 'uppercase', letterSpacing: '0.07em', flex: 1 }}>SELECTED ({chosen.length})</span>
              {chosen.length > 0 && <button onClick={() => setChosen([])} title="Clear all" style={{ background: 'none', border: 'none', color: 'var(--text-lo)', cursor: 'pointer', fontSize: 12, padding: 0 }}>✕ Clear</button>}
            </div>
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {chosen.length === 0 ? (
                <div style={{ fontSize: 12, color: 'var(--text-lo)', padding: '16px 14px' }}>None selected</div>
              ) : chosen.map(rec => (
                <div key={rec.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, padding: '9px 14px', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rec.name}</div>
                    {rec.sub && <div style={{ fontSize: 10, color: 'var(--text-lo)' }}>{rec.sub}</div>}
                  </div>
                   <button onClick={e => { e.stopPropagation(); toggleRecord(rec) }} aria-label={`Remove ${rec.name}`} style={{ background: 'none', border: 'none', color: 'var(--text-lo)', cursor: 'pointer', fontSize: 14, lineHeight: 1, padding: 0, flexShrink: 0, marginTop: 1 }}>×</button>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '14px 24px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
          <button onClick={() => onConfirm(objName, chosen)}
            style={{ padding: '10px 28px', background: chosen.length > 0 ? 'linear-gradient(135deg,#1e40af,#3b82f6)' : 'var(--surface-hi)', border: chosen.length > 0 ? 'none' : '1px solid var(--border)', borderRadius: 8, color: chosen.length > 0 ? 'white' : 'var(--text-mid)', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
            Confirm Selection
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Searchable object picker ─────────────────────────────────────────────────
function ObjectPicker({ objects, onSelect, disabled }) {
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)

  useEffect(() => {
    function close(e) { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const filtered = objects.filter(o =>
    !search ||
    o.name.toLowerCase().includes(search.toLowerCase()) ||
    o.label.toLowerCase().includes(search.toLowerCase())
  ).slice(0, 60)

  function pick(name) {
    onSelect(name)
    setSearch('')
    setOpen(false)
  }

  return (
    <div ref={wrapRef} style={{ position: 'relative' }}>
      <input
        style={{ width: '100%', padding: '9px 11px', background: 'var(--input-bg)', border: '1px solid var(--input-border)', borderRadius: 7, color: 'var(--input-color)', fontSize: 13, boxSizing: 'border-box', outline: 'none', fontFamily: 'inherit' }}
        value={search}
        onChange={e => { setSearch(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        placeholder={disabled ? 'All objects selected' : 'Search objects…'}
        disabled={disabled || objects.length === 0}
        autoComplete="off"
      />
      {open && filtered.length > 0 && (
        <div style={{ position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, zIndex: 200, maxHeight: 220, overflowY: 'auto', boxShadow: '0 12px 32px rgba(0,0,0,0.35)' }}>
          {filtered.map(obj => (
            <div key={obj.name} onMouseDown={e => { e.preventDefault(); pick(obj.name) }}
              style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 14px', cursor: 'pointer', borderBottom: '1px solid var(--border)' }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--surface-hi)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <div style={{ flex: 1 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{obj.label}</span>
                {obj.label !== obj.name && <span style={{ fontSize: 11, color: 'var(--text-lo)', marginLeft: 6 }}>({obj.name})</span>}
              </div>
              {obj.count > 0 && <span style={{ fontSize: 11, color: 'var(--text-lo)', flexShrink: 0 }}>{obj.count.toLocaleString()}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Progress Panel ───────────────────────────────────────────────────────────
function ProgressPanel({ progress, depOrder, migrating, dryRun }) {
  if (!progress && !migrating) return null

  if (!progress) {
    return (
      <div style={s.section}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-mid)', textTransform: 'uppercase', letterSpacing: '0.08em', flex: 1 }}>Migration Progress</div>
        </div>
        <div style={s.progBar()}><div style={s.progFill(0, '#06b6d4')} /></div>
        <div style={{ fontSize: 12, color: 'var(--text-lo)', marginTop: 6 }}>Starting migration…</div>
      </div>
    )
  }

  const objResults = progress.object_results || {}
  const pct = progress.progress_pct || 0
  const status = progress.status || 'running'
  const statusColor = status === 'completed' ? '#22c55e' : status === 'failed' ? '#ef4444' : status === 'rolling_back' ? '#fbbf24' : '#3b82f6'

  return (
    <div style={s.section}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-mid)', textTransform: 'uppercase', letterSpacing: '0.08em', flex: 1 }}>
          {dryRun ? 'Dry Run Validation' : 'Migration Progress'}
        </div>
        {dryRun && <span style={{ fontSize: 11, fontWeight: 700, color: '#f59e0b', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.25)', borderRadius: 20, padding: '2px 10px' }}>DRY RUN</span>}
        <div style={{ fontSize: 12, fontWeight: 700, color: statusColor }}>{status.replace(/_/g, ' ').toUpperCase()}</div>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#93c5fd' }}>{pct}%</div>
      </div>
      <div style={s.progBar()}>
        <div style={s.progFill(pct, statusColor)} />
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-lo)', marginTop: 6, marginBottom: 16 }}>{progress.message}</div>
      {depOrder.map(objName => {
        const r = objResults[objName] || { status: 'waiting', queried: 0, inserted: 0, updated: 0, failed: 0, skipped_dry_run: 0, error_categories: {} }
        const isDryRun = r.skipped_dry_run > 0
        const cats = r.error_categories || {}
        const catEntries = Object.entries(cats).sort((a, b) => b[1] - a[1])
        return (
          <div key={objName} style={{ ...s.objStatus(r.status), flexDirection: 'column', alignItems: 'stretch', padding: '10px 12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {r.status === 'running' ? <span style={{ fontSize: 14 }}>⟳</span> : <div style={s.statusDot(r.status)} />}
              <span style={{ fontSize: 13, fontWeight: 600, color: STATUS_COLOR[r.status]?.text || 'var(--text)', flex: 1 }}>{objName}</span>
              {isDryRun && (
                <span style={{ fontSize: 11, fontWeight: 700, color: '#f59e0b', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.25)', borderRadius: 20, padding: '1px 8px' }}>
                  ~{r.skipped_dry_run.toLocaleString()} would write
                </span>
              )}
              {!isDryRun && r.queried > 0 && (
                <span style={{ fontSize: 11, color: 'var(--text-lo)', display: 'flex', gap: 10 }}>
                  <span>{r.queried.toLocaleString()} queried</span>
                  {r.inserted > 0 && <span style={{ color: '#86efac' }}>+{r.inserted.toLocaleString()}</span>}
                  {r.updated  > 0 && <span style={{ color: '#93c5fd' }}>↻{r.updated.toLocaleString()}</span>}
                  {r.failed   > 0 && <span style={{ color: '#fca5a5' }}>✕{r.failed.toLocaleString()}</span>}
                </span>
              )}
            </div>
            {r.error && (
              <div style={{ fontSize: 11, color: '#fca5a5', marginTop: 6, paddingLeft: 16, wordBreak: 'break-word', lineHeight: 1.5 }}>
                {r.error}
              </div>
            )}
            {catEntries.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6, paddingLeft: 16 }}>
                {catEntries.map(([code, count]) => (
                  <span key={code} style={{ fontSize: 10, fontWeight: 600, color: '#fbbf24', background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.2)', borderRadius: 4, padding: '1px 6px' }}>
                    {code}: {count}
                  </span>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─── Summary Panel ────────────────────────────────────────────────────────────
function SummaryPanel({ result, onRollback, rollingBack, jobId, logPath }) {
  if (!result) return null
  const isSuccess = result.status === 'completed'
  const rollbackRemaining = result.rollback_remaining || 0
  return (
    <div style={{ ...s.section, border: `1px solid ${isSuccess ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}` }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-mid)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 16 }}>
        {isSuccess ? '✅ Migration Complete' : result.status === 'rolled_back' ? '↩ Rolled Back' : result.status === 'stopped' ? '⏹ Migration Stopped' : '❌ Migration Failed'}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 12, marginBottom: 16 }}>
        {[
          ['Records Queried', result.total_queried, 'var(--text)'],
          ['Inserted',        result.total_inserted, '#86efac'],
          ['Updated',         result.total_updated,  '#93c5fd'],
          ['Failed',          result.total_failed,   '#fca5a5'],
        ].map(([label, val, color]) => (
          <div key={label} style={{ background: 'var(--surface-hi)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
            <div style={{ fontSize: 26, fontWeight: 800, color, lineHeight: 1 }}>{(val || 0).toLocaleString()}</div>
            <div style={{ fontSize: 11, color: 'var(--text-lo)', marginTop: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
          </div>
        ))}
      </div>
      {result.error && <div style={s.err}>{result.error}</div>}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {['completed', 'failed', 'stopped'].includes(result.status) && rollbackRemaining > 0 && (
          <button onClick={onRollback} disabled={rollingBack}
            style={{ ...s.btn('danger'), opacity: rollingBack ? 0.5 : 1, cursor: rollingBack ? 'not-allowed' : 'pointer' }}>
            {rollingBack ? 'Rolling back…' : `↩ Rollback (delete ${rollbackRemaining.toLocaleString()} remaining records)`}
          </button>
        )}
        {jobId && (
          <a href={`/migrate/log/${jobId}`} download
            style={{ display: 'inline-block', padding: '9px 18px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-mid)', fontSize: 13, fontWeight: 600, textDecoration: 'none' }}>
            ⬇ Download Log
          </a>
        )}
      </div>
      {(result.total_updated || 0) > 0 && (
        <div style={{ color: 'var(--text-mid)', fontSize: 12, marginTop: 10 }}>
          Rollback only deletes newly inserted records; updates to existing records are not restored.
        </div>
      )}
    </div>
  )
}

// ─── Live Log Panel ───────────────────────────────────────────────────────────
// ─── Activity feed helpers ────────────────────────────────────────────────────
function _classifyLine(line) {
  if (!line || !line.trim()) return 'blank'
  const l = line.trim()
  if (l.includes('❌') || l.includes('⛔') || (l.toUpperCase().includes('FAILED') && !l.startsWith('    →'))) return 'error'
  if (l.includes('✅') || l.includes('🎉') || l.toUpperCase().includes('COMPLETE')) return 'success'
  if (l.includes('⚠️')) return 'warn'
  if (l.startsWith('---===') || l.startsWith('===') || /^[-=]+$/.test(l)) {
    const stripped = l.replace(/^[-=\s]+|[-=\s]+$/g, '').trim()
    return stripped ? 'section' : 'divider'
  }
  if (l.startsWith('== ') || l.toUpperCase().includes('STARTING MIGRATION')) return 'banner'
  if (l.includes('📥') || l.includes('🔍')) return 'fetch'
  if (l.includes('📦')) return 'batch'
  if (l.includes('⚙️')) return 'write'
  if (l.startsWith('    →') || l.includes('→ Job') || l.includes('state=')) return 'poll'
  if (/^\s*(Job ID|Source|Target|Mode|Objects)\b/.test(l)) return 'meta'
  if (l.startsWith('---') || l.startsWith('---------')) {
    const stripped = l.replace(/^[-\s]+|[-\s]+$/g, '').trim()
    return stripped ? 'section' : 'divider'
  }
  return 'log'
}

const _BADGE_CFG = {
  error:   { label: 'ERR',   bg: ['#7f1d1d','#fca5a5'], row: 'rgba(239,68,68,0.06)',  border: 'rgba(239,68,68,0.18)',  text: '#fca5a5' },
  success: { label: 'OK',    bg: ['#14532d','#86efac'], row: 'rgba(34,197,94,0.06)',  border: 'rgba(34,197,94,0.15)',  text: '#86efac' },
  warn:    { label: 'WARN',  bg: ['#713f12','#fde68a'], row: 'rgba(234,179,8,0.05)',  border: 'rgba(234,179,8,0.15)',  text: '#fde68a' },
  section: { label: 'OBJ',   bg: ['#1e3a5f','#93c5fd'], row: 'rgba(59,130,246,0.05)', border: 'rgba(59,130,246,0.18)', text: '#e2e8f0' },
  banner:  { label: 'START', bg: ['#2e1065','#a5b4fc'], row: 'rgba(99,102,241,0.06)', border: 'rgba(99,102,241,0.18)', text: '#e2e8f0' },
  fetch:   { label: 'FETCH', bg: ['#0c4a6e','#67e8f9'], row: 'rgba(6,182,212,0.04)',  border: 'rgba(6,182,212,0.12)',  text: '#67e8f9' },
  batch:   { label: 'BATCH', bg: ['#3b0764','#c4b5fd'], row: 'rgba(168,85,247,0.04)', border: 'rgba(168,85,247,0.12)', text: '#c4b5fd' },
  write:   { label: 'WRITE', bg: ['#451a03','#fbbf24'], row: 'rgba(251,191,36,0.04)', border: 'rgba(251,191,36,0.1)',  text: '#fbbf24' },
  poll:    { label: 'POLL',  bg: ['#1e293b','#475569'], row: 'transparent',           border: 'transparent',           text: '#475569' },
  meta:    { label: 'INFO',  bg: ['#1e293b','#64748b'], row: 'transparent',           border: 'transparent',           text: '#64748b' },
  divider: { label: null,    bg: null,                  row: 'transparent',           border: 'transparent',           text: '#334155' },
  log:     { label: 'LOG',   bg: ['#1e293b','#64748b'], row: 'transparent',           border: 'transparent',           text: '#94a3b8' },
}

function ActivityRow({ line, kind }) {
  const c = _BADGE_CFG[kind] || _BADGE_CFG.log
  if (kind === 'divider') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '10px 4px' }}>
        <div style={{ flex: 1, height: 1, background: 'linear-gradient(to right, transparent, rgba(99,102,241,0.35))' }} />
        <div style={{ width: 6, height: 6, borderRadius: 1, background: 'rgba(99,102,241,0.5)', transform: 'rotate(45deg)', flexShrink: 0 }} />
        <div style={{ flex: 1, height: 1, background: 'linear-gradient(to left, transparent, rgba(99,102,241,0.35))' }} />
      </div>
    )
  }
  const display = (kind === 'section' || kind === 'banner')
    ? line.trim().replace(/^[-=\s]+|[-=\s]+$/g, '').trim() || line.trim()
    : line.trim()
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, padding: '5px 10px', background: c.row, border: `1px solid ${c.border}`, borderRadius: 6 }}>
      {c.bg && (
        <span style={{ fontSize: 9, fontWeight: 800, padding: '2px 5px', borderRadius: 3, background: c.bg[0], color: c.bg[1], flexShrink: 0, letterSpacing: '0.07em', fontFamily: 'ui-monospace,monospace', lineHeight: 1.6 }}>
          {c.label}
        </span>
      )}
      <span style={{ fontSize: 12, color: c.text, lineHeight: 1.55, wordBreak: 'break-word', fontFamily: '"SF Mono","Fira Code",ui-monospace,monospace', flex: 1, fontWeight: (kind === 'section' || kind === 'banner') ? 700 : 400 }}>
        {display}
      </span>
    </div>
  )
}

function JobMonitorPanel({ lines, jobId, migrating }) {
  const bottomRef  = React.useRef(null)
  const scrollRef  = React.useRef(null)
  const [autoScroll, setAutoScroll] = React.useState(true)
  const [showPoll,   setShowPoll]   = React.useState(false)
  const [stopping,   setStopping]   = React.useState(false)

  async function handleStop() {
    if (!jobId || stopping) return
    setStopping(true)
    try {
      await fetch(`/migrate/stop/${jobId}`, { method: 'POST', credentials: 'include' })
    } catch (_) {}
  }

  React.useEffect(() => {
    if (autoScroll && bottomRef.current) bottomRef.current.scrollIntoView({ behavior: 'smooth' })
  }, [lines, autoScroll])

  if (!lines || lines.length === 0) {
    if (!migrating) return null
    return (
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 14, padding: '20px', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 9, height: 9, borderRadius: '50%', background: '#06b6d4', boxShadow: '0 0 7px rgba(6,182,212,0.7)', flexShrink: 0 }} />
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', flex: 1 }}>Migration Activity</span>
          <span style={{ fontSize: 12, color: 'var(--text-lo)' }}>Waiting for first log entry…</span>
        </div>
      </div>
    )
  }

  const classified = lines.map(l => ({ line: l, kind: _classifyLine(l) }))
  const pollCount  = classified.filter(x => x.kind === 'poll').length
  const eventCount = classified.filter(x => x.kind !== 'blank' && x.kind !== 'divider').length

  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 14, padding: '20px', marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <div style={{ width: 9, height: 9, borderRadius: '50%', background: '#06b6d4', boxShadow: '0 0 7px rgba(6,182,212,0.7)', flexShrink: 0 }} />
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', flex: 1 }}>Migration Activity</span>
        <span style={{ fontSize: 11, color: 'var(--text-lo)', background: 'var(--surface-hi)', padding: '2px 8px', borderRadius: 10, border: '1px solid var(--border)' }}>
          {eventCount} events
        </span>
        {pollCount > 0 && (
          <button onClick={() => setShowPoll(v => !v)}
            style={{ fontSize: 11, padding: '3px 9px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-lo)', cursor: 'pointer' }}>
            {showPoll ? 'Hide' : 'Show'} polling ({pollCount})
          </button>
        )}
        <button onClick={() => setAutoScroll(v => !v)}
          style={{ fontSize: 11, padding: '3px 9px', background: autoScroll ? 'rgba(6,182,212,0.1)' : 'transparent', border: `1px solid ${autoScroll ? 'rgba(6,182,212,0.3)' : 'var(--border)'}`, borderRadius: 6, color: autoScroll ? '#67e8f9' : 'var(--text-lo)', cursor: 'pointer' }}>
          {autoScroll ? '↓ Live' : '↓ Paused'}
        </button>
        {migrating && (
          <button onClick={handleStop} disabled={stopping}
            style={{ fontSize: 11, padding: '3px 10px', background: stopping ? 'rgba(239,68,68,0.05)' : 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.35)', borderRadius: 6, color: stopping ? 'rgba(252,165,165,0.5)' : '#fca5a5', cursor: stopping ? 'not-allowed' : 'pointer', fontWeight: 600 }}>
            {stopping ? '⏳ Stopping…' : '⏹ Stop'}
          </button>
        )}
      </div>
      <div ref={scrollRef}
        style={{ display: 'flex', flexDirection: 'column', gap: 3, maxHeight: 500, overflowY: 'auto', paddingRight: 2 }}
        onScroll={e => {
          const el = e.currentTarget
          setAutoScroll(el.scrollHeight - el.scrollTop - el.clientHeight < 60)
        }}>
        {classified.map(({ line, kind }, i) => {
          if (kind === 'blank') return <div key={i} style={{ height: 4 }} />
          if (kind === 'poll' && !showPoll) return null
          return <ActivityRow key={i} line={line} kind={kind} />
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ─── Main page ───────────────────────────────────────────────────────────────
export default function MigratePage({ auth, onAuthChange }) {
  const [groups, setGroups]       = useState([])
  const [loading, setLoading]     = useState(false)
  const [loadErr, setLoadErr]     = useState('')
  const [selected, setSelected]   = useState(new Set())

  const [savedTargetOrgs, setSavedTargetOrgs] = useState(() => {
    try { return JSON.parse(localStorage.getItem('sf-target-orgs') || '[]') } catch { return [] }
  })
  const [selectedTargetIdx, setSelectedTargetIdx] = useState(-1)
  const [targetOrg, setTargetOrg]   = useState(null)
  const [showSourceModal, setShowSourceModal] = useState(false)
  const [showTargetModal, setShowTargetModal] = useState(false)
  const [targetModalDefaultTab, setTargetModalDefaultTab] = useState('credentials')
  const pendingAliasRef = useRef('')

  const [selectedBundle, setSelectedBundle] = useState('')
  const [filters, setFilters]       = useState({})
  const [recordSelections, setRecordSelections] = useState({})
  const [pickerOpen, setPickerOpen] = useState(false)
  const [scope, setScope] = useState(null)
  const [scopeLoading, setScopeLoading] = useState(false)
  const [scopeError, setScopeError] = useState('')
  const scopeRequestRef = useRef(null)
  const scopeSuppressedRef = useRef(false)

  const [mode, setMode]             = useState('upsert')
  const [depOrder, setDepOrder]     = useState([])
  const [dryRun, setDryRun]         = useState(false)
  const [failurePct, setFailurePct] = useState(0)

  const [migrating, setMigrating]   = useState(false)
  const [jobId, setJobId]           = useState(null)
  const [progress, setProgress]     = useState(null)
  const [result, setResult]         = useState(null)
  const [startErr, setStartErr]     = useState('')
  const [rollingBack, setRollingBack] = useState(false)
  const [liveLog, setLiveLog]       = useState([])   // kept for SummaryPanel compat
  const [terminalLines, setTerminalLines] = useState([])

  const esRef = useRef(null)
  const prevProductKeyRef = useRef(null)

  const loadGroups = useCallback(async () => {
    if (!auth) return
    setLoading(true); setLoadErr('')
    try {
      const res = await fetch('/migrate/describe', { credentials: 'include' })
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || `HTTP ${res.status}`) }
      const data = await res.json()
      setGroups(data.groups)
    } catch (e) { setLoadErr(e.message) }
    finally { setLoading(false) }
  }, [auth])

  useEffect(() => { loadGroups() }, [loadGroups])

  useEffect(() => {
    if (selected.size === 0) { setDepOrder([]); return }
    fetch('/migrate/dependency-order', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
      body: JSON.stringify({ selected_objects: [...selected] }),
    }).then(r => r.json()).then(d => setDepOrder(d.order || [])).catch(() => setDepOrder([...selected]))
  }, [selected])

  const productBundle = PRODUCT_BUNDLES.has(selectedBundle)
  const productIds = (recordSelections.Product2 || []).map(r => r.id).sort()
  const productKey = `${selectedBundle}:${productIds.join(',')}`
  const partialProductPlan = !selectedBundle && selected.has('Product2') &&
    ((productIds.length > 0 && selected.size > 1) || !!(filters.Product2 || '').trim())

  // Reset migration state when product selection changes between runs
  useEffect(() => {
    if (prevProductKeyRef.current === null) { prevProductKeyRef.current = productKey; return }
    if (productKey === prevProductKeyRef.current) return
    prevProductKeyRef.current = productKey
    if (!migrating) {
      setProgress(null); setResult(null); setLiveLog([]); setTerminalLines([]); setJobId(null); setStartErr('')
    }
  }, [productKey]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (scopeRequestRef.current) scopeRequestRef.current.abort()
    setScope(null)
    setScopeError('')
    setScopeLoading(false)
    if (!productBundle || productIds.length === 0) return
    scopeSuppressedRef.current = false
    const controller = new AbortController()
    scopeRequestRef.current = controller
    setScopeLoading(true)
    fetch('/migrate/scope-filters', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
      body: JSON.stringify({ product_ids: productIds }), signal: controller.signal,
    })
      .then(async res => {
        const d = await res.json()
        if (!res.ok) throw new Error(d.detail || `Scope discovery failed (HTTP ${res.status})`)
        return d
      })
      .then(d => {
        if (controller.signal.aborted || scopeSuppressedRef.current) return
        const bundleNames = new Set(groups.find(g => g.key === selectedBundle)?.objects.filter(o => o.available).map(o => o.name) || [])
        if (!d.filters || typeof d.filters !== 'object' || !d.filters.Product2 || !bundleNames.has('Product2') ||
            Object.keys(d.filters).some(name => !bundleNames.has(name) || typeof d.filters[name] !== 'string' || !d.filters[name].trim()) ||
            !Number.isInteger(d.product_count) || d.product_count < productIds.length) {
          throw new Error('Incomplete product scope response; migration is blocked.')
        }
        setScope({ key: productKey, filters: d.filters, productCount: d.product_count })
        setSelected(new Set(Object.keys(d.filters)))
      })
      .catch(e => { if (!controller.signal.aborted) setScopeError(e.message || 'Product scope discovery failed') })
      .finally(() => { if (!controller.signal.aborted) setScopeLoading(false) })
    return () => controller.abort()
  }, [selectedBundle, productKey, groups])

  function startStream(jid) {
    if (esRef.current) esRef.current.close()
    const es = new EventSource(`/migrate/stream/${jid}`)
    esRef.current = es
    es.onmessage = (e) => {
      const data = JSON.parse(e.data)
      // Accumulate terminal log lines
      const newLines = data.log_lines_delta || []
      if (newLines.length > 0) {
        setTerminalLines(prev => [...prev, ...newLines].slice(-3000))
      }
      // Keep simple liveLog for legacy SummaryPanel/compat
      setLiveLog(prev => {
        const entry = { ts: new Date().toISOString(), pct: data.progress_pct, msg: data.message, obj: data.current_object, status: data.status }
        return [entry, ...prev].slice(0, 50)
      })
      setProgress(data)
      if (['completed', 'failed', 'rolled_back', 'stopped'].includes(data.status)) {
         es.close(); esRef.current = null; setMigrating(false); setRollingBack(false)
        fetch(`/migrate/result/${jid}`, { credentials: 'include' })
          .then(r => r.json()).then(setResult).catch(() => {})
      }
    }
     // EventSource reconnects automatically; a transport error is not a terminal job status.
  }

  useEffect(() => () => { if (esRef.current) esRef.current.close() }, [])

  function toggleObject(name) {
    setSelected(prev => { const n = new Set(prev); n.has(name) ? n.delete(name) : n.add(name); return n })
  }
  function toggleGroup(grp) {
    const avail = grp.objects.filter(o => o.available).map(o => o.name)
    const allOn = avail.every(n => selected.has(n))
    setSelected(prev => { const n = new Set(prev); allOn ? avail.forEach(v => n.delete(v)) : avail.forEach(v => n.add(v)); return n })
  }

  async function openPlatformLogin(mode, loginUrl, alias) {
    pendingAliasRef.current = alias || ''
    setStartErr('')
    try {
      const params = new URLSearchParams({ popup: mode })
      if (loginUrl) params.set('login_url', loginUrl)
      const res = await fetch(`/auth/platform-login?${params}`, { credentials: 'include' })
      if (!res.ok) throw new Error('Failed to start authorization')
      const { auth_url, job_id } = await res.json()

      const win = window.open(auth_url, '_blank')
      if (!win) { setStartErr('Could not open new tab. Allow popups for this site.'); return }

      const pollRef = { id: null }
      pollRef.id = setInterval(async () => {
        try {
          const r = await fetch(`/auth/platform-status/${job_id}`, { credentials: 'include' })
          if (!r.ok) return
          const data = await r.json()
          if (data.status === 'pending') return

          clearInterval(pollRef.id)
          if (data.status === 'error') {
            setStartErr(`Authorization failed: ${data.error}`)
            return
          }
          // status === 'done'
          if (mode === 'target') {
            handleTargetAuthorized({ access_token: data.access_token, instance_url: data.instance_url, org_name: '', alias: pendingAliasRef.current })
          } else {
            const me = await fetch('/auth/me', { credentials: 'include' })
            if (me.ok) {
              const d = await me.json()
              if (d.authenticated && onAuthChange) onAuthChange({ ...d, authenticated: true })
            }
          }
        } catch {}
      }, 1000)

      setTimeout(() => clearInterval(pollRef.id), 300_000)
    } catch (e) {
      setStartErr(`Failed to start authorization: ${e.message}`)
    }
  }


  function handleSourceAuthorized(data) {
    if (onAuthChange) onAuthChange({ ...data, authenticated: true })
    setShowSourceModal(false)
  }

  function handleTargetAuthorized(org) {
    const entry = { instance_url: org.instance_url, org_name: org.org_name || '', alias: org.alias || org.org_name || '', access_token: org.access_token }
    const current = (() => { try { return JSON.parse(localStorage.getItem('sf-target-orgs') || '[]') } catch { return [] } })()
    const persisted = [entry, ...current.filter(o => o.instance_url !== org.instance_url)]
    localStorage.setItem('sf-target-orgs', JSON.stringify(persisted))
    setSavedTargetOrgs(persisted)
    setSelectedTargetIdx(0)
    setTargetOrg(entry)
    setShowTargetModal(false)
  }

  async function handleTargetCredentials(username, password, loginUrl, alias) {
    const domain = loginUrl.replace('https://', '').replace(/\/$/, '') || 'login.salesforce.com'
    const res = await fetch('/migrate/validate-target', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
      body: JSON.stringify({ username, password, domain }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Authentication failed')
    handleTargetAuthorized({ access_token: data.access_token, instance_url: data.instance_url, org_name: data.org_name || '', alias })
  }

  async function handleSourceCredentials(username, password, loginUrl, alias) {
    const domain = loginUrl.replace('https://', '').replace(/\/$/, '') || 'login.salesforce.com'
    const res = await fetch('/auth/login-password', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
      body: JSON.stringify({ username, password, domain, alias }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Authentication failed')
    setShowSourceModal(false)
    const me = await fetch('/auth/me', { credentials: 'include' })
    if (me.ok) {
      const d = await me.json()
      if (d.authenticated && onAuthChange) onAuthChange({ ...d, authenticated: true })
    }
  }

  function handleTargetSelect(idx) {
    setSelectedTargetIdx(idx)
    setTargetOrg(idx >= 0 ? savedTargetOrgs[idx] : null)
  }

  function removeTargetOrg(idx, e) {
    e.stopPropagation()
    const updated = savedTargetOrgs.filter((_, i) => i !== idx)
    localStorage.setItem('sf-target-orgs', JSON.stringify(updated))
    setSavedTargetOrgs(updated)
    if (selectedTargetIdx === idx) { setSelectedTargetIdx(-1); setTargetOrg(null) }
    else if (selectedTargetIdx > idx) setSelectedTargetIdx(i => i - 1)
  }

  async function handleStartMigration() {
    if (!targetOrg || selected.size === 0 || migrating) return
    if (selectedBundle && (!productBundle || !scopeReady)) return
    if (partialProductPlan) {
      setStartErr('A filtered Product2 with other objects requires a product bundle. Use Revenue Product Bundle to compute a safe scope.')
      return
    }
    const productRecordOnly = !selectedBundle && selected.size === 1 && selected.has('Product2') &&
      (recordSelections.Product2 || []).length > 0 && !(filters.Product2 || '').trim()
    if (productRecordOnly && (productIds.length > 150 || productIds.some(id => typeof id !== 'string' || !/^[a-zA-Z0-9]{15}(?:[a-zA-Z0-9]{3})?$/.test(id)))) {
      setStartErr('Select valid Product2 record IDs (up to 150).')
      return
    }

    setStartErr(''); setResult(null); setProgress(null); setLiveLog([]); setTerminalLines([]); setMigrating(true)
    try {
      const res = await fetch('/migrate/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
        body: JSON.stringify({
          target_access_token: targetOrg.access_token,
          target_instance_url: targetOrg.instance_url,
          selected_objects: [...selected],
          mode,
          dry_run: dryRun,
          failure_threshold_pct: failurePct,
          ...(productBundle || productRecordOnly ? { product_ids: productIds } : { object_filters: Object.fromEntries(
              [...selected].flatMap(k => {
                const recs = recordSelections[k] || []
                if (recs.length > 0) {
                  const ids = recs.map(r => `'${r.id}'`).join(',')
                  return [[k, `Id IN (${ids})`]]
                }
                const manual = (filters[k] || '').trim()
                if (manual) return [[k, manual]]
                return []
              })
            ) }),
        }),
      })
      const d = await res.json()
      if (!res.ok) throw new Error(d.detail || 'Failed to start')
      setJobId(d.job_id)
      setDepOrder(d.dep_order)
      startStream(d.job_id)
    } catch (e) { setStartErr(e.message); setMigrating(false) }
  }

  async function handleRollback() {
    if (!jobId || !targetOrg) return
    setRollingBack(true)
    try {
      const res = await fetch(`/migrate/rollback/${jobId}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
        body: JSON.stringify({ target_access_token: targetOrg.access_token, target_instance_url: targetOrg.instance_url }),
      })
      const d = await res.json()
      if (!res.ok) throw new Error(d.detail || 'Rollback failed')
      setMigrating(true)
      startStream(jobId)
    } catch (e) { setStartErr(e.message); setRollingBack(false) }
  }

  if (!auth) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)', flexDirection: 'column', gap: 12 }}>
      <div style={{ fontSize: 36 }}>🔌</div>
      <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-mid)' }}>No Salesforce org connected</div>
      <div style={{ color: 'var(--text-lo)', fontSize: 13 }}>Connect your source org in Settings first.</div>
    </div>
  )

  const totalSelected = selected.size
  const totalRecords = groups.flatMap(g => g.objects).filter(o => selected.has(o.name)).reduce((sum, o) => sum + (o.count || 0), 0)
  const isBusy = migrating || rollingBack
  const scopeReady = productBundle && !scopeLoading && !scopeError && productIds.length > 0 && scope?.key === productKey &&
    selected.has('Product2') && selected.size === Object.keys(scope.filters).length &&
    [...selected].every(name => typeof scope.filters[name] === 'string' && scope.filters[name].trim())
  const cannotStart = !targetOrg || totalSelected === 0 || isBusy || partialProductPlan || (selectedBundle && (!productBundle || !scopeReady))
  const allObjs = groups.flatMap(g => g.objects)
  const availObjs = allObjs.filter(o => o.available)
  const unselectedObjs = availObjs.filter(o => !selected.has(o.name))

  function handleBundleSelect(e) {
    setSelectedBundle(e.target.value)
    setRecordSelections({})
    setFilters({})
    setScope(null)
    setSelected(new Set())
    if (PRODUCT_BUNDLES.has(e.target.value)) setMode('insert')
  }

  function useProductBundle() {
    if (isBusy) return
    setSelectedBundle('revenue_product_bundle')
    setSelected(new Set(['Product2']))
    setRecordSelections({ Product2: recordSelections.Product2 || [] })
    setFilters({})
    setScope(null)
    setMode('insert')
    setStartErr('')
  }

  function clearSelection() {
    scopeSuppressedRef.current = true
    if (scopeRequestRef.current) scopeRequestRef.current.abort()
    setSelected(new Set())
    setRecordSelections({})
    setFilters({})
    setScope(null)
  }

  return (
    <div style={s.page}>
      <div style={s.inner}>

        {/* ── PAGE HEADER ── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginBottom: 28 }}>
          <div style={{ width: 56, height: 56, borderRadius: 14, background: 'linear-gradient(135deg,#1e40af,#3b82f6)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, boxShadow: '0 8px 24px rgba(59,130,246,0.3)' }}>
            <DbIcon size={28} color="white" />
          </div>
          <div style={{ flex: 1 }}>
            <h1 style={{ fontSize: 26, fontWeight: 800, color: 'var(--text)', margin: 0, lineHeight: 1.2 }}>Data Migration</h1>
            <p style={{ fontSize: 13, color: 'var(--text-lo)', margin: '3px 0 0' }}>Migrate Salesforce data between orgs — Revenue Cloud, OmniStudio, CML, and standard objects</p>
          </div>
          <div style={{ display: 'flex', gap: 10, flexShrink: 0 }}>
            <button style={{ padding: '9px 18px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-mid)', fontSize: 13, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 14 }}>🕐</span> Migration History
            </button>
            <button style={{ padding: '9px 18px', background: 'linear-gradient(135deg,#1e40af,#3b82f6)', border: 'none', borderRadius: 8, color: 'white', fontSize: 13, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, boxShadow: '0 4px 12px rgba(59,130,246,0.35)' }}>
              <span style={{ fontSize: 15 }}>＋</span> New Migration
            </button>
          </div>
        </div>

        {/* Modals */}
        {showSourceModal && (
          <OrgAuthModal
            title="Authorize Source Org"
            requireAlias={false}
            onClose={() => setShowSourceModal(false)}
            onAuthorize={(loginUrl, alias) => { setShowSourceModal(false); openPlatformLogin('source', loginUrl, alias) }}
            onCredentials={handleSourceCredentials}
          />
        )}
        {showTargetModal && (
          <OrgAuthModal
            title="Authorize Target Org"
            requireAlias
            defaultTab={targetModalDefaultTab}
            onClose={() => { setShowTargetModal(false); setTargetModalDefaultTab('credentials') }}
            onAuthorize={(loginUrl, alias) => { setShowTargetModal(false); openPlatformLogin('target', loginUrl, alias) }}
            onCredentials={handleTargetCredentials}
          />
        )}
        {pickerOpen && (!selectedBundle || productBundle) && (() => {
          const bundleGrp = selectedBundle ? groups.find(g => g.key === selectedBundle) : null
          const pickerObjects = bundleGrp
            ? bundleGrp.objects.filter(o => o.available && o.name === 'Product2')
            : groups.flatMap(g => g.objects).filter(o => o.available)
          const fixedObj = selectedBundle ? 'Product2' : ''
          const fallbackObj = pickerObjects[0]?.name || ''
          return (
            <RecordPickerModal
              availableObjects={pickerObjects}
              initialObjectName={fixedObj || fallbackObj}
              fixedObject={fixedObj || undefined}
              recordSelections={recordSelections}
              onClose={() => setPickerOpen(false)}
              onConfirm={(objName, recs) => {
                 if (bundleGrp) {
                   setSelected(new Set(recs.length > 0 ? ['Product2'] : []))
                 } else {
                   setSelected(prev => { const n = new Set(prev); if (recs.length) n.add(objName); else n.delete(objName); return n })
                   if (objName === 'Product2' && recs.length) {
                     setFilters(prev => ({ ...prev, Product2: '' }))
                   }
                 }
                 setRecordSelections(prev => ({ ...prev, [objName]: recs }))
                setPickerOpen(false)
              }}
            />
          )
        })()}

        {/* ── ORG CONNECTIONS ── */}
        <div style={s.section}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 20 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-mid)" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>
            <span style={s.sectionTitle}>Org Connections</span>
          </div>
          <div style={{ display: 'flex', gap: 20, alignItems: 'stretch', flexWrap: 'wrap' }}>

            {/* Source Org Card */}
            <div style={{ flex: 1, minWidth: 240, background: auth ? 'rgba(34,197,94,0.04)' : 'var(--surface-hi)', border: `1px solid ${auth ? 'rgba(34,197,94,0.2)' : 'var(--border)'}`, borderRadius: 12, padding: '18px 20px' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-lo)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12 }}>Source Org</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
                <div style={{ width: 42, height: 42, borderRadius: '50%', background: 'linear-gradient(135deg,#1e40af,#3b82f6)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <SfCloudIcon size={20} color="white" />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)', marginBottom: 2 }}>
                    {auth?.alias || 'Connected Org'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-lo)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {auth?.instance_url || '—'}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <div style={{ flex: 1, padding: '8px 12px', background: 'var(--input-bg)', border: '1px solid var(--input-border)', borderRadius: 7, color: 'var(--input-color)', fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 7, height: 7, borderRadius: '50%', background: auth ? '#22c55e' : 'var(--border-hi)', flexShrink: 0 }} />
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: auth ? 'var(--input-color)' : 'var(--text-lo)' }}>
                    {auth ? (auth.alias || auth.instance_url) : 'Not connected'}
                  </span>
                </div>
                <button style={s.btn('primary')} onClick={() => setShowSourceModal(true)} disabled={isBusy}>Authorize</button>
              </div>
            </div>

            {/* Arrow */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, padding: '0 4px' }}>
              <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--surface-hi)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-mid)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
              </div>
            </div>

            {/* Target Org Card */}
            <div style={{ flex: 1, minWidth: 240, background: targetOrg ? 'rgba(34,197,94,0.04)' : 'var(--surface-hi)', border: `1px solid ${targetOrg ? 'rgba(34,197,94,0.2)' : 'var(--border)'}`, borderRadius: 12, padding: '18px 20px' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-lo)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12 }}>Target Org</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
                <div style={{ width: 42, height: 42, borderRadius: '50%', background: targetOrg ? 'linear-gradient(135deg,#065f46,#22c55e)' : 'var(--surface)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <SfCloudIcon size={20} color={targetOrg ? 'white' : 'var(--text-lo)'} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)', marginBottom: 2 }}>
                    {targetOrg ? (targetOrg.alias || 'Target Org') : 'No org selected'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-lo)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {targetOrg?.instance_url || 'Select or authorize a target org'}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <select
                  style={{ flex: 1, padding: '8px 12px', background: 'var(--input-bg)', border: `1px solid ${targetOrg ? 'rgba(34,197,94,0.4)' : 'var(--input-border)'}`, borderRadius: 7, color: savedTargetOrgs.length ? 'var(--input-color)' : 'var(--text-lo)', fontSize: 12, cursor: 'pointer', outline: 'none' }}
                  value={selectedTargetIdx}
                  onChange={e => handleTargetSelect(Number(e.target.value))}
                  disabled={isBusy}
                >
                  <option value={-1}>Select an org…</option>
                  {savedTargetOrgs.map((org, i) => (
                    <option key={org.instance_url} value={i}>{org.alias || org.org_name || org.instance_url}</option>
                  ))}
                </select>
                <button style={s.btn('primary')} onClick={() => setShowTargetModal(true)} disabled={isBusy}>Authorize</button>
              </div>
            </div>
          </div>
        </div>

        {/* ── MIGRATION MODE ── */}
        <div style={s.section}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 16 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-mid)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 010 14.14M4.93 4.93a10 10 0 000 14.14"/>
            </svg>
            <span style={s.sectionTitle}>Migration Mode</span>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            {[
              ['upsert', '↻', 'Upsert', 'Insert new + update existing by key field'],
              ['insert', '+', 'Insert Only', 'Create new records; existing records are not skipped'],
            ].map(([val, icon, label, desc]) => {
              const isSelected = mode === val
              return (
                <button key={val} onClick={() => !isBusy && setMode(val)} style={{
                  flex: 1, padding: '16px 18px', borderRadius: 10, cursor: isBusy ? 'not-allowed' : 'pointer',
                  background: isSelected ? 'rgba(59,130,246,0.12)' : 'var(--surface-hi)',
                  border: `1.5px solid ${isSelected ? '#3b82f6' : 'var(--border)'}`,
                  textAlign: 'left', opacity: isBusy ? 0.5 : 1, position: 'relative',
                }}>
                  {isSelected && (
                    <div style={{ position: 'absolute', top: 12, right: 12, width: 20, height: 20, borderRadius: '50%', background: '#3b82f6', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="2,6 5,9 10,3"/>
                      </svg>
                    </div>
                  )}
                  <div style={{ fontSize: 22, marginBottom: 8, color: isSelected ? '#93c5fd' : 'var(--text-lo)' }}>{icon}</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: isSelected ? '#93c5fd' : 'var(--text)', marginBottom: 4 }}>{label}</div>
                  <div style={{ fontSize: 12, color: isSelected ? 'rgba(147,197,253,0.8)' : 'var(--text-lo)' }}>{desc}</div>
                </button>
              )
            })}
          </div>
        </div>

        {/* ── MIGRATION PLAN ── */}
        <div style={s.section}>
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 20 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-mid)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            <span style={{ ...s.sectionTitle, flex: 1 }}>Migration Plan</span>
            {totalSelected > 0 && (
              <div style={{ display: 'flex', gap: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#3b82f6', background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.25)', borderRadius: 20, padding: '2px 10px' }}>
                  📦 {totalSelected} object{totalSelected !== 1 ? 's' : ''}
                </span>
                {!selectedBundle && totalRecords > 0 && (
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#06b6d4', background: 'rgba(6,182,212,0.1)', border: '1px solid rgba(6,182,212,0.25)', borderRadius: 20, padding: '2px 10px' }}>
                    ~{totalRecords.toLocaleString()} records
                  </span>
                )}
              </div>
            )}
          </div>

          {loadErr && <div style={s.err}>{loadErr} <button onClick={loadGroups} style={{ background: 'none', border: 'none', color: '#3b82f6', cursor: 'pointer', fontSize: 12 }}>Retry</button></div>}
          {loading && <div style={{ color: 'var(--text-lo)', fontSize: 13, marginBottom: 12 }}>Probing org objects…</div>}

          {/* Controls row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
            {/* Bundle dropdown */}
            <div>
              <label style={s.label}>Migration Bundle</label>
              <div style={{ display: 'flex', alignItems: 'center', background: 'var(--input-bg)', border: '1px solid var(--input-border)', borderRadius: 7, overflow: 'hidden' }}>
                <div style={{ padding: '0 10px', color: 'var(--text-lo)', borderRight: '1px solid var(--input-border)', display: 'flex', alignItems: 'center', height: '100%' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>
                  </svg>
                </div>
                 <select value={selectedBundle} onChange={handleBundleSelect} disabled={isBusy || loading} aria-label="Migration Bundle"
                  style={{ flex: 1, padding: '9px 11px', background: 'transparent', border: 'none', color: selectedBundle ? 'var(--input-color)' : 'var(--text-lo)', fontSize: 13, cursor: 'pointer', outline: 'none', fontFamily: 'inherit' }}>
                  <option value="">Select a bundle…</option>
                  {groups.filter(g => g.available).map(grp => (
                    <option key={grp.key} value={grp.key}>{grp.icon} {grp.label}</option>
                  ))}
                </select>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-lo)', marginTop: 4 }}>Product bundles support record selection; choose no bundle to migrate individual objects.</div>
            </div>

            {/* Record search */}
            <div>
              <label style={s.label}>
                 {productBundle ? 'Select Product from Source Org' : 'Add Object from Source Org'}
              </label>
               {productBundle ? (() => {
                 const primaryRecs = recordSelections.Product2 || []
                const displayVal = primaryRecs.length > 0 ? primaryRecs.map(r => r.name).join(', ') : ''
                return (
                  <div style={{ display: 'flex', gap: 8 }}>
                    <div style={{ flex: 1, padding: '9px 12px', background: 'var(--input-bg)', border: `1px solid ${displayVal ? 'rgba(59,130,246,0.4)' : 'var(--input-border)'}`, borderRadius: 7, color: displayVal ? '#93c5fd' : 'var(--text-lo)', fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', userSelect: 'none' }}>
                      {displayVal || 'Click 🔍 to select a record…'}
                    </div>
                     <button onClick={() => !isBusy && setPickerOpen(true)} disabled={isBusy || loading} aria-label="Select Product2 records"
                      style={{ flexShrink: 0, padding: '0 12px', background: displayVal ? 'rgba(59,130,246,0.1)' : 'var(--surface-hi)', border: `1px solid ${displayVal ? 'rgba(59,130,246,0.3)' : 'var(--border)'}`, borderRadius: 7, color: '#93c5fd', cursor: 'pointer', fontSize: 16 }}>🔍</button>
                  </div>
                )
               })() : !selectedBundle ? (
                <div style={{ display: 'flex', gap: 8 }}>
                  <div style={{ flex: 1 }}>
                    <ObjectPicker
                      objects={unselectedObjs}
                       onSelect={name => { if (!isBusy) { setRecordSelections(prev => ({ ...prev, [name]: [] })); setSelected(prev => { const n = new Set(prev); n.add(name); return n }) } }}
                      disabled={isBusy || loading || unselectedObjs.length === 0}
                    />
                  </div>
                   <button onClick={() => !isBusy && setPickerOpen(true)} disabled={isBusy || loading || availObjs.length === 0} aria-label="Select records from source org"
                    style={{ flexShrink: 0, padding: '0 12px', background: 'var(--surface-hi)', border: '1px solid var(--border)', borderRadius: 7, color: '#93c5fd', cursor: 'pointer', fontSize: 16 }}>🔍</button>
                </div>
               ) : <div role="alert" style={s.warn}>Record selection for this bundle is unsupported. Choose no bundle to migrate individual objects.</div>}
               <div style={{ fontSize: 11, color: 'var(--text-lo)', marginTop: 4 }}>
                 {productBundle ? 'Select Product2 records; the server determines all related objects and filters.' : !selectedBundle ? 'Type to add an object, or click 🔍 to select specific records' : ''}
               </div>
               {productBundle && (
                 <div role={scopeError ? 'alert' : 'status'} style={{ marginTop: 8, ...(scopeError ? s.err : scopeReady ? s.ok : s.warn) }}>
                   {scopeError ? `Product scope failed: ${scopeError}` : scopeReady ? `Product scope ready — ${scope.productCount} products (including linked products), ${Object.keys(scope.filters).length} scoped objects. Server will recompute at start.` : scopeLoading ? 'Computing product scope… Start is disabled.' : productIds.length === 0 ? 'Select at least one Product2 record to compute a safe scope.' : 'Waiting for complete product scope… Start is disabled.'}
                 </div>
               )}
            </div>
          </div>

          {/* Object table */}
          {selected.size > 0 ? (
            <div>
              {partialProductPlan && (
                <div role="alert" style={s.warn}>
                  A Product2 filter cannot scope its related objects on its own. To migrate the product and its related records,{' '}
                  <button type="button" onClick={useProductBundle} disabled={isBusy} style={{ background: 'none', border: 'none', color: 'inherit', textDecoration: 'underline', cursor: isBusy ? 'not-allowed' : 'pointer', font: 'inherit', fontWeight: 700 }}>
                    Use Revenue Product Bundle
                  </button>. This replaces the manual object selection and switches to Insert Only; select Product2 records if needed and review the computed scope before starting.
                </div>
              )}
              {/* Column headers */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 80px 1fr 36px', gap: '0 12px', padding: '4px 12px 8px', borderBottom: '1px solid var(--border)', marginBottom: 6 }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-lo)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Object</div>
                 <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-lo)', textTransform: 'uppercase', letterSpacing: '0.07em', textAlign: 'right' }}>{productBundle ? 'Scope' : 'Records'}</div>
                 <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-lo)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>{productBundle ? 'Server-owned product scope' : 'WHERE / Record Filter'}</div>
                <div />
              </div>
              {[...selected].map(name => {
                const obj = allObjs.find(o => o.name === name) || { name, label: name, count: 0 }
                const recs = recordSelections[name] || []
                const hasRecordFilter = recs.length > 0
                const color = objColor(name)
                const initials = name.slice(0, 2).toUpperCase()
                return (
                  <div key={name} style={{ display: 'grid', gridTemplateColumns: '1fr 80px 1fr 36px', gap: '0 12px', alignItems: 'center', padding: '9px 12px', borderRadius: 8, marginBottom: 4, background: 'var(--surface-hi)', border: `1px solid ${hasRecordFilter ? 'rgba(59,130,246,0.3)' : 'var(--border)'}` }}>
                    {/* Object label with colored icon */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                      <div style={{ width: 28, height: 28, borderRadius: 8, background: color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <span style={{ fontSize: 9, fontWeight: 700, color: 'white', letterSpacing: '0.02em' }}>{initials}</span>
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>{obj.label !== obj.name ? obj.label : obj.name}</span>
                        {obj.label !== obj.name && <span style={{ fontSize: 11, color: 'var(--text-lo)', marginLeft: 5 }}>({obj.name})</span>}
                      </div>
                    </div>
                    {/* Record count */}
                    <div style={{ fontSize: 12, color: 'var(--text-lo)', textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
                        {productBundle ? (scopeReady && scope.filters[name] ? 'Scoped' : 'Pending') : obj.count > 0 ? obj.count.toLocaleString() : '—'}
                    </div>
                    {/* Filter or record selection display */}
                     {productBundle ? (
                        <div style={{ fontSize: 12, color: 'var(--text-mid)' }}>{scopeReady ? 'Server-owned scope from selected Product2 records' : 'Awaiting server-owned product scope'}</div>
                     ) : hasRecordFilter ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#3b82f6', fontWeight: 600 }}>
                        <span>🎯</span>
                        <span>{recs.length} record{recs.length !== 1 ? 's' : ''} selected</span>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ opacity: 0.6, flexShrink: 0 }}>
                          <polygon points="22,3 2,3 10,12.46 10,19 14,21 14,12.46"/>
                        </svg>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <input
                          style={{ flex: 1, padding: '6px 9px', background: 'var(--input-bg)', border: `1px solid ${filters[name] ? 'rgba(59,130,246,0.4)' : 'var(--input-border)'}`, borderRadius: 6, color: filters[name] ? '#93c5fd' : 'var(--input-color)', fontSize: 11, outline: 'none', fontFamily: 'monospace', minWidth: 0 }}
                           value={filters[name] || ''} aria-label={`WHERE filter for ${name}`}
                          onChange={e => setFilters(f => ({ ...f, [name]: e.target.value }))}
                          placeholder="e.g. IsActive = true"
                          disabled={isBusy}
                        />
                        <button title="Filter" style={{ background: 'none', border: 'none', color: filters[name] ? '#3b82f6' : 'var(--text-lo)', cursor: 'pointer', padding: '4px', display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                            <polygon points="22,3 2,3 10,12.46 10,19 14,21 14,12.46"/>
                          </svg>
                        </button>
                      </div>
                    )}
                    {/* Remove + chevron */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <button onClick={() => { if (!isBusy) { toggleObject(name); setRecordSelections(prev => { const n = {...prev}; delete n[name]; return n }) } }} disabled={isBusy || productBundle} aria-label={`Remove ${name}`}
                        style={{ background: 'none', border: 'none', color: 'var(--text-lo)', cursor: 'pointer', fontSize: 15, lineHeight: 1, padding: '0 2px' }}>×</button>
                    </div>
                  </div>
                )
              })}
               {!isBusy && !productBundle && (
                  <button onClick={clearSelection}
                  style={{ marginTop: 8, padding: '5px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-lo)', fontSize: 11, cursor: 'pointer' }}>
                  Clear All
                </button>
              )}
            </div>
          ) : (
            !loading && (
              <div style={{ color: 'var(--text-lo)', fontSize: 13, textAlign: 'center', padding: '28px 0', borderTop: '1px solid var(--border)' }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>📦</div>
                Select a Migration Bundle or add individual objects above
              </div>
            )
          )}
        </div>

        {/* ── EXECUTION PLAN ── */}
         {depOrder.length > 0 && !migrating && !selectedBundle && (
          <div style={s.section}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-mid)" strokeWidth="2" strokeLinecap="round">
                <circle cx="12" cy="12" r="10"/><polyline points="12,6 12,12 16,14"/>
              </svg>
              <span style={s.sectionTitle}>Execution Plan</span>
              <span style={{ fontSize: 11, color: 'var(--text-lo)', marginLeft: 4 }}>— dependency-resolved order</span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-lo)', marginBottom: 12 }}>Objects will migrate in this order — parents always before children.</div>
            <div style={s.depBox}>
              {depOrder.map((name, i) => (
                <div key={name} style={s.depStep}>
                  <div style={{ width: 22, height: 22, borderRadius: '50%', background: 'rgba(59,130,246,0.15)', border: '1.5px solid rgba(59,130,246,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <span style={{ fontSize: 10, fontWeight: 800, color: '#3b82f6' }}>{i + 1}</span>
                  </div>
                  <div style={{ width: 24, height: 24, borderRadius: 6, background: objColor(name), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <span style={{ fontSize: 8, fontWeight: 700, color: 'white' }}>{name.slice(0,2).toUpperCase()}</span>
                  </div>
                  <span style={{ fontSize: 12, color: 'var(--text)', flex: 1 }}>{name}</span>
                  {(recordSelections[name] || []).length > 0 ? (
                    <span style={{ fontSize: 10, color: '#3b82f6', background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 4, padding: '1px 6px', flexShrink: 0 }}>
                      🎯 {recordSelections[name].length} records
                    </span>
                  ) : filters[name]?.trim() ? (
                    <span style={{ fontSize: 10, color: '#fde68a', fontFamily: 'monospace', background: 'rgba(234,179,8,0.08)', border: '1px solid rgba(234,179,8,0.2)', borderRadius: 4, padding: '1px 6px', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      WHERE {filters[name].trim()}
                    </span>
                  ) : null}
                  {i < depOrder.length - 1 && <span style={{ fontSize: 11, color: 'var(--text-lo)' }}>↓</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {(migrating || progress) && <ProgressPanel progress={progress} depOrder={depOrder} migrating={migrating} dryRun={dryRun} />}
        {(migrating || terminalLines.length > 0) && <JobMonitorPanel lines={terminalLines} jobId={jobId} migrating={migrating} />}
        {result && <SummaryPanel result={result} onRollback={handleRollback} rollingBack={rollingBack} jobId={jobId} logPath={result?.log_path || ''} />}

        {/* ── BOTTOM ACTION BAR ── */}
        <div style={{ ...s.section, display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', background: 'var(--surface)', borderTop: '2px solid var(--border)' }}>
          {migrating ? (
            <>
              <div style={{ flex: 1, minWidth: 160 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#67e8f9', marginBottom: 2, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#06b6d4', boxShadow: '0 0 7px rgba(6,182,212,0.7)' }} />
                  Migration Running…
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-lo)' }}>
                  {targetOrg ? `→ ${targetOrg.alias || targetOrg.instance_url}` : ''}
                </div>
              </div>
            </>
          ) : (
            <>
              <div style={{ flex: 1, minWidth: 160 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)', marginBottom: 2 }}>
                  {totalSelected > 0 ? `${totalSelected} object${totalSelected > 1 ? 's' : ''} selected` : 'Select objects above to begin'}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-lo)' }}>
                  {targetOrg ? `→ ${targetOrg.alias || targetOrg.instance_url}` : 'Connect a target org to enable migration'}
                </div>
              </div>
              {totalSelected > 0 && (
                <button onClick={clearSelection}
                  style={{ padding: '9px 18px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-lo)', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
                  Clear Selection
                </button>
              )}
              {startErr && <div role="alert" style={{ ...s.err, marginBottom: 0 }}>{startErr}</div>}
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: isBusy ? 'not-allowed' : 'pointer', fontSize: 13, color: dryRun ? '#f59e0b' : 'var(--text-lo)', userSelect: 'none' }}>
                  <input
                    type="checkbox"
                    checked={dryRun}
                    onChange={e => !isBusy && setDryRun(e.target.checked)}
                    disabled={isBusy}
                    style={{ accentColor: '#f59e0b', width: 15, height: 15 }}
                  />
                  Dry Run (validate only)
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-lo)', userSelect: 'none' }}>
                  Error tolerance:
                  <select
                    value={failurePct}
                    onChange={e => !isBusy && setFailurePct(Number(e.target.value))}
                    disabled={isBusy}
                    style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)', borderRadius: 6, color: 'var(--input-color)', fontSize: 12, padding: '3px 6px', cursor: isBusy ? 'not-allowed' : 'pointer' }}
                  >
                    <option value={0}>Strict (0%)</option>
                    <option value={5}>5%</option>
                    <option value={10}>10%</option>
                    <option value={25}>25%</option>
                    <option value={100}>Lenient (any)</option>
                  </select>
                </label>
              </div>
              <button
                onClick={handleStartMigration}
                disabled={cannotStart}
                style={{ padding: '10px 24px', background: cannotStart ? 'var(--surface-hi)' : dryRun ? 'linear-gradient(135deg,#92400e,#f59e0b)' : 'linear-gradient(135deg,#1e40af,#3b82f6)', border: cannotStart ? '1px solid var(--border)' : 'none', borderRadius: 8, color: cannotStart ? 'var(--text-lo)' : 'white', fontSize: 14, fontWeight: 700, cursor: cannotStart ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: 8, boxShadow: cannotStart ? 'none' : '0 4px 12px rgba(59,130,246,0.35)' }}>
                {dryRun ? '🔍 Validate (Dry Run)' : '🚀 Start Migration'}
              </button>
            </>
          )}
        </div>

        <div style={{ fontSize: 11, color: 'var(--text-lo)', textAlign: 'center', marginTop: 8 }}>
          Bulk API 2.0 · Smart Keying · Rate Limiting · Rollback · Real-time progress
        </div>
      </div>
    </div>
  )
}
