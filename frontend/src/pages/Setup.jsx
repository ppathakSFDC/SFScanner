import React, { useState } from 'react'

const s = {
  page: {
    minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: 'linear-gradient(135deg, #050c0c 0%, #001c26 100%)', padding: 24,
  },
  card: {
    background: '#0d1e1e', borderRadius: 16, padding: '40px 36px',
    boxShadow: '0 25px 50px rgba(0,0,0,0.5)', maxWidth: 520, width: '100%',
  },
  logo: {
    width: 52, height: 52, borderRadius: 12,
    background: 'linear-gradient(135deg, #06b6d4, #0891b2)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 24, marginBottom: 20,
  },
  title: { fontSize: 24, fontWeight: 700, color: '#f1f5f9', marginBottom: 6 },
  subtitle: { color: '#94a3b8', fontSize: 14, marginBottom: 32, lineHeight: 1.6 },
  section: { marginBottom: 24 },
  sectionTitle: {
    fontSize: 11, fontWeight: 700, color: '#06b6d4', textTransform: 'uppercase',
    letterSpacing: '0.08em', marginBottom: 12,
  },
  field: { marginBottom: 14 },
  label: { display: 'block', fontSize: 13, color: '#cbd5e1', marginBottom: 6, fontWeight: 500 },
  input: {
    width: '100%', padding: '10px 12px', background: '#050c0c',
    border: '1px solid #0f2e2e', borderRadius: 8, color: '#f1f5f9',
    fontSize: 14, boxSizing: 'border-box', outline: 'none',
    transition: 'border-color 0.2s',
  },
  hint: { fontSize: 11, color: '#4a9a9a', marginTop: 4 },
  btn: {
    width: '100%', padding: '13px 24px',
    background: 'linear-gradient(135deg, #06b6d4, #0891b2)',
    border: 'none', borderRadius: 10, color: 'white', fontSize: 15, fontWeight: 600,
    cursor: 'pointer', marginTop: 8,
  },
  btnDisabled: { opacity: 0.5, cursor: 'not-allowed' },
  error: {
    background: '#450a0a', border: '1px solid #7f1d1d', borderRadius: 8,
    padding: '10px 14px', color: '#fca5a5', fontSize: 13, marginBottom: 16,
  },
  success: {
    background: '#052e16', border: '1px solid #14532d', borderRadius: 8,
    padding: '10px 14px', color: '#86efac', fontSize: 13, marginBottom: 16,
  },
}

export default function Setup({ onConfigured }) {
  const [form, setForm] = useState({
    sf_client_id: '',
    sf_client_secret: '',
    anthropic_api_key: '',
    sf_login_url: 'https://login.salesforce.com',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const valid = form.sf_client_id.trim() && form.sf_client_secret.trim() && form.anthropic_api_key.trim()

  async function handleSave(e) {
    e.preventDefault()
    if (!valid) return
    setSaving(true)
    setError('')
    try {
      const res = await fetch('/setup/configure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) throw new Error(await res.text())
      setSuccess(true)
      setTimeout(() => onConfigured(), 1200)
    } catch (err) {
      setError(err.message || 'Failed to save configuration')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={s.page}>
      <div style={s.card}>
        <div style={s.logo}>
          <img src="/proworker-logo.png" alt="ProWorker" style={{ width: 64, height: 64, borderRadius: 18, objectFit: 'cover' }} />
        </div>
        <h1 style={s.title}>ProWorker Setup</h1>
        <p style={s.subtitle}>
          Enter your Salesforce Connected App credentials and Anthropic API key
          to get started. These are saved to the local <code>.env</code> file.
        </p>

        {error && <div style={s.error}>{error}</div>}
        {success && <div style={s.success}>Configuration saved! Redirecting…</div>}

        <form onSubmit={handleSave}>
          <div style={s.section}>
            <div style={s.sectionTitle}>Salesforce Connected App</div>
            <div style={s.field}>
              <label style={s.label}>Consumer Key (Client ID)</label>
              <input style={s.input} value={form.sf_client_id} onChange={set('sf_client_id')}
                placeholder="3MVG9..." autoComplete="off" />
              <div style={s.hint}>Setup → App Manager → your Connected App → Consumer Key</div>
            </div>
            <div style={s.field}>
              <label style={s.label}>Consumer Secret (Client Secret)</label>
              <input style={s.input} type="password" value={form.sf_client_secret} onChange={set('sf_client_secret')}
                placeholder="••••••••" autoComplete="off" />
            </div>
            <div style={s.field}>
              <label style={s.label}>Login URL</label>
              <input style={s.input} value={form.sf_login_url} onChange={set('sf_login_url')} />
              <div style={s.hint}>Use https://test.salesforce.com for sandboxes</div>
            </div>
          </div>

          <div style={s.section}>
            <div style={s.sectionTitle}>Anthropic</div>
            <div style={s.field}>
              <label style={s.label}>API Key</label>
              <input style={s.input} type="password" value={form.anthropic_api_key} onChange={set('anthropic_api_key')}
                placeholder="sk-ant-..." autoComplete="off" />
              <div style={s.hint}>console.anthropic.com → API Keys</div>
            </div>
          </div>

          <button
            type="submit"
            style={{ ...s.btn, ...((!valid || saving) ? s.btnDisabled : {}) }}
            disabled={!valid || saving}
          >
            {saving ? 'Saving…' : 'Save & Continue'}
          </button>
        </form>
      </div>
    </div>
  )
}
