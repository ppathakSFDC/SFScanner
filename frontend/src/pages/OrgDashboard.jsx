import React, { useState, useEffect, useCallback, useRef } from 'react'

// ─── CSS Keyframes ────────────────────────────────────────────────────────────
const ANIM_CSS = `
  @keyframes sfFadeUp    { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
  @keyframes sfPulseRed  { 0%,100%{box-shadow:0 4px 24px rgba(0,0,0,.25),0 0 0 0 rgba(239,68,68,0)} 50%{box-shadow:0 4px 24px rgba(0,0,0,.25),0 0 28px 7px rgba(239,68,68,.32)} }
  @keyframes sfPulseOrange{0%,100%{box-shadow:0 4px 24px rgba(0,0,0,.25),0 0 0 0 rgba(249,115,22,0)} 50%{box-shadow:0 4px 24px rgba(0,0,0,.25),0 0 22px 5px rgba(249,115,22,.26)} }
  .sfc-fade     { animation: sfFadeUp      .5s ease both; }
  .sfc-critical { animation: sfPulseRed    2.8s ease-in-out infinite; }
  .sfc-warn     { animation: sfPulseOrange 2.8s ease-in-out infinite; }
`

// ─── Colour palette ───────────────────────────────────────────────────────────
const C = {
  bg:       'var(--bg)',
  surface:  'var(--surface)',
  surfaceHi:'var(--surface-hi)',
  border:   'var(--border)',
  borderHi: 'var(--border-hi)',
  cyan:     '#06b6d4',
  cyanDim:  '#0891b2',
  cyanLo:   'rgba(6,182,212,0.12)',
  green:    '#22c55e',
  orange:   '#f97316',
  red:      '#ef4444',
  purple:   '#a855f7',
  yellow:   '#eab308',
  text:     'var(--text)',
  textMid:  'var(--text-mid)',
  textLo:   'var(--text-lo)',
  textDim:  'var(--text-dim)',
}

const CARD = {
  background: C.surface,
  borderRadius: 16,
  boxShadow: '0 4px 24px rgba(0,0,0,0.25)',
  border: `1px solid var(--border)`,
}

// ─── Category definitions ─────────────────────────────────────────────────────
const CATEGORIES = [
  { key:'crm',    label:'Standard CRM',      icon:'👥', color: C.cyan,    probe:'Account' },
  { key:'custom', label:'Custom Objects',     icon:'🔷', color:'#818cf8',  probe:null },
  { key:'apex',   label:'Apex Classes',       icon:'⚡', color: C.orange,  probe:'ApexClass' },
  { key:'flows',  label:'Flows & Processes',  icon:'🌊', color:'#34d399',  probe:'FlowDefinition' },
  { key:'perms',  label:'Profiles & Perms',   icon:'🛡️', color: C.yellow,  probe:'Profile' },
  { key:'integr', label:'Integrations & API', icon:'🔗', color: C.purple,  probe:'ConnectedApp' },
]

const CATEGORY_DETAILS = {
  crm: {
    desc: 'Core Salesforce standard objects — the backbone of every CRM implementation.',
    subItems: [
      { name:'Accounts', icon:'🏢' }, { name:'Contacts', icon:'👤' },
      { name:'Opportunities', icon:'💰' }, { name:'Leads', icon:'📋' },
      { name:'Cases', icon:'🎫' }, { name:'Activities', icon:'📅' },
    ],
    scanNav:'scanner', scanLabel:'Scan CRM Objects', expertNav:'professor', scanFilter:'all',
    tip:'Check field utilisation, FLS gaps and RecordType proliferation.',
  },
  custom: {
    desc: 'Custom sObjects built for your business — objects, fields, relationships and metadata.',
    subItems: [
      { name:'Custom Objects', icon:'🔷' }, { name:'Custom Fields', icon:'📝' },
      { name:'Validation Rules', icon:'✅' }, { name:'Custom Metadata', icon:'📦' },
      { name:'Big Objects', icon:'🗃️' }, { name:'External Objects', icon:'🌐' },
    ],
    scanNav:'scanner', scanLabel:'Scan Custom Objects', expertNav:'professor', scanFilter:'all',
    tip:'Look for objects with no records, orphaned fields and missing descriptions.',
  },
  apex: {
    desc: 'Apex code layer — classes, triggers, batch jobs, scheduled work and SOQL.',
    subItems: [
      { name:'Apex Classes', icon:'</>' }, { name:'Apex Triggers', icon:'⚡' },
      { name:'Batch Jobs', icon:'📦' }, { name:'Queueable', icon:'📋' },
      { name:'Test Classes', icon:'🧪' }, { name:'SOQL Queries', icon:'🔍' },
    ],
    scanNav:'scanner', scanLabel:'Scan Apex Code', expertNav:'professor', scanFilter:'apex',
    tip:'Watch for governor-limit violations, missing bulk patterns and low test coverage.',
  },
  flows: {
    desc: 'Declarative automation — screen flows, autolaunched flows and legacy processes.',
    subItems: [
      { name:'Screen Flows', icon:'🖥️' }, { name:'Autolaunched Flows', icon:'🚀' },
      { name:'Scheduled Flows', icon:'⏰' }, { name:'Platform Events', icon:'📡' },
      { name:'Process Builder', icon:'⚙️' }, { name:'Workflow Rules', icon:'🔄' },
    ],
    scanNav:'scanner', scanLabel:'Scan Flows', expertNav:'professor', scanFilter:'flow',
    tip:'Check for flows with no fault paths, unhandled DML errors and infinite loops.',
  },
  perms: {
    desc: 'Access control — profiles, permission sets, roles and field-level security (FLS).',
    subItems: [
      { name:'Profiles', icon:'👤' }, { name:'Permission Sets', icon:'🔐' },
      { name:'Perm Set Groups', icon:'🗂️' }, { name:'Roles', icon:'👑' },
      { name:'Users', icon:'🧑' }, { name:'Field-Level Security', icon:'🔒' },
      { name:'Sharing Rules', icon:'🤝' },
    ],
    scanNav:'orgscan', scanLabel:'Scan Permissions', expertNav:'professor', scanFilter:null,
    tip:'Audit ViewAllData, ModifyAllData and over-permissive profiles first.',
  },
  integr: {
    desc: 'Integration layer — connected apps, named credentials, remote sites and APIs.',
    subItems: [
      { name:'Connected Apps', icon:'🔌' }, { name:'Named Credentials', icon:'🔑' },
      { name:'Remote Site Settings', icon:'🌐' }, { name:'Auth Providers', icon:'🔓' },
      { name:'REST / SOAP APIs', icon:'📡' }, { name:'Platform Events', icon:'📬' },
    ],
    scanNav:'scanner', scanLabel:'Scan Integrations', expertNav:'professor', scanFilter:null,
    tip:'Verify OAuth scopes, unused connected apps and certificate expiry dates.',
  },
}

const CAT_ACTIONS = {
  custom: { count:23, label:'to review',  color:'#f97316' },
  apex:   { count:8,  label:'auto-fixes', color:'#06b6d4' },
  perms:  { count:15, label:'findings',   color:'#ef4444' },
}

