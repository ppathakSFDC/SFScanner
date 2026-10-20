import React, { useState } from 'react'

const styles = {
  page: {
    minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: 'linear-gradient(135deg, #050c0c 0%, #001c26 100%)',
    padding: '24px 16px',
  },
  card: {
    background: '#0d1e1e', borderRadius: 16, padding: '44px 40px',
    boxShadow: '0 25px 50px rgba(0,0,0,0.5)', maxWidth: 460, width: '100%', textAlign: 'center',
  },
  logo: {
    width: 64, height: 64, borderRadius: 16, background: 'linear-gradient(135deg, #06b6d4, #0891b2)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    margin: '0 auto 24px', fontSize: 28,
  },
  title: { fontSize: 28, fontWeight: 700, color: '#f1f5f9', marginBottom: 8 },
  subtitle: { color: '#94a3b8', fontSize: 15, marginBottom: 32, lineHeight: 1.6 },
  features: {
    display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 28, textAlign: 'left',
  },
  feature: {
    background: '#050c0c', borderRadius: 10, padding: '11px 13px',
    border: '1px solid #0f2e2e',
  },
  featureTitle: { color: '#a5f3fc', fontSize: 12, fontWeight: 600, marginBottom: 2 },
  featureDesc: { color: '#4a9a9a', fontSize: 11 },
  btn: {
    width: '100%', padding: '13px 24px', background: 'linear-gradient(135deg, #06b6d4, #0891b2)',
    border: 'none', borderRadius: 10, color: 'white', fontSize: 15, fontWeight: 600,
    cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
    transition: 'opacity 0.2s',
  },
  note: { color: '#4a9a9a', fontSize: 12, marginTop: 12 },
  divider: {
    display: 'flex', alignItems: 'center', gap: 12, margin: '20px 0',
    color: '#0f2e2e', fontSize: 12,
  },
  dividerLine: { flex: 1, height: 1, background: '#0f2e2e' },
  sidToggle: {
    width: '100%', padding: '11px 24px', background: 'transparent',
    border: '1px solid #0f2e2e', borderRadius: 10, color: '#94a3b8', fontSize: 14,
    fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center',
    justifyContent: 'center', gap: 8, transition: 'all 0.15s',
  },
  sidForm: {
    marginTop: 16, textAlign: 'left',
    background: '#050c0c', borderRadius: 10, padding: '18px 20px',
    border: '1px solid #0f2e2e',
  },
  label: { display: 'block', fontSize: 12, color: '#cbd5e1', marginBottom: 5, fontWeight: 600 },
  input: {
    width: '100%', padding: '10px 12px', background: '#0d1e1e',
    border: '1px solid #0f2e2e', borderRadius: 8, color: '#f1f5f9',
    fontSize: 13, boxSizing: 'border-box', outline: 'none', marginBottom: 12,
    fontFamily: 'monospace',
  },
  hint: { fontSize: 11, color: '#4a9a9a', marginTop: -8, marginBottom: 12, lineHeight: 1.5 },
  howto: {
    background: '#0d1e1e', borderRadius: 8, padding: '10px 14px',
    border: '1px solid #0f2e2e', marginBottom: 14,
  },
  howtoTitle: { color: '#94a3b8', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 },
  howtoStep: { color: '#4a9a9a', fontSize: 12, lineHeight: 2 },
  code: { background: '#050c0c', color: '#67e8f9', padding: '1px 6px', borderRadius: 4, fontFamily: 'monospace', fontSize: 11 },
  connectBtn: {
    width: '100%', padding: '11px 24px',
    background: 'linear-gradient(135deg, #059669, #10b981)',
    border: 'none', borderRadius: 8, color: 'white', fontSize: 14,
    fontWeight: 600, cursor: 'pointer', marginTop: 4,
  },
  error: {
    background: '#450a0a', border: '1px solid #7f1d1d', borderRadius: 8,
    padding: '10px 14px', color: '#fca5a5', fontSize: 13, marginBottom: 12, textAlign: 'left',
  },
}

const FEATURES = [
  { title: 'OmniScript', desc: '7 best-practice rules' },
  { title: 'Apex + SOQL', desc: '19 governor limit rules' },
  { title: 'Flows', desc: '7 bulkification rules' },
  { title: 'DataRaptor', desc: '6 performance rules' },
  { title: 'Integration Proc.', desc: '6 resilience rules' },
  { title: 'FlexCard', desc: '4 performance rules' },
]

