import React, { useState, useEffect } from 'react'

const s = {
  page: {
    height: '100%',
    background: 'var(--bg)',
    padding: '32px 24px',
    overflowY: 'auto',
    overscrollBehavior: 'none',
  },
  inner: { maxWidth: 640, margin: '0 auto' },
  title: { fontSize: 26, fontWeight: 700, color: 'var(--text)', marginBottom: 6 },
  subtitle: { color: 'var(--text-mid)', fontSize: 15, marginBottom: 32 },
  section: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 14,
    padding: 28,
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: 700,
    color: '#06b6d4',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    marginBottom: 18,
  },
  statusCard: {
    background: 'rgba(34,197,94,0.06)',
    border: '1px solid rgba(34,197,94,0.2)',
    borderRadius: 10,
    padding: '14px 18px',
    marginBottom: 16,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: '50%',
    background: '#22c55e',
    flexShrink: 0,
  },
  statusText: { color: '#86efac', fontSize: 14, fontWeight: 600 },
  statusSub: { color: '#4ade80', fontSize: 12, marginTop: 2 },
  btnRow: { display: 'flex', gap: 10, flexWrap: 'wrap' },
  btnPrimary: {
    padding: '9px 18px',
    background: 'linear-gradient(135deg, #06b6d4, #0891b2)',
    border: 'none',
    borderRadius: 8,
    color: 'white',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
  btnDanger: {
    padding: '9px 18px',
    background: 'transparent',
    border: '1px solid rgba(239,68,68,0.4)',
    borderRadius: 8,
    color: '#fca5a5',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
  noOrg: {
    color: 'var(--text-mid)',
    fontSize: 14,
    marginBottom: 16,
    lineHeight: 1.6,
  },
  field: { marginBottom: 16 },
  label: { display: 'block', fontSize: 13, color: 'var(--text-mid)', marginBottom: 6, fontWeight: 500 },
  input: {
    width: '100%',
    padding: '10px 12px',
    background: 'var(--input-bg)',
    border: '1px solid var(--input-border)',
    borderRadius: 8,
    color: 'var(--input-color)',
    fontSize: 14,
    boxSizing: 'border-box',
    outline: 'none',
  },
  hint: { fontSize: 11, color: 'var(--text-lo)', marginTop: 4 },
  saveBtn: {
    padding: '10px 24px',
    background: 'linear-gradient(135deg, #06b6d4, #0891b2)',
    border: 'none',
    borderRadius: 8,
    color: 'white',
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: 4,
  },
  saveBtnDisabled: { opacity: 0.5, cursor: 'not-allowed' },
  success: {
    background: 'rgba(34,197,94,0.06)',
    border: '1px solid rgba(34,197,94,0.2)',
    borderRadius: 8,
    padding: '10px 14px',
    color: '#86efac',
    fontSize: 13,
    marginBottom: 14,
  },
  error: {
    background: 'rgba(239,68,68,0.06)',
    border: '1px solid rgba(239,68,68,0.3)',
    borderRadius: 8,
    padding: '10px 14px',
    color: '#fca5a5',
    fontSize: 13,
    marginBottom: 14,
  },
}

export default function ConnectionsPage({ auth, onLogout, onNavigate, oauthError, onClearError, onAuthChange }) {
  const [savedOrgs, setSavedOrgs] = useState([])
  const [form, setForm] = useState({
    sf_client_id: '',
    sf_client_secret: '',
    anthropic_api_key: '',
    sf_login_url: 'https://login.salesforce.com',
  })
  const [pwForm, setPwForm] = useState({ username: '', password: '', domain: 'login.salesforce.com', alias: '' })
  const [pwLogging, setPwLogging] = useState(false)
  const [pwError, setPwError] = useState('')
  const [tokenForm, setTokenForm] = useState({ access_token: '', instance_url: '' })
  const [tokenLogging, setTokenLogging] = useState(false)
  const [tokenError, setTokenError] = useState('')
  const [cliForm, setCliForm] = useState({ org: '' })
  const [cliLogging, setCliLogging] = useState(false)
  const [cliError, setCliError] = useState('')
  const [loginMode, setLoginMode] = useState('cli')
  const [configMeta, setConfigMeta] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState(null)
  const [saveError, setSaveError] = useState('')
  const [disconnecting, setDisconnecting] = useState(false)

  useEffect(() => {
    fetch('/setup/config')
      .then(r => r.json())
      .then(data => {
        setConfigMeta(data)
        setForm(f => ({ ...f, sf_login_url: data.sf_login_url || f.sf_login_url }))
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetch('/auth/orgs', { credentials: 'include' })
      .then(r => r.ok ? r.json() : { orgs: [] })
      .then(d => setSavedOrgs(d.orgs || []))
      .catch(() => {})
  }, [auth])

  async function switchOrg(orgKey) {
    const res = await fetch(`/auth/orgs/switch/${orgKey}`, {
      method: 'POST', credentials: 'include',
    })
    if (res.ok) {
      const data = await res.json()
      if (onAuthChange) onAuthChange(data)
    }
  }

  async function disconnectOrg(orgKey) {
    await fetch(`/auth/orgs/${orgKey}`, { method: 'DELETE', credentials: 'include' })
    const r = await fetch('/auth/orgs', { credentials: 'include' })
    const d = r.ok ? await r.json() : { orgs: [] }
    setSavedOrgs(d.orgs || [])
    if (d.orgs.length === 0 && onAuthChange) onAuthChange(null)
  }

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))
  const setPw = (k) => (e) => setPwForm(f => ({ ...f, [k]: e.target.value }))
  const setTok = (k) => (e) => setTokenForm(f => ({ ...f, [k]: e.target.value }))
  const setCli = (k) => (e) => setCliForm(f => ({ ...f, [k]: e.target.value }))

  async function handleCliLogin(e) {
    e.preventDefault()
    setCliLogging(true)
    setCliError('')
    try {
      const res = await fetch('/auth/login-cli', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ org: cliForm.org }),
      })
      let data
      try { data = await res.json() } catch { throw new Error(`Server error (${res.status})`) }
      if (!res.ok) throw new Error(data.detail || 'Login failed')
      if (onAuthChange) onAuthChange(data)
      setCliForm({ org: '' })
    } catch (err) {
      setCliError(err.message)
    } finally {
      setCliLogging(false)
    }
  }

  async function handleTokenLogin(e) {
    e.preventDefault()
    setTokenLogging(true)
    setTokenError('')
    try {
      const res = await fetch('/auth/login-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(tokenForm),
      })
      let data
      try { data = await res.json() } catch { throw new Error(`Server error (${res.status})`) }
      if (!res.ok) throw new Error(data.detail || 'Login failed')
      if (onAuthChange) onAuthChange(data)
      setTokenForm({ access_token: '', instance_url: '' })
    } catch (err) {
      setTokenError(err.message)
    } finally {
      setTokenLogging(false)
    }
  }

  async function handlePasswordLogin(e) {
    e.preventDefault()
    setPwLogging(true)
    setPwError('')
    try {
      const res = await fetch('/auth/login-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(pwForm),
      })
      let data
      try { data = await res.json() } catch { throw new Error(`Server error (${res.status})`) }
      if (!res.ok) throw new Error(data.detail || 'Login failed')
      if (onAuthChange) onAuthChange(data)
      setPwForm({ username: '', password: '', domain: 'login.salesforce.com', alias: '' })
    } catch (err) {
      setPwError(err.message)
    } finally {
      setPwLogging(false)
    }
  }

  async function handleDisconnect() {
    setDisconnecting(true)
    try {
      await fetch('/auth/logout', { method: 'POST', credentials: 'include' })
      onLogout()
    } finally {
      setDisconnecting(false)
    }
  }

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    setSaveMsg(null)
    setSaveError('')
    try {
      const payload = {
        sf_login_url: form.sf_login_url,
        ...(form.sf_client_id ? { sf_client_id: form.sf_client_id } : {}),
        ...(form.sf_client_secret ? { sf_client_secret: form.sf_client_secret } : {}),
        ...(form.anthropic_api_key ? { anthropic_api_key: form.anthropic_api_key } : {}),
      }
      const res = await fetch('/setup/configure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error(await res.text())
      setSaveMsg('Configuration saved. Now click "Connect Salesforce Org" above to authenticate.')
      setForm(f => ({ ...f, sf_client_id: '', sf_client_secret: '', anthropic_api_key: '' }))
      const updated = await fetch('/setup/config').then(r => r.json())
      setConfigMeta(updated)
    } catch (err) {
      setSaveError(err.message || 'Failed to save.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={s.page}>
      <div style={s.inner}>
        <h1 style={s.title}>Connections</h1>
        <p style={s.subtitle}>Manage your Salesforce org connection and API configuration.</p>

        {oauthError && (
          <div style={{ ...s.error, display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <span>⚠️ Salesforce OAuth error: <strong>{oauthError}</strong></span>
            <button onClick={onClearError} style={{ background: 'none', border: 'none', color: '#fca5a5', cursor: 'pointer', fontSize: 16 }}>✕</button>
          </div>
        )}

        {savedOrgs.length > 0 && (
          <div style={{ ...s.section, marginBottom: 24 }}>
            <div style={s.sectionTitle}>Connected Orgs ({savedOrgs.length})</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {savedOrgs.map(org => (
                <div key={org.org_key} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 14px', borderRadius: 10,
                  background: org.active ? 'rgba(6,182,212,0.06)' : 'rgba(148,163,184,0.04)',
                  border: `1px solid ${org.active ? 'rgba(6,182,212,0.3)' : 'var(--border)'}`,
                }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)',
                      display: 'flex', alignItems: 'center', gap: 8 }}>
                      {org.label || org.alias || org.instance_url}
                      {org.active && (
                        <span style={{ fontSize: 10, color: '#06b6d4', background: 'rgba(6,182,212,0.12)',
                          borderRadius: 20, padding: '2px 8px', fontWeight: 700 }}>ACTIVE</span>
                      )}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-lo)', marginTop: 2 }}>{org.instance_url}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    {!org.active && (
                      <button onClick={() => switchOrg(org.org_key)} style={{
                        padding: '5px 12px', borderRadius: 7, fontSize: 12, fontWeight: 600,
                        background: 'rgba(6,182,212,0.1)', border: '1px solid rgba(6,182,212,0.3)',
                        color: '#06b6d4', cursor: 'pointer',
                      }}>Switch</button>
                    )}
                    <button onClick={() => disconnectOrg(org.org_key)} style={{
                      padding: '5px 10px', borderRadius: 7, fontSize: 12, fontWeight: 600,
                      background: 'transparent', border: '1px solid rgba(239,68,68,0.3)',
                      color: '#fca5a5', cursor: 'pointer',
                    }}>✕</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={s.section}>
          <div style={s.sectionTitle}>Salesforce Org</div>
          {auth ? (
            <>
              <div style={s.statusCard}>
                <div style={s.statusDot} />
                <div>
                  <div style={s.statusText}>{auth.alias ? auth.alias : 'Connected'}</div>
                  <div style={s.statusSub}>{auth.instance_url}</div>
                </div>
              </div>
              <div style={s.btnRow}>
                <button style={s.btnDanger} onClick={handleDisconnect} disabled={disconnecting}>
                  {disconnecting ? 'Disconnecting…' : 'Disconnect'}
                </button>
              </div>
            </>
          ) : (
            <>
              {/* Mode tabs */}
              <div style={{ display: 'flex', gap: 0, marginBottom: 20, background: 'var(--surface-hi)', borderRadius: 8, padding: 3 }}>
                {[['cli', 'SF CLI Org'], ['token', 'Session ID (SID)'], ['password', 'Username + Password']].map(([mode, label]) => (
                  <button key={mode} onClick={() => setLoginMode(mode)} style={{
                    flex: 1, padding: '7px 0', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                    background: loginMode === mode ? 'var(--surface)' : 'transparent',
                    color: loginMode === mode ? '#67e8f9' : 'var(--text-lo)',
                  }}>{label}</button>
                ))}
              </div>

              {loginMode === 'cli' && (
                <>
                  <div style={{ ...s.noOrg, marginBottom: 16 }}>
                    Connect using an org already authenticated via the Salesforce CLI.<br />
                    Run <strong>sf org list</strong> in your terminal to see available org aliases.
                  </div>
                  {cliError && <div style={s.error}>{cliError}</div>}
                  <form onSubmit={handleCliLogin}>
                    <div style={s.field}>
                      <label style={s.label}>Org Alias or Username</label>
                      <input style={s.input} value={cliForm.org} onChange={setCli('org')}
                        placeholder="e.g. my-sandbox or user@example.com" required autoComplete="off" />
                      <div style={s.hint}>
                        Must be authenticated via <code>sf org login web</code> or <code>sf org login jwt</code> first.
                      </div>
                    </div>
                    <button type="submit" style={{ ...s.saveBtn, ...(cliLogging ? s.saveBtnDisabled : {}) }} disabled={cliLogging}>
                      {cliLogging ? 'Connecting…' : 'Connect via CLI'}
                    </button>
                  </form>
                </>
              )}

              {loginMode === 'token' && (
                <>
                  <div style={{ background: 'var(--surface-hi)', borderRadius: 10, padding: '14px 18px', marginBottom: 16, border: '1px solid var(--border)' }}>
                    <div style={{ color: 'var(--text-mid)', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
                      3 ways to get your Session ID
                    </div>
                    <div style={{ color: 'var(--text-lo)', fontSize: 12, lineHeight: 2 }}>
                      <strong style={{ color: '#a5f3fc' }}>Option 1 — Browser cookie (fastest, no setup)</strong><br />
                      1. Log in to Salesforce in your browser<br />
                      2. Press <code style={{ background: 'var(--surface)', color: '#67e8f9', padding: '1px 5px', borderRadius: 3 }}>F12</code> → Application tab → Cookies → find your org domain<br />
                      3. Copy the value of the cookie named <code style={{ background: 'var(--surface)', color: '#67e8f9', padding: '1px 5px', borderRadius: 3 }}>sid</code><br />
                      <br />
                      <strong style={{ color: '#a5f3fc' }}>Option 2 — Developer Console</strong><br />
                      Open Setup → Developer Console → Execute: <code style={{ background: 'var(--surface)', color: '#67e8f9', padding: '1px 5px', borderRadius: 3 }}>System.debug(UserInfo.getSessionId());</code><br />
                      Copy the value from the debug log<br />
                      <br />
                      <strong style={{ color: '#a5f3fc' }}>Option 3 — Salesforce CLI</strong><br />
                      Run: <code style={{ background: 'var(--surface)', color: '#67e8f9', padding: '1px 5px', borderRadius: 3 }}>sf org display --target-org &lt;alias&gt; --json</code> → copy <code style={{ background: 'var(--surface)', color: '#67e8f9', padding: '1px 5px', borderRadius: 3 }}>accessToken</code>
                    </div>
                  </div>
                  {tokenError && <div style={s.error}>{tokenError}</div>}
                  <form onSubmit={handleTokenLogin}>
                    <div style={s.field}>
                      <label style={s.label}>Session ID (SID)</label>
                      <input style={{ ...s.input, fontFamily: 'monospace' }} value={tokenForm.access_token} onChange={setTok('access_token')}
                        placeholder="00D… or long alphanumeric string from browser cookie" required autoComplete="off" spellCheck="false" />
                      <div style={s.hint}>Paste the <strong>sid</strong> browser cookie value, or the accessToken from the CLI.</div>
                    </div>
                    <div style={s.field}>
                      <label style={s.label}>Org URL</label>
                      <input style={{ ...s.input, fontFamily: 'monospace' }} value={tokenForm.instance_url} onChange={setTok('instance_url')}
                        placeholder="https://yourorg.my.salesforce.com" required autoComplete="off" spellCheck="false" />
                      <div style={s.hint}>Your org's My Domain URL — visible in the browser address bar when logged in.</div>
                    </div>
                    <button type="submit" style={{ ...s.saveBtn, ...(tokenLogging ? s.saveBtnDisabled : {}) }} disabled={tokenLogging}>
                      {tokenLogging ? 'Verifying…' : 'Connect with Session ID'}
                    </button>
                  </form>
                </>
              )}

              {loginMode === 'password' && (
                <>
                  {pwError && <div style={s.error}>{pwError}</div>}
                  <form onSubmit={handlePasswordLogin}>
                    <div style={s.field}>
                      <label style={s.label}>Alias Name <span style={{ color: '#4a9a9a', fontWeight: 400 }}>(optional)</span></label>
                      <input style={s.input} value={pwForm.alias} onChange={setPw('alias')}
                        placeholder="e.g. My Sandbox, Prod Org" autoComplete="off" />
                      <div style={s.hint}>A friendly label to identify this connection.</div>
                    </div>
                    <div style={s.field}>
                      <label style={s.label}>Salesforce Username</label>
                      <input style={s.input} value={pwForm.username} onChange={setPw('username')}
                        placeholder="you@example.com" required autoComplete="username" />
                    </div>
                    <div style={s.field}>
                      <label style={s.label}>Password</label>
                      <input style={s.input} type="password" value={pwForm.password} onChange={setPw('password')}
                        placeholder="Password (+ security token if IP not allowlisted)" required autoComplete="current-password" />
                      <div style={s.hint}>If your IP is not allowlisted, append your security token directly to your password (no space).</div>
                    </div>
                    <div style={s.field}>
                      <label style={s.label}>Login URL</label>
                      <input style={s.input} value={pwForm.domain} onChange={setPw('domain')}
                        placeholder="login.salesforce.com" autoComplete="off" />
                      <div style={s.hint}>Use <code>test.salesforce.com</code> for sandboxes, or your My Domain URL.</div>
                    </div>
                    <button type="submit" style={{ ...s.saveBtn, ...(pwLogging ? s.saveBtnDisabled : {}) }} disabled={pwLogging}>
                      {pwLogging ? 'Connecting…' : 'Connect Salesforce Org'}
                    </button>
                  </form>
                </>
              )}
            </>
          )}
        </div>

        <div style={s.section}>
          <div style={s.sectionTitle}>API Configuration</div>

          {configMeta && (
            <div style={{ marginBottom: 16, fontSize: 12, color: '#4a9a9a', lineHeight: 1.8 }}>
              {configMeta.sf_client_id_set ? '✓' : '✗'} SF Consumer Key &nbsp;·&nbsp;
              {configMeta.sf_client_secret_set ? '✓' : '✗'} SF Consumer Secret &nbsp;·&nbsp;
              {configMeta.anthropic_api_key_set ? '✓' : '✗'} Anthropic API Key
            </div>
          )}

          {saveMsg && <div style={s.success}>{saveMsg}</div>}
          {saveError && <div style={s.error}>{saveError}</div>}

          <form onSubmit={handleSave}>
            <div style={s.field}>
              <label style={s.label}>Consumer Key (leave blank to keep current)</label>
              <input style={s.input} value={form.sf_client_id} onChange={set('sf_client_id')}
                placeholder="3MVG9…" autoComplete="off" />
            </div>
            <div style={s.field}>
              <label style={s.label}>Consumer Secret (leave blank to keep current)</label>
              <input style={s.input} type="password" value={form.sf_client_secret}
                onChange={set('sf_client_secret')} placeholder="••••••••" autoComplete="off" />
            </div>
            <div style={s.field}>
              <label style={s.label}>Anthropic API Key (leave blank to keep current)</label>
              <input style={s.input} type="password" value={form.anthropic_api_key}
                onChange={set('anthropic_api_key')} placeholder="sk-ant-…" autoComplete="off" />
            </div>
            <div style={s.field}>
              <label style={s.label}>Login URL</label>
              <input style={s.input} value={form.sf_login_url} onChange={set('sf_login_url')} />
              <div style={s.hint}>
                If your org uses My Domain, enter its URL (e.g. <em>https://yourorg.my.salesforce.com</em>).
                Use <em>https://test.salesforce.com</em> for sandboxes.
              </div>
            </div>
            <button
              type="submit"
              style={{ ...s.saveBtn, ...(saving ? s.saveBtnDisabled : {}) }}
              disabled={saving}
            >
              {saving ? 'Saving…' : 'Save Configuration'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
