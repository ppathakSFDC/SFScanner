import React, { useState, useEffect, useMemo, useRef } from 'react'

const ACCENT = '#2563eb'   // blue matching screenshot

// ─── SVG Icons ────────────────────────────────────────────────────────────────
function IconObjects() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <circle cx="8"  cy="8"  r="3" stroke={ACCENT} strokeWidth="1.8"/>
      <circle cx="16" cy="8"  r="3" stroke={ACCENT} strokeWidth="1.8"/>
      <circle cx="8"  cy="16" r="3" stroke={ACCENT} strokeWidth="1.8"/>
      <circle cx="16" cy="16" r="3" stroke={ACCENT} strokeWidth="1.8"/>
    </svg>
  )
}
function IconMeta() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8"/>
      <rect x="14" y="3" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8"/>
      <rect x="14" y="14" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8"/>
      <rect x="3" y="14" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.8"/>
    </svg>
  )
}
function IconChevronDown() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}
function IconSearch() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <circle cx="10.5" cy="10.5" r="7" stroke="currentColor" strokeWidth="2"/>
      <path d="M16 16L21 21" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
    </svg>
  )
}

function Spinner() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 40, gap: 10, color: 'var(--text-lo)' }}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style={{ animation: 'spin .8s linear infinite' }}>
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" strokeDasharray="30 56" strokeLinecap="round"/>
      </svg>
      <span style={{ fontSize: 13 }}>Loading…</span>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  )
}

// ─── Collapsible JSON Tree ────────────────────────────────────────────────────
function JsonNode({ label, value, depth = 0, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  const isArr  = Array.isArray(value)
  const isObj  = value !== null && typeof value === 'object' && !isArr
  const isNull = value === null

  const count   = isArr ? value.length : isObj ? Object.keys(value).length : 0
  const hasKids = (isArr || isObj) && count > 0
  const bracket = isArr ? ['[', ']'] : ['{', '}']

  const labelColor  = '#9ca3af'
  const bracketCol  = '#d1d5db'
  const countCol    = '#6b7280'
  const strColor    = '#86efac'
  const numColor    = '#67e8f9'
  const boolTColor  = '#4ade80'
  const boolFColor  = '#f87171'
  const nullColor   = '#94a3b8'

  function PrimVal() {
    if (isNull)             return <span style={{ color: nullColor }}>null</span>
    if (typeof value === 'string')  return <span style={{ color: strColor }}>"{value}"</span>
    if (typeof value === 'number')  return <span style={{ color: numColor }}>{value}</span>
    if (typeof value === 'boolean') return <span style={{ color: value ? boolTColor : boolFColor }}>{String(value)}</span>
    return <span style={{ color: '#e5e7eb' }}>{String(value)}</span>
  }

  if (!isArr && !isObj) {
    return (
      <div style={{ paddingLeft: depth * 16, lineHeight: '1.7', whiteSpace: 'nowrap' }}>
        {label !== undefined && <span style={{ color: labelColor }}>"{label}": </span>}
        <PrimVal />
      </div>
    )
  }

  return (
    <div style={{ paddingLeft: depth * 16 }}>
      <div
        onClick={() => hasKids && setOpen(o => !o)}
        style={{ display: 'flex', alignItems: 'center', gap: 4, lineHeight: '1.7',
          cursor: hasKids ? 'pointer' : 'default', userSelect: 'none' }}
      >
        <span style={{ width: 14, fontSize: 9, color: countCol, flexShrink: 0 }}>
          {hasKids ? (open ? '▼' : '▶') : ' '}
        </span>
        {label !== undefined && <span style={{ color: labelColor }}>"{label}": </span>}
        {!open
          ? <>
              <span style={{ color: bracketCol }}>{bracket[0]}</span>
              {hasKids && <span style={{ color: countCol, fontStyle: 'italic', fontSize: 12 }}>&hellip;</span>}
              <span style={{ color: bracketCol }}>{bracket[1]}</span>
              {count > 0 && <span style={{ color: countCol, fontStyle: 'italic', fontSize: 11, marginLeft: 4 }}>{count} {count === 1 ? 'Item' : 'Items'}</span>}
            </>
          : <span style={{ color: bracketCol }}>{bracket[0]}</span>
        }
      </div>

      {open && hasKids && (
        <>
          <div style={{ paddingLeft: 14 }}>
            {isArr
              ? value.map((v, i) => <JsonNode key={i} label={i} value={v} depth={0} />)
              : Object.entries(value).map(([k, v]) => <JsonNode key={k} label={k} value={v} depth={0} />)
            }
          </div>
          <div style={{ paddingLeft: 14, color: bracketCol, lineHeight: '1.7' }}>{bracket[1]}</div>
        </>
      )}
    </div>
  )
}

// Build a structured display from the raw Salesforce describe JSON
function buildDescribeTree(raw) {
  // Separate scalar fields from collections
  const attrs   = {}
  const colls   = {}
  const SKIP    = new Set(['urls'])  // hide noisy keys

  for (const [k, v] of Object.entries(raw)) {
    if (SKIP.has(k)) continue
    if (Array.isArray(v) || (v !== null && typeof v === 'object')) colls[k] = v
    else attrs[k] = v
  }

  // Pretty-print key name: camelCase → Title Case Words
  const fmt = s => s
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, c => c.toUpperCase())
    .trim()

  const tree = {}
  if (Object.keys(attrs).length) tree['Attributes'] = attrs
  for (const [k, v] of Object.entries(colls)) tree[fmt(k)] = v
  return tree
}