export default function Login({ onAuthChange }) {
  const [showSid, setShowSid] = useState(false)
  const [showHowTo, setShowHowTo] = useState(false)
  const [sid, setSid] = useState('')
  const [orgUrl, setOrgUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSidConnect(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/auth/login-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ access_token: sid.trim(), instance_url: orgUrl.trim() }),
      })
      let data
      try { data = await res.json() } catch { throw new Error(`Server error (${res.status})`) }
      if (!res.ok) throw new Error(data.detail || 'Connection failed')
      if (onAuthChange) onAuthChange(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.logo}>
          <img src="/proworker-logo.png" alt="ProWorker" style={{ width: 64, height: 64, borderRadius: 18, objectFit: 'cover' }} />
        </div>
        <h1 style={styles.title}>ProWorker</h1>
        <p style={styles.subtitle}>
          AI-powered Salesforce org analyzer. Detect performance, security, and
          best-practice issues across all your components.
        </p>
        <div style={styles.features}>
          {FEATURES.map(f => (
            <div key={f.title} style={styles.feature}>
              <div style={styles.featureTitle}>{f.title}</div>
              <div style={styles.featureDesc}>{f.desc}</div>
            </div>
          ))}
        </div>

        {/* OAuth button */}
        <button style={styles.btn} onClick={() => window.location.href = '/auth/login'}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
            <polyline points="10,17 15,12 10,7"/>
            <line x1="15" y1="12" x2="3" y2="12"/>
          </svg>
          Connect via OAuth
        </button>
        <p style={styles.note}>OAuth requires Consumer Key + Secret in Settings</p>

        {/* Divider */}
        <div style={styles.divider}>
          <div style={styles.dividerLine} />
          <span>or connect instantly</span>
          <div style={styles.dividerLine} />
        </div>

        {/* SID login toggle */}
        <button
          style={{
            ...styles.sidToggle,
            borderColor: showSid ? '#059669' : '#0f2e2e',
            color: showSid ? '#86efac' : '#94a3b8',
          }}
          onClick={() => setShowSid(v => !v)}
        >
          <span style={{ fontSize: 16 }}>🔑</span>
          Connect with Session ID (SID)
          <span style={{ marginLeft: 'auto', fontSize: 12 }}>{showSid ? '▲' : '▼'}</span>
        </button>

        {showSid && (
          <div style={styles.sidForm}>

            {/* How-to collapsed helper */}
            <button
              onClick={() => setShowHowTo(v => !v)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, marginBottom: 12, color: '#06b6d4', fontSize: 12, fontWeight: 600 }}
            >
              {showHowTo ? '▲' : '▼'} How to get your SID
            </button>

            {showHowTo && (
              <div style={styles.howto}>
                <div style={styles.howtoTitle}>3 ways to get your Session ID</div>
                <div style={styles.howtoStep}>
                  <strong style={{ color: '#94a3b8' }}>Option 1 — Browser cookie (fastest)</strong><br />
                  1. Log in to Salesforce in your browser<br />
                  2. Open DevTools → <span style={styles.code}>F12</span> → Application tab → Cookies<br />
                  3. Find the cookie named <span style={styles.code}>sid</span> — copy its value<br />
                  <br />
                  <strong style={{ color: '#94a3b8' }}>Option 2 — Developer Console</strong><br />
                  1. Open your org → Setup menu → Developer Console<br />
                  2. Run: <span style={styles.code}>System.debug(UserInfo.getSessionId());</span><br />
                  3. Copy the session ID from the debug log<br />
                  <br />
                  <strong style={{ color: '#94a3b8' }}>Option 3 — Salesforce CLI</strong><br />
                  Run: <span style={styles.code}>sf org display --target-org &lt;alias&gt; --json</span><br />
                  Copy the <span style={styles.code}>accessToken</span> value
                </div>
              </div>
            )}

            {error && <div style={styles.error}>{error}</div>}

            <form onSubmit={handleSidConnect}>
              <label style={styles.label}>Session ID (SID)</label>
              <input
                style={styles.input}
                value={sid}
                onChange={e => setSid(e.target.value)}
                placeholder="00D… or long alphanumeric string"
                required
                autoComplete="off"
                spellCheck="false"
              />
              <div style={styles.hint}>
                Paste the value of the <code style={styles.code}>sid</code> cookie from your browser,
                or the <code style={styles.code}>accessToken</code> from the CLI.
              </div>

              <label style={styles.label}>Org URL</label>
              <input
                style={styles.input}
                value={orgUrl}
                onChange={e => setOrgUrl(e.target.value)}
                placeholder="https://yourorg.my.salesforce.com"
                required
                autoComplete="off"
                spellCheck="false"
              />
              <div style={styles.hint}>
                Your org's My Domain URL (no trailing slash). Find it in the browser address bar when logged in.
              </div>

              <button
                type="submit"
                disabled={loading || !sid.trim() || !orgUrl.trim()}
                style={{ ...styles.connectBtn, opacity: (loading || !sid.trim() || !orgUrl.trim()) ? 0.6 : 1, cursor: (loading || !sid.trim() || !orgUrl.trim()) ? 'not-allowed' : 'pointer' }}
              >
                {loading ? 'Verifying…' : 'Connect with Session ID'}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  )
}
