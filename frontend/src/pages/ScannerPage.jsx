import React, { useState, useEffect, useCallback, useRef } from 'react'

// ─── Style constants (follow global theme via CSS vars) ───────────────────────
const LIGHT_BG = 'var(--bg)'
const CARD_BG  = 'var(--surface)'
const CARD_HI  = 'var(--surface-hi)'
const BORDER   = 'var(--border)'
const BORDER_HI= 'var(--border-hi)'
const TEXT_DARK= 'var(--text)'
const TEXT_MID = 'var(--text-mid)'
const TEXT_LO  = 'var(--text-lo)'
const ACCENT   = '#06b6d4'
const BLUE     = '#2563eb'
const RED      = '#ef4444'
const ORANGE   = '#f97316'
const GREEN    = '#22c55e'
const PURPLE   = '#a855f7'

// ─── Type metadata ────────────────────────────────────────────────────────────
const TYPE_META = {
  OmniScript:              { color: '#6366f1', bg: 'rgba(99,102,241,0.15)',  icon: '🤖', label: 'OmniScript'           },
  DataRaptor:              { color: GREEN,     bg: 'rgba(34,197,94,0.15)',   icon: '📊', label: 'DataRaptor'           },
  'Integration Procedure': { color: ORANGE,    bg: 'rgba(249,115,22,0.15)', icon: '🌐', label: 'Integration Procedure'},
  'Apex Class':            { color: '#ec4899', bg: 'rgba(236,72,153,0.15)', icon: '</>', label: 'Apex Class'          },
  'Apex Trigger':          { color: ORANGE,    bg: 'rgba(249,115,22,0.15)', icon: '⚡', label: 'Apex Trigger'         },
  Flow:                    { color: '#0ea5e9', bg: 'rgba(14,165,233,0.15)', icon: '🔄', label: 'Flow'                 },
  'Custom Object':         { color: PURPLE,    bg: 'rgba(168,85,247,0.15)', icon: '🗃️', label: 'Custom Object'       },
  FlexCard:                { color: '#14b8a6', bg: 'rgba(20,184,166,0.15)', icon: '🃏', label: 'FlexCard'             },
  'Business Rule':         { color: '#e11d48', bg: 'rgba(225,29,72,0.15)',  icon: '📋', label: 'Business Rule'        },
  'CML Rule':              { color: '#7c3aed', bg: 'rgba(124,58,237,0.15)', icon: '🔗', label: 'CML Rule'             },
  'Data Mapper':           { color: '#f59e0b', bg: 'rgba(245,158,11,0.15)', icon: '🗺️', label: 'Data Mapper'         },
  SOQL:                    { color: '#0891b2', bg: 'rgba(8,145,178,0.15)',   icon: '🔍', label: 'SOQL'                 },
  'Org Limit':             { color: TEXT_MID,  bg: 'rgba(148,163,184,0.12)',icon: '📈', label: 'Org Limit'           },
}

const AGENT_ID = {
  OmniScript:              'omniscript_expert',
  DataRaptor:              'dataraptor_expert',
  'Integration Procedure': 'integration_expert',
  'Apex Class':            'apex_expert',
  'Apex Trigger':          'apex_expert',
  Flow:                    'flow_expert',
  'Custom Object':         'general_expert',
  FlexCard:                'omniscript_expert',
  'Business Rule':         'general_expert',
  'CML Rule':              'general_expert',
  'Data Mapper':           'dataraptor_expert',
  SOQL:                    'apex_expert',
  'Org Limit':             'general_expert',
}

// Left sidebar category filter definitions
const CATEGORIES = [
  { id: 'all',            label: 'All',                    types: null,                                       color: BLUE,     icon: '⊞'   },
  { id: 'omniscript',     label: 'OmniScripts',            types: ['OmniScript'],                             color: '#6366f1',icon: '🤖'  },
  { id: 'dataraptor',     label: 'DataRaptors',            types: ['DataRaptor'],                             color: GREEN,    icon: '📊'  },
  { id: 'integration',    label: 'Integration Procedures', types: ['Integration Procedure'],                  color: ORANGE,   icon: '🌐'  },
  { id: 'data_mapper',    label: 'Data Mappers',           types: ['Data Mapper'],                            color: '#f59e0b',icon: '🗺️'  },
  { id: 'flexcard',       label: 'FlexCards',              types: ['FlexCard'],                               color: '#14b8a6',icon: '🃏'  },
  { id: 'bre',            label: 'BRE',                    types: ['Business Rule'],                          color: '#e11d48',icon: '📋'  },
  { id: 'cml',            label: 'CML',                    types: ['CML Rule'],                               color: '#7c3aed',icon: '🔗'  },
  { id: 'flow',           label: 'Flows',                  types: ['Flow'],                                   color: '#0ea5e9',icon: '🔄'  },
  { id: 'apex',           label: 'Apex',                   types: ['Apex Class','Apex Trigger'],              color: '#ec4899',icon: '</>' },
  { id: 'soql',           label: 'SOQL',                   types: ['SOQL'],                                   color: '#0891b2',icon: '🔍'  },
]

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatusBadge({ issues }) {
  const high = issues.filter(i => i.severity === 'high').length
  const med  = issues.filter(i => i.severity === 'medium').length
  if (high > 0)  return <span style={badge(RED,    'rgba(239,68,68,0.12)')}>● Issues</span>
  if (med  > 0)  return <span style={badge(ORANGE, 'rgba(249,115,22,0.12)')}>⚠ Warnings</span>
  return <span style={badge(GREEN, 'rgba(34,197,94,0.12)')}>● Passed</span>
}