// ─── Sub-item data sources ────────────────────────────────────────────────────
const SUB_ITEM_SOURCES = {
  crm: {
    'Accounts':      { object:'Account',    fields:'Name,Type,Industry,Phone',           filter:'' },
    'Contacts':      { object:'Contact',    fields:'Name,Title,Email,Phone',             filter:'' },
    'Opportunities': { object:'Opportunity',fields:'Name,StageName,Amount,CloseDate',    filter:'' },
    'Leads':         { object:'Lead',       fields:'Name,Company,Status,Email',          filter:'' },
    'Cases':         { object:'Case',       fields:'CaseNumber,Subject,Status,Priority', filter:'' },
    'Activities':    { object:'Task',       fields:'Subject,Status,ActivityDate',        filter:'' },
  },
  custom: {
    'Custom Objects':   { object:'EntityDefinition', fields:'QualifiedApiName,Label,DeveloperName', tooling:false, filter:'IsCustomizable = true AND IsCustomMetadataType = false AND IsCustomSetting = false' },
    'Custom Fields':    { object:'CustomField',      fields:'DeveloperName,TableEnumOrId,DataType,Label', tooling:true, filter:'' },
    'Validation Rules': { object:'ValidationRule',   fields:'ValidationName,Active,Description', tooling:true, filter:'' },
    'Custom Metadata':  { object:'EntityDefinition', fields:'QualifiedApiName,Label', tooling:false, filter:'IsCustomMetadataType = true' },
    'Big Objects':      { object:'EntityDefinition', fields:'QualifiedApiName,Label', filter:'IsCustomizable = true' },
    'External Objects': { object:'EntityDefinition', fields:'QualifiedApiName,Label', filter:'IsCustomizable = true' },
  },
  apex: {
    'Apex Classes':  { object:'ApexClass',   fields:'Name,Status,LengthWithoutComments,ApiVersion', tooling:true, filter:"Status = 'Active'" },
    'Apex Triggers': { object:'ApexTrigger', fields:'Name,TableEnumOrId,Status,ApiVersion',          tooling:true, filter:"Status = 'Active'" },
    'Batch Jobs':    { object:'ApexClass',   fields:'Name,Status,LengthWithoutComments',             tooling:true, filter:"Status = 'Active' AND Name LIKE '%Batch%'" },
    'Queueable':     { object:'ApexClass',   fields:'Name,Status,LengthWithoutComments',             tooling:true, filter:"Status = 'Active' AND Name LIKE '%Queue%'" },
    'Test Classes':  { object:'ApexClass',   fields:'Name,Status,LengthWithoutComments',             tooling:true, filter:"Status = 'Active' AND Name LIKE '%Test%'" },
  },
  flows: {
    'Screen Flows':       { object:'Flow', fields:'MasterLabel,ProcessType,ApiVersion', tooling:true, filter:"Status = 'Active' AND ProcessType = 'Flow'" },
    'Autolaunched Flows': { object:'Flow', fields:'MasterLabel,ProcessType,ApiVersion', tooling:true, filter:"Status = 'Active' AND ProcessType = 'AutoLaunchedFlow'" },
    'Scheduled Flows':    { object:'Flow', fields:'MasterLabel,ProcessType,ApiVersion', tooling:true, filter:"Status = 'Active'" },
    'Platform Events':    { object:'PlatformEventChannel', fields:'MasterLabel,EventType', filter:'' },
    'Process Builder':    { object:'Flow', fields:'MasterLabel,ProcessType,ApiVersion', tooling:true, filter:"Status = 'Active' AND ProcessType = 'Workflow'" },
    'Workflow Rules':     { object:'WorkflowRule', fields:'Name,TableEnumOrId,Active', tooling:true, filter:'' },
  },
  perms: {
    'Profiles':        { object:'Profile',            fields:'Name,UserType,Description',                     filter:'' },
    'Permission Sets': { object:'PermissionSet',      fields:'Name,Label,IsCustom,Description',               filter:'IsOwnedByProfile = false' },
    'Perm Set Groups': { object:'PermissionSetGroup', fields:'DeveloperName,MasterLabel,Description',         filter:'' },
    'Roles':           { object:'UserRole',           fields:'Name,DeveloperName',                            filter:'' },
    'Users':           { object:'User',               fields:'Name,Username,IsActive,UserType,LastLoginDate',  filter:'' },
  },
  integr: {
    'Connected Apps':       { object:'ConnectedApp',         fields:'Name,Description',                     tooling:true, filter:'' },
    'Named Credentials':    { object:'NamedCredential',      fields:'DeveloperName,Endpoint,PrincipalType', tooling:true, filter:'' },
    'Remote Site Settings': { object:'RemoteSiteSetting',    fields:'SiteName,SiteURL,IsActive',            tooling:true, filter:'' },
    'Auth Providers':       { object:'AuthProvider',         fields:'Name,ProviderType,FriendlyName',       tooling:true, filter:'' },
    'Platform Events':      { object:'PlatformEventChannel', fields:'MasterLabel,EventType',                filter:'' },
  },
}

const COL_LABELS = {
  QualifiedApiName:'API Name', DeveloperName:'Developer Name', TableEnumOrId:'SObject',
  LengthWithoutComments:'Lines', ValidationName:'Rule Name', ActiveVersionId:'Active Version',
  PrincipalType:'Auth Type', ContactEmail:'Contact', SiteURL:'URL', SiteName:'Site Name',
  IsActive:'Active', IsCustom:'Custom', CaseNumber:'Case #', FriendlyName:'Display Name',
  ProviderType:'Provider', UserType:'User Type', MasterLabel:'Name', EventType:'Event Type',
  ProcessType:'Flow Type', Username:'Username', ApiVersion:'API Ver',
}
function fmtCol(name) { return COL_LABELS[name] || name.replace(/([A-Z])/g,' $1').trim() }
function fmtVal(val) {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'boolean') return val ? 'Yes' : 'No'
  if (typeof val === 'number') return val.toLocaleString()
  return String(val)
}

// ─── Sparkline SVG ────────────────────────────────────────────────────────────
function Sparkline({ data, color, width=180, height=48 }) {
  if (!data?.length) return null
  const max=Math.max(...data), min=Math.min(...data), range=max-min||1, pad=4
  const pts = data.map((v,i) => [
    pad + (i/(data.length-1))*(width-pad*2),
    pad + ((1-(v-min)/range)*(height-pad*2))
  ])
  const line = pts.map(([x,y])=>`${x},${y}`).join(' ')
  const fill = `${pts[0][0]},${height} ${line} ${pts[pts.length-1][0]},${height}`
  const gid = `sg${color.replace(/[^a-z0-9]/gi,'')}`
  return (
    <svg width={width} height={height} style={{display:'block',overflow:'visible'}}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity="0.35"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <polygon points={fill} fill={`url(#${gid})`}/>
      <polyline points={line} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round"/>
      <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r="3" fill={color}/>
    </svg>
  )
}

// ─── Ring Gauge (270° semi-circular SVG arc) ──────────────────────────────────
function RingGauge({ pct=0, color=C.cyan, size=120, label='', loading=false, centerText }) {
  const [animPct, setAnimPct] = useState(0)
  useEffect(() => {
    const t = setTimeout(() => setAnimPct(pct), 60)
    return () => clearTimeout(t)
  }, [pct])

  const cx = size/2, cy = size/2
  const SW = Math.max(6, size * 0.085)
  const R  = (size - SW) / 2 - 2
  const gid = `rg${color.replace(/[^a-z0-9]/gi,'')}${size}`

  function pt(deg) {
    const rad = ((deg - 90) * Math.PI) / 180
    return { x: cx + R * Math.cos(rad), y: cy + R * Math.sin(rad) }
  }
  function arcPath(startDeg, sweepDeg) {
    const s = pt(startDeg), e = pt(startDeg + sweepDeg - 0.01)
    const large = sweepDeg > 180 ? 1 : 0
    return `M ${s.x.toFixed(2)},${s.y.toFixed(2)} A ${R},${R} 0 ${large},1 ${e.x.toFixed(2)},${e.y.toFixed(2)}`
  }
  const arcLen = (270/360) * 2 * Math.PI * R
  const trackPath = arcPath(135, 270)
  const fillPath  = arcPath(135, 270)
  const offset = arcLen * (1 - (loading ? 0 : animPct) / 100)

  const pStart = pt(135), pEnd = pt(405)
  const displayVal = centerText !== undefined ? centerText : `${Math.round(loading ? 0 : pct)}%`
  const fontSize = size < 90 ? Math.round(size * 0.18) : Math.round(size * 0.16)

  return (
    <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:4}}>
      <svg width={size} height={size} style={{overflow:'visible',display:'block'}}>
        <defs>
          <linearGradient id={gid} gradientUnits="userSpaceOnUse"
            x1={pStart.x.toFixed(2)} y1={pStart.y.toFixed(2)}
            x2={pEnd.x.toFixed(2)}   y2={pEnd.y.toFixed(2)}>
            <stop offset="0%"   stopColor={color} stopOpacity="0.4"/>
            <stop offset="100%" stopColor={color} stopOpacity="1"/>
          </linearGradient>
        </defs>
        {/* track */}
        <path d={trackPath} fill="none" stroke={`${color}1a`} strokeWidth={SW} strokeLinecap="round"/>
        {/* fill */}
        <path d={fillPath} fill="none" stroke={`url(#${gid})`} strokeWidth={SW} strokeLinecap="round"
          strokeDasharray={arcLen}
          strokeDashoffset={offset}
          style={{transition:'stroke-dashoffset 1.3s cubic-bezier(.4,0,.2,1)'}}
        />
        {/* center value */}
        <text x={cx} y={cy + fontSize * 0.38} textAnchor="middle"
          fill={loading ? 'var(--text-lo)' : 'white'}
          fontSize={fontSize} fontWeight="800" fontFamily="system-ui">
          {loading ? '…' : displayVal}
        </text>
      </svg>
      {label && (
        <span style={{fontSize:10,color:C.textLo,fontWeight:600,textTransform:'uppercase',letterSpacing:'0.07em',textAlign:'center'}}>
          {label}
        </span>
      )}
    </div>
  )
}

