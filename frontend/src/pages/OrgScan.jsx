import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

// ─── Design tokens ────────────────────────────────────────────────────────────
const BG      = 'var(--nav-bg)'
const SURFACE = 'var(--nav-surface)'
const CARD    = 'var(--nav-card)'
const BORDER  = 'var(--nav-border)'
const TEXT    = 'var(--text)'
const TEXT_MID= 'var(--text-mid)'
const TEXT_DIM= 'var(--text-dim)'

// Metric card configs
const METRICS = (s) => [
  { key:'total_components',      label:'Components Scanned', sub:'All components analyzed',    accent:'#06b6d4', subColor:'#22c55e', icon: CubeIcon,     grad:'linear-gradient(145deg,#0e2a3a,#071820)' },
  { key:'apex_classes',          label:'Apex Classes',       sub:(n)=>`${n} with issues`,      accent:'#f472b6', subColor:'#f472b6', icon: CodeIcon,     grad:'linear-gradient(145deg,#3a0f1a,#200810)' },
  { key:'apex_triggers',         label:'Apex Triggers',      sub:(n)=>`${n} with issues`,      accent:'#fbbf24', subColor:'#fbbf24', icon: BoltIcon,     grad:'linear-gradient(145deg,#3a2810,#201408)' },
  { key:'flows',                 label:'Flows',              sub:(n)=>`${n} with issues`,      accent:'#38bdf8', subColor:'#38bdf8', icon: FlowIcon,     grad:'linear-gradient(145deg,#0f1e3a,#070f20)' },
  { key:'custom_objects',        label:'Custom Objects',     sub:'No issues',                  accent:'#818cf8', subColor:'#22c55e', icon: DiamondIcon,  grad:'linear-gradient(145deg,#1a0f3a,#0e0720)' },
  { key:'omniscripts',           label:'OmniScripts',        sub:(n)=>`${n} with issues`,      accent:'#fb923c', subColor:'#fb923c', icon: GridIcon,     grad:'linear-gradient(145deg,#3a1c0f,#201008)' },
  { key:'dataraptors',           label:'DataRaptors',        sub:(n)=>`${n} with issues`,      accent:'#34d399', subColor:'#34d399', icon: DBIcon,       grad:'linear-gradient(145deg,#0f3a20,#082014)' },
  { key:'integration_procedures',label:'Integration Procs',  sub:(n)=>`${n} with issues`,      accent:'#fde68a', subColor:'#fde68a', icon: GearIcon,     grad:'linear-gradient(145deg,#3a2a0f,#201808)' },
  { key:'high',                  label:'Critical Issues',    sub:'Needs attention',            accent:'#ef4444', subColor:'#ef4444', icon: AlertIcon,    grad:'linear-gradient(145deg,#3a0f0f,#200808)' },
  { key:'medium',                label:'Warnings',           sub:'Review recommended',         accent:'#f59e0b', subColor:'#f59e0b', icon: WarnIcon,     grad:'linear-gradient(145deg,#3a2a0f,#201808)' },
]

// ─── SVG Icons ────────────────────────────────────────────────────────────────
const icon = (path, vb='0 0 24 24') => (color='white', size=22) => (
  <svg width={size} height={size} viewBox={vb} fill="none">
    {path.map((d,i) => <path key={i} d={d} stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />)}
  </svg>
)
const CubeIcon   = icon(['M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z','M3.27 6.96L12 12.01l8.73-5.05','M12 22.08V12'])
const CodeIcon   = icon(['M16 18l6-6-6-6','M8 6l-6 6 6 6'])
const BoltIcon   = icon(['M13 2L3 14h9l-1 8 10-12h-9l1-8z'])
const FlowIcon   = icon(['M22 12h-4l-3 9L9 3l-3 9H2'])
const DiamondIcon= icon(['M12 2l10 10-10 10L2 12z'])
const GridIcon   = icon(['M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z'])
const DBIcon     = icon(['M12 2C6.5 2 2 4 2 6.5v11C2 20 6.5 22 12 22s10-2 10-4.5v-11C22 4 17.5 2 12 2z','M2 6.5C2 9 6.5 11 12 11s10-2 10-4.5','M2 12c0 2.5 4.5 4.5 10 4.5s10-2 10-4.5'])
const GearIcon   = icon(['M12 15a3 3 0 100-6 3 3 0 000 6z','M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z'])
const AlertIcon  = icon(['M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z','M12 9v4','M12 17h.01'])
const WarnIcon   = icon(['M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9','M13.73 21a2 2 0 01-3.46 0'])
const RescanIcon = icon(['M23 4v6h-6','M1 20v-6h6','M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15'])
const ReportIcon = icon(['M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z','M14 2v6h6','M16 13H8','M16 17H8','M10 9H8'])
const TrendIcon  = icon(['M23 6l-9.5 9.5-5-5L1 18','M17 6h6v6'])