function badge(color, bg) {
  return { fontSize: 11, fontWeight: 700, color, background: bg, border: `1px solid ${color}22`,
    borderRadius: 20, padding: '3px 10px', whiteSpace: 'nowrap' }
}

function TypeChip({ type }) {
  const m = TYPE_META[type] || { color: TEXT_MID, bg: 'rgba(148,163,184,0.12)', label: type }
  return (
    <span style={{ fontSize: 11, fontWeight: 700, color: m.color, background: m.bg,
      borderRadius: 20, padding: '2px 9px', whiteSpace: 'nowrap' }}>
      {m.icon} {m.label}
    </span>
  )
}

function StatCard({ icon, iconBg, number, label, color, onClick, active }) {
  const [hov, setHov] = React.useState(false)
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        flex: 1, minWidth: 160, background: active ? `${color}08` : CARD_BG,
        border: `1.5px solid ${active ? color + '55' : hov ? color + '33' : BORDER}`,
        borderRadius: 12, padding: '18px 20px',
        display: 'flex', alignItems: 'flex-start', gap: 14,
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.15s',
        boxShadow: active ? `0 4px 16px ${color}18` : hov ? `0 2px 8px ${color}10` : 'none',
      }}
    >
      <div style={{
        width: 42, height: 42, borderRadius: '50%', background: active ? color + '22' : iconBg,
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: 20,
        transition: 'background 0.15s',
      }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: 28, fontWeight: 800, color, lineHeight: 1, letterSpacing: '-0.02em' }}>
          {number ?? '—'}
        </div>
        <div style={{ fontSize: 12, color: TEXT_MID, marginTop: 3, marginBottom: 6 }}>{label}</div>
        {onClick && (
          <div style={{ fontSize: 11, color: active ? color : ACCENT, fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 3 }}>
            {active ? '✕ Clear filter' : 'View all →'}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Action card button ───────────────────────────────────────────────────────
function ActionCard({ icon, iconBg, iconBorder, label, sub, color, badge, onClick, disabled }) {
  const [hov, setHov] = React.useState(false)
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        width: '100%', textAlign: 'left', cursor: disabled ? 'not-allowed' : 'pointer',
        background: hov && !disabled ? `${color}08` : CARD_BG,
        border: `1.5px solid ${hov && !disabled ? color + '44' : BORDER}`,
        borderRadius: 12, padding: '14px 16px',
        display: 'flex', alignItems: 'center', gap: 14,
        transition: 'all 0.15s', opacity: disabled ? 0.45 : 1,
        boxShadow: hov && !disabled ? `0 4px 16px ${color}18` : 'none',
      }}
    >
      <div style={{
        width: 42, height: 42, borderRadius: 11, flexShrink: 0,
        background: iconBg, border: `1.5px solid ${iconBorder}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
        boxShadow: hov && !disabled ? `0 0 12px ${color}30` : 'none',
        transition: 'box-shadow 0.15s',
      }}>
        {icon}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color }}>{label}</span>
          {badge && (
            <span style={{ fontSize: 10, fontWeight: 700, color: 'white',
              background: color, borderRadius: 20, padding: '1px 7px' }}>{badge}</span>
          )}
        </div>
        <div style={{ fontSize: 12, color: TEXT_MID, lineHeight: 1.4 }}>{sub}</div>
      </div>
      <span style={{ color: hov && !disabled ? color : TEXT_MID, fontSize: 18, transition: 'color 0.15s' }}>›</span>
    </button>
  )
}

// ─── Deploy info right panel ──────────────────────────────────────────────────
function DeployPanel({ onNavigateMigrate, onBack }) {
  const steps = [
    { n: '1', title: 'Review your changes', desc: 'Check all modified components in the scanner results before deploying.' },
    { n: '2', title: 'Validate metadata',   desc: 'Run a validation-only deploy to catch errors without modifying the org.' },
    { n: '3', title: 'Deploy to org',       desc: 'Use the Migration tool to push components with dependency ordering.' },
    { n: '4', title: 'Verify in org',       desc: 'Confirm changes are active and run regression tests post-deploy.' },
  ]
  return (
    <div style={{ padding: '22px 22px 32px', overflowY: 'auto', height: '100%', boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <button onClick={onBack} style={{ background: 'none', border: `1px solid ${BORDER}`,
          borderRadius: 7, color: TEXT_MID, fontSize: 12, padding: '4px 10px', cursor: 'pointer' }}>← Back</button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 20 }}>🚀</span>
          <span style={{ fontSize: 16, fontWeight: 800, color: TEXT_DARK }}>Deploy to Org</span>
        </div>
      </div>

      <div style={{ background: `${PURPLE}0d`, border: `1px solid ${PURPLE}33`,
        borderRadius: 10, padding: '12px 16px', marginBottom: 20, fontSize: 13, color: PURPLE, lineHeight: 1.6 }}>
        Deploy validated changes from your Salesforce org safely using the Migration tool.
      </div>

      <div style={{ marginBottom: 22 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: TEXT_MID, textTransform: 'uppercase',
          letterSpacing: '0.07em', marginBottom: 12 }}>Deploy Steps</div>
        {steps.map((step, i) => (
          <div key={i} style={{ display: 'flex', gap: 12, marginBottom: 14 }}>
            <div style={{ width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
              background: PURPLE, color: 'white', fontSize: 11, fontWeight: 800,
              display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{step.n}</div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: TEXT_DARK, marginBottom: 2 }}>{step.title}</div>
              <div style={{ fontSize: 12, color: TEXT_MID, lineHeight: 1.5 }}>{step.desc}</div>
            </div>
          </div>
        ))}
      </div>

      <button onClick={onNavigateMigrate} style={{
        width: '100%', padding: '11px 0',
        background: `linear-gradient(135deg,${PURPLE},#7c3aed)`,
        border: 'none', borderRadius: 10, color: 'white',
        fontSize: 13, fontWeight: 700, cursor: 'pointer',
        boxShadow: `0 4px 16px ${PURPLE}40`,
      }}>Open Migration Tool →</button>
    </div>
  )
}

