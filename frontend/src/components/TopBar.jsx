import React, { useState, useRef, useEffect } from 'react'
import OrgAuthModal from './OrgAuthModal.jsx'

export default function TopBar({ auth, onNavigate, theme, onToggleTheme, onAuthChange }) {
  const [search, setSearch] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [authError, setAuthError] = useState('')
  const menuRef = useRef(null)

  const orgDomain = auth?.instance_url
    ? auth.instance_url.replace('https://', '').split('.')[0]
    : null

  const userAlias = auth?.alias?.trim() || ''
  const initials = userAlias
    ? userAlias.slice(0, 2).toUpperCase()
    : (orgDomain ? orgDomain.slice(0, 2).toUpperCase() : 'SF')

  const displayName = userAlias || orgDomain || 'User'

  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false)
      }
    }
    if (menuOpen) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [menuOpen])

  async function handleOAuthConnect(loginUrl, alias) {
    setAuthError('')
    try {
      const params = new URLSearchParams({ popup: 'source' })
      if (loginUrl && loginUrl !== 'https://login.salesforce.com') params.set('login_url', loginUrl)
      const res = await fetch(`/auth/platform-login?${params}`, { credentials: 'include' })
      if (!res.ok) throw new Error('Failed to start authorization')
      const { auth_url, job_id } = await res.json()

      const win = window.open(auth_url, '_blank')
      if (!win) { setAuthError('Could not open popup. Allow popups for this site.'); return }

      const pollRef = { id: null }
      pollRef.id = setInterval(async () => {
        try {
          const r = await fetch(`/auth/platform-status/${job_id}`, { credentials: 'include' })
          if (!r.ok) return
          const data = await r.json()
          if (data.status === 'pending') return
          clearInterval(pollRef.id)
          if (data.status === 'error') { setAuthError(`Authorization failed: ${data.error}`); return }
          const me = await fetch('/auth/me', { credentials: 'include' })
          if (me.ok) {
            const d = await me.json()
            if (d.authenticated && onAuthChange) onAuthChange({ ...d, alias: alias || d.alias || '', authenticated: true })
          }
          setShowSettings(false)
        } catch {}
      }, 1000)
      setTimeout(() => clearInterval(pollRef.id), 300_000)
    } catch (e) {
      setAuthError(`Failed to start authorization: ${e.message}`)
    }
  }

  async function handleCredentialsConnect(username, password, loginUrl, alias) {
    const domain = loginUrl.replace('https://', '').replace(/\/$/, '') || 'login.salesforce.com'
    const res = await fetch('/auth/login-password', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
      body: JSON.stringify({ username, password, domain, alias: alias || '' }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Authentication failed')
    const me = await fetch('/auth/me', { credentials: 'include' })
    if (me.ok) {
      const d = await me.json()
      if (d.authenticated && onAuthChange) onAuthChange({ ...d, authenticated: true })
    }
    setShowSettings(false)
  }

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, height: 52,
      background: 'var(--topbar-bg)', zIndex: 30,
      display: 'flex', alignItems: 'center',
      padding: '0 20px', gap: 16,
      borderBottom: '1px solid rgba(255,255,255,0.07)',
    }}>
      {/* Logo + Brand */}
      <div onClick={() => onNavigate?.('agents')} style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0, minWidth: 170, cursor: 'pointer' }}>
        <img
          src="/proworker-logo.png"
          alt="ProWorker"
          style={{ width: 34, height: 34, borderRadius: 10, objectFit: 'cover', flexShrink: 0 }}
        />
        <div>
          <div style={{ fontSize: 15, fontWeight: 800, color: 'white', lineHeight: 1.1, letterSpacing: '-0.01em' }}>ProWorker</div>
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.45)', fontWeight: 500 }}>Scan. Fix. Deploy.</div>
        </div>
      </div>

      {/* Divider */}
      <div style={{ width: 1, height: 28, background: 'rgba(255,255,255,0.1)', flexShrink: 0 }} />

      {/* Search */}
      <div style={{ flex: 1, maxWidth: 520, position: 'relative' }}>
        <svg style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }}
          width="15" height="15" viewBox="0 0 24 24" fill="none">
          <circle cx="11" cy="11" r="7" stroke="rgba(255,255,255,0.4)" strokeWidth="2"/>
          <path d="M16 16l4 4" stroke="rgba(255,255,255,0.4)" strokeWidth="2.5" strokeLinecap="round"/>
        </svg>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search components, issues, or go to..."
          style={{
            width: '100%', height: 36, paddingLeft: 36, paddingRight: 12,
            background: 'var(--topbar-search)', border: '1px solid var(--topbar-in-border)',
            borderRadius: 8, color: 'white', fontSize: 13, outline: 'none',
            boxSizing: 'border-box',
          }}
        />
      </div>

      <div style={{ flex: 1 }} />

      {/* Right side */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        {/* Org pill */}
        {auth ? (
          <button
            onClick={() => onNavigate?.('connections')}
            style={{
              display: 'flex', alignItems: 'center', gap: 7,
              padding: '6px 12px', background: 'rgba(255,255,255,0.08)',
              border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8,
              color: 'white', fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M4 13.5A8.5 8.5 0 0 1 12 5a8.5 8.5 0 0 1 8 5.5" stroke="#06b6d4" strokeWidth="2" strokeLinecap="round"/>
              <path d="M4 13.5C4 18.2 7.6 22 12 22s8-3.8 8-8.5" stroke="#06b6d4" strokeWidth="2" strokeLinecap="round"/>
              <circle cx="12" cy="13" r="3" fill="#06b6d4"/>
            </svg>
            <span>{orgDomain || 'Production'}</span>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none">
              <path d="M6 9l6 6 6-6" stroke="rgba(255,255,255,0.5)" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        ) : (
          <button
            onClick={() => onNavigate?.('connections')}
            style={{
              padding: '7px 16px', background: 'linear-gradient(135deg,#06b6d4,#0891b2)',
              border: 'none', borderRadius: 8, color: 'white',
              fontSize: 12, fontWeight: 700, cursor: 'pointer',
            }}>
            + Connect Org
          </button>
        )}

        {/* Theme toggle */}
        <button
          onClick={onToggleTheme}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          style={{
            width: 34, height: 34, borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)',
            background: 'rgba(255,255,255,0.06)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16, transition: 'background 0.15s',
          }}>
          {theme === 'dark' ? '☀️' : '🌙'}
        </button>

        {/* Bell */}
        <button style={{
          width: 34, height: 34, borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)',
          background: 'rgba(255,255,255,0.06)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M6 10a6 6 0 1 1 12 0v4l2 2H4l2-2v-4z" stroke="rgba(255,255,255,0.6)" strokeWidth="1.8"/>
            <path d="M10 18a2 2 0 0 0 4 0" stroke="rgba(255,255,255,0.6)" strokeWidth="1.8" strokeLinecap="round"/>
          </svg>
        </button>

        {/* Avatar with dropdown */}
        <div ref={menuRef} style={{ position: 'relative', flexShrink: 0 }}>
          <div
            onClick={() => setMenuOpen(o => !o)}
            title={displayName}
            style={{
              width: 34, height: 34, borderRadius: '50%',
              background: menuOpen
                ? 'linear-gradient(135deg,#0891b2,#1d4ed8)'
                : 'linear-gradient(135deg,#06b6d4,#2563eb)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12, fontWeight: 700, color: 'white', cursor: 'pointer',
              boxShadow: menuOpen ? '0 0 0 2px rgba(6,182,212,0.5)' : 'none',
              transition: 'box-shadow 0.15s, background 0.15s',
              userSelect: 'none',
            }}
          >
            {initials}
          </div>

          {menuOpen && (
            <div style={{
              position: 'absolute', top: 'calc(100% + 8px)', right: 0,
              background: 'var(--sidebar-bg, #0d1e1e)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 10, minWidth: 200,
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
              zIndex: 100, overflow: 'hidden',
            }}>
              {/* User info header */}
              <div style={{
                padding: '14px 16px 12px',
                borderBottom: '1px solid rgba(255,255,255,0.08)',
              }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: '50%',
                    background: 'linear-gradient(135deg,#06b6d4,#2563eb)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 13, fontWeight: 700, color: 'white', flexShrink: 0,
                  }}>
                    {initials}
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'white' }}>{displayName}</div>
                    {orgDomain && (
                      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', marginTop: 1 }}>
                        {orgDomain}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Menu items */}
              {[
                {
                  icon: (
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2"/>
                      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" stroke="currentColor" strokeWidth="2"/>
                    </svg>
                  ),
                  label: 'Settings',
                  action: () => { setMenuOpen(false); setAuthError(''); setShowSettings(true) },
                },
                {
                  icon: (
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2"/>
                      <path d="M12 8v4M12 16h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                    </svg>
                  ),
                  label: 'About',
                  action: () => { onNavigate?.('info'); setMenuOpen(false) },
                },
              ].map(item => (
                <button
                  key={item.label}
                  onClick={item.action}
                  style={{
                    width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                    padding: '10px 16px', background: 'none', border: 'none',
                    color: 'rgba(255,255,255,0.75)', fontSize: 13, cursor: 'pointer',
                    textAlign: 'left', transition: 'background 0.1s, color 0.1s',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.07)'; e.currentTarget.style.color = 'white' }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'none'; e.currentTarget.style.color = 'rgba(255,255,255,0.75)' }}
                >
                  <span style={{ color: 'rgba(6,182,212,0.85)' }}>{item.icon}</span>
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Settings / Connect Org modal */}
      {showSettings && (
        <>
          {authError && (
            <div style={{
              position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
              background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.35)',
              borderRadius: 8, padding: '10px 18px', color: '#fca5a5', fontSize: 13,
              zIndex: 1100, maxWidth: 480, textAlign: 'center',
            }}>
              {authError}
            </div>
          )}
          <OrgAuthModal
            title="Connect Org"
            showAlias={true}
            onClose={() => { setShowSettings(false); setAuthError('') }}
            onAuthorize={(loginUrl, alias) => handleOAuthConnect(loginUrl, alias)}
            onCredentials={(user, pass, loginUrl, alias) => handleCredentialsConnect(user, pass, loginUrl, alias)}
          />
        </>
      )}
    </div>
  )
}