// ─── Type chip colours ────────────────────────────────────────────────────────
const TYPE_COLORS = {
  'OmniScript':             { bg:'rgba(251,146,60,0.15)',  color:'#fb923c',  border:'rgba(251,146,60,0.3)'  },
  'DataRaptor':             { bg:'rgba(52,211,153,0.15)',  color:'#34d399',  border:'rgba(52,211,153,0.3)'  },
  'Integration Procedure':  { bg:'rgba(253,230,138,0.15)', color:'#fde68a',  border:'rgba(253,230,138,0.3)' },
  'Apex Class':             { bg:'rgba(244,114,182,0.15)', color:'#f472b6',  border:'rgba(244,114,182,0.3)' },
  'Apex Trigger':           { bg:'rgba(251,191,36,0.15)',  color:'#fbbf24',  border:'rgba(251,191,36,0.3)'  },
  'Flow':                   { bg:'rgba(56,189,248,0.15)',  color:'#38bdf8',  border:'rgba(56,189,248,0.3)'  },
  'Custom Object':          { bg:'rgba(129,140,248,0.15)', color:'#818cf8',  border:'rgba(129,140,248,0.3)' },
  'Org Limit':              { bg:'rgba(148,163,184,0.15)', color:'#94a3b8',  border:'rgba(148,163,184,0.3)' },
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function MetricCard({ metric, value, issues }) {
  const [hovered, setHovered] = useState(false)
  const Icon = metric.icon
  const subText = typeof metric.sub === 'function' ? metric.sub(issues) : metric.sub
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        minWidth: 160, flex: '0 0 auto',
        background: metric.grad,
        border: `1px solid ${hovered ? metric.accent + '55' : metric.accent + '28'}`,
        borderRadius: 14, padding: '18px 18px 16px',
        cursor: 'pointer', transition: 'all 0.2s',
        transform: hovered ? 'translateY(-2px)' : 'none',
        boxShadow: hovered ? `0 8px 24px ${metric.accent}22` : 'none',
        position: 'relative', overflow: 'hidden',
      }}
    >
      {/* glow bg */}
      <div style={{
        position:'absolute', top:0, right:0, width:80, height:80,
        background: `radial-gradient(circle at 100% 0%, ${metric.accent}20, transparent 70%)`,
        pointerEvents:'none',
      }} />
      {/* arrow top-right */}
      <div style={{ position:'absolute', top:14, right:14, color: TEXT_DIM, fontSize:12 }}>›</div>
      {/* icon */}
      <div style={{ marginBottom:12 }}>
        {metric.icon(metric.accent, 24)}
      </div>
      {/* number */}
      <div style={{ fontSize:32, fontWeight:800, color:TEXT, lineHeight:1, letterSpacing:'-0.02em', marginBottom:6 }}>
        {(value ?? 0).toLocaleString()}
      </div>
      {/* label */}
      <div style={{ fontSize:13, color:TEXT_MID, fontWeight:500, marginBottom:6 }}>
        {metric.label}
      </div>
      {/* sub */}
      <div style={{ display:'flex', alignItems:'center', gap:5 }}>
        <div style={{ width:7, height:7, borderRadius:'50%', background: metric.subColor, flexShrink:0 }} />
        <span style={{ fontSize:11, color: metric.subColor, fontWeight:600 }}>{subText}</span>
      </div>
    </div>
  )
}

function TypeChip({ type }) {
  const c = TYPE_COLORS[type] || TYPE_COLORS['Org Limit']
  return (
    <span style={{
      fontSize:11, fontWeight:700, color:c.color,
      background:c.bg, border:`1px solid ${c.border}`,
      borderRadius:20, padding:'2px 9px', whiteSpace:'nowrap',
    }}>{type}</span>
  )
}

