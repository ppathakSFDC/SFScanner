import React, { useState, useEffect, useRef } from 'react'

const s = {
  overlay: {
    position: 'fixed', inset: 0,
    background: 'rgba(0,0,0,0.6)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 200,
  },
  modal: {
    background: '#0d1e1e',
    border: '1px solid #0f2e2e',
    borderRadius: 14,
    padding: '28px 28px 24px',
    width: 380,
    boxShadow: '0 24px 48px rgba(0,0,0,0.6)',
  },
  title: { fontSize: 16, fontWeight: 700, color: '#f1f5f9', marginBottom: 6 },
  subtitle: { fontSize: 13, color: '#4a9a9a', marginBottom: 20, lineHeight: 1.5 },
  label: { fontSize: 12, fontWeight: 600, color: '#94a3b8', marginBottom: 6, display: 'block' },
  inputWrap: { position: 'relative', marginBottom: 6 },
  input: {
    width: '100%', padding: '10px 40px 10px 12px',
    background: '#050c0c', border: '1px solid #0f2e2e',
    borderRadius: 8, color: '#f1f5f9', fontSize: 14,
    outline: 'none', boxSizing: 'border-box', fontFamily: 'monospace',
  },
  eyeBtn: {
    position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
    background: 'none', border: 'none', cursor: 'pointer',
    color: '#4a9a9a', fontSize: 14, padding: 0,
  },
  hint: { fontSize: 11, color: '#4a9a9a', marginBottom: 20 },
  row: { display: 'flex', gap: 8, justifyContent: 'flex-end' },
  cancelBtn: {
    padding: '8px 16px', background: 'transparent',
    border: '1px solid #0f2e2e', borderRadius: 8,
    color: '#94a3b8', fontSize: 13, cursor: 'pointer',
  },
  saveBtn: (disabled) => ({
    padding: '8px 20px',
    background: disabled ? '#0d1e1e' : 'linear-gradient(135deg, #06b6d4, #0891b2)',
    border: disabled ? '1px solid #0f2e2e' : 'none',
    borderRadius: 8, color: disabled ? '#4a9a9a' : 'white',
    fontSize: 13, fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer',
  }),
  success: {
    fontSize: 12, color: '#86efac', marginBottom: 12,
    background: 'rgba(34,197,94,0.08)', borderRadius: 6,
    padding: '6px 10px', border: '1px solid rgba(34,197,94,0.2)',
  },
  error: {
    fontSize: 12, color: '#fca5a5', marginBottom: 12,
    background: 'rgba(239,68,68,0.08)', borderRadius: 6,
    padding: '6px 10px', border: '1px solid rgba(239,68,68,0.2)',
  },
}

export default function ApiKeyModal({ onClose }) {
  const [key, setKey] = useState('')
  const [show, setShow] = useState(false)
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState(null) // 'saved' | 'error:<msg>'
  const inputRef = useRef()

  useEffect(() => { inputRef.current?.focus() }, [])

  async function handleSave() {
    if (!key.trim()) return
    setSaving(true)
    setStatus(null)
    try {
      const res = await fetch('/setup/anthropic-key', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ anthropic_api_key: key.trim() }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed')
      setStatus('saved')
      setTimeout(onClose, 900)
    } catch (e) {
      setStatus('error:' + e.message)
    } finally {
      setSaving(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') handleSave()
    if (e.key === 'Escape') onClose()
  }

  return (
    <div style={s.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={s.modal}>
        <div style={s.title}>🔑 Update Anthropic API Key</div>
        <div style={s.subtitle}>
          Enter your API key from{' '}
          <span style={{ color: '#67e8f9' }}>console.anthropic.com</span> → API Keys
        </div>

        {status === 'saved' && <div style={s.success}>✓ API key saved successfully</div>}
        {status?.startsWith('error:') && <div style={s.error}>{status.slice(6)}</div>}

        <label style={s.label}>API Key</label>
        <div style={s.inputWrap}>
          <input
            ref={inputRef}
            style={s.input}
            type={show ? 'text' : 'password'}
            value={key}
            onChange={e => setKey(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="sk-ant-..."
            autoComplete="off"
          />
          <button style={s.eyeBtn} onClick={() => setShow(v => !v)}>
            {show ? '🙈' : '👁️'}
          </button>
        </div>
        <div style={s.hint}>The key is saved to backend/.env and takes effect immediately.</div>

        <div style={s.row}>
          <button style={s.cancelBtn} onClick={onClose}>Cancel</button>
          <button
            style={s.saveBtn(!key.trim() || saving)}
            onClick={handleSave}
            disabled={!key.trim() || saving}
          >
            {saving ? 'Saving…' : 'Save Key'}
          </button>
        </div>
      </div>
    </div>
  )
}
