import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

const S = {
  page: { minHeight: '100vh', background: '#050c0c', padding: 24 },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 32, maxWidth: 1100, margin: '0 auto 32px',
  },
  logo: { fontSize: 22, fontWeight: 700, color: '#a5f3fc' },
  logoutBtn: {
    background: 'transparent', border: '1px solid #0f2e2e', color: '#94a3b8',
    padding: '8px 16px', borderRadius: 8, cursor: 'pointer', fontSize: 13,
  },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, maxWidth: 1100, margin: '0 auto' },
  card: { background: '#0d1e1e', borderRadius: 14, padding: 28, border: '1px solid #0f2e2e' },
  cardTitle: { color: '#94a3b8', fontSize: 13, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 20 },
  scanBtn: {
    width: '100%', padding: '16px 24px', background: 'linear-gradient(135deg, #06b6d4, #0891b2)',
    border: 'none', borderRadius: 10, color: 'white', fontSize: 16, fontWeight: 600,
    cursor: 'pointer', transition: 'opacity 0.2s', marginTop: 8,
  },
  scanBtnDisabled: {
    width: '100%', padding: '16px 24px', background: '#0f2e2e',
    border: 'none', borderRadius: 10, color: '#4a9a9a', fontSize: 16, fontWeight: 600,
    cursor: 'not-allowed', marginTop: 8,
  },
  progressBar: { background: '#050c0c', borderRadius: 8, height: 10, overflow: 'hidden', marginTop: 12 },
  progressFill: { height: '100%', background: 'linear-gradient(90deg, #06b6d4, #0891b2)', transition: 'width 0.5s' },
  progressMsg: { color: '#94a3b8', fontSize: 13, marginTop: 8 },
  historyItem: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '14px 0', borderBottom: '1px solid #0d1e1e', cursor: 'pointer',
  },
  historyName: { color: '#f1f5f9', fontSize: 14, fontWeight: 500 },
  historyDate: { color: '#4a9a9a', fontSize: 12, marginTop: 2 },
  badge: { padding: '3px 8px', borderRadius: 6, fontSize: 12, fontWeight: 600 },
  infoGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginTop: 8 },
  infoTile: { background: '#050c0c', borderRadius: 10, padding: 16, textAlign: 'center' },
  infoNum: { fontSize: 28, fontWeight: 700, color: '#a5f3fc' },
  infoLabel: { color: '#4a9a9a', fontSize: 12, marginTop: 4 },
  fullWidth: { gridColumn: '1 / -1' },
}

function SeverityBadge({ count, severity }) {
  const colors = {
    critical: { bg: '#450a0a', color: '#fca5a5' },
    high: { bg: '#431407', color: '#fdba74' },
    medium: { bg: '#422006', color: '#fcd34d' },
    low: { bg: '#14532d', color: '#86efac' },
  }
  const c = colors[severity] || { bg: '#0d1e1e', color: '#94a3b8' }
  return (
    <span style={{ ...S.badge, background: c.bg, color: c.color }}>
      {count} {severity}
    </span>
  )
}

