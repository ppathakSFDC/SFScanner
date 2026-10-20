import React from 'react'

export default function OrgAuthModal({ title, requireAlias = false, showAlias = false, onClose, onAuthorize, onCredentials, defaultTab = 'oauth' }) {
  const [tab, setTab]             = React.useState(defaultTab)
  const [alias, setAlias]         = React.useState('')
  const [env, setEnv]             = React.useState('production')
  const [customUrl, setCustomUrl] = React.useState('')
  const [urlError, setUrlError]   = React.useState('')
  const [credUser, setCredUser]   = React.useState('')
  const [credPass, setCredPass]   = React.useState('')
  const [credErr, setCredErr]     = React.useState('')
  const [credLoading, setCredLoading] = React.useState(false)

  function getLoginUrl() {
    if (env === 'sandbox') return 'https://test.salesforce.com'
    if (env === 'custom') return customUrl.trim()
    return 'https://login.salesforce.com'
  }

  function validateCommon() {
    if (requireAlias && !alias.trim()) return 'Alias is required'
    if (env === 'custom') {
      const u = customUrl.trim()
      if (!u) return 'Instance URL is required'
      if (!u.startsWith('https://')) return 'Must be a valid https Salesforce URL.'
      if (!/(salesforce\.com|force\.com)$/i.test(u)) return 'Must be a valid https Salesforce URL.'
    }
    return null
  }

  function handleAuthorize() {
    const err = validateCommon()
    if (err) { setUrlError(err); return }
    onAuthorize(getLoginUrl(), alias.trim())
  }

  async function handleCredentials() {
    const commonErr = validateCommon()
    if (commonErr) { setUrlError(commonErr); return }
    if (!credUser.trim()) { setCredErr('Username is required'); return }
    if (!credPass) { setCredErr('Password is required'); return }
    setCredErr(''); setCredLoading(true)
    try {
      await onCredentials(credUser.trim(), credPass, getLoginUrl(), alias.trim())
    } catch (e) {
      setCredErr(e.message || 'Authentication failed')
    } finally {
      setCredLoading(false)
    }
  }

  const inp = (hasErr) => ({
    width: '100%', padding: '10px 14px', boxSizing: 'border-box',
    background: 'var(--input-bg)', color: 'var(--input-color)',
    border: `1px solid ${hasErr ? '#ef4444' : 'var(--input-border)'}`,
    borderRadius: 8, fontSize: 14, outline: 'none', fontFamily: 'inherit',
  })
  const lbl = { display: 'block', fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: 'var(--text-mid)', marginBottom: 10, textTransform: 'uppercase' }

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 14, padding: '32px 36px', width: 480, maxWidth: '94vw', boxShadow: '0 24px 60px rgba(0,0,0,0.45)' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)', flex: 1 }}>{title}</div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-lo)', cursor: 'pointer', fontSize: 22, lineHeight: 1 }}>×</button>
        </div>

        {/* Tab switcher */}
        <div style={{ display: 'flex', gap: 0, marginBottom: 24, background: 'var(--surface-hi)', borderRadius: 8, padding: 4 }}>
          {[['oauth', 'Browser OAuth'], ['credentials', 'Use Credentials']].map(([key, label]) => (
            <button key={key} onClick={() => { setTab(key); setUrlError(''); setCredErr('') }}
              style={{ flex: 1, padding: '7px 0', background: tab === key ? 'var(--surface)' : 'transparent', border: tab === key ? '1px solid var(--border)' : '1px solid transparent', borderRadius: 6, color: tab === key ? 'var(--text)' : 'var(--text-mid)', fontSize: 13, fontWeight: tab === key ? 600 : 400, cursor: 'pointer', transition: 'all 0.15s' }}>
              {label}
            </button>
          ))}
        </div>

        {/* Alias */}
        {(requireAlias || showAlias) && (
          <div style={{ marginBottom: 24 }}>
            <label style={lbl}>Alias{requireAlias ? ' (Required)' : ' (Optional)'}</label>
            <input style={inp(urlError === 'Alias is required')} value={alias} onChange={e => { setAlias(e.target.value); setUrlError('') }}
              placeholder="e.g. MyOrg" autoFocus={tab === 'oauth'} autoComplete="off" />
            {urlError === 'Alias is required' && <div style={{ fontSize: 12, color: '#ef4444', marginTop: 5 }}>{urlError}</div>}
          </div>
        )}

        {/* Environment */}
        <div style={{ marginBottom: 24 }}>
          <label style={lbl}>Environment</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[['production', 'Production'], ['sandbox', 'Sandbox'], ['custom', 'Custom']].map(([val, label]) => (
              <label key={val} style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
                <div style={{
                  width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
                  border: `2px solid ${env === val ? '#3b82f6' : 'var(--border-hi)'}`,
                  background: env === val ? '#3b82f6' : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: env === val ? '0 0 0 3px rgba(59,130,246,0.2)' : 'none',
                  transition: 'all 0.15s',
                }} onClick={() => { setEnv(val); setUrlError('') }}>
                  {env === val && <div style={{ width: 7, height: 7, borderRadius: '50%', background: 'white' }} />}
                </div>
                <span style={{ fontSize: 14, color: 'var(--text)', fontWeight: env === val ? 600 : 400 }}
                  onClick={() => { setEnv(val); setUrlError('') }}>{label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Custom URL */}
        {env === 'custom' && (
          <div style={{ marginBottom: 24 }}>
            <label style={lbl}>Instance URL</label>
            <input style={{ ...inp(!!urlError && urlError !== 'Alias is required'), fontFamily: 'monospace', fontSize: 13 }}
              value={customUrl} onChange={e => { setCustomUrl(e.target.value); setUrlError('') }}
              placeholder="https://yourorg.my.salesforce.com" autoComplete="off" />
            {urlError && urlError !== 'Alias is required' && (
              <div style={{ fontSize: 12, color: '#ef4444', marginTop: 5 }}>{urlError}</div>
            )}
            <div style={{ fontSize: 11, color: 'var(--text-lo)', marginTop: 5 }}>
              Lightning URLs like <code style={{ color: '#93c5fd' }}>*.lightning.force.com</code> are automatically converted.
            </div>
          </div>
        )}

        {/* Credentials fields */}
        {tab === 'credentials' && (
          <div style={{ marginBottom: 24 }}>
            <div style={{ marginBottom: 14 }}>
              <label style={lbl}>Username</label>
              <input style={inp(credErr === 'Username is required')} value={credUser}
                onChange={e => { setCredUser(e.target.value); setCredErr('') }}
                placeholder="user@example.com" autoFocus autoComplete="username" />
            </div>
            <div>
              <label style={lbl}>Password + Security Token</label>
              <input type="password" style={inp(credErr === 'Password is required')} value={credPass}
                onChange={e => { setCredPass(e.target.value); setCredErr('') }}
                placeholder="passwordSECURITYTOKEN" autoComplete="current-password" />
              <div style={{ fontSize: 11, color: 'var(--text-lo)', marginTop: 5 }}>
                Append your security token to the password if your IP is not allowlisted.
              </div>
            </div>
            {credErr && <div style={{ fontSize: 12, color: '#fca5a5', marginTop: 10, padding: '8px 10px', background: 'rgba(239,68,68,0.07)', borderRadius: 6, border: '1px solid rgba(239,68,68,0.25)' }}>{credErr}</div>}
          </div>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 4 }}>
          <button onClick={onClose} style={{ padding: '10px 24px', background: 'transparent', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-mid)', fontSize: 14, cursor: 'pointer', fontWeight: 500 }}>Cancel</button>
          {tab === 'oauth' ? (
            <button onClick={handleAuthorize} style={{ padding: '10px 32px', background: 'linear-gradient(135deg,#1e40af,#3b82f6)', border: 'none', borderRadius: 8, color: 'white', fontSize: 14, cursor: 'pointer', fontWeight: 700, boxShadow: '0 4px 12px rgba(59,130,246,0.35)' }}>
              Authorize
            </button>
          ) : (
            <button onClick={handleCredentials} disabled={credLoading} style={{ padding: '10px 32px', background: credLoading ? 'rgba(59,130,246,0.5)' : 'linear-gradient(135deg,#1e40af,#3b82f6)', border: 'none', borderRadius: 8, color: 'white', fontSize: 14, cursor: credLoading ? 'not-allowed' : 'pointer', fontWeight: 700, boxShadow: '0 4px 12px rgba(59,130,246,0.35)' }}>
              {credLoading ? 'Connecting…' : 'Connect'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
