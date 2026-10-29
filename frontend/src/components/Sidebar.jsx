import React, { useState } from 'react'

const ACCENT = '#06b6d4'
const SIDEBAR_W = 190
const HEADER_H = 52

const NAV_ITEMS = [
  {
    id: 'agents', label: 'Home',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <path d="M3 12L12 3l9 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M9 21V12h6v9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    id: 'scanner', label: 'Scanner',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2"/>
        <path d="M16.5 16.5L21 21" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
        <path d="M8 11h6M11 8v6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: 'orgscan', label: 'Org Scan',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <rect x="3" y="14" width="4" height="7" rx="1" stroke="currentColor" strokeWidth="1.8"/>
        <rect x="10" y="9" width="4" height="12" rx="1" stroke="currentColor" strokeWidth="1.8"/>
        <rect x="17" y="3" width="4" height="18" rx="1" stroke="currentColor" strokeWidth="1.8"/>
      </svg>
    ),
  },
  {
    id: 'migrate', label: 'Migrate',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <path d="M7 16L3 12l4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M17 8l4 4-4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M3 12h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: 'info', label: 'Info',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <ellipse cx="12" cy="7" rx="8" ry="3" stroke="currentColor" strokeWidth="1.8"/>
        <path d="M4 7v5c0 1.66 3.58 3 8 3s8-1.34 8-3V7" stroke="currentColor" strokeWidth="1.8"/>
        <path d="M4 12v5c0 1.66 3.58 3 8 3s8-1.34 8-3v-5" stroke="currentColor" strokeWidth="1.8"/>
      </svg>
    ),
  },
  {
    id: 'security', label: 'Security',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <path d="M12 2L4 5v6c0 5.25 3.5 10.15 8 11.35C16.5 21.15 20 16.25 20 11V5l-8-3z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx="12" cy="11" r="2" stroke="currentColor" strokeWidth="1.8"/>
        <line x1="12" y1="13" x2="12" y2="16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: 'gdpr', label: 'Compliance',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <path d="M12 2L4 5v6c0 5.25 3.5 10.15 8 11.35C16.5 21.15 20 16.25 20 11V5l-8-3z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M9 12l2 2 4-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    id: 'professor', label: 'Professor',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M2 17l10 5 10-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    id: 'crm_agent', label: 'CRM Agent',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    id: 'rc_product_agent', label: 'RC Builder',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.8"/>
        <rect x="14" y="3" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.8"/>
        <rect x="3" y="14" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.8"/>
        <path d="M17.5 14v6M14.5 17h6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: 'compare', label: 'Compare Orgs',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <path d="M7 16L3 12l4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M17 8l4 4-4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <line x1="3" y1="12" x2="21" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeDasharray="4 3"/>
      </svg>
    ),
  },
  {
    id: 'connections', label: 'Settings',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2"/>
        <path d="M12 2v2M12 20v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M2 12h2M20 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
  },
]

function NavItem({ item, active, onClick }) {
  const [hovered, setHovered] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        width: '100%', height: 44, padding: '0 16px',
        display: 'flex', alignItems: 'center', gap: 12,
        background: active
          ? 'var(--sidebar-active-bg)'
          : hovered ? 'var(--sidebar-hover-bg)' : 'transparent',
        borderLeft: active ? `3px solid ${ACCENT}` : '3px solid transparent',
        border: 'none', borderTop: 'none', borderBottom: 'none', borderRight: 'none',
        borderLeftWidth: 3, borderLeftStyle: 'solid',
        borderLeftColor: active ? ACCENT : 'transparent',
        cursor: 'pointer', transition: 'all 0.15s',
        color: active ? 'var(--sidebar-text-active)' : hovered ? 'var(--sidebar-text-hover)' : 'var(--sidebar-text)',
      }}
    >
      <span style={{ flexShrink: 0, color: active ? ACCENT : 'inherit', display: 'flex' }}>
        {item.icon}
      </span>
      <span style={{ fontSize: 13, fontWeight: active ? 600 : 400 }}>{item.label}</span>
    </button>
  )
}

export default function Sidebar({ activePage, onNavigate, auth }) {
  return (
    <div style={{
      position: 'fixed',
      left: 0, top: HEADER_H,
      width: SIDEBAR_W,
      height: `calc(100vh - ${HEADER_H}px)`,
      background: 'var(--sidebar-bg)',
      borderRight: '1px solid var(--sidebar-border)',
      display: 'flex', flexDirection: 'column',
      zIndex: 20,
    }}>
      {/* Nav items */}
      <div style={{ flex: 1, paddingTop: 12 }}>
        {NAV_ITEMS.map(item => (
          <NavItem
            key={item.id}
            item={item}
            active={activePage === item.id || (activePage === 'agents' && item.id === 'agents')}
            onClick={() => onNavigate(item.id)}
          />
        ))}
      </div>

      {/* Bottom illustration */}
      <div style={{ padding: '20px 16px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
        {/* Cloud + shield SVG illustration */}
        <svg width="88" height="72" viewBox="0 0 88 72" fill="none">
          <defs>
            <linearGradient id="cloudGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#1e3a6e"/>
              <stop offset="100%" stopColor="#0f2d5a"/>
            </linearGradient>
            <linearGradient id="shieldGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#06b6d4"/>
              <stop offset="100%" stopColor="#0891b2"/>
            </linearGradient>
          </defs>
          {/* Mountain base */}
          <path d="M0 72 L22 38 L36 52 L52 28 L72 55 L88 72 Z" fill="url(#cloudGrad)" opacity="0.7"/>
          {/* Cloud */}
          <ellipse cx="44" cy="38" rx="24" ry="14" fill="url(#shieldGrad)" opacity="0.9"/>
          <ellipse cx="32" cy="42" rx="16" ry="10" fill="url(#shieldGrad)" opacity="0.9"/>
          <ellipse cx="56" cy="42" rx="16" ry="10" fill="url(#shieldGrad)" opacity="0.9"/>
          <rect x="26" y="40" width="36" height="16" fill="url(#shieldGrad)" opacity="0.9"/>
          {/* Shield icon */}
          <path d="M44 28 L54 32 L54 40 C54 45 44 50 44 50 C44 50 34 45 34 40 L34 32 Z"
            fill="white" opacity="0.95"/>
          <path d="M40 40 L43 43 L49 36" stroke="url(#shieldGrad)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
        </svg>

        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'white', marginBottom: 2 }}>Better Orgs.</div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>Stronger Salesforce.</div>
        </div>

        {/* Connection status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: auth ? '#22c55e' : 'rgba(255,255,255,0.3)',
            boxShadow: auth ? '0 0 6px rgba(34,197,94,0.5)' : 'none',
          }} />
          <span style={{ fontSize: 11, color: auth ? 'rgba(255,255,255,0.6)' : 'rgba(255,255,255,0.3)' }}>
            {auth ? 'Org Connected' : 'Not Connected'}
          </span>
        </div>
      </div>
    </div>
  )
}