function SeverityBadge({ severity }) {
  const isHigh = severity === 'high'
  return (
    <div style={{
      display:'flex', alignItems:'center', gap:5,
      background: isHigh ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.15)',
      border: `1px solid ${isHigh ? 'rgba(239,68,68,0.35)' : 'rgba(245,158,11,0.35)'}`,
      borderRadius:20, padding:'3px 10px', flexShrink:0,
    }}>
      <div style={{
        width:14, height:14, borderRadius:'50%', flexShrink:0,
        background: isHigh ? '#ef4444' : '#f59e0b',
        display:'flex', alignItems:'center', justifyContent:'center',
        fontSize:8, fontWeight:800, color:'white',
      }}>
        {isHigh ? '!' : '⚠'}
      </div>
      <span style={{ fontSize:11, fontWeight:700, color: isHigh ? '#fca5a5' : '#fde68a' }}>
        {isHigh ? 'Critical' : 'Warning'}
      </span>
    </div>
  )
}

function IssueRow({ issue, onViewDetails }) {
  const [hovered, setHov] = useState(false)
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display:'flex', alignItems:'center', gap:12,
        padding:'14px 20px',
        background: hovered ? 'rgba(255,255,255,0.04)' : 'transparent',
        borderBottom: `1px solid ${BORDER}`,
        transition:'background 0.15s',
      }}
    >
      {/* Severity badge */}
      <SeverityBadge severity={issue.severity} />
      {/* Type chip */}
      <TypeChip type={issue.component_type} />
      {/* Name + sub-detail */}
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:13, fontWeight:700, color:TEXT, marginBottom:2,
          overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
          {issue.component}
        </div>
        <div style={{ fontSize:11, color:TEXT_DIM }}>
          {issue.component_type}{issue.fix ? ` · ${issue.fix.slice(0,60)}` : ''}
        </div>
      </div>
      {/* Description */}
      <div style={{ flex:1.2, minWidth:0, fontSize:13, color:TEXT_MID,
        overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
        {issue.issue}
      </div>
      {/* View Details button */}
      <button
        onClick={() => onViewDetails?.(issue)}
        style={{
          padding:'6px 14px', flexShrink:0,
          background: hovered ? 'rgba(99,102,241,0.2)' : SURFACE,
          border:`1px solid ${hovered ? 'rgba(99,102,241,0.5)' : BORDER}`,
          borderRadius:8, color: hovered ? '#818cf8' : TEXT_MID,
          fontSize:12, fontWeight:600, cursor:'pointer', transition:'all 0.15s',
        }}>
        View Details
      </button>
      <span style={{ color:TEXT_DIM, fontSize:14, flexShrink:0 }}>›</span>
    </div>
  )
}