// ─── Objects Tab ──────────────────────────────────────────────────────────────
function ObjectsTab({ objects, loading }) {
  const [query,       setQuery]       = useState('')
  const [open,        setOpen]        = useState(false)
  const [selected,    setSelected]    = useState(null)
  const [describe,    setDescribe]    = useState(null)
  const [descLoading, setDescLoading] = useState(false)
  const [descError,   setDescError]   = useState('')
  const inputRef   = useRef(null)
  const dropRef    = useRef(null)

  // Filtered list — only shown when dropdown is open
  const filtered = useMemo(() => {
    if (!query.trim()) return objects
    const q = query.toLowerCase()
    return objects.filter(o =>
      o.name.toLowerCase().includes(q) || (o.label || '').toLowerCase().includes(q)
    )
  }, [objects, query])

  // Close dropdown on outside click
  useEffect(() => {
    function onDoc(e) {
      if (dropRef.current && !dropRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  // Fetch describe when object is selected
  useEffect(() => {
    if (!selected) { setDescribe(null); return }
    setDescLoading(true); setDescError('')
    fetch(`/info/describe/${selected.name}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : r.json().then(d => Promise.reject(d.detail || r.statusText)))
      .then(d => setDescribe(buildDescribeTree(d)))
      .catch(e => setDescError(String(e)))
      .finally(() => setDescLoading(false))
  }, [selected])

  function pick(obj) {
    setSelected(obj)
    setQuery('')
    setOpen(false)
  }

  const inputLabel = selected ? selected.name : ''

  return (
    <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '28px 32px' }}>
      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <IconObjects />
        <span style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Standard and Custom Objects</span>
        {objects.length > 0 && (
          <span style={{
            padding: '2px 10px', borderRadius: 20,
            border: '1px solid rgba(37,99,235,0.4)',
            color: ACCENT, fontSize: 12, fontWeight: 500,
          }}>
            {objects.length.toLocaleString()} objects
          </span>
        )}
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-lo)', margin: '0 0 24px', lineHeight: 1.5 }}>
        Explore detailed metadata for all standard and custom objects in your Salesforce org. View field definitions, relationships, record types, and more.
      </p>

      {/* Select card */}
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 10, padding: '20px 24px', marginBottom: 24,
      }}>
        {/* Combobox */}
        <div ref={dropRef} style={{ position: 'relative' }}>
          {/* Outlined input with floating label */}
          <div
            style={{
              position: 'relative',
              border: `1px solid ${open ? ACCENT : 'var(--border)'}`,
              borderRadius: 6,
              background: 'var(--bg)',
              cursor: 'text',
            }}
            onClick={() => { setOpen(true); inputRef.current?.focus() }}
          >
            {/* Floating label */}
            <span style={{
              position: 'absolute',
              top: open || inputLabel ? -10 : 14,
              left: 12,
              fontSize: open || inputLabel ? 11 : 14,
              color: open ? ACCENT : 'var(--text-lo)',
              background: 'var(--surface)',
              padding: '0 4px',
              transition: 'all 0.15s',
              pointerEvents: 'none',
              zIndex: 1,
            }}>
              Standard and Custom Objects
            </span>

            <input
              ref={inputRef}
              value={query}
              onChange={e => { setQuery(e.target.value); setOpen(true) }}
              onFocus={() => setOpen(true)}
              placeholder={selected && !open ? '' : ''}
              style={{
                width: '100%', boxSizing: 'border-box',
                padding: '14px 40px 14px 16px',
                background: 'transparent', border: 'none',
                color: 'var(--text)', fontSize: 14,
                outline: 'none', fontFamily: 'inherit',
              }}
            />
            {/* Show selected name when closed */}
            {selected && !open && !query && (
              <span style={{
                position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)',
                fontSize: 14, color: 'var(--text)', pointerEvents: 'none',
              }}>
                {selected.name}
              </span>
            )}
            {/* Chevron */}
            <span style={{
              position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
              color: open ? ACCENT : 'var(--text-lo)', display: 'flex', pointerEvents: 'none',
            }}>
              <IconChevronDown />
            </span>
          </div>

          {/* Dropdown list */}
          {open && (
            <div style={{
              position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
              background: 'var(--surface)',
              border: `1px solid ${ACCENT}`,
              borderRadius: 6,
              maxHeight: 320, overflowY: 'auto',
              zIndex: 200,
              boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
            }}>
              {loading && (
                <div style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-lo)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ animation: 'spin .8s linear infinite' }}>
                    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" strokeDasharray="30 56" strokeLinecap="round"/>
                  </svg>
                  Loading objects…
                </div>
              )}
              {!loading && filtered.length === 0 && (
                <div style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-lo)' }}>
                  No objects match "{query}"
                </div>
              )}
              {!loading && filtered.map(o => (
                <div
                  key={o.name}
                  onMouseDown={e => { e.preventDefault(); pick(o) }}
                  style={{
                    padding: '9px 16px', cursor: 'pointer',
                    borderBottom: '1px solid var(--border)',
                    background: selected?.name === o.name ? 'rgba(37,99,235,0.07)' : 'transparent',
                    display: 'flex', alignItems: 'baseline', gap: 10,
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(37,99,235,0.05)'}
                  onMouseLeave={e => e.currentTarget.style.background = selected?.name === o.name ? 'rgba(37,99,235,0.07)' : 'transparent'}
                >
                  <span style={{ fontSize: 13, color: 'var(--text)', fontFamily: 'monospace' }}>{o.name}</span>
                  {o.label && o.label !== o.name && (
                    <span style={{ fontSize: 11, color: 'var(--text-lo)' }}>{o.label}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Showing metadata for… */}
        {selected && !open && (
          <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-lo)' }}>
            Showing metadata for: <strong style={{ color: 'var(--text)' }}>{selected.name}</strong>
          </div>
        )}
      </div>

      {/* Describe result */}
      {descLoading && <Spinner />}
      {descError && (
        <div style={{ padding: '10px 14px', background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, color: '#fca5a5', fontSize: 12 }}>
          {descError}
        </div>
      )}
      {describe && !descLoading && (
        <div style={{
          background: '#111827',
          border: '1px solid #374151',
          borderRadius: 10,
          padding: '20px 24px',
          fontFamily: "'Fira Mono', 'Cascadia Code', 'Consolas', monospace",
          fontSize: 13,
          lineHeight: 1.6,
          color: '#e5e7eb',
          overflowX: 'auto',
        }}>
          {/* Root: "Information" wrapper */}
          <div>
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'default' }}
            >
              <span style={{ width: 14, fontSize: 9, color: '#6b7280' }}>▼</span>
              <span style={{ color: '#9ca3af' }}>"Information": </span>
              <span style={{ color: '#d1d5db' }}>{'{'}</span>
              <span style={{ color: '#6b7280', fontStyle: 'italic', fontSize: 11, marginLeft: 4 }}>
                {Object.keys(describe).length} {Object.keys(describe).length === 1 ? 'Item' : 'Items'}
              </span>
            </div>
            <div style={{ paddingLeft: 20 }}>
              {Object.entries(describe).map(([k, v]) => (
                <JsonNode key={k} label={k} value={v} depth={0} defaultOpen={false} />
              ))}
            </div>
            <div style={{ color: '#d1d5db' }}>{'}'}</div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Metadata Tab ─────────────────────────────────────────────────────────────
function MetadataTab({ types, loading }) {
  const [query,       setQuery]       = useState('')
  const [open,        setOpen]        = useState(false)
  const [selected,    setSelected]    = useState(null)
  const [components,  setComponents]  = useState([])
  const [compLoading, setCompLoading] = useState(false)
  const inputRef = useRef(null)
  const dropRef  = useRef(null)

  // Filter types for dropdown
  const filtered = useMemo(() => {
    if (!query.trim()) return types
    const q = query.toLowerCase()
    return types.filter(t => t.xmlName.toLowerCase().includes(q))
  }, [types, query])

  // Close on outside click
  useEffect(() => {
    function onDoc(e) { if (dropRef.current && !dropRef.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  // Fetch components when type selected
  useEffect(() => {
    if (!selected) { setComponents([]); return }
    setCompLoading(true); setComponents([])
    fetch(`/info/metadata-components/${selected.xmlName}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r.statusText))
      .then(d => setComponents(d.components || []))
      .catch(() => setComponents([]))
      .finally(() => setCompLoading(false))
  }, [selected])

  function pick(t) { setSelected(t); setQuery(''); setOpen(false) }

  const inputLabel = selected ? selected.xmlName : ''

  // Build JSON tree data combining components + type description
  const treeData = selected ? {
    Components: components,
    TypeDescription: selected,
  } : null

  return (
    <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '28px 32px' }}>
      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <IconMeta />
        <span style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Metadata Types and Components</span>
        {types.length > 0 && (
          <span style={{
            padding: '2px 10px', borderRadius: 20,
            border: '1px solid rgba(37,99,235,0.4)',
            color: ACCENT, fontSize: 12, fontWeight: 500,
          }}>
            {types.length.toLocaleString()} types
          </span>
        )}
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-lo)', margin: '0 0 24px', lineHeight: 1.5 }}>
        Browse all metadata types available in your org. Select a type to see its deployed components and type configuration.
      </p>

      {/* Select card */}
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 10, padding: '20px 24px', marginBottom: 24,
      }}>
        <div ref={dropRef} style={{ position: 'relative' }}>
          {/* Outlined input with floating label */}
          <div
            style={{
              position: 'relative',
              border: `1px solid ${open ? ACCENT : 'var(--border)'}`,
              borderRadius: 6, background: 'var(--bg)', cursor: 'text',
            }}
            onClick={() => { setOpen(true); inputRef.current?.focus() }}
          >
            <span style={{
              position: 'absolute',
              top: open || inputLabel ? -10 : 14,
              left: 12,
              fontSize: open || inputLabel ? 11 : 14,
              color: open ? ACCENT : 'var(--text-lo)',
              background: 'var(--surface)',
              padding: '0 4px',
              transition: 'all 0.15s',
              pointerEvents: 'none',
              zIndex: 1,
            }}>
              Metadata Types and Components
            </span>
            <input
              ref={inputRef}
              value={query}
              onChange={e => { setQuery(e.target.value); setOpen(true) }}
              onFocus={() => setOpen(true)}
              style={{
                width: '100%', boxSizing: 'border-box',
                padding: '14px 40px 14px 16px',
                background: 'transparent', border: 'none',
                color: 'var(--text)', fontSize: 14,
                outline: 'none', fontFamily: 'inherit',
              }}
            />
            {selected && !open && !query && (
              <span style={{
                position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)',
                fontSize: 14, color: 'var(--text)', pointerEvents: 'none',
              }}>
                {selected.xmlName}
              </span>
            )}
            <span style={{
              position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
              color: open ? ACCENT : 'var(--text-lo)', display: 'flex', pointerEvents: 'none',
            }}>
              <IconChevronDown />
            </span>
          </div>

          {/* Dropdown */}
          {open && (
            <div style={{
              position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
              background: 'var(--surface)',
              border: `1px solid ${ACCENT}`,
              borderRadius: 6, maxHeight: 320, overflowY: 'auto',
              zIndex: 200, boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
            }}>
              {loading && (
                <div style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-lo)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ animation: 'spin .8s linear infinite' }}>
                    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" strokeDasharray="30 56" strokeLinecap="round"/>
                  </svg>
                  Loading types…
                </div>
              )}
              {!loading && filtered.length === 0 && (
                <div style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-lo)' }}>
                  No types match "{query}"
                </div>
              )}
              {!loading && filtered.map(t => (
                <div
                  key={t.xmlName}
                  onMouseDown={e => { e.preventDefault(); pick(t) }}
                  style={{
                    padding: '9px 16px', cursor: 'pointer',
                    borderBottom: '1px solid var(--border)',
                    background: selected?.xmlName === t.xmlName ? 'rgba(37,99,235,0.07)' : 'transparent',
                    display: 'flex', alignItems: 'baseline', gap: 10,
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(37,99,235,0.05)'}
                  onMouseLeave={e => e.currentTarget.style.background = selected?.xmlName === t.xmlName ? 'rgba(37,99,235,0.07)' : 'transparent'}
                >
                  <span style={{ fontSize: 13, color: 'var(--text)', fontFamily: 'monospace' }}>{t.xmlName}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-lo)', display: 'flex', gap: 6 }}>
                    {t.inFolder && <span>folder-based</span>}
                    {t.suffix && <span>*.{t.suffix}</span>}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {selected && !open && (
          <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-lo)' }}>
            Showing components for: <strong style={{ color: 'var(--text)' }}>{selected.xmlName}</strong>
            {selected.directoryName && <span style={{ marginLeft: 8, opacity: 0.6 }}>· {selected.directoryName}{selected.suffix ? `/*.${selected.suffix}` : ''}</span>}
            {selected.inFolder && <span style={{ marginLeft: 8, color: ACCENT }}>· folder-based</span>}
          </div>
        )}
      </div>

      {/* JSON tree result */}
      {compLoading && <Spinner />}
      {!compLoading && treeData && (
        <div style={{
          background: '#111827',
          border: '1px solid #374151',
          borderRadius: 10,
          padding: '20px 24px',
          fontFamily: "'Fira Mono', 'Cascadia Code', 'Consolas', monospace",
          fontSize: 13,
          lineHeight: 1.6,
          color: '#e5e7eb',
          overflowX: 'auto',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'default' }}>
              <span style={{ width: 14, fontSize: 9, color: '#6b7280' }}>▼</span>
              <span style={{ color: '#9ca3af' }}>"{selected.xmlName}": </span>
              <span style={{ color: '#d1d5db' }}>{'{'}</span>
              <span style={{ color: '#6b7280', fontStyle: 'italic', fontSize: 11, marginLeft: 4 }}>2 Items</span>
            </div>
            <div style={{ paddingLeft: 20 }}>
              {Object.entries(treeData).map(([k, v]) => (
                <JsonNode key={k} label={k} value={v} depth={0} defaultOpen={k === 'TypeDescription'} />
              ))}
            </div>
            <div style={{ color: '#d1d5db' }}>{'}'}</div>
          </div>
        </div>
      )}
    </div>
  )
}

// Detect whether a component list came from SOAP listMetadata (has FileProperties fields)
// or Tooling API (has Salesforce record fields).
function isSoapSource(components) {
  if (!components.length) return false
  const c = components[0]
  return 'fullName' in c || 'fileName' in c || 'manageableState' in c
}

// Format a date string (ISO or YYYY-MM-DD style) to locale date
function fmtDate(d) {
  if (!d) return ''
  try { return new Date(d).toLocaleDateString() } catch { return d }
}

// Manageable state colour hints
const STATE_COLORS = {
  unmanaged:      'var(--text-lo)',
  installed:      '#60a5fa',
  installedEditable: '#34d399',
  released:       '#a78bfa',
  deprecated:     '#f87171',
  deleted:        '#f87171',
}

function ComponentsPanel({ type, components, loading, search, onSearch, inline = false }) {
  const soap = isSoapSource(components)

  const filtered = useMemo(() => {
    if (!search) return components
    const q = search.toLowerCase()
    return components.filter(c => {
      const n = c.fullName || c.Name || c.ApiName || c.DeveloperName || c.QualifiedApiName || ''
      return n.toLowerCase().includes(q)
    })
  }, [components, search])

  const wrapStyle = inline
    ? { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }
    : { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }

  return (
    <div style={wrapStyle}>
      {/* Header */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)', fontFamily: 'monospace' }}>{type.xmlName}</div>
          <div style={{ fontSize: 11, color: 'var(--text-lo)', marginTop: 1 }}>
            {type.directoryName && `dir: ${type.directoryName}`}
            {type.suffix && ` · *.${type.suffix}`}
            {type.inFolder && ' · folder-based'}
          </div>
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-lo)', background: 'var(--surface-hi)', padding: '3px 8px', borderRadius: 6, border: '1px solid var(--border)' }}>
          {loading ? '…' : `${filtered.length.toLocaleString()} component${filtered.length !== 1 ? 's' : ''}`}
        </span>
      </div>

      {/* Search */}
      <div style={{ padding: '8px 16px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ position: 'relative' }}>
          <span style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-lo)', display: 'flex' }}><IconSearch /></span>
          <input value={search} onChange={e => onSearch(e.target.value)} placeholder="Search components…"
            style={{ width: '100%', boxSizing: 'border-box', padding: '7px 9px 7px 28px', background: 'var(--input-bg)', border: '1px solid var(--input-border)', borderRadius: 6, color: 'var(--input-color)', fontSize: 12, outline: 'none', fontFamily: 'inherit' }}
          />
        </div>
      </div>

      {/* Table header (SOAP FileProperties columns) */}
      {soap && !loading && filtered.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 140px 100px 90px',
          padding: '5px 16px', gap: 8,
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface)',
        }}>
          {['Full Name / File Path', 'Namespace', 'State', 'Modified'].map(h => (
            <span key={h} style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-lo)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</span>
          ))}
        </div>
      )}

      {/* Rows */}
      <div style={inline ? {} : { flex: 1, minHeight: 0, overflowY: 'auto' }}>
        {loading && <Spinner />}

        {!loading && soap && filtered.map((c, i) => {
          const state = c.manageableState || 'unmanaged'
          const stateColor = STATE_COLORS[state] || 'var(--text-lo)'
          return (
            <div key={c.fullName || i} style={{
              display: 'grid', gridTemplateColumns: '1fr 140px 100px 90px',
              padding: '8px 16px', gap: 8,
              borderBottom: '1px solid var(--border)',
              alignItems: 'center',
            }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, color: 'var(--text)', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.fullName || '—'}
                </div>
                {c.fileName && c.fileName !== c.fullName && (
                  <div style={{ fontSize: 10, color: 'var(--text-lo)', marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.fileName}</div>
                )}
                {c.lastModifiedByName && (
                  <div style={{ fontSize: 10, color: 'var(--text-lo)', marginTop: 1 }}>by {c.lastModifiedByName}</div>
                )}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-lo)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {c.namespacePrefix || <span style={{ opacity: 0.4 }}>—</span>}
              </div>
              <div style={{ fontSize: 11, color: stateColor }}>{state}</div>
              <div style={{ fontSize: 11, color: 'var(--text-lo)' }}>{fmtDate(c.lastModifiedDate)}</div>
            </div>
          )
        })}

        {!loading && !soap && filtered.map((c, i) => {
          const name = c.fullName || c.Name || c.ApiName || c.Label || c.DeveloperName || c.QualifiedApiName || c.Id || '—'
          const sub  = c.Status || c.ProcessType || c.DataType || c.TemplateType || c.TableEnumOrId || c.namespacePrefix || ''
          const date = fmtDate(c.lastModifiedDate || c.LastModifiedDate)
          const badge = c.namespacePrefix || (c.IsCustom === false ? 'standard' : c.IsCustom === true ? 'custom' : '')
          return (
            <div key={c.Id || c.fullName || i} style={{ padding: '9px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, color: 'var(--text)', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</div>
                {sub && <div style={{ fontSize: 11, color: 'var(--text-lo)', marginTop: 1 }}>{sub}</div>}
              </div>
              {badge && <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 10, border: '1px solid var(--border)', color: 'var(--text-lo)', flexShrink: 0 }}>{badge}</span>}
              {date && <div style={{ fontSize: 11, color: 'var(--text-lo)', flexShrink: 0 }}>{date}</div>}
            </div>
          )
        })}

        {!loading && filtered.length === 0 && (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-lo)', fontSize: 13 }}>
            {components.length === 0 ? 'No components found for this type.' : 'No components match your search.'}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function InfoPage({ auth }) {
  const [activeTab,    setActiveTab]    = useState('objects')
  const [sobjects,     setSobjects]     = useState([])
  const [objLoading,   setObjLoading]   = useState(false)
  const [metaTypes,    setMetaTypes]    = useState([])
  const [metaLoading,  setMetaLoading]  = useState(false)
  const [error,        setError]        = useState('')

  // Metadata tab state
  // Fetch sObjects once on first visit to objects tab (background — list is used by combobox)
  useEffect(() => {
    if (sobjects.length > 0) return
    setObjLoading(true)
    fetch('/info/sobjects', { credentials: 'include' })
      .then(r => r.ok ? r.json() : r.json().then(d => Promise.reject(d.detail || r.statusText)))
      .then(d => setSobjects(d.sobjects || []))
      .catch(e => setError(String(e)))
      .finally(() => setObjLoading(false))
  }, [sobjects.length])

  // Fetch metadata types on first visit to metadata tab
  useEffect(() => {
    if (activeTab !== 'metadata' || metaTypes.length > 0) return
    setMetaLoading(true)
    fetch('/info/metadata-types', { credentials: 'include' })
      .then(r => r.ok ? r.json() : r.json().then(d => Promise.reject(d.detail || r.statusText)))
      .then(d => setMetaTypes(d.metadata_types || []))
      .catch(e => setError(String(e)))
      .finally(() => setMetaLoading(false))
  }, [activeTab, metaTypes.length])

  const TABS = [
    { id: 'objects',  label: 'Standard and Custom Objects',  icon: <IconObjects /> },
    { id: 'metadata', label: 'Metadata Types and Components', icon: <IconMeta /> },
  ]

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--bg)', overflow: 'hidden' }}>
      {/* Tab bar */}
      <div style={{ borderBottom: '1px solid var(--border)', flexShrink: 0, paddingLeft: 8 }}>
        <div style={{ display: 'flex' }}>
          {TABS.map(tab => {
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => { setActiveTab(tab.id); setError('') }}
                style={{
                  padding: '14px 20px', border: 'none', background: 'transparent', cursor: 'pointer',
                  color: active ? ACCENT : 'var(--text-mid)',
                  borderBottom: `2px solid ${active ? ACCENT : 'transparent'}`,
                  marginBottom: -1, fontSize: 13, fontWeight: active ? 600 : 400,
                  display: 'flex', alignItems: 'center', gap: 7, transition: 'color 0.15s',
                  whiteSpace: 'nowrap',
                }}
              >
                <span style={{ color: active ? ACCENT : 'var(--text-lo)', display: 'flex' }}>{tab.icon}</span>
                {tab.label}
              </button>
            )
          })}
        </div>
      </div>

      {error && (
        <div style={{ margin: '12px 24px 0', padding: '9px 13px', background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 7, color: '#fca5a5', fontSize: 12, flexShrink: 0 }}>
          {error}
        </div>
      )}

      {/* Content */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {activeTab === 'objects' && (
          <ObjectsTab objects={sobjects} loading={objLoading} />
        )}
        {activeTab === 'metadata' && (
          <MetadataTab types={metaTypes} loading={metaLoading} />
        )}
      </div>
    </div>
  )
}
