import React, { useState } from 'react'
import ApiKeyModal from '../components/ApiKeyModal.jsx'

const s = {
  page: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#050c0c',
    padding: 40,
    textAlign: 'center',
  },
  icon: { fontSize: 56, marginBottom: 24 },
  title: { fontSize: 26, fontWeight: 700, color: '#f1f5f9', marginBottom: 10 },
  subtitle: { fontSize: 15, color: '#4a9a9a', maxWidth: 420, lineHeight: 1.7 },
  hint: {
    marginTop: 36,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    color: '#4a9a9a',
    fontSize: 13,
  },
  arrow: { fontSize: 18, color: '#06b6d4' },
  keyBtn: {
    marginTop: 28,
    padding: '8px 18px',
    background: 'transparent',
    border: '1px solid #0f2e2e',
    borderRadius: 8,
    color: '#4a9a9a',
    fontSize: 13,
    cursor: 'pointer',
    display: 'flex', alignItems: 'center', gap: 6,
  },
}

export default function Welcome() {
  const [showKeyModal, setShowKeyModal] = useState(false)

  return (
    <div style={s.page}>
      {showKeyModal && <ApiKeyModal onClose={() => setShowKeyModal(false)} />}
      <div style={s.icon}>
        <img src="/proworker-logo.png" alt="ProWorker" style={{ width: 64, height: 64, borderRadius: 16, objectFit: 'cover' }} />
      </div>
      <h1 style={s.title}>ProWorker</h1>
      <p style={s.subtitle}>
        AI-powered Salesforce specialist agents. Select an agent from the sidebar to start a conversation.
      </p>
      <div style={s.hint}>
        <span style={s.arrow}>←</span>
        <span>Pick an agent from the left panel</span>
      </div>
      <button style={s.keyBtn} onClick={() => setShowKeyModal(true)}>
        🔑 Update Anthropic API Key
      </button>
    </div>
  )
}