function ProgressBar({ pct, color }) {
  return (
    <div style={{ height:4, background:'rgba(255,255,255,0.08)', borderRadius:2, overflow:'hidden', marginTop:6, width:'100%' }}>
      <div style={{
        height:'100%', width:`${Math.min(pct,100)}%`,
        background:`linear-gradient(90deg, ${color}, ${color}bb)`,
        borderRadius:2, transition:'width 1s ease',
      }} />
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function OrgScan({ auth, onConnectOrg }) {
  const navigate = useNavigate()
  const [scan, setScan]               = useState(null)
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState('')
  const [tokenExpired, setTokenExpired] = useState(false)
  const [activeTab, setActiveTab]     = useState('all')
  const [sortBy, setSortBy]           = useState('severity')

  const [deepScanning, setDeepScanning] = useState(false)
  const [deepProgress, setDeepProgress] = useState(null)
  const [deepError, setDeepError]       = useState('')
  const esRef = useRef(null)
  const [collapsed, setCollapsed] = useState({})
  const toggleSection = (key) => setCollapsed(prev => ({ ...prev, [key]: !prev[key] }))

  const runDeepScan = useCallback(async () => {
    setDeepScanning(true); setDeepError('')
    setDeepProgress({ status:'running', progress_pct:0, message:'Starting…' })
    try {
      const res = await fetch('/scan/start', { method:'POST', credentials:'include' })
      if (res.status === 401) { setDeepError('Session expired — reconnect in Settings.'); setDeepScanning(false); return }
      if (!res.ok) { const d = await res.json().catch(()=>({})); throw new Error(d.detail || `HTTP ${res.status}`) }
      const { scan_id } = await res.json()
      if (esRef.current) esRef.current.close()
      const es = new EventSource(`/scan/stream/${scan_id}`)
      esRef.current = es
      es.onmessage = (e) => {
        const data = JSON.parse(e.data)
        setDeepProgress(data)
        if (data.status === 'completed') { es.close(); esRef.current = null; setDeepScanning(false); navigate(`/report/${scan_id}`) }
        else if (data.status === 'failed') { es.close(); esRef.current = null; setDeepScanning(false); setDeepError(data.message || 'Scan failed'); setDeepProgress(null) }
      }
      es.onerror = () => { es.close(); esRef.current = null; setDeepScanning(false); setDeepError('Connection lost'); setDeepProgress(null) }
    } catch(e) { setDeepScanning(false); setDeepError(e.message); setDeepProgress(null) }
  }, [navigate])

  useEffect(() => () => { if (esRef.current) esRef.current.close() }, [])

  const runScan = useCallback(async () => {
    setLoading(true); setError(''); setTokenExpired(false)
    try {
      const res = await fetch('/agents/org/scan', { credentials:'include' })
      if (res.status === 401) { setTokenExpired(true); return }
      if (!res.ok) { const d = await res.json().catch(()=>({})); throw new Error(d.detail || `HTTP ${res.status}`) }
      setScan(await res.json())
    } catch(err) { setError(err.message) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { if (auth) runScan() }, [auth, runScan])

  if (!auth) return (
    <div style={{ background:BG, minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', flexDirection:'column', gap:16 }}>
      <div style={{ fontSize:48 }}>🔌</div>
      <div style={{ fontSize:18, fontWeight:700, color:TEXT }}>No Salesforce org connected</div>
      <div style={{ fontSize:14, color:TEXT_MID, marginBottom:8 }}>Connect your org to run a full scan.</div>
      <button onClick={onConnectOrg} style={{ padding:'10px 24px', background:'linear-gradient(135deg,#06b6d4,#0891b2)', border:'none', borderRadius:10, color:'white', fontWeight:700, fontSize:14, cursor:'pointer' }}>
        Connect Org
      </button>
    </div>
  )

  const s2 = scan?.summary
  const allIssues  = scan?.issues || []
  const highIssues = allIssues.filter(i => i.severity === 'high')
  const medIssues  = allIssues.filter(i => i.severity === 'medium')
  const attentionItems = scan?.attention || []
  const total = s2?.total_components || 0
  const clean = Math.max(0, total - (s2?.attention_required || 0))
  const cleanPct   = total ? (clean / total) * 100 : 0
  const highPct    = total ? ((s2?.high||0) / total) * 100 : 0
  const medPct     = total ? ((s2?.medium||0) / total) * 100 : 0

  const tabIssues = activeTab === 'all' ? allIssues : activeTab === 'high' ? highIssues : medIssues
  const sortedIssues = [...tabIssues].sort((a,b) => {
    if (sortBy === 'severity') return (a.severity==='high' ? 0:1) - (b.severity==='high' ? 0:1)
    return a.component.localeCompare(b.component)
  })

  const scanTime = scan ? new Date().toLocaleString('en-US', { month:'short', day:'numeric', year:'numeric', hour:'2-digit', minute:'2-digit' }) : null

  return (
    <div style={{ background:BG, height:'100%', overflowY:'auto', overscrollBehavior:'none', fontFamily:'system-ui,-apple-system,sans-serif' }}>
      <style>{`
        @keyframes spin { to { transform:rotate(360deg) } }
        @keyframes fadeUp { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
        .orgscan-row { animation: fadeUp .3s ease both; }
        ::-webkit-scrollbar { width:5px; height:5px; }
        ::-webkit-scrollbar-track { background:transparent; }
        ::-webkit-scrollbar-thumb { background:var(--scroll-thumb); border-radius:3px; }
      `}</style>

      <div style={{ padding:'28px 24px 60px' }}>

        {/* ── HEADER ── */}
        <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:24, flexWrap:'wrap', gap:16 }}>
          <div>
            <h1 style={{ fontSize:28, fontWeight:800, color:TEXT, margin:'0 0 10px', letterSpacing:'-0.02em' }}>
              Assessment Report
            </h1>
            <div style={{ display:'flex', alignItems:'center', gap:12, flexWrap:'wrap' }}>
              {scan && !loading && (
                <div style={{ display:'flex', alignItems:'center', gap:6, background:'rgba(34,197,94,0.12)', border:'1px solid rgba(34,197,94,0.3)', borderRadius:20, padding:'4px 12px' }}>
                  <div style={{ width:7, height:7, borderRadius:'50%', background:'#22c55e', boxShadow:'0 0 6px #22c55e' }} />
                  <span style={{ fontSize:12, fontWeight:700, color:'#86efac' }}>Scan Completed</span>
                </div>
              )}
              {loading && (
                <div style={{ display:'flex', alignItems:'center', gap:6, background:'rgba(6,182,212,0.12)', border:'1px solid rgba(6,182,212,0.3)', borderRadius:20, padding:'4px 12px' }}>
                  <span style={{ display:'inline-block', animation:'spin 0.8s linear infinite', fontSize:12 }}>⟳</span>
                  <span style={{ fontSize:12, fontWeight:700, color:'#67e8f9' }}>Scanning…</span>
                </div>
              )}
              {scanTime && <span style={{ fontSize:13, color:TEXT_DIM }}>Last scanned: {scanTime}</span>}
            </div>
            {scan?.instance_url && (
              <a href={scan.instance_url} target="_blank" rel="noreferrer"
                style={{ fontSize:13, color:'#38bdf8', marginTop:8, display:'block', textDecoration:'none' }}>
                {scan.instance_url}
              </a>
            )}
          </div>
          <div style={{ display:'flex', gap:10, alignItems:'center' }}>
            <button onClick={runScan} disabled={loading||deepScanning} style={{
              display:'flex', alignItems:'center', gap:8,
              padding:'10px 20px', background:'transparent',
              border:`1px solid ${BORDER}`, borderRadius:10,
              color:TEXT, fontSize:13, fontWeight:600,
              cursor: loading||deepScanning ? 'not-allowed':'pointer',
              opacity: loading||deepScanning ? 0.5:1,
            }}>
              <span style={{ display:'inline-block', animation: loading ? 'spin 0.8s linear infinite':undefined, fontSize:15 }}>↻</span>
              {loading ? 'Scanning…':'Rescan'}
            </button>
            <button onClick={runDeepScan} disabled={deepScanning||loading} style={{
              display:'flex', alignItems:'center', gap:8,
              padding:'10px 20px',
              background: deepScanning ? SURFACE : 'linear-gradient(135deg,#2563eb,#1d4ed8)',
              border: deepScanning ? `1px solid ${BORDER}` : 'none',
              borderRadius:10, color:'white',
              fontSize:13, fontWeight:700,
              cursor: deepScanning||loading ? 'not-allowed':'pointer',
              boxShadow: deepScanning ? 'none':'0 0 20px rgba(37,99,235,0.4)',
            }}>
              {deepScanning
                ? <span style={{ animation:'spin 0.8s linear infinite', display:'inline-block', fontSize:15 }}>⟳</span>
                : ReportIcon('white', 16)}
              {deepScanning ? `${deepProgress?.progress_pct||0}%  Scanning…` : 'Deep Scan + Report ▾'}
            </button>
          </div>
        </div>

        {/* ── DEEP SCAN PROGRESS ── */}
        {deepScanning && deepProgress && (
          <div style={{ background:SURFACE, border:`1px solid ${BORDER}`, borderRadius:12, padding:'16px 20px', marginBottom:20 }}>
            <div style={{ display:'flex', justifyContent:'space-between', marginBottom:8 }}>
              <span style={{ fontSize:13, color:TEXT_MID }}>{deepProgress.message || 'Scanning…'}</span>
              <span style={{ fontSize:13, fontWeight:700, color:'#38bdf8' }}>{deepProgress.progress_pct}%</span>
            </div>
            <ProgressBar pct={deepProgress.progress_pct} color='#2563eb' />
          </div>
        )}

        {/* Errors */}
        {(deepError||error) && (
          <div style={{ background:'rgba(239,68,68,0.08)', border:'1px solid rgba(239,68,68,0.25)', borderRadius:10, padding:'12px 18px', color:'#fca5a5', fontSize:13, marginBottom:20 }}>
            {deepError||error}
          </div>
        )}
        {tokenExpired && (
          <div style={{ background:'rgba(245,158,11,0.08)', border:'1px solid rgba(245,158,11,0.25)', borderRadius:12, padding:'18px 22px', marginBottom:20 }}>
            <div style={{ fontSize:15, fontWeight:700, color:'#fde68a', marginBottom:8 }}>⚠️ Session token expired</div>
            <div style={{ fontSize:13, color:TEXT_MID, lineHeight:1.8, marginBottom:14 }}>
              1. Open your org in a browser tab<br/>
              2. DevTools (F12) → Application → Cookies → copy the <strong style={{color:'#fde68a'}}>sid</strong> value<br/>
              3. Paste it in Settings → Session Token
            </div>
            <button onClick={onConnectOrg} style={{ padding:'8px 18px', background:'linear-gradient(135deg,#06b6d4,#0891b2)', border:'none', borderRadius:8, color:'white', fontWeight:700, fontSize:13, cursor:'pointer' }}>
              Reconnect Org
            </button>
          </div>
        )}

        {/* Loading placeholder */}
        {loading && !scan && (
          <div style={{ textAlign:'center', color:TEXT_MID, padding:'80px 0', fontSize:15 }}>
            <div style={{ fontSize:36, marginBottom:16, animation:'spin 1.5s linear infinite', display:'inline-block' }}>⟳</div>
            <div>Fetching org components and analyzing performance…</div>
          </div>
        )}

        {scan && s2 && (
          <>
            {/* ── METRIC CARDS ── */}
            <div style={{ background:SURFACE, border:`1px solid ${BORDER}`, borderRadius:16, marginBottom:20, overflow:'hidden' }}>
              <div onClick={() => toggleSection('metrics')} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'14px 20px', cursor:'pointer', borderBottom: collapsed.metrics ? 'none' : `1px solid ${BORDER}` }}>
                <div style={{ display:'flex', alignItems:'center', gap:10 }}>
                  <div style={{ width:30, height:30, borderRadius:8, background:'rgba(6,182,212,0.12)', border:'1px solid rgba(6,182,212,0.25)', display:'flex', alignItems:'center', justifyContent:'center' }}>
                    {CubeIcon('#06b6d4', 15)}
                  </div>
                  <span style={{ fontSize:14, fontWeight:700, color:TEXT }}>Component Metrics</span>
                </div>
                <span style={{ fontSize:16, color:TEXT_MID, transform: collapsed.metrics ? 'rotate(-90deg)' : 'none', transition:'transform 0.2s' }}>⌄</span>
              </div>
              {!collapsed.metrics && (
                <div style={{ display:'flex', gap:12, overflowX:'auto', padding:'16px 20px 12px', scrollbarWidth:'none', msOverflowStyle:'none' }}>
                  {METRICS(s2).map((m) => (
                    <MetricCard key={m.key} metric={m} value={s2[m.key] ?? 0} issues={s2[m.key] ?? 0} />
                  ))}
                </div>
              )}
            </div>

            {/* ── ISSUES SUMMARY BAR ── */}
            <div style={{ background:SURFACE, border:`1px solid ${BORDER}`, borderRadius:16, marginBottom:20, overflow:'hidden' }}>
              <div onClick={() => toggleSection('summary')} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'14px 20px', cursor:'pointer', borderBottom: collapsed.summary ? 'none' : `1px solid ${BORDER}` }}>
                <div style={{ display:'flex', alignItems:'center', gap:10 }}>
                  <div style={{ width:30, height:30, borderRadius:8, background:'rgba(255,255,255,0.06)', display:'flex', alignItems:'center', justifyContent:'center' }}>
                    {FlowIcon(TEXT_MID, 15)}
                  </div>
                  <span style={{ fontSize:14, fontWeight:700, color:TEXT }}>Issues Summary</span>
                </div>
                <span style={{ fontSize:16, color:TEXT_MID, transform: collapsed.summary ? 'rotate(-90deg)' : 'none', transition:'transform 0.2s' }}>⌄</span>
              </div>
              {!collapsed.summary && (
                <div style={{ padding:'20px 28px', display:'flex', alignItems:'center', gap:28, flexWrap:'wrap' }}>
                  {/* Stats */}
                  <div style={{ display:'flex', gap:32, flex:1, flexWrap:'wrap' }}>
                    {[
                      { num:s2.high,   label:'Critical', color:'#ef4444', pct:highPct  },
                      { num:s2.medium, label:'Warnings',  color:'#f59e0b', pct:medPct   },
                      { num:clean,     label:'Clean',     color:'#22c55e', pct:cleanPct },
                    ].map(item => (
                      <div key={item.label} style={{ minWidth:120 }}>
                        <div style={{ fontSize:32, fontWeight:800, color:item.color, letterSpacing:'-0.02em', lineHeight:1 }}>
                          {item.num?.toLocaleString() ?? 0}
                        </div>
                        <div style={{ fontSize:12, color:TEXT_MID, fontWeight:600, marginTop:4 }}>{item.label}</div>
                        <ProgressBar pct={item.pct} color={item.color} />
                      </div>
                    ))}
                  </div>
                  {clean > 0 && (
                    <div style={{ display:'flex', alignItems:'center', gap:12, background:'rgba(34,197,94,0.08)', border:'1px solid rgba(34,197,94,0.2)', borderRadius:12, padding:'12px 16px', flexShrink:0, maxWidth:280 }}>
                      {TrendIcon('#22c55e', 20)}
                      <div>
                        <div style={{ fontSize:13, fontWeight:700, color:'#86efac' }}>Great progress!</div>
                        <div style={{ fontSize:12, color:TEXT_MID }}>Your org has {clean.toLocaleString()} components in good health.</div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* ── NEEDS ATTENTION / ALL ISSUES ── */}
            <div style={{ background:SURFACE, border:`1px solid ${BORDER}`, borderRadius:16, overflow:'hidden', marginBottom:20 }}>
              {/* Section header */}
              <div style={{ display:'flex', alignItems:'center', gap:12, padding:'14px 24px', borderBottom: collapsed.attention ? 'none' : `1px solid ${BORDER}`, flexWrap:'wrap' }}>
                <div style={{ display:'flex', alignItems:'center', gap:10, flex:1 }}>
                  <div style={{ width:30, height:30, borderRadius:8, background:'rgba(239,68,68,0.15)', border:'1px solid rgba(239,68,68,0.3)', display:'flex', alignItems:'center', justifyContent:'center' }}>
                    {WarnIcon('#ef4444', 14)}
                  </div>
                  <span style={{ fontSize:14, fontWeight:700, color:TEXT }}>Needs Attention</span>
                  <div style={{ background:'rgba(249,115,22,0.2)', border:'1px solid rgba(249,115,22,0.35)', borderRadius:20, padding:'2px 10px', fontSize:12, fontWeight:800, color:'#fb923c' }}>
                    {allIssues.length}
                  </div>
                </div>

                {/* Filter tabs (only show when expanded) */}
                {!collapsed.attention && (
                  <div style={{ display:'flex', gap:6 }}>
                    {[
                      { id:'all',    label:'All',      count: allIssues.length  },
                      { id:'high',   label:'Critical', count: highIssues.length },
                      { id:'medium', label:'Warnings', count: medIssues.length  },
                    ].map(tab => (
                      <button key={tab.id} onClick={(e) => { e.stopPropagation(); setActiveTab(tab.id) }} style={{
                        padding:'5px 14px', borderRadius:20, fontSize:12, fontWeight:700,
                        cursor:'pointer', border:'none', transition:'all 0.15s',
                        background: activeTab===tab.id ? '#2563eb' : 'rgba(255,255,255,0.06)',
                        color: activeTab===tab.id ? 'white' : TEXT_MID,
                      }}>
                        {tab.label}
                      </button>
                    ))}
                  </div>
                )}
                {!collapsed.attention && (
                  <select value={sortBy} onChange={e => setSortBy(e.target.value)}
                    style={{ padding:'5px 10px', background:CARD, border:`1px solid ${BORDER}`, borderRadius:8, color:TEXT_MID, fontSize:12, cursor:'pointer', outline:'none' }}>
                    <option value="severity">Sort: Severity</option>
                    <option value="name">Sort: Name</option>
                  </select>
                )}
                <button onClick={() => toggleSection('attention')} style={{ background:'none', border:'none', cursor:'pointer', color:TEXT_MID, fontSize:16, padding:'2px 6px', transform: collapsed.attention ? 'rotate(-90deg)' : 'none', transition:'transform 0.2s', flexShrink:0 }}>⌄</button>
              </div>

              {/* Issue rows */}
              {!collapsed.attention && (
                sortedIssues.length === 0 ? (
                  <div style={{ textAlign:'center', padding:'40px 20px', color:TEXT_MID, fontSize:14 }}>
                    <div style={{ fontSize:28, marginBottom:10 }}>✅</div>
                    No issues in this category
                  </div>
                ) : (
                  <div>
                    {sortedIssues.map((issue, i) => (
                      <div key={i} className="orgscan-row" style={{ animationDelay:`${i*0.03}s` }}>
                        <IssueRow issue={issue} onViewDetails={() => {}} />
                      </div>
                    ))}
                  </div>
                )
              )}
            </div>

            {/* ── ALL COMPONENTS TABLE ── */}
            {(() => {
              const allComps = [
                ...(scan.components.omniscripts||[]).map(c=>({...c,type:'OmniScript'})),
                ...(scan.components.dataraptors||[]).map(c=>({...c,type:'DataRaptor'})),
                ...(scan.components.integration_procedures||[]).map(c=>({...c,type:'Integration Procedure'})),
                ...(scan.components.apex_classes||[]).map(c=>({...c,type:'Apex Class'})),
                ...(scan.components.apex_triggers||[]).map(c=>({...c,type:'Apex Trigger'})),
                ...(scan.components.flows||[]).map(c=>({...c,type:'Flow'})),
                ...(scan.components.custom_objects||[]).map(c=>({...c,type:'Custom Object'})),
              ]
              if (!allComps.length) return null
              const issueMap = {}
              allIssues.forEach(i => { const k=`${i.component_type}::${i.component}`; issueMap[k]=(issueMap[k]||0)+1 })
              return (
                <div style={{ background:SURFACE, border:`1px solid ${BORDER}`, borderRadius:16, overflow:'hidden' }}>
                  <div onClick={() => toggleSection('components')} style={{ padding:'14px 24px', borderBottom: collapsed.components ? 'none' : `1px solid ${BORDER}`, display:'flex', alignItems:'center', gap:10, cursor:'pointer', justifyContent:'space-between' }}>
                    <div style={{ display:'flex', alignItems:'center', gap:10 }}>
                      <div style={{ width:30, height:30, borderRadius:8, background:'rgba(6,182,212,0.12)', border:'1px solid rgba(6,182,212,0.25)', display:'flex', alignItems:'center', justifyContent:'center' }}>
                        {GridIcon('#06b6d4', 14)}
                      </div>
                      <span style={{ fontSize:14, fontWeight:700, color:TEXT }}>All Components</span>
                      <span style={{ background:'rgba(6,182,212,0.12)', border:'1px solid rgba(6,182,212,0.25)', borderRadius:20, padding:'2px 10px', fontSize:12, fontWeight:700, color:'#38bdf8' }}>
                        {allComps.length}
                      </span>
                    </div>
                    <span style={{ fontSize:16, color:TEXT_MID, transform: collapsed.components ? 'rotate(-90deg)' : 'none', transition:'transform 0.2s' }}>⌄</span>
                  </div>
                  {!collapsed.components && (
                    <div style={{ overflowX:'auto' }}>
                      <table style={{ width:'100%', borderCollapse:'collapse' }}>
                        <thead>
                          <tr>
                            {['Name','Type','Detail','Issues'].map(h => (
                              <th key={h} style={{ fontSize:11, fontWeight:700, color:TEXT_DIM, textTransform:'uppercase', letterSpacing:'0.07em', padding:'10px 20px', borderBottom:`1px solid ${BORDER}`, textAlign:'left', background:'rgba(255,255,255,0.02)' }}>
                                {h}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {allComps.map((c,i) => {
                            const cnt = issueMap[`${c.type}::${c.name}`]||0
                            return (
                              <tr key={i} style={{ borderBottom:`1px solid rgba(255,255,255,0.04)` }}>
                                <td style={{ padding:'10px 20px', fontSize:13, color:TEXT, fontWeight:500 }}>{c.name}</td>
                                <td style={{ padding:'10px 20px' }}><TypeChip type={c.type} /></td>
                                <td style={{ padding:'10px 20px', fontSize:12, color:TEXT_DIM }}>{c.sub_type||c.interface_type||'—'}</td>
                                <td style={{ padding:'10px 20px' }}>
                                  {cnt>0
                                    ? <span style={{ fontSize:12, fontWeight:700, color:'#fca5a5' }}>{cnt} issue{cnt>1?'s':''}</span>
                                    : <span style={{ fontSize:12, fontWeight:600, color:'#34d399' }}>✓ Clean</span>}
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )
            })()}
          </>
        )}
      </div>
    </div>
  )
}
