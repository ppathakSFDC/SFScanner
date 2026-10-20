import React from 'react'

const s = {
  nav: {
    background: '#0d1e1e',
    borderBottom: '1px solid #0f2e2e',
    padding: '0 24px',
    display: 'flex',
    alignItems: 'center',
    height: 56,
    gap: 4,
  },
  brand: {
    fontSize: 18,
    fontWeight: 700,
    color: '#f1f5f9',
    marginRight: 24,
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  tabs: { display: 'flex', gap: 2, flex: 1 },
  tab: {
    padding: '6px 16px',
    borderRadius: 8,
    border: 'none',
    background: 'transparent',
    color: '#94a3b8',
    fontSize: 14,
    fontWeight: 500,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    transition: 'all 0.15s',
  },
  tabActive: {
    background: 'rgba(99,102,241,0.15)',
    color: '#67e8f9',
  },
  status: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 12,
    color: '#94a3b8',
    padding: '4px 10px',
    borderRadius: 20,
    background: '#050c0c',
    border: '1px solid #0f2e2e',
  },
  dot: (connected) => ({
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: connected ? '#22c55e' : '#4a9a9a',
    flexShrink: 0,
  }),
}

const TABS = [
  { id: 'agents', label: 'Agents', icon: '🤖' },
  { id: 'scanner', label: 'Scanner', icon: '🔍', requiresAuth: true },
  { id: 'connections', label: 'Connections', icon: '🔗' },
]

export default function NavBar({ activePage, onNavigate, auth }) {
  return (
    <nav style={s.nav}>
      <div style={s.brand}>
        <img src="/proworker-logo.png" alt="ProWorker" style={{ width: 22, height: 22, borderRadius: 5, objectFit: 'cover' }} />
        ProWorker
      </div>
      <div style={s.tabs}>
        {TABS.filter(t => !t.requiresAuth || auth).map(tab => (
          <button
            key={tab.id}
            style={{ ...s.tab, ...(activePage === tab.id ? s.tabActive : {}) }}
            onClick={() => onNavigate(tab.id)}
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>
      <div style={s.status}>
        <div style={s.dot(!!auth)} />
        {auth ? 'Org Connected' : 'No Org'}
      </div>
    </nav>
  )
}