export default function Dashboard({ auth, onLogout }) {
  const [scanning, setScanning] = useState(false)
  const [progress, setProgress] = useState(null)
  const [history, setHistory] = useState([])
  const navigate = useNavigate()
  const esRef = useRef(null)

  useEffect(() => {
    loadHistory()
  }, [])

  async function loadHistory() {
    try {
      const r = await fetch('/scan/list', { credentials: 'include' })
      if (r.ok) setHistory(await r.json())
    } catch (e) {}
  }

  async function startScan() {
    setScanning(true)
    setProgress({ status: 'running', progress_pct: 0, message: 'Starting scan...' })
    try {
      const r = await fetch('/scan/start', { method: 'POST', credentials: 'include' })
      const { scan_id } = await r.json()
      // SSE for live progress
      esRef.current = new EventSource(`/scan/stream/${scan_id}`)
      esRef.current.onmessage = (e) => {
        const data = JSON.parse(e.data)
        setProgress(data)
        if (data.status === 'completed') {
          esRef.current.close()
          setScanning(false)
          loadHistory()
          navigate(`/report/${scan_id}`)
        }
        if (data.status === 'failed') {
          esRef.current.close()
          setScanning(false)
        }
      }
    } catch (err) {
      setScanning(false)
      setProgress({ status: 'failed', message: 'Failed to start scan' })
    }
  }

  async function handleLogout() {
    await fetch('/auth/logout', { method: 'POST', credentials: 'include' })
    onLogout()
  }

  return (
    <div style={S.page}>
      <div style={S.header}>
        <span style={{ ...S.logo, display: 'flex', alignItems: 'center', gap: 8 }}>
          <img src="/proworker-logo.png" alt="" style={{ width: 24, height: 24, borderRadius: 6, objectFit: 'cover' }} />
          ProWorker
        </span>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0' }}>
              {auth?.alias || (() => {
                try {
                  const host = new URL(auth?.instance_url || '').hostname
                  const sub = host.replace(/\.(sandbox\.my|my|lightning)\.salesforce\.com$/, '').replace(/\.salesforce\.com$/, '')
                  return sub.split(/[-_]/).map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(' ')
                } catch { return auth?.instance_url || '' }
              })()}
              <span style={{ color: '#334155', margin: '0 7px' }}>|</span>
              <span style={{ color: '#06b6d4', fontWeight: 500 }}>Org Health</span>
            </div>
            <div style={{ fontSize: 11, color: '#4a9a9a', marginTop: 2 }}>{auth?.instance_url}</div>
          </div>
          <button style={S.logoutBtn} onClick={handleLogout}>Logout</button>
        </div>
      </div>

      <div style={S.grid}>
        {/* Scan card */}
        <div style={S.card}>
          <div style={S.cardTitle}>Run New Scan</div>
          <p style={{ color: '#94a3b8', fontSize: 14, lineHeight: 1.7, marginBottom: 16 }}>
            Analyze your org's Apex, Flows, OmniScripts, DataRaptors, Integration Procedures,
            Pricing Procedures, and Business Rules against best-practice guidelines.
          </p>
          <div style={S.infoGrid}>
            {[
              ['7', 'Component Types'],
              ['45+', 'Rules Checked'],
              ['AI', 'Fix Suggestions'],
            ].map(([n, l]) => (
              <div key={l} style={S.infoTile}>
                <div style={S.infoNum}>{n}</div>
                <div style={S.infoLabel}>{l}</div>
              </div>
            ))}
          </div>
          <button
            style={scanning ? S.scanBtnDisabled : S.scanBtn}
            onClick={startScan}
            disabled={scanning}
          >
            {scanning ? 'Scanning...' : 'Start Full Scan'}
          </button>
          {progress && (
            <div>
              <div style={S.progressBar}>
                <div style={{ ...S.progressFill, width: `${progress.progress_pct}%` }} />
              </div>
              <div style={S.progressMsg}>{progress.message}</div>
              {progress.status === 'failed' && (
                <div style={{ color: '#fca5a5', fontSize: 13, marginTop: 4 }}>{progress.message}</div>
              )}
            </div>
          )}
        </div>

        {/* History card */}
        <div style={S.card}>
          <div style={S.cardTitle}>Recent Scans</div>
          {history.length === 0 && (
            <div style={{ color: '#4a9a9a', fontSize: 14, textAlign: 'center', padding: '24px 0' }}>
              No scans yet. Run your first scan to see results here.
            </div>
          )}
          {history.map(h => (
            <div key={h.scan_id} style={S.historyItem} onClick={() => navigate(`/report/${h.scan_id}`)}>
              <div>
                <div style={S.historyName}>{h.org_name}</div>
                <div style={S.historyDate}>{new Date(h.started_at).toLocaleString()}</div>
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                {h.critical_count > 0 && <SeverityBadge count={h.critical_count} severity="critical" />}
                {h.high_count > 0 && <SeverityBadge count={h.high_count} severity="high" />}
                <span style={{ ...S.badge, background: '#0d1e1e', color: '#94a3b8' }}>
                  {h.total_findings} total
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