// ─── Category Card ────────────────────────────────────────────────────────────
function CategoryCard({ cat, count, health, loading, onClick, active }) {
  const [hov, setHov] = useState(false)
  const hColor = health == null ? C.textLo : health >= 70 ? C.green : health >= 50 ? C.orange : C.red
  const sevClass = health == null ? '' : health < 50 ? 'sfc-critical' : health < 65 ? 'sfc-warn' : ''
  const elevated = hov || active

  return (
    <div
      className={sevClass}
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        borderRadius:16,
        background:`linear-gradient(135deg, ${cat.color}12, ${cat.color}04 60%, transparent)`,
        border:`1px solid ${elevated ? cat.color+'55' : cat.color+'22'}`,
        boxShadow: elevated
          ? `0 8px 32px rgba(0,0,0,0.3), 0 0 20px ${cat.color}18`
          : '0 4px 16px rgba(0,0,0,0.2)',
        transform: elevated ? 'scale(1.025)' : 'scale(1)',
        transition:'transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease',
        cursor:'pointer', position:'relative', overflow:'hidden',
        padding:'14px 14px 12px',
      }}>
      {/* top accent */}
      <div style={{
        position:'absolute',top:0,left:0,right:0,height:2,borderRadius:'16px 16px 0 0',
        background:`linear-gradient(90deg,${cat.color},${cat.color}00)`,
      }}/>

      <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:8}}>
        {/* left */}
        <div style={{flex:1,minWidth:0}}>
          <div style={{display:'flex',alignItems:'center',gap:6,marginBottom:6}}>
            <span style={{fontSize:16}}>{cat.icon}</span>
            <span style={{fontSize:11,fontWeight:700,color:elevated?C.text:C.textMid}}>{cat.label}</span>
          </div>
          {loading
            ? <div style={{height:24,background:C.surfaceHi,borderRadius:4,width:'55%'}}/>
            : <div style={{fontSize:24,fontWeight:900,color:elevated?cat.color:C.text,letterSpacing:'-0.03em',lineHeight:1}}>
                {count!=null ? count.toLocaleString() : '—'}
              </div>
          }
          <div style={{display:'flex',alignItems:'center',gap:4,marginTop:6}}>
            <div style={{width:5,height:5,borderRadius:'50%',background:hColor,flexShrink:0}}/>
            <span style={{fontSize:10,color:hColor,fontWeight:600}}>
              {loading ? '...' : health!=null ? `${health}% health` : 'Click to explore'}
            </span>
          </div>
          {CAT_ACTIONS[cat.key] && !loading && (
            <div style={{
              marginTop:6,display:'inline-flex',alignItems:'center',gap:3,
              fontSize:9,fontWeight:700,color:CAT_ACTIONS[cat.key].color,
              background:`${CAT_ACTIONS[cat.key].color}18`,
              border:`1px solid ${CAT_ACTIONS[cat.key].color}35`,
              borderRadius:20,padding:'2px 7px',
            }}>
              {CAT_ACTIONS[cat.key].count} {CAT_ACTIONS[cat.key].label} →
            </div>
          )}
        </div>
        {/* right: mini gauge */}
        {health != null && (
          <div style={{flexShrink:0}}>
            <RingGauge pct={health} color={hColor} size={72} loading={loading}/>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Org Health Panel (left column) ──────────────────────────────────────────
function OrgHealthPanel({ auth, scores, loading, scanData, findingData, onNavigate }) {
  const overallHealth = scores
    ? Math.round(Object.values(scores).reduce((a,b)=>a+b,0)/Object.keys(scores).length)
    : 0
  const overallColor = overallHealth>=70 ? C.green : overallHealth>=50 ? C.orange : C.red

  return (
    <div style={{display:'flex',flexDirection:'column',gap:12}}>

      {/* ── Health Score card ── */}
      <div style={{...CARD,padding:'20px 16px',display:'flex',flexDirection:'column',alignItems:'center'}}>
        <div style={{fontSize:10,fontWeight:800,color:C.textLo,textTransform:'uppercase',letterSpacing:'0.1em',marginBottom:12,alignSelf:'flex-start'}}>
          Org Health Score
        </div>
        <RingGauge pct={overallHealth} color={overallColor} size={140} loading={loading&&!!auth}/>
        {/* per-category mini bars */}
        {scores && (
          <div style={{width:'100%',marginTop:14,display:'flex',flexDirection:'column',gap:7}}>
            {CATEGORIES.map(cat => {
              const sc = scores[cat.key]
              const hc = sc>=70 ? C.green : sc>=50 ? C.orange : C.red
              return (
                <div key={cat.key}>
                  <div style={{display:'flex',justifyContent:'space-between',marginBottom:2}}>
                    <span style={{fontSize:10,color:C.textMid,fontWeight:600,display:'flex',alignItems:'center',gap:4}}>
                      <span style={{fontSize:11}}>{cat.icon}</span>{cat.label}
                    </span>
                    <span style={{fontSize:10,fontWeight:700,color:hc}}>{sc}%</span>
                  </div>
                  <div style={{height:4,background:`${hc}1a`,borderRadius:3,overflow:'hidden'}}>
                    <div style={{
                      height:'100%',width:`${sc}%`,borderRadius:3,
                      background:`linear-gradient(90deg,${hc}88,${hc})`,
                      transition:'width 1.2s cubic-bezier(.4,0,.2,1)',
                    }}/>
                  </div>
                </div>
              )
            })}
          </div>
        )}
        {!auth && <div style={{fontSize:11,color:C.textLo,marginTop:12,textAlign:'center'}}>Connect org to view health</div>}
      </div>

      {/* ── Scan Controls card ── */}
      <div style={{...CARD,padding:'16px'}}>
        <div style={{fontSize:10,fontWeight:800,color:C.textLo,textTransform:'uppercase',letterSpacing:'0.1em',marginBottom:10}}>
          Scan Controls
        </div>
        <button onClick={()=>onNavigate?.('orgscan')} style={{
          width:'100%',padding:'10px',marginBottom:8,
          background:'linear-gradient(135deg,#06b6d4,#0891b2)',
          border:'none',borderRadius:10,color:'white',
          fontSize:13,fontWeight:700,cursor:'pointer',
          boxShadow:'0 4px 14px rgba(6,182,212,0.3)',
        }}>🔍 Run Full Scan</button>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
          <button onClick={()=>onNavigate?.('scanner')} style={{
            padding:'8px 6px',background:C.surfaceHi,
            border:`1px solid ${C.border}`,borderRadius:9,
            color:C.textMid,fontSize:12,fontWeight:600,cursor:'pointer',
          }}>⚡ Apex Scan</button>
          <button onClick={()=>onNavigate?.('migrate')} style={{
            padding:'8px 6px',background:C.surfaceHi,
            border:`1px solid ${C.border}`,borderRadius:9,
            color:C.textMid,fontSize:12,fontWeight:600,cursor:'pointer',
          }}>🚀 Migrate</button>
        </div>
      </div>

      {/* ── Trend card ── */}
      <div style={{...CARD,padding:'16px'}}>
        <div style={{fontSize:10,fontWeight:800,color:C.textLo,textTransform:'uppercase',letterSpacing:'0.1em',marginBottom:12}}>
          12-Week Trend
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:12}}>
          <div>
            <div style={{fontSize:10,color:C.textLo,marginBottom:4,display:'flex',gap:5,alignItems:'center'}}>
              <span style={{width:10,height:2,background:C.cyan,display:'inline-block',borderRadius:1}}/>
              Objects scanned
            </div>
            <Sparkline data={scanData} color={C.cyan} width={200} height={38}/>
          </div>
          <div>
            <div style={{fontSize:10,color:C.textLo,marginBottom:4,display:'flex',gap:5,alignItems:'center'}}>
              <span style={{width:10,height:2,background:C.orange,display:'inline-block',borderRadius:1}}/>
              Findings detected
            </div>
            <Sparkline data={findingData} color={C.orange} width={200} height={38}/>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Action Feed (right column) ───────────────────────────────────────────────
const SEV_ORDER = { [C.red]:0, [C.orange]:1, [C.yellow]:2 }

function ActionItem({ icon, title, sub, badge, badgeColor, severity }) {
  const [hov, setHov] = useState(false)
  return (
    <div
      onMouseEnter={()=>setHov(true)}
      onMouseLeave={()=>setHov(false)}
      style={{
        display:'flex',alignItems:'flex-start',gap:10,padding:'10px 12px',
        borderLeft:`2.5px solid ${severity}`,
        background: hov ? `${severity}06` : 'transparent',
        borderRadius:'0 8px 8px 0',
        transition:'background 0.12s',
        cursor:'default',
      }}>
      <div style={{
        width:32,height:32,borderRadius:9,flexShrink:0,
        background:`${badgeColor}18`,border:`1px solid ${badgeColor}30`,
        display:'flex',alignItems:'center',justifyContent:'center',fontSize:14,
      }}>{icon}</div>
      <div style={{flex:1,minWidth:0}}>
        <div style={{
          fontSize:12,color:C.text,fontWeight:500,lineHeight:1.4,
          display:'-webkit-box',WebkitLineClamp:2,WebkitBoxOrient:'vertical',overflow:'hidden',
        }}>{title}</div>
        <div style={{display:'flex',alignItems:'center',gap:6,marginTop:4}}>
          {badge && (
            <span style={{
              fontSize:9,fontWeight:700,color:badgeColor,
              background:`${badgeColor}18`,border:`1px solid ${badgeColor}30`,
              borderRadius:4,padding:'1px 6px',
            }}>{badge}</span>
          )}
          <span style={{fontSize:10,color:C.textLo}}>{sub}</span>
        </div>
      </div>
    </div>
  )
}

function ActionFeed({ findings, recs }) {
  const all = [...findings, ...recs].sort((a,b) =>
    (SEV_ORDER[a.severity]??3) - (SEV_ORDER[b.severity]??3)
  )
  const critCount = all.filter(i => i.severity===C.red).length

  return (
    <div style={{...CARD,display:'flex',flexDirection:'column',overflow:'hidden'}}>
      <div style={{padding:'16px 16px 10px',borderBottom:`1px solid ${C.border}`}}>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <span style={{fontSize:13,fontWeight:800,color:C.text,flex:1}}>Action Required</span>
          {critCount>0 && (
            <span style={{
              fontSize:10,fontWeight:700,color:C.red,
              background:'rgba(239,68,68,0.12)',border:'1px solid rgba(239,68,68,0.25)',
              borderRadius:20,padding:'2px 8px',
            }}>{critCount} critical</span>
          )}
        </div>
        <div style={{fontSize:11,color:C.textLo,marginTop:2}}>Sorted by severity</div>
      </div>
      <div style={{overflowY:'auto',flex:1,maxHeight:560,paddingTop:4,paddingBottom:8}}>
        {all.map((item,i) => (
          <ActionItem key={i} {...item}/>
        ))}
      </div>
    </div>
  )
}

// ─── Storage Panel (ring gauges) ─────────────────────────────────────────────
function StoragePanel({ data, loading }) {
  function fmtMB(mb) {
    if (mb==null) return '—'
    return mb>=1024 ? `${(mb/1024).toFixed(1)} GB` : `${mb} MB`
  }

  const dataMB = data?.DataStorageMB   || { Max:0, Remaining:0 }
  const fileMB = data?.FileStorageMB   || { Max:0, Remaining:0 }
  const apiDay = data?.DailyApiRequests|| { Max:0, Remaining:0 }

  const dataUsed = dataMB.Max - dataMB.Remaining
  const fileUsed = fileMB.Max - fileMB.Remaining
  const dataPct  = dataMB.Max > 0 ? Math.min(100, Math.round((dataUsed/dataMB.Max)*100)) : 0
  const filePct  = fileMB.Max > 0 ? Math.min(100, Math.round((fileUsed/fileMB.Max)*100)) : 0
  const apiUsed  = apiDay.Max - apiDay.Remaining
  const apiPct   = apiDay.Max > 0 ? Math.min(100, Math.round((apiUsed/apiDay.Max)*100))  : 0

  const dataColor = dataPct>=80 ? C.red : dataPct>=60 ? C.orange : C.cyan
  const fileColor = filePct>=80 ? C.red : filePct>=60 ? C.orange : C.purple
  const apiColor  = apiPct >=80 ? C.red : apiPct >=60 ? C.orange : C.green

  const gauges = [
    { label:'Data', pct:dataPct, color:dataColor, cap:`${fmtMB(dataUsed)} / ${fmtMB(dataMB.Max)}` },
    { label:'Files', pct:filePct, color:fileColor, cap:`${fmtMB(fileUsed)} / ${fmtMB(fileMB.Max)}` },
    ...(apiDay.Max>0 ? [{ label:'API / day', pct:apiPct, color:apiColor, cap:`${apiUsed.toLocaleString()} / ${apiDay.Max.toLocaleString()}` }] : []),
  ]

  return (
    <div style={{...CARD,padding:'16px 14px'}}>
      <div style={{fontSize:10,fontWeight:800,color:C.textLo,textTransform:'uppercase',letterSpacing:'0.1em',marginBottom:14,display:'flex',alignItems:'center',gap:6}}>
        <span>💾</span> Org Storage
        {loading && <span style={{marginLeft:'auto',fontSize:11,color:C.textLo}}>Loading…</span>}
      </div>
      {loading ? (
        <div style={{height:100,background:C.surfaceHi,borderRadius:8,opacity:0.5}}/>
      ) : !data ? (
        <div style={{textAlign:'center',color:C.textLo,fontSize:12,padding:'20px 0'}}>Connect org to view storage</div>
      ) : (
        <div style={{display:'flex',justifyContent:'space-around',alignItems:'flex-start',gap:8}}>
          {gauges.map(g => (
            <div key={g.label} style={{display:'flex',flexDirection:'column',alignItems:'center',gap:6}}>
              <RingGauge pct={g.pct} color={g.color} size={80} loading={loading}/>
              <div style={{textAlign:'center'}}>
                <div style={{fontSize:10,fontWeight:700,color:C.textMid}}>{g.label}</div>
                <div style={{fontSize:9,color:C.textLo,marginTop:1}}>{g.cap}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Apex Coverage Panel ─────────────────────────────────────────────────────
function ApexCoveragePanel({ data, loading }) {
  const pct     = data?.overall_pct      ?? 0
  const passed  = data?.passed           ?? 0
  const failed  = data?.failed           ?? 0
  const total   = data?.total_tests      ?? 0
  const below75 = data?.classes_below_75 ?? 0
  const list    = data?.below_75_list    ?? []

  const coverColor = pct>=75 ? C.green : pct>=50 ? C.orange : C.red

  const S=118, CX=59, CY=59, R=44, SW=12
  const circ = 2*Math.PI*R
  const gid = `cov${coverColor.replace(/[^a-z0-9]/gi,'')}`

  return (
    <div style={{...CARD,padding:'16px 14px'}}>
      <div style={{fontSize:10,fontWeight:800,color:C.textLo,textTransform:'uppercase',letterSpacing:'0.1em',marginBottom:12,display:'flex',alignItems:'center',gap:6}}>
        <span>🧪</span> Test Coverage
        {loading && <span style={{marginLeft:'auto',fontSize:11,color:C.textLo}}>Loading…</span>}
      </div>

      {loading ? (
        <div style={{height:100,background:C.surfaceHi,borderRadius:8,opacity:0.5}}/>
      ) : !data ? (
        <div style={{textAlign:'center',color:C.textLo,fontSize:12,padding:'20px 0'}}>Connect org to view coverage</div>
      ) : (
        <>
          <div style={{display:'flex',gap:10,alignItems:'center',marginBottom:12}}>
            <svg width={S} height={S} viewBox={`0 0 ${S} ${S}`} style={{flexShrink:0}}>
              <defs>
                <linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%"   stopColor={coverColor} stopOpacity="0.5"/>
                  <stop offset="100%" stopColor={coverColor} stopOpacity="1"/>
                </linearGradient>
              </defs>
              <circle cx={CX} cy={CY} r={R} fill="none" stroke={`${coverColor}18`} strokeWidth={SW}/>
              <circle cx={CX} cy={CY} r={R} fill="none"
                stroke={`url(#${gid})`} strokeWidth={SW} strokeLinecap="round"
                strokeDasharray={`${(pct/100)*circ} ${circ}`}
                style={{transform:'rotate(-90deg)',transformOrigin:`${CX}px ${CY}px`,transition:'stroke-dasharray 1.2s cubic-bezier(.4,0,.2,1)'}}
              />
              <text x={CX} y={CY-5}  textAnchor="middle" fill="white"          fontSize="20" fontWeight="800" fontFamily="system-ui">{pct}%</text>
              <text x={CX} y={CY+12} textAnchor="middle" fill="var(--text-lo)" fontSize="9"  fontWeight="700" letterSpacing="0.08em" fontFamily="system-ui">COVERAGE</text>
            </svg>
            <div style={{flex:1,display:'flex',flexDirection:'column',gap:7}}>
              {[
                { label:'Tests',       value:total.toLocaleString(),   color:C.textMid },
                { label:'Passed',      value:passed.toLocaleString(),  color:C.green   },
                { label:'Failed',      value:failed.toLocaleString(),  color:failed>0?C.red:C.textLo },
                { label:'Below 75%',   value:below75.toLocaleString(), color:below75>0?C.orange:C.green },
              ].map(r => (
                <div key={r.label} style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <span style={{fontSize:10,color:C.textLo}}>{r.label}</span>
                  <span style={{fontSize:12,fontWeight:800,color:r.color}}>{r.value}</span>
                </div>
              ))}
            </div>
          </div>
          {list.length>0 && (
            <div style={{borderTop:`1px solid ${C.border}`,paddingTop:8}}>
              <div style={{fontSize:9,fontWeight:800,color:C.textLo,textTransform:'uppercase',letterSpacing:'0.09em',marginBottom:6}}>
                Lowest Coverage Classes
              </div>
              {list.slice(0,4).map(cls => {
                const bc = cls.pct<50 ? C.red : C.orange
                return (
                  <div key={cls.name} style={{marginBottom:5}}>
                    <div style={{display:'flex',justifyContent:'space-between',marginBottom:2}}>
                      <span style={{fontSize:10,color:C.textMid,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',maxWidth:'72%'}}>{cls.name}</span>
                      <span style={{fontSize:10,fontWeight:700,color:bc}}>{cls.pct}%</span>
                    </div>
                    <div style={{height:3,background:`${bc}18`,borderRadius:2,overflow:'hidden'}}>
                      <div style={{height:'100%',width:`${cls.pct}%`,background:bc,borderRadius:2,transition:'width 1s ease'}}/>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ─── Org Details Card ─────────────────────────────────────────────────────────
function OrgDetailsCard({ orgInfo }) {
  const [open, setOpen] = useState(false)
  const primary = [
    { label:'Organization', value:orgInfo.Name,         icon:'🏢' },
    { label:'Org ID',       value:orgInfo.Id,           icon:'🔑' },
    { label:'Instance',     value:orgInfo.InstanceName, icon:'🌐' },
  ].filter(f=>f.value)
  const secondary = [
    { label:'Edition',  value:orgInfo.OrganizationType,    icon:'📦' },
    { label:'Country',  value:orgInfo.Country,             icon:'📍' },
    { label:'Timezone', value:orgInfo.TimeZoneSidKey,      icon:'🕐' },
    { label:'Locale',   value:orgInfo.DefaultLocaleSidKey, icon:'🌍' },
    { label:'Language', value:orgInfo.LanguageLocaleKey,   icon:'💬' },
  ].filter(f=>f.value)

  return (
    <div style={{
      ...CARD,padding:'12px 20px',marginBottom:16,
      display:'flex',alignItems:'center',gap:28,flexWrap:'wrap',
    }}>
      {primary.map(f => (
        <div key={f.label} style={{display:'flex',alignItems:'center',gap:7,minWidth:0}}>
          <span style={{fontSize:15}}>{f.icon}</span>
          <div>
            <div style={{fontSize:10,color:C.textLo,fontWeight:600,textTransform:'uppercase',letterSpacing:'0.06em'}}>{f.label}</div>
            <div style={{fontSize:13,color:C.text,fontWeight:600,maxWidth:260,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{f.value}</div>
          </div>
        </div>
      ))}
      {secondary.length>0 && (
        <div style={{position:'relative',marginLeft:'auto',flexShrink:0}}
          onMouseEnter={()=>setOpen(true)}
          onMouseLeave={()=>setOpen(false)}>
          <span style={{
            fontSize:11,color:C.textLo,cursor:'default',
            padding:'4px 10px',border:`1px solid ${C.border}`,
            borderRadius:20,background:C.surfaceHi,
          }}>Org Details ▾</span>
          {open && (
            <div style={{
              position:'absolute',top:'calc(100% + 6px)',right:0,zIndex:50,
              background:C.surface,border:`1px solid ${C.borderHi}`,
              borderRadius:12,padding:'14px 18px',minWidth:220,
              boxShadow:'0 8px 32px rgba(0,0,0,0.4)',
              display:'flex',flexDirection:'column',gap:10,
            }}>
              {secondary.map(f => (
                <div key={f.label} style={{display:'flex',alignItems:'center',gap:8}}>
                  <span style={{fontSize:14}}>{f.icon}</span>
                  <div>
                    <div style={{fontSize:9,color:C.textLo,fontWeight:700,textTransform:'uppercase',letterSpacing:'0.07em'}}>{f.label}</div>
                    <div style={{fontSize:12,color:C.textMid,fontWeight:500}}>{f.value}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Category Detail Panel ────────────────────────────────────────────────────
function CategoryDetailPanel({ cat, detail, count, health, onNavigate, onClose }) {
  const hColor = health>=70 ? C.green : health>=50 ? C.orange : C.red
  const [activeItem, setActiveItem] = useState(null)
  const [itemData,   setItemData]   = useState(null)
  const [itemLoad,   setItemLoad]   = useState(false)
  const [itemErr,    setItemErr]    = useState('')

  function fetchSubItem(name, source) {
    if (activeItem===name) { setActiveItem(null); setItemData(null); return }
    setActiveItem(name); setItemData(null); setItemErr(''); setItemLoad(true)
    const params = new URLSearchParams({
      object_name: source.object, fields: source.fields,
      filter_clause: source.filter||'', tooling: source.tooling?'true':'false', limit:'200',
    })
    fetch(`/auth/list-records?${params}`,{credentials:'include'})
      .then(r=>r.text().then(t=>{
        try { const j=JSON.parse(t); if(!r.ok) return Promise.reject(j.detail||`HTTP ${r.status}`); return j }
        catch { return Promise.reject(r.ok?'Invalid response':`HTTP ${r.status} — restart the backend`) }
      }))
      .then(d=>setItemData(d))
      .catch(e=>setItemErr(String(e)))
      .finally(()=>setItemLoad(false))
  }

  return (
    <div className="sfc-fade" style={{
      ...CARD,padding:'20px 24px',marginBottom:16,
      border:`1px solid ${cat.color}50`,
      boxShadow:`0 8px 32px ${cat.color}18`,
      position:'relative',overflow:'hidden',
    }}>
      <div style={{position:'absolute',top:0,left:0,right:0,height:2,borderRadius:'16px 16px 0 0',
        background:`linear-gradient(90deg,${cat.color},${cat.color}00)`}}/>
      <div style={{position:'absolute',top:0,right:0,width:200,height:200,
        background:`radial-gradient(circle at 100% 0%,${cat.color}0d,transparent 70%)`,pointerEvents:'none'}}/>

      <div style={{display:'flex',alignItems:'flex-start',gap:24}}>
        <div style={{flex:1,minWidth:0}}>
          <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:10}}>
            <div style={{width:44,height:44,borderRadius:12,flexShrink:0,
              background:`${cat.color}20`,border:`1px solid ${cat.color}40`,
              display:'flex',alignItems:'center',justifyContent:'center',fontSize:22}}>
              {cat.icon}
            </div>
            <div style={{flex:1}}>
              <div style={{fontSize:17,fontWeight:800,color:C.text}}>{cat.label}</div>
              <div style={{fontSize:12,color:C.textLo,marginTop:2,lineHeight:1.5}}>{detail.desc}</div>
            </div>
            {count!=null && (
              <div style={{textAlign:'right',flexShrink:0}}>
                <div style={{fontSize:30,fontWeight:900,color:cat.color,lineHeight:1,letterSpacing:'-0.03em'}}>
                  {count.toLocaleString()}
                </div>
                {health!=null && <div style={{fontSize:11,color:hColor,fontWeight:600,marginTop:2}}>{health}% healthy</div>}
              </div>
            )}
          </div>

          <div style={{display:'flex',flexWrap:'wrap',gap:6,marginBottom:10}}>
            {detail.subItems.map(item => {
              const src = SUB_ITEM_SOURCES[cat.key]?.[item.name]
              const isActive = activeItem===item.name
              const busy = isActive && itemLoad
              return (
                <span key={item.name} onClick={()=>src&&fetchSubItem(item.name,src)} style={{
                  fontSize:12,
                  color:isActive?cat.color:src?C.text:C.textLo,
                  background:isActive?`${cat.color}18`:src?C.surfaceHi:'transparent',
                  border:`1px solid ${isActive?cat.color+'60':src?C.border:'transparent'}`,
                  borderRadius:20,padding:'5px 12px',
                  display:'flex',alignItems:'center',gap:5,
                  cursor:src?'pointer':'default',transition:'all 0.12s',fontWeight:isActive?700:500,
                }}>
                  <span style={{fontSize:14}}>{busy?'⏳':item.icon}</span>
                  {item.name}
                  {src&&!isActive&&<span style={{fontSize:10,color:C.textLo,marginLeft:2}}>›</span>}
                </span>
              )
            })}
          </div>

          {(itemLoad||itemData||itemErr) && (
            <div style={{border:`1px solid ${cat.color}30`,borderRadius:10,overflow:'hidden',marginBottom:10}}>
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'7px 12px',
                background:`${cat.color}10`,borderBottom:`1px solid ${cat.color}25`}}>
                <span style={{fontSize:11,fontWeight:700,color:cat.color}}>
                  {activeItem}{itemData&&` — ${itemData.records.length} of ${itemData.total}`}
                </span>
                {itemLoad&&<span style={{fontSize:11,color:C.textLo}}>Loading…</span>}
                {itemErr&&<span style={{fontSize:11,color:C.red}}>{itemErr}</span>}
              </div>
              {itemData && (
                <div style={{overflowX:'auto',maxHeight:300,overflowY:'auto'}}>
                  <table style={{width:'100%',borderCollapse:'collapse',fontSize:12}}>
                    <thead>
                      <tr style={{background:C.surfaceHi,position:'sticky',top:0,zIndex:1}}>
                        {itemData.columns.map(col=>(
                          <th key={col} style={{padding:'6px 12px',textAlign:'left',color:C.textLo,fontWeight:700,
                            fontSize:10,textTransform:'uppercase',letterSpacing:'0.06em',
                            borderBottom:`1px solid ${C.border}`,whiteSpace:'nowrap'}}>
                            {fmtCol(col)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {itemData.records.length===0 ? (
                        <tr><td colSpan={itemData.columns.length} style={{padding:'16px 12px',color:C.textLo,textAlign:'center',fontStyle:'italic'}}>No records found</td></tr>
                      ) : itemData.records.map((rec,i) => (
                        <tr key={rec.Id||i} style={{borderBottom:`1px solid ${C.border}`,background:i%2===0?'transparent':`${C.surfaceHi}88`}}>
                          {itemData.columns.map(col=>(
                            <td key={col} style={{padding:'6px 12px',color:C.text,maxWidth:220,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                              {fmtVal(rec[col])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          <div style={{display:'flex',alignItems:'center',gap:8,padding:'8px 12px',
            background:`${cat.color}0a`,border:`1px solid ${cat.color}25`,borderRadius:8}}>
            <span style={{fontSize:14}}>💡</span>
            <span style={{fontSize:12,color:C.textMid,lineHeight:1.5}}>{detail.tip}</span>
          </div>
        </div>

        <div style={{display:'flex',flexDirection:'column',gap:8,width:210,flexShrink:0}}>
          <button onClick={()=>{
            const src = activeItem && SUB_ITEM_SOURCES[cat.key]?.[activeItem]
            if (src) onNavigate('records-list',{...src,label:activeItem})
            else onNavigate(detail.scanNav||'scanner')
          }} style={{
            padding:'11px 16px',background:`linear-gradient(135deg,${cat.color},${cat.color}bb)`,
            border:'none',borderRadius:10,color:'white',fontSize:13,fontWeight:700,cursor:'pointer',
            display:'flex',alignItems:'center',gap:8,boxShadow:`0 4px 16px ${cat.color}30`,
          }}>🔍 {activeItem?`Browse ${activeItem}`:detail.scanLabel}</button>
          <button onClick={()=>onNavigate('orgscan')} style={{
            padding:'11px 16px',background:C.surfaceHi,border:`1px solid ${C.border}`,
            borderRadius:10,color:C.text,fontSize:13,fontWeight:600,cursor:'pointer',
            display:'flex',alignItems:'center',gap:8,
          }}>📊 Full Org Scan</button>
          <button onClick={()=>onNavigate('professor')} style={{
            padding:'11px 16px',background:C.surfaceHi,border:`1px solid ${C.border}`,
            borderRadius:10,color:C.textMid,fontSize:13,fontWeight:600,cursor:'pointer',
            display:'flex',alignItems:'center',gap:8,
          }}>🎓 Ask AI Expert</button>
          <button onClick={()=>onNavigate('migrate')} style={{
            padding:'11px 16px',background:C.surfaceHi,border:`1px solid ${C.border}`,
            borderRadius:10,color:C.textMid,fontSize:13,fontWeight:600,cursor:'pointer',
            display:'flex',alignItems:'center',gap:8,
          }}>🚀 Migrate</button>
        </div>

        <button onClick={onClose} style={{
          background:'none',border:`1px solid ${C.border}`,borderRadius:6,color:C.textLo,
          width:26,height:26,flexShrink:0,fontSize:16,cursor:'pointer',
          display:'flex',alignItems:'center',justifyContent:'center',lineHeight:1,
        }}>×</button>
      </div>
    </div>
  )
}

// ─── Connect Org Modal ────────────────────────────────────────────────────────
function ConnectOrgModal({ onClose, onAuthChange }) {
  const [loginMode,    setLoginMode]    = useState('password')
  const [pwForm,       setPwForm]       = useState({ username:'', password:'', domain:'login.salesforce.com', alias:'' })
  const [pwLogging,    setPwLogging]    = useState(false)
  const [pwError,      setPwError]      = useState('')
  const [cliOrg,       setCliOrg]       = useState('')
  const [cliLogging,   setCliLogging]   = useState(false)
  const [cliError,     setCliError]     = useState('')
  const [tokenForm,    setTokenForm]    = useState({ access_token:'', instance_url:'' })
  const [tokenLogging, setTokenLogging] = useState(false)
  const [tokenError,   setTokenError]   = useState('')

  async function handlePasswordLogin(e) {
    e.preventDefault()
    setPwLogging(true); setPwError('')
    try {
      const res = await fetch('/auth/login-password', {
        method:'POST', headers:{'Content-Type':'application/json'},
        credentials:'include', body: JSON.stringify(pwForm),
      })
      let data
      try { data = await res.json() } catch { throw new Error(`Server error (${res.status})`) }
      if (!res.ok) throw new Error(data.detail || 'Login failed')
      if (onAuthChange) onAuthChange(data)
      onClose()
    } catch(err) { setPwError(err.message) }
    finally { setPwLogging(false) }
  }

  async function handleCliLogin(e) {
    e.preventDefault()
    setCliLogging(true); setCliError('')
    try {
      const res = await fetch('/auth/login-cli', {
        method:'POST', headers:{'Content-Type':'application/json'},
        credentials:'include', body: JSON.stringify({ org: cliOrg }),
      })
      let data
      try { data = await res.json() } catch { throw new Error(`Server error (${res.status})`) }
      if (!res.ok) throw new Error(data.detail || 'Login failed')
      if (onAuthChange) onAuthChange(data)
      onClose()
    } catch(err) { setCliError(err.message) }
    finally { setCliLogging(false) }
  }

  async function handleTokenLogin(e) {
    e.preventDefault()
    setTokenLogging(true); setTokenError('')
    try {
      const res = await fetch('/auth/login-token', {
        method:'POST', headers:{'Content-Type':'application/json'},
        credentials:'include', body: JSON.stringify(tokenForm),
      })
      let data
      try { data = await res.json() } catch { throw new Error(`Server error (${res.status})`) }
      if (!res.ok) throw new Error(data.detail || 'Login failed')
      if (onAuthChange) onAuthChange(data)
      onClose()
    } catch(err) { setTokenError(err.message) }
    finally { setTokenLogging(false) }
  }

  const inputStyle = {
    width:'100%', padding:'10px 12px', borderRadius:8,
    background:'#050c0c', border:'1px solid #0f2e2e', color:'#e2e8f0',
    fontSize:14, outline:'none', boxSizing:'border-box',
  }
  const labelStyle = { color:'#94a3b8', fontSize:12, fontWeight:600, marginBottom:4, display:'block' }
  const submitBtn  = (loading) => ({
    width:'100%', padding:'11px 20px', borderRadius:9, fontSize:14, fontWeight:700,
    background: loading ? '#0f2e2e' : 'linear-gradient(135deg,#06b6d4,#0891b2)',
    border:'none', color: loading ? '#4a9a9a' : 'white',
    cursor: loading ? 'not-allowed' : 'pointer', marginTop:4, transition:'all 0.2s',
  })

  return (
    <div
      style={{
        position:'fixed',inset:0,zIndex:1000,
        display:'flex',alignItems:'center',justifyContent:'center',
        background:'rgba(5,12,12,0.82)',backdropFilter:'blur(8px)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background:'#0d1e1e',borderRadius:16,padding:28,width:440,maxWidth:'92vw',
          border:'1px solid #1a3a3a',boxShadow:'0 24px 64px rgba(0,0,0,0.65)',
          position:'relative',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20}}>
          <div style={{fontSize:17,fontWeight:700,color:'#e2e8f0'}}>Connect Salesforce Org</div>
          <button
            onClick={onClose}
            style={{background:'transparent',border:'none',color:'#64748b',fontSize:22,cursor:'pointer',lineHeight:1,padding:'2px 8px',borderRadius:6}}
          >×</button>
        </div>

        {/* Tabs */}
        <div style={{display:'flex',gap:3,marginBottom:20,background:'#050c0c',borderRadius:10,padding:4}}>
          {[['password','Username + Password'],['cli','SF CLI Org'],['token','Session ID']].map(([mode,label]) => (
            <button key={mode} onClick={() => setLoginMode(mode)} style={{
              flex:1, padding:'7px 4px', borderRadius:7, fontSize:11, fontWeight:600,
              cursor:'pointer', border:'none',
              background: loginMode===mode ? '#0f2e2e' : 'transparent',
              color: loginMode===mode ? '#06b6d4' : '#4a9a9a',
              transition:'all 0.15s',
            }}>{label}</button>
          ))}
        </div>

        {/* Username + Password */}
        {loginMode === 'password' && (
          <form onSubmit={handlePasswordLogin} style={{display:'flex',flexDirection:'column',gap:12}}>
            <div>
              <label style={labelStyle}>Username</label>
              <input style={inputStyle} value={pwForm.username}
                onChange={e => setPwForm({...pwForm, username:e.target.value})}
                placeholder="user@example.com" required />
            </div>
            <div>
              <label style={labelStyle}>Password + Security Token</label>
              <input style={inputStyle} type="password" value={pwForm.password}
                onChange={e => setPwForm({...pwForm, password:e.target.value})}
                placeholder="passwordSecurityToken" required />
            </div>
            <div>
              <label style={labelStyle}>Login Domain</label>
              <select style={inputStyle} value={pwForm.domain}
                onChange={e => setPwForm({...pwForm, domain:e.target.value})}>
                <option value="login.salesforce.com">Production (login.salesforce.com)</option>
                <option value="test.salesforce.com">Sandbox (test.salesforce.com)</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>Alias (optional)</label>
              <input style={inputStyle} value={pwForm.alias}
                onChange={e => setPwForm({...pwForm, alias:e.target.value})}
                placeholder="my-org" />
            </div>
            {pwError && <div style={{color:'#fca5a5',fontSize:13}}>{pwError}</div>}
            <button type="submit" style={submitBtn(pwLogging)} disabled={pwLogging}>
              {pwLogging ? 'Connecting…' : 'Connect'}
            </button>
          </form>
        )}

        {/* SF CLI Org */}
        {loginMode === 'cli' && (
          <form onSubmit={handleCliLogin} style={{display:'flex',flexDirection:'column',gap:12}}>
            <div style={{color:'#4a9a9a',fontSize:13,lineHeight:1.6,background:'#050c0c',borderRadius:8,padding:12}}>
              Uses an org already authenticated via{' '}
              <code style={{color:'#a5f3fc',fontSize:12}}>sf org login</code> or{' '}
              <code style={{color:'#a5f3fc',fontSize:12}}>sfdx auth:web:login</code>.
            </div>
            <div>
              <label style={labelStyle}>Org Alias or Username</label>
              <input style={inputStyle} value={cliOrg}
                onChange={e => setCliOrg(e.target.value)}
                placeholder="my-org or user@example.com" />
            </div>
            {cliError && <div style={{color:'#fca5a5',fontSize:13}}>{cliError}</div>}
            <button type="submit" style={submitBtn(cliLogging)} disabled={cliLogging}>
              {cliLogging ? 'Connecting…' : 'Connect via SF CLI'}
            </button>
          </form>
        )}

        {/* Session ID (SID) */}
        {loginMode === 'token' && (
          <form onSubmit={handleTokenLogin} style={{display:'flex',flexDirection:'column',gap:12}}>
            <div>
              <label style={labelStyle}>Access Token (Session ID)</label>
              <input style={inputStyle} value={tokenForm.access_token}
                onChange={e => setTokenForm({...tokenForm, access_token:e.target.value})}
                placeholder="00D…" required />
            </div>
            <div>
              <label style={labelStyle}>Instance URL</label>
              <input style={inputStyle} value={tokenForm.instance_url}
                onChange={e => setTokenForm({...tokenForm, instance_url:e.target.value})}
                placeholder="https://myorg.my.salesforce.com" required />
            </div>
            {tokenError && <div style={{color:'#fca5a5',fontSize:13}}>{tokenError}</div>}
            <button type="submit" style={submitBtn(tokenLogging)} disabled={tokenLogging}>
              {tokenLogging ? 'Connecting…' : 'Connect with Token'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function OrgDashboard({ auth, onConnect, onNavigate, onAuthChange }) {
  const [catData,         setCatData]         = useState({})
  const [loading,         setLoading]         = useState(true)
  const [showConnectModal,setShowConnectModal] = useState(false)
  const [orgName,         setOrgName]         = useState('')
  const [totalObjects,    setTotal]           = useState(0)
  const [activeCategory,  setActiveCategory]  = useState(null)
  const [topFilter,       setTopFilter]       = useState('all')
  const [orgInfo,         setOrgInfo]         = useState(null)
  const [storageData,     setStorageData]     = useState(null)
  const [storageLoading,  setStorageLoading]  = useState(false)
  const [coverageData,    setCoverageData]    = useState(null)
  const [coverageLoading, setCoverageLoading] = useState(false)
  const [healthScores,    setHealthScores]    = useState(null)
  const [healthLoading,   setHealthLoading]   = useState(false)

  useEffect(() => {
    if (!auth) { setOrgInfo(null); return }
    fetch('/auth/org-info',{credentials:'include'})
      .then(r=>r.ok?r.json():null).then(d=>{if(d)setOrgInfo(d)}).catch(()=>{})
  }, [auth])

  useEffect(() => {
    if (!auth) { setStorageData(null); return }
    setStorageLoading(true)
    fetch('/auth/limits',{credentials:'include'})
      .then(r=>r.ok?r.json():null).then(d=>{if(d)setStorageData(d)}).catch(()=>{})
      .finally(()=>setStorageLoading(false))
  }, [auth])

  useEffect(() => {
    if (!auth) { setCoverageData(null); return }
    setCoverageLoading(true)
    fetch('/auth/apex-coverage',{credentials:'include'})
      .then(r=>r.ok?r.json():null).then(d=>{if(d)setCoverageData(d)}).catch(()=>{})
      .finally(()=>setCoverageLoading(false))
  }, [auth])

  useEffect(() => {
    if (!auth) { setHealthScores(null); return }
    setHealthLoading(true)
    fetch('/scan/latest-health', { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d?.health_scores) {
          const hs = d.health_scores
          setHealthScores({
            apex:   hs.apex   ?? 70,
            flows:  hs.flows  ?? 70,
            perms:  hs.perms  ?? 70,
            integr: hs.integr ?? 70,
            omni:   hs.omni   ?? 70,
            crm:    Math.round(((hs.apex ?? 70) + (hs.flows ?? 70)) / 2),
            custom: hs.omni   ?? 70,
          })
        }
      })
      .catch(() => {})
      .finally(() => setHealthLoading(false))
  }, [auth])

  useEffect(() => {
    if (!auth) { setLoading(false); return }
    setLoading(true)
    fetch('/migrate/describe',{credentials:'include'})
      .then(r=>r.ok?r.json():null)
      .then(data=>{
        if(!data) return
        const map={}; let tot=0
        data.groups?.forEach(grp=>{
          grp.objects?.forEach(o=>{if(o.available){map[grp.key]=(map[grp.key]||0)+(o.count||0);tot+=(o.count||0)}})
        })
        setCatData(map); setTotal(tot)
        setOrgName(auth.instance_url?.replace('https://','').split('.')[0]||'Org')
      })
      .catch(()=>{}).finally(()=>setLoading(false))
  }, [auth])

  const getHealth = (key) => healthScores?.[key] ?? null
  const getCatCount = (key) => catData[key] ?? null

  const scanData    = [12,18,14,22,19,28,24,30,26,34,29,38]
  const findingData = [3,5,4,7,6,9,7,11,8,13,10,15]

  const FINDINGS = [
    { icon:'⚡', title:'Apex class MassEmailService missing governor limit checks', sub:'Apex · 2 days ago',  badge:'Security',    badgeColor:C.red,    severity:C.red    },
    { icon:'🌊', title:'Flow "Lead_Auto_Convert" has no fault path on DML',         sub:'Flow · 3 days ago',  badge:'Reliability', badgeColor:C.orange, severity:C.orange },
    { icon:'🛡️', title:'Profile "Sales User" has ViewAllData permission',           sub:'Perms · 5 days ago', badge:'Access',      badgeColor:C.yellow, severity:C.yellow },
    { icon:'🔷', title:'Custom object Invoice__c missing FLS on 14 fields',         sub:'Custom · 1 wk ago',  badge:'FLS',         badgeColor:'#818cf8',severity:C.orange },
  ]
  const RECS = [
    { icon:'🔧', title:'Add null-check guards to 8 Apex trigger handlers',          sub:'Best Practice · High',   badge:'Apex',    badgeColor:C.orange, severity:C.orange },
    { icon:'📋', title:'Enable field history tracking on Opportunity Amount',        sub:'Audit · Medium',          badge:'Data',    badgeColor:C.purple, severity:C.yellow },
    { icon:'🔐', title:'Restrict ConnectedApp OAuth scopes to minimum required',     sub:'Security · High',         badge:'Security',badgeColor:C.red,    severity:C.red    },
    { icon:'📦', title:'Remove 23 inactive workflow rules to reduce org complexity', sub:'Maintenance · Low',        badge:'Cleanup', badgeColor:C.cyan,   severity:C.cyan   },
  ]

  const filteredCats = CATEGORIES.filter(cat => {
    if (topFilter==='custom') return cat.key==='custom'
    if (topFilter==='issues') { const h=getHealth(cat.key); return h!=null&&h<65 }
    return true
  })

  return (
    <div style={{
      flex:1,overflowY:'auto',overscrollBehavior:'none',background:C.bg,
      padding:'20px 24px 60px',fontFamily:'system-ui,-apple-system,sans-serif',
    }}>
      <style>{ANIM_CSS}</style>

      {/* ── TOP BAR ── */}
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20,flexWrap:'wrap',gap:12}}>
        <div>
          <div style={{display:'flex',alignItems:'center',gap:10}}>
            <h1 style={{fontSize:24,fontWeight:800,color:C.text,margin:0,letterSpacing:'-0.02em'}}>
              {auth ? `${orgName||'Org'} · Overview` : 'ProWorker'}
            </h1>
            {auth && (
              <span style={{fontSize:10,fontWeight:700,color:C.green,
                background:'rgba(34,197,94,0.12)',border:'1px solid rgba(34,197,94,0.25)',
                borderRadius:20,padding:'2px 10px',letterSpacing:'0.06em'}}>LIVE</span>
            )}
          </div>
          <p style={{color:C.textLo,fontSize:13,margin:'4px 0 0'}}>
            {auth ? `Connected to ${auth.instance_url}` : 'AI-powered Salesforce org analysis, migration & documentation'}
          </p>
        </div>
        <div style={{display:'flex',gap:10}}>
          {[{id:'all',label:'All Objects'},{id:'custom',label:'Custom Only'},{id:'issues',label:'Issues Only'}].map(f=>(
            <button key={f.id} onClick={()=>setTopFilter(f.id)} style={{
              padding:'6px 14px',borderRadius:20,fontSize:12,cursor:'pointer',fontWeight:600,
              border: topFilter===f.id?`1px solid ${C.cyan}`:`1px solid ${C.border}`,
              background: topFilter===f.id?C.cyanLo:'transparent',
              color: topFilter===f.id?C.cyan:C.textLo,
              transition:'all 0.15s',
            }}>{f.label}</button>
          ))}
          {!auth && (
            <button onClick={() => setShowConnectModal(true)} style={{
              padding:'8px 18px',borderRadius:10,fontSize:13,cursor:'pointer',fontWeight:700,
              background:'linear-gradient(135deg,#06b6d4,#0891b2)',border:'none',color:'white',
            }}>+ Connect Salesforce Org</button>
          )}
        </div>
      </div>

      {/* ── ORG DETAILS ── */}
      {auth && orgInfo && <OrgDetailsCard orgInfo={orgInfo}/>}

      {/* ── MAIN 3-COL GRID ── */}
      <div style={{display:'grid',gridTemplateColumns:'240px 1fr 270px',gap:16,alignItems:'start'}}>

        {/* LEFT: Health Panel */}
        <OrgHealthPanel
          auth={auth}
          scores={healthScores}
          loading={loading&&!!auth}
          scanData={scanData}
          findingData={findingData}
          onNavigate={onNavigate}
        />

        {/* CENTER: Categories + Detail + Storage/Coverage */}
        <div>
          {/* Category Cards 3×2 grid */}
          <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:12,marginBottom:16}}>
            {filteredCats.map(cat=>(
              <CategoryCard
                key={cat.key}
                cat={cat}
                count={getCatCount(cat.key)}
                health={getHealth(cat.key)}
                loading={loading&&!!auth}
                active={activeCategory===cat.key}
                onClick={()=>setActiveCategory(prev=>prev===cat.key?null:cat.key)}
              />
            ))}
          </div>

          {/* Detail Panel */}
          {activeCategory && (()=>{
            const cat=CATEGORIES.find(c=>c.key===activeCategory)
            const detail=CATEGORY_DETAILS[activeCategory]
            return (
              <CategoryDetailPanel
                cat={cat} detail={detail}
                count={getCatCount(activeCategory)}
                health={getHealth(activeCategory)}
                onNavigate={onNavigate}
                onClose={()=>setActiveCategory(null)}
              />
            )
          })()}

          {/* Storage + Coverage 2-col */}
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
            <StoragePanel   data={storageData}  loading={storageLoading&&!!auth}/>
            <ApexCoveragePanel data={coverageData} loading={coverageLoading&&!!auth}/>
          </div>
        </div>

        {/* RIGHT: Action Feed */}
        <ActionFeed findings={FINDINGS} recs={RECS}/>
      </div>

      {/* ── NOT CONNECTED OVERLAY ── */}
      {!auth && (
        <div style={{
          position:'fixed',inset:0,marginLeft:84,
          background:'rgba(5,12,12,0.75)',backdropFilter:'blur(6px)',
          display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',
          gap:16,zIndex:20,
        }}>
          <div style={{fontSize:48}}>🔌</div>
          <div style={{fontSize:22,fontWeight:700,color:C.text}}>Connect a Salesforce Org</div>
          <div style={{fontSize:14,color:C.textLo,maxWidth:360,textAlign:'center',lineHeight:1.7}}>
            Get live object counts, health scores, findings and AI-powered recommendations for your org.
          </div>
          <button onClick={() => setShowConnectModal(true)} style={{
            padding:'12px 28px',borderRadius:12,fontSize:14,fontWeight:700,
            background:'linear-gradient(135deg,#06b6d4,#0891b2)',
            border:'none',color:'white',cursor:'pointer',
            boxShadow:'0 0 32px rgba(6,182,212,0.35)',
          }}>+ Connect Salesforce Org</button>
        </div>
      )}

      {showConnectModal && (
        <ConnectOrgModal
          onClose={() => setShowConnectModal(false)}
          onAuthChange={onAuthChange}
        />
      )}
    </div>
  )
}