// ─── Empty-state right panel ──────────────────────────────────────────────────
function EmptyRightPanel({ onIdentify, onFix, onDeploy, onImprove, hasScan, hasIssues, hasWarnings, scanning }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', padding: '24px 20px 28px', gap: 0, height: '100%', boxSizing: 'border-box', overflowY: 'auto' }}>
      {/* Illustration */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: 20 }}>
        <div style={{ position: 'relative', width: 220, height: 170, marginBottom: 16 }}>
          <svg width="220" height="150" viewBox="0 0 220 150" fill="none" style={{ display: 'block' }}>
            <defs>
              <linearGradient id="cloudBig2" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="rgba(6,182,212,0.2)"/>
                <stop offset="100%" stopColor="rgba(6,182,212,0.1)"/>
              </linearGradient>
              <filter id="glow2">
                <feDropShadow dx="0" dy="2" stdDeviation="6" floodColor="#06b6d4" floodOpacity="0.25"/>
              </filter>
            </defs>
            <ellipse cx="110" cy="95" rx="64" ry="34" fill="url(#cloudBig2)"/>
            <ellipse cx="86"  cy="80" rx="32" ry="24" fill="url(#cloudBig2)"/>
            <ellipse cx="132" cy="78" rx="28" ry="22" fill="url(#cloudBig2)"/>
            <circle cx="110" cy="88" r="30" fill="#0d2020" filter="url(#glow2)"/>
            <circle cx="106" cy="84" r="11" stroke={ACCENT} strokeWidth="3" fill="none"/>
            <path d="M114 92 L123 101" stroke={ACCENT} strokeWidth="3.5" strokeLinecap="round"/>
          </svg>
          {[
            { x: 8,   y: 14, bg: 'rgba(34,197,94,0.15)',   border: 'rgba(34,197,94,0.35)',   icon: '🛡️' },
            { x: 170, y: 6,  bg: 'rgba(168,85,247,0.15)', border: 'rgba(168,85,247,0.35)', icon: '</>' },
            { x: 0,   y: 88, bg: 'rgba(14,165,233,0.15)', border: 'rgba(14,165,233,0.35)', icon: '🗄️' },
            { x: 178, y: 84, bg: 'rgba(236,72,153,0.15)', border: 'rgba(236,72,153,0.35)', icon: '🚀' },
          ].map((sq, i) => (
            <div key={i} style={{
              position: 'absolute', top: sq.y, left: sq.x,
              width: 38, height: 38, borderRadius: 10,
              background: sq.bg, border: `1.5px solid ${sq.border}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 17, boxShadow: '0 3px 10px rgba(0,0,0,0.10)',
            }}>{sq.icon}</div>
          ))}
        </div>
        <div style={{ fontSize: 17, fontWeight: 800, color: TEXT_DARK, marginBottom: 6, textAlign: 'center' }}>
          Select a component to view details
        </div>
        <div style={{ fontSize: 12, color: TEXT_MID, textAlign: 'center', maxWidth: 310, lineHeight: 1.6 }}>
          Or use the quick actions below to get started.
        </div>
      </div>

      {/* 4 action cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <ActionCard
          icon="🛡️" iconBg="rgba(34,197,94,0.15)"   iconBorder="rgba(34,197,94,0.3)"
          label="Identify" color={GREEN}
          sub={hasScan ? 'Re-scan org for best practice violations' : 'Scan org for best practice violations'}
          badge={scanning ? '…' : null}
          onClick={onIdentify}
          disabled={scanning}
        />
        <ActionCard
          icon="🔧" iconBg="rgba(37,99,235,0.15)"   iconBorder="rgba(37,99,235,0.3)"
          label="Fix" color={BLUE}
          sub={hasIssues ? 'Jump to first critical issue to fix' : 'No critical issues found — run a scan first'}
          badge={hasIssues || null}
          onClick={onFix}
          disabled={!hasIssues}
        />
        <ActionCard
          icon="🚀" iconBg="rgba(168,85,247,0.15)" iconBorder="rgba(168,85,247,0.3)"
          label="Deploy" color={PURPLE}
          sub="Open the Migration tool to deploy to your org"
          onClick={onDeploy}
        />
        <ActionCard
          icon="📈" iconBg="rgba(249,115,22,0.15)" iconBorder="rgba(249,115,22,0.3)"
          label="Improve" color={ORANGE}
          sub={hasWarnings ? 'Jump to first warning for optimization' : 'No warnings found — run a scan first'}
          badge={hasWarnings || null}
          onClick={onImprove}
          disabled={!hasWarnings}
        />
      </div>
    </div>
  )
}

// ─── Main ScannerPage ─────────────────────────────────────────────────────────
export default function ScannerPage({ auth, onConnectOrg, onNavigate }) {
  const [scan,        setScan]        = useState(null)
  const [scanning,    setScanning]    = useState(false)
  const [scanError,   setScanError]   = useState('')
  const [tokenExpired,setTokenExpired]= useState(false)
  const [fetchErrors, setFetchErrors] = useState({})

  const [search,       setSearch]       = useState('')
  const [catFilter,    setCatFilter]    = useState('all')
  const [statusFilter, setStatusFilter] = useState(null) // 'issues'|'warnings'|'passed'|'optimize'
  const [selected,     setSelected]     = useState(null)
  const [checked,      setChecked]      = useState(new Set())

  const [fixing,      setFixing]      = useState(false)
  const [fixText,     setFixText]     = useState('')
  const [deployPanel, setDeployPanel] = useState(false)
  const fixBottomRef = useRef(null)

  // ── All existing logic preserved ──────────────────────────────────────────
  const runScan = useCallback(async () => {
    setScanning(true); setScanError(''); setTokenExpired(false)
    setFetchErrors({}); setSelected(null); setFixText('')
    try {
      const res = await fetch('/agents/org/scan', { credentials: 'include' })
      if (res.status === 401) { setTokenExpired(true); return }
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        throw new Error(d.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setScan(data)
      if (data.fetch_errors && Object.keys(data.fetch_errors).length > 0) {
        const errors = data.fetch_errors
        if (Object.values(errors).every(e => e.includes('401'))) { setTokenExpired(true); return }
        setFetchErrors(errors)
      }
    } catch (e) { setScanError(e.message) }
    finally { setScanning(false) }
  }, [])

  useEffect(() => { if (auth) runScan() }, [auth, runScan])
  useEffect(() => { fixBottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [fixText])

  const allComps = scan ? [
    ...(scan.components.omniscripts || []).map(c => ({ ...c, type: 'OmniScript',
      issues: scan.issues.filter(i => i.component === c.name && i.component_type === 'OmniScript') })),
    ...(scan.components.dataraptors || []).map(c => ({ ...c, type: 'DataRaptor',
      issues: scan.issues.filter(i => i.component === c.name && i.component_type === 'DataRaptor') })),
    ...(scan.components.integration_procedures || []).map(c => ({ ...c, type: 'Integration Procedure',
      issues: scan.issues.filter(i => i.component === c.name && i.component_type === 'Integration Procedure') })),
    ...(scan.components.data_mappers || []).map(c => ({ ...c, type: 'Data Mapper',
      issues: scan.issues.filter(i => i.component === c.name && i.component_type === 'Data Mapper') })),
    ...(scan.components.flexcards || []).map(c => ({ ...c, type: 'FlexCard',
      issues: scan.issues.filter(i => i.component === c.name && i.component_type === 'FlexCard') })),
    ...(scan.components.business_rules || []).map(c => ({ ...c, type: 'Business Rule',
      issues: scan.issues.filter(i => i.component === c.name && i.component_type === 'Business Rule') })),
    ...(scan.components.cml_rules || []).map(c => ({ ...c, type: 'CML Rule',
      issues: scan.issues.filter(i => i.component === c.name && i.component_type === 'CML Rule') })),
    ...(scan.components.flows || []).map(c => ({ ...c, type: 'Flow',
      issues: scan.issues.filter(i => i.component === c.name && i.component_type === 'Flow') })),
    ...(scan.components.apex_classes || []).map(c => ({ ...c, type: 'Apex Class',
      issues: scan.issues.filter(i => i.component === c.name && i.component_type === 'Apex Class') })),
    ...(scan.components.apex_triggers || []).map(c => ({ ...c, type: 'Apex Trigger',
      issues: scan.issues.filter(i => i.component === c.name && i.component_type === 'Apex Trigger') })),
    ...(scan.components.custom_objects || []).map(c => ({ ...c, type: 'Custom Object',
      issues: scan.issues.filter(i => i.component === c.name && i.component_type === 'Custom Object') })),
    // SOQL: virtual entries derived from SOQL issues (one row per apex class with SOQL findings)
    ...Array.from(new Set(scan.issues.filter(i => i.component_type === 'SOQL').map(i => i.component)))
      .map(name => ({ name, id: name, type: 'SOQL',
        issues: scan.issues.filter(i => i.component === name && i.component_type === 'SOQL') })),
    // Org Limits
    ...Array.from(new Set(scan.issues.filter(i => i.component_type === 'Org Limit').map(i => i.component)))
      .map(limitKey => ({ name: limitKey, id: limitKey, type: 'Org Limit',
        issues: scan.issues.filter(i => i.component === limitKey && i.component_type === 'Org Limit') })),
  ] : []

  const catDef = CATEGORIES.find(c => c.id === catFilter)
  const filteredComps = allComps.filter(c => {
    if (search && !c.name.toLowerCase().includes(search.toLowerCase())) return false
    if (catFilter !== 'all' && catDef?.types && !catDef.types.includes(c.type)) return false
    if (statusFilter === 'issues')   return c.issues.some(i => i.severity === 'high')
    if (statusFilter === 'warnings') return c.issues.some(i => i.severity === 'medium') && !c.issues.some(i => i.severity === 'high')
    if (statusFilter === 'passed')   return c.issues.length === 0
    if (statusFilter === 'optimize') return c.type === 'SOQL' || c.issues.some(i => i.severity === 'medium')
    return true
  })

  const catCount = (cat) => {
    if (!cat.types) return allComps.length
    return allComps.filter(c => cat.types.includes(c.type)).length
  }

  function selectComponent(comp) {
    setSelected(comp); setFixText('')
    setChecked(new Set(comp.issues.map((_, i) => i).filter(i => comp.issues[i].severity === 'high')))
  }
  function toggleIssue(idx) {
    setChecked(prev => { const n = new Set(prev); n.has(idx) ? n.delete(idx) : n.add(idx); return n })
  }

  async function getFixInstructions() {
    if (!selected || checked.size === 0) return
    const agentId = AGENT_ID[selected.type] || 'general_expert'
    const chosenIssues = selected.issues.filter((_, i) => checked.has(i))
    const issueList = chosenIssues.map(i => `• ${i.issue}`).join('\n')
    const prompt =
      `Provide specific, step-by-step fix instructions for the ${selected.type} named "${selected.name}".\n\n` +
      `Issues to resolve:\n${issueList}\n\nFor each issue:\n` +
      `1. Explain exactly what to change\n2. Show before/after configuration\n3. Explain the improvement\nBe direct and specific.`
    setFixing(true); setFixText('')
    try {
      const res = await fetch(`/chat/${agentId}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
        body: JSON.stringify({ messages: [{ role: 'user', content: prompt }], org_context: true }),
      })
      if (res.status === 401) { setFixText('⚠️ Session expired. Reconnect your org in Settings.'); return }
      if (!res.ok) { const d = await res.json().catch(() => ({})); setFixText(`Error: ${d.detail || res.status}`); return }
      const reader = res.body.getReader(); const decoder = new TextDecoder(); let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n'); buf = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (raw === '[DONE]') break
          try { const p = JSON.parse(raw); if (p.text) setFixText(prev => prev + p.text); if (p.error) setFixText(prev => prev + `\n⚠️ ${p.error}`) } catch (_) {}
        }
      }
    } catch (e) { setFixText(`Error: ${e.message}`) }
    finally { setFixing(false) }
  }

  const summary = scan?.summary
  const issuesCount  = summary?.high  || 0
  const warnCount    = summary?.medium || 0
  const totalComps   = summary?.total_components || 0
  const passedCount  = allComps.filter(c => c.issues.length === 0).length
  const optCount     = allComps.filter(c => c.type === 'SOQL' || c.issues.some(i => i.severity === 'medium')).length

  // Derived counts for action cards
  const criticalComps  = allComps.filter(c => c.issues.some(i => i.severity === 'high'))
  const warningComps   = allComps.filter(c => c.issues.some(i => i.severity === 'medium') && !c.issues.some(i => i.severity === 'high'))

  // ── 4 action handlers ─────────────────────────────────────────────────────
  function handleIdentify() {
    setDeployPanel(false)
    setSelected(null)
    setCatFilter('all')
    runScan()
  }

  function handleFix() {
    setDeployPanel(false)
    const first = criticalComps[0]
    if (first) { setCatFilter('all'); selectComponent(first) }
  }

  function handleDeploy() {
    setSelected(null)
    setDeployPanel(true)
  }

  function handleImprove() {
    setDeployPanel(false)
    const first = warningComps[0]
    if (first) { setCatFilter('all'); selectComponent(first) }
  }

  // ── Not connected ──────────────────────────────────────────────────────────
  if (!auth) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: LIGHT_BG, flexDirection: 'column', gap: 14 }}>
        <div style={{ fontSize: 48 }}>🔌</div>
        <div style={{ fontSize: 18, fontWeight: 700, color: TEXT_DARK }}>No Salesforce org connected</div>
        <div style={{ fontSize: 13, color: TEXT_MID, marginBottom: 4 }}>Connect your org to scan and analyze components.</div>
        <button onClick={onConnectOrg} style={{
          padding: '10px 24px', background: `linear-gradient(135deg,${ACCENT},#0891b2)`,
          border: 'none', borderRadius: 9, color: 'white', fontWeight: 700, fontSize: 14, cursor: 'pointer',
        }}>Connect Org</button>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%',
      background: LIGHT_BG, overflow: 'hidden' }}>

      {/* ── PAGE HEADER ─────────────────────────────────────────────────── */}
      <div style={{ background: CARD_BG, borderBottom: `1px solid ${BORDER}`,
        padding: '16px 24px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <img src="/proworker-logo.png" alt="ProWorker"
              style={{ width: 48, height: 48, borderRadius: 12, objectFit: 'cover', flexShrink: 0, boxShadow: '0 4px 12px rgba(6,182,212,0.3)' }}
            />
            <div>
              <div style={{ fontSize: 20, fontWeight: 800, color: TEXT_DARK, lineHeight: 1.1 }}>ProWorker</div>
              <div style={{ fontSize: 12, color: TEXT_MID, marginTop: 2 }}>
                Analyze your Salesforce org for best practice violations, risks and inefficiencies.
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button
              onClick={runScan} disabled={scanning}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '9px 20px', borderRadius: 9, border: 'none', cursor: 'pointer',
                background: scanning ? BORDER : 'linear-gradient(135deg,#2563eb,#1d4ed8)',
                color: scanning ? TEXT_MID : 'white', fontSize: 13, fontWeight: 700,
              }}
            >
              {scanning
                ? <><span style={{ display:'inline-block', animation:'scanSpin 1s linear infinite' }}>⟳</span> Scanning…</>
                : <><span>▶</span> Scan Now</>}
            </button>
            <button style={{
              width: 36, height: 36, borderRadius: 8, border: `1px solid ${BORDER}`,
              background: CARD_BG, cursor: 'pointer', fontSize: 16,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>⚙</button>
          </div>
        </div>
      </div>

      {/* ── STAT CARDS ──────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 12, padding: '14px 24px',
        flexShrink: 0, flexWrap: 'wrap' }}>
        <StatCard icon="🚨" iconBg="rgba(239,68,68,0.12)"   number={issuesCount} label="Issues Found"              color={RED}
          active={statusFilter==='issues'}
          onClick={() => { setStatusFilter(s => s==='issues' ? null : 'issues'); setSelected(null); setDeployPanel(false) }} />
        <StatCard icon="⚠️" iconBg="rgba(249,115,22,0.12)" number={warnCount}   label="Warnings"                  color={ORANGE}
          active={statusFilter==='warnings'}
          onClick={() => { setStatusFilter(s => s==='warnings' ? null : 'warnings'); setSelected(null); setDeployPanel(false) }} />
        <StatCard icon="✅" iconBg="rgba(34,197,94,0.12)"   number={passedCount} label="Passed Checks"             color={GREEN}
          active={statusFilter==='passed'}
          onClick={() => { setStatusFilter(s => s==='passed' ? null : 'passed'); setSelected(null); setDeployPanel(false) }} />
        <StatCard icon="📈" iconBg="rgba(168,85,247,0.12)" number={optCount}    label="Optimization Opportunities" color={PURPLE}
          active={statusFilter==='optimize'}
          onClick={() => { setStatusFilter(s => s==='optimize' ? null : 'optimize'); setSelected(null); setDeployPanel(false) }} />
      </div>

      {/* ── ERRORS ──────────────────────────────────────────────────────── */}
      {tokenExpired && (
        <div style={{ margin: '0 24px 10px', padding: '10px 14px',
          background: 'rgba(234,179,8,0.1)', border: '1px solid rgba(234,179,8,0.3)', borderRadius: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#fde68a' }}>⚠️ Session expired — </span>
          <button onClick={onConnectOrg} style={{ fontSize: 13, color: ACCENT, background: 'none',
            border: 'none', cursor: 'pointer', textDecoration: 'underline', fontWeight: 600 }}>
            Reconnect org
          </button>
        </div>
      )}
      {scanError && (
        <div style={{ margin: '0 24px 10px', padding: '10px 14px',
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8,
          fontSize: 13, color: '#fca5a5' }}>{scanError}</div>
      )}

      {/* ── 3-COLUMN BODY ───────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', margin: '0 24px 24px',
        background: CARD_BG, border: `1px solid ${BORDER}`, borderRadius: 14 }}>

        {/* LEFT: Category nav */}
        <div style={{ width: 210, flexShrink: 0, borderRight: `1px solid ${BORDER}`,
          overflowY: 'auto', background: CARD_BG }}>
          <div style={{ padding: '14px 16px', borderBottom: `1px solid ${BORDER}` }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: TEXT_DARK }}>
              Components {scan ? `(${allComps.length})` : ''}
            </div>
          </div>
          {CATEGORIES.map(cat => {
            const count = catCount(cat)
            if (cat.id !== 'all' && count === 0) return null
            const active = catFilter === cat.id && !statusFilter
            return (
              <button key={cat.id} onClick={() => { setCatFilter(cat.id); setStatusFilter(null) }} style={{
                width: '100%', height: 40, padding: '0 16px', display: 'flex',
                alignItems: 'center', gap: 10, border: 'none', cursor: 'pointer',
                background: active ? `${cat.color}18` : 'transparent',
                borderLeft: `3px solid ${active ? cat.color : 'transparent'}`,
                transition: 'all 0.12s',
              }}>
                <span style={{
                  width: 24, height: 24, borderRadius: 6, flexShrink: 0, fontSize: 13,
                  background: active ? cat.color : 'var(--surface-hi)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: active ? 'white' : cat.color,
                }}>{cat.icon}</span>
                <span style={{ flex: 1, fontSize: 13, fontWeight: active ? 600 : 400,
                  color: active ? cat.color : TEXT_DARK, textAlign: 'left' }}>{cat.label}</span>
                <span style={{
                  fontSize: 11, fontWeight: 700, padding: '1px 7px', borderRadius: 20,
                  background: active ? cat.color : 'var(--surface-hi)',
                  color: active ? 'white' : TEXT_MID,
                }}>{count}</span>
              </button>
            )
          })}

        </div>

        {/* CENTER: Component list */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column',
          background: LIGHT_BG, borderRight: `1px solid ${BORDER}`, overflow: 'hidden' }}>
          {/* Search + filter bar */}
          <div style={{ padding: '12px 14px', borderBottom: `1px solid ${BORDER}`,
            display: 'flex', gap: 8, flexShrink: 0, background: CARD_BG }}>
            <div style={{ flex: 1, position: 'relative' }}>
              <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
                fontSize: 13, color: TEXT_MID }}>🔍</span>
              <input value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Search components..."
                style={{ width: '100%', height: 34, paddingLeft: 30, paddingRight: 10,
                  background: CARD_BG, border: `1px solid ${BORDER}`, borderRadius: 8,
                  color: TEXT_DARK, fontSize: 13, outline: 'none', boxSizing: 'border-box' }} />
            </div>
            <button style={{ padding: '0 12px', height: 34, border: `1px solid ${BORDER}`,
              borderRadius: 8, background: CARD_BG, fontSize: 12, color: TEXT_MID,
              cursor: 'pointer', whiteSpace: 'nowrap' }}>▼ All</button>
          </div>

          {/* Active status filter banner */}
          {statusFilter && (() => {
            const META = {
              issues:   { label: 'Issues Found',              color: RED,    icon: '🚨' },
              warnings: { label: 'Warnings',                  color: ORANGE, icon: '⚠️' },
              passed:   { label: 'Passed Checks',             color: GREEN,  icon: '✅' },
              optimize: { label: 'Optimization Opportunities',color: PURPLE, icon: '📈' },
            }
            const m = META[statusFilter]
            return (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 14px',
                background: `${m.color}10`, borderBottom: `1px solid ${m.color}30`, flexShrink: 0 }}>
                <span style={{ fontSize: 13 }}>{m.icon}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: m.color, flex: 1 }}>
                  Showing: {m.label} ({filteredComps.length})
                </span>
                <button onClick={() => setStatusFilter(null)} style={{
                  background: 'none', border: 'none', color: m.color,
                  fontSize: 12, cursor: 'pointer', fontWeight: 700, padding: '2px 6px',
                  borderRadius: 4, lineHeight: 1,
                }}>✕ Clear</button>
              </div>
            )
          })()}

          {/* Component rows */}
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {scanning && (
              <div style={{ padding: '40px 20px', textAlign: 'center', color: TEXT_MID, fontSize: 13 }}>
                Fetching org components…
              </div>
            )}
            {!scanning && filteredComps.length === 0 && (
              <div style={{ padding: '40px 20px', textAlign: 'center', color: TEXT_MID, fontSize: 13 }}>
                {scan ? 'No components found' : 'Run a scan to see components'}
              </div>
            )}
            {filteredComps.map((comp, i) => {
              const m = TYPE_META[comp.type] || {}
              const isSelected = selected?.name === comp.name && selected?.type === comp.type
              return (
                <div key={i} onClick={() => selectComponent(comp)} style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '11px 14px', cursor: 'pointer',
                  background: isSelected ? 'rgba(6,182,212,0.1)' : 'transparent',
                  borderLeft: `3px solid ${isSelected ? ACCENT : 'transparent'}`,
                  borderBottom: `1px solid ${BORDER}`,
                  transition: 'all 0.1s',
                }}>
                  <div style={{
                    width: 34, height: 34, borderRadius: 8, flexShrink: 0,
                    background: m.bg || 'var(--surface-hi)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16,
                  }}>{m.icon || '•'}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: TEXT_DARK,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {comp.type}: {comp.name}
                    </div>
                    <div style={{ fontSize: 11, color: TEXT_MID, marginTop: 1, display: 'flex', alignItems: 'center', gap: 5 }}>
                      {comp.sub_type || comp.interface_type || m.label || comp.type}
                      {comp.type === 'Business Rule' && comp.is_active === false && (
                        <span style={{ fontSize: 10, fontWeight: 700, color: '#f97316', background: 'rgba(249,115,22,0.12)', borderRadius: 4, padding: '0px 5px' }}>INACTIVE</span>
                      )}
                    </div>
                  </div>
                  <StatusBadge issues={comp.issues} />
                  <span style={{ color: TEXT_MID, fontSize: 14, marginLeft: 4 }}>›</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* RIGHT: Detail panel */}
        <div style={{ width: 480, flexShrink: 0, overflowY: deployPanel ? 'hidden' : 'auto', background: CARD_BG, display: 'flex', flexDirection: 'column' }}>
          {deployPanel ? (
            <DeployPanel
              onNavigateMigrate={() => onNavigate?.('migrate')}
              onBack={() => setDeployPanel(false)}
            />
          ) : !selected ? (
            <EmptyRightPanel
              onIdentify={handleIdentify}
              onFix={handleFix}
              onDeploy={handleDeploy}
              onImprove={handleImprove}
              hasScan={!!scan}
              hasIssues={criticalComps.length}
              hasWarnings={warningComps.length}
              scanning={scanning}
            />
          ) : (
            <div style={{ padding: '20px 20px 48px' }}>
              {/* Back button */}
              <button
                onClick={() => { setSelected(null); setFixText('') }}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  marginBottom: 14, background: 'none',
                  border: `1px solid ${BORDER}`, borderRadius: 8,
                  color: TEXT_MID, fontSize: 12, fontWeight: 600,
                  padding: '5px 12px', cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = ACCENT; e.currentTarget.style.color = ACCENT }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = BORDER; e.currentTarget.style.color = TEXT_MID }}
              >
                ← Back
              </button>

              {/* Component header */}
              <div style={{ background: LIGHT_BG, border: `1px solid ${BORDER}`,
                borderRadius: 10, padding: '14px 16px', marginBottom: 18 }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                  <TypeChip type={selected.type} />
                  {selected.issues.filter(i => i.severity === 'high').length > 0 && (
                    <span style={badge(RED, 'rgba(239,68,68,0.12)')}>
                      {selected.issues.filter(i => i.severity === 'high').length} critical
                    </span>
                  )}
                  {selected.issues.filter(i => i.severity === 'medium').length > 0 && (
                    <span style={badge(ORANGE, 'rgba(249,115,22,0.12)')}>
                      {selected.issues.filter(i => i.severity === 'medium').length} warnings
                    </span>
                  )}
                  {selected.issues.length === 0 && (
                    <span style={badge(GREEN, 'rgba(34,197,94,0.12)')}>✓ Clean</span>
                  )}
                </div>
                <div style={{ fontSize: 16, fontWeight: 700, color: TEXT_DARK }}>{selected.name}</div>
                {(selected.sub_type || selected.interface_type) && (
                  <div style={{ fontSize: 12, color: TEXT_MID, marginTop: 2, display: 'flex', alignItems: 'center', gap: 6 }}>
                    {selected.sub_type || selected.interface_type}
                    {selected.type === 'Business Rule' && selected.is_active === false && (
                      <span style={{ fontSize: 10, fontWeight: 700, color: '#f97316', background: 'rgba(249,115,22,0.12)', borderRadius: 4, padding: '1px 6px' }}>INACTIVE</span>
                    )}
                    {selected.type === 'Business Rule' && selected.status && (
                      <span style={{ fontSize: 10, fontWeight: 700, color: '#06b6d4', background: 'rgba(6,182,212,0.1)', borderRadius: 4, padding: '1px 6px' }}>{selected.status}</span>
                    )}
                  </div>
                )}
              </div>

              {/* Org Limit bar */}
              {selected.type === 'Org Limit' && scan?.org_limits?.[selected.name] && (() => {
                const lim = scan.org_limits[selected.name]
                const barC = lim.pct >= 90 ? RED : lim.pct >= 75 ? ORANGE : GREEN
                return (
                  <div style={{ background: LIGHT_BG, border: `1px solid ${BORDER}`,
                    borderRadius: 10, padding: '14px 16px', marginBottom: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontSize: 12, color: TEXT_MID }}>Used</span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: barC }}>{lim.pct}%</span>
                    </div>
                    <div style={{ background: BORDER, borderRadius: 6, height: 8, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${lim.pct}%`, background: barC,
                        borderRadius: 6, transition: 'width 0.4s' }} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 5 }}>
                      <span style={{ fontSize: 11, color: TEXT_MID }}>{lim.used?.toLocaleString()} used</span>
                      <span style={{ fontSize: 11, color: TEXT_MID }}>{lim.max?.toLocaleString()} max</span>
                    </div>
                  </div>
                )
              })()}

              {/* Issues */}
              {selected.issues.length === 0 ? (
                <div style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.25)',
                  borderRadius: 10, padding: '14px 16px', color: GREEN,
                  fontSize: 13, textAlign: 'center', marginBottom: 16 }}>
                  ✅ No performance issues detected for this component
                </div>
              ) : (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: TEXT_MID,
                    textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>
                    Performance Issues — select to fix
                  </div>
                  {selected.issues.map((issue, idx) => {
                    const isChecked = checked.has(idx)
                    const isHigh = issue.severity === 'high'
                    const sevColor = isHigh ? RED : ORANGE
                    return (
                      <div key={idx} onClick={() => toggleIssue(idx)} style={{
                        display: 'flex', gap: 10, padding: '12px 13px', marginBottom: 7,
                        background: isChecked ? (isHigh ? 'rgba(239,68,68,0.12)' : 'rgba(249,115,22,0.12)') : 'transparent',
                        border: `1px solid ${isChecked ? (isHigh ? 'rgba(239,68,68,0.35)' : 'rgba(249,115,22,0.35)') : BORDER}`,
                        borderLeft: `3px solid ${sevColor}`,
                        borderRadius: 8, cursor: 'pointer', transition: 'all 0.12s',
                      }}>
                        <div style={{
                          width: 17, height: 17, borderRadius: 4, flexShrink: 0, marginTop: 2,
                          background: isChecked ? ACCENT : 'transparent',
                          border: `2px solid ${isChecked ? ACCENT : BORDER}`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                          {isChecked && <span style={{ color: 'white', fontSize: 10, lineHeight: 1 }}>✓</span>}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                            <span style={{ fontSize: 10, fontWeight: 700, color: sevColor,
                              background: isHigh ? 'rgba(239,68,68,0.15)' : 'rgba(249,115,22,0.15)',
                              borderRadius: 20, padding: '1px 7px' }}>
                              {isHigh ? '● Critical' : '⚠ Warning'}
                            </span>
                          </div>
                          <div style={{ fontSize: 12, color: TEXT_DARK, lineHeight: 1.5, marginBottom: 3 }}>
                            {issue.issue}
                          </div>
                          <div style={{ fontSize: 11, color: TEXT_MID, fontStyle: 'italic' }}>
                            Fix: {issue.fix}
                          </div>
                        </div>
                      </div>
                    )
                  })}

                  <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
                    <button onClick={getFixInstructions}
                      disabled={checked.size === 0 || fixing}
                      style={{
                        padding: '9px 18px',
                        background: checked.size === 0 || fixing ? BORDER
                          : `linear-gradient(135deg,${ACCENT},#0891b2)`,
                        border: 'none', borderRadius: 8,
                        color: checked.size === 0 || fixing ? TEXT_MID : 'white',
                        fontSize: 13, fontWeight: 600,
                        cursor: checked.size === 0 || fixing ? 'not-allowed' : 'pointer',
                      }}>
                      {fixing ? '⟳ Analyzing…' : `🔧 Get Fix Instructions${checked.size > 0 ? ` (${checked.size})` : ''}`}
                    </button>
                    {checked.size === 0 && (
                      <span style={{ fontSize: 12, color: TEXT_MID }}>Select at least one issue</span>
                    )}
                  </div>
                </div>
              )}

              {/* AI Fix output */}
              {(fixText || fixing) && (
                <div style={{ background: CARD_BG, border: `1px solid ${BORDER}`, borderRadius: 10, overflow: 'hidden' }}>
                  <div style={{ padding: '9px 14px', borderBottom: `1px solid ${BORDER}`,
                    background: LIGHT_BG, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: ACCENT }}>🔧 AI Fix Instructions</span>
                    {fixing && <span style={{ fontSize: 11, color: TEXT_MID }}>generating…</span>}
                  </div>
                  <div style={{ padding: '14px 16px', fontSize: 13, color: TEXT_DARK,
                    lineHeight: 1.7, whiteSpace: 'pre-wrap', maxHeight: 480, overflowY: 'auto' }}>
                    {fixText}
                    {fixing && (
                      <span style={{ display: 'inline-block', width: 7, height: 13,
                        background: ACCENT, marginLeft: 2, borderRadius: 2,
                        animation: 'sfBlink 1s step-end infinite' }} />
                    )}
                    <div ref={fixBottomRef} />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes sfBlink { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes scanSpin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
        ::-webkit-scrollbar { width: 5px; height: 5px }
        ::-webkit-scrollbar-track { background: transparent }
        ::-webkit-scrollbar-thumb { background: var(--scroll-thumb); border-radius: 3px }
        ::-webkit-scrollbar-thumb:hover { background: var(--scroll-thumb-hover) }
      `}</style>
    </div>
  )
}
