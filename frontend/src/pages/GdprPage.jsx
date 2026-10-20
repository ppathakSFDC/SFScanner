import React, { useState, useRef, useEffect } from 'react'

const NAV_BG   = 'var(--nav-bg)'
const SURFACE  = 'var(--nav-surface)'
const CARD     = 'var(--nav-card)'
const BORDER   = 'var(--nav-border)'
const TEXT     = 'var(--text)'
const TEXT_MID = 'var(--text-mid)'
const TEXT_DIM = 'var(--text-dim)'
const GREEN    = '#10b981'
const RED      = '#ef4444'
const AMBER    = '#f59e0b'
const BLUE     = '#3b82f6'
const ACCENT   = '#06b6d4'

const s = {
  page:    { height: '100%', background: NAV_BG, display: 'flex', flexDirection: 'column', overflow: 'hidden' },
  header:  { background: SURFACE, borderBottom: `1px solid ${BORDER}`, padding: '12px 24px', display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 },
  body:    { flex: 1, display: 'flex', overflow: 'hidden', gap: 0 },
  chatCol: { flex: 1, display: 'flex', flexDirection: 'column', borderRight: `1px solid ${BORDER}`, minWidth: 0 },
  rightCol:{ width: 440, display: 'flex', flexDirection: 'column', flexShrink: 0, overflow: 'hidden' },
  msgs:    { flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 },
  inputRow:{ borderTop: `1px solid ${BORDER}`, padding: '12px 16px', display: 'flex', gap: 8, flexShrink: 0, background: SURFACE },
  textarea:{ flex: 1, background: CARD, border: `1px solid ${BORDER}`, borderRadius: 10, color: TEXT, fontSize: 14, padding: '10px 14px', resize: 'none', outline: 'none', fontFamily: 'inherit', lineHeight: 1.5 },
  sendBtn: { background: ACCENT, border: 'none', borderRadius: 10, color: '#000', fontWeight: 700, fontSize: 13, padding: '0 18px', cursor: 'pointer', flexShrink: 0 },
  panel:   { flex: 1, overflowY: 'auto', padding: 16 },
  panelHdr:{ background: SURFACE, borderBottom: `1px solid ${BORDER}`, padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 },
  badge:   (color) => ({ background: color + '22', color, border: `1px solid ${color}44`, borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 700 }),
  actionBar:{ borderTop: `1px solid ${BORDER}`, padding: '10px 16px', display: 'flex', gap: 8, flexShrink: 0, flexWrap: 'wrap' },
  btn:     (color, disabled) => ({ background: disabled ? '#374151' : color + '22', color: disabled ? TEXT_DIM : color, border: `1px solid ${disabled ? BORDER : color + '66'}`, borderRadius: 8, padding: '7px 14px', fontSize: 12, fontWeight: 700, cursor: disabled ? 'not-allowed' : 'pointer', transition: 'all 0.15s' }),
  chip:    { background: CARD, border: `1px solid ${BORDER}`, borderRadius: 6, padding: '4px 10px', fontSize: 11, color: '#e5e7eb', cursor: 'pointer' },
  table:   { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
  th:      { background: '#1f2937', color: TEXT_DIM, padding: '6px 10px', textAlign: 'left', fontWeight: 600, borderBottom: `1px solid ${BORDER}` },
  td:      { padding: '6px 10px', borderBottom: `1px solid ${BORDER}22`, color: TEXT_MID, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
}

const TEMPLATES = [
  { label: 'Inactive Contacts 7yr+', id: 'inactive_contacts' },
  { label: 'Old Leads 3yr+',         id: 'unqualified_leads' },
  { label: 'Closed Cases 5yr+',      id: 'closed_cases' },
  { label: 'Test Accounts',          id: 'test_accounts' },
  { label: 'Bounced Email Contacts', id: 'bounced_emails' },
]

export default function GdprPage({ auth, onConnectOrg }) {
  const [messages, setMessages] = useState([{
    role: 'assistant',
    content: "Hello! I'm your GDPR Compliance Agent.\n\nTell me what you'd like to do:\n- **\"Find contacts with no activity for 7 years\"** — I'll build the query, show you the records, then anonymise or delete on your confirmation.\n- **\"Export all data for john@example.com\"** — Subject Access Request export.\n- **\"What personal data fields does the Contact object have?\"** — PII field detection.\n\nYou can also click a template below to get started quickly.",
  }])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [previewData, setPreviewData] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [actionResult, setActionResult] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [currentSoql, setCurrentSoql] = useState('')
  const [currentObject, setCurrentObject] = useState('Contact')
  const [confirmPending, setConfirmPending] = useState(null) // {type, label}
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  // Extract SOQL from AI response text
  function extractSoql(text) {
    const m = text.match(/```(?:sql|soql)?\s*(SELECT[\s\S]+?)```/i)
    if (m) return m[1].trim()
    const m2 = text.match(/`(SELECT[^`]+)`/i)
    if (m2) return m2[1].trim()
    return null
  }

  function extractObject(soql) {
    const m = soql.match(/FROM\s+(\w+)/i)
    return m ? m[1] : 'Contact'
  }

  async function loadTemplate(id) {
    setPreviewLoading(true)
    setActionResult(null)
    try {
      const res = await fetch('/gdpr/retention-suggestions', { credentials: 'include' })
      const data = await res.json()
      const tpl = data.templates.find(t => t.id === id)
      if (!tpl) return
      setCurrentSoql(tpl.soql)
      setCurrentObject(tpl.object)
      await runPreview(tpl.soql, tpl.object)
      sendMessage(`Use this retention rule: ${tpl.label}. SOQL: \`${tpl.soql}\``)
    } finally {
      setPreviewLoading(false)
    }
  }

  async function runPreview(soql, obj) {
    if (!soql) return
    setPreviewLoading(true)
    setActionResult(null)
    try {
      const res = await fetch('/gdpr/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ soql, object_name: obj || currentObject }),
      })
      const data = await res.json()
      if (!res.ok) {
        setPreviewData({ error: data.detail || 'Preview failed' })
      } else {
        setPreviewData(data)
      }
    } catch (e) {
      setPreviewData({ error: e.message })
    } finally {
      setPreviewLoading(false)
    }
  }

  async function executeAction(type, confirmed = false) {
    if (!previewData || !previewData.records?.length) return
    if (!confirmed) {
      setConfirmPending({ type, label: type === 'anonymize' ? 'Anonymise' : 'Delete' })
      return
    }
    setConfirmPending(null)
    setActionLoading(true)
    setActionResult(null)
    const ids = previewData.records.map(r => r.Id).filter(Boolean)
    try {
      const res = await fetch(`/gdpr/${type}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ record_ids: ids, object_name: currentObject, confirm: true }),
      })
      const data = await res.json()
      setActionResult({ type, ...data })
      // Add summary to chat
      const summary = type === 'anonymize'
        ? `✅ Anonymised **${data.updated || 0}** ${currentObject} records. Fields cleared: ${(data.fields_anonymized || []).join(', ')}`
        : `✅ Deleted **${data.deleted || 0}** ${currentObject} records.`
      setMessages(prev => [...prev, { role: 'assistant', content: summary }])
    } catch (e) {
      setActionResult({ error: e.message })
    } finally {
      setActionLoading(false)
    }
  }

  async function exportSAR() {
    const email = window.prompt('Enter the data subject\'s email address:')
    if (!email) return
    const url = `/gdpr/export`
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, object_name: currentObject }),
    })
    if (!res.ok) { alert('Export failed'); return }
    const blob = await res.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `SAR_${email.replace('@','_')}.json`
    a.click()
  }

  async function sendMessage(overrideText) {
    const text = (overrideText || input).trim()
    if (!text || streaming) return
    const userMsg = { role: 'user', content: text }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    if (!overrideText) setInput('')
    setStreaming(true)

    const assistantMsg = { role: 'assistant', content: '' }
    setMessages(prev => [...prev, assistantMsg])

    try {
      const res = await fetch('/chat/gdpr_agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ messages: newMessages, org_context: !!auth }),
      })
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullText = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (raw === '[DONE]') break
          try {
            const parsed = JSON.parse(raw)
            if (parsed.text) {
              fullText += parsed.text
              setMessages(prev => {
                const updated = [...prev]
                updated[updated.length - 1] = { role: 'assistant', content: fullText }
                return updated
              })
            }
          } catch { /* ignore */ }
        }
      }

      // Auto-extract SOQL from AI response
      const soql = extractSoql(fullText)
      if (soql) {
        const obj = extractObject(soql)
        setCurrentSoql(soql)
        setCurrentObject(obj)
        await runPreview(soql, obj)
      }
    } catch (e) {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: 'assistant', content: `Error: ${e.message}` }
        return updated
      })
    } finally {
      setStreaming(false)
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  const recordIds = previewData?.records?.map(r => r.Id).filter(Boolean) || []
  const hasRecords = recordIds.length > 0
  const columns = previewData?.records?.[0] ? Object.keys(previewData.records[0]).filter(k => k !== 'attributes') : []

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <span style={{ fontSize: 22 }}>🔒</span>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: TEXT }}>GDPR Compliance Agent</div>
          <div style={{ fontSize: 11, color: TEXT_DIM }}>Data retention · Right to erasure · Subject Access Requests</div>
        </div>
        {!auth && (
          <button onClick={onConnectOrg} style={{ marginLeft: 'auto', background: ACCENT + '22', border: `1px solid ${ACCENT}44`, color: ACCENT, borderRadius: 8, padding: '6px 14px', fontSize: 12, cursor: 'pointer', fontWeight: 600 }}>
            Connect Org
          </button>
        )}
        {auth && <span style={{ ...s.badge(GREEN), marginLeft: 'auto' }}>Org Connected</span>}
      </div>

      <div style={s.body}>
        {/* Chat column */}
        <div style={s.chatCol}>
          <div style={s.msgs}>
            {messages.map((m, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
                <div style={{
                  maxWidth: '85%',
                  background: m.role === 'user' ? ACCENT + '22' : CARD,
                  border: `1px solid ${m.role === 'user' ? ACCENT + '44' : BORDER}`,
                  borderRadius: 12,
                  padding: '10px 14px',
                  fontSize: 13,
                  color: TEXT,
                  lineHeight: 1.6,
                  whiteSpace: 'pre-wrap',
                }}>
                  {m.content.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, j) => {
                    if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={j}>{part.slice(2,-2)}</strong>
                    if (/^`[^`]+`$/.test(part)) return <code key={j} style={{ background: '#1f2937', padding: '1px 6px', borderRadius: 4, fontSize: 12, color: '#a5f3fc' }}>{part.slice(1,-1)}</code>
                    return part
                  })}
                </div>
              </div>
            ))}
            {streaming && (
              <div style={{ color: TEXT_DIM, fontSize: 12, display: 'flex', gap: 4, alignItems: 'center' }}>
                <span>Analysing</span>
                {[0,1,2].map(i => <span key={i} style={{ animation: `pulse 1s ${i*0.2}s infinite`, opacity: 0.6 }}>●</span>)}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick template chips */}
          <div style={{ padding: '8px 16px', borderTop: `1px solid ${BORDER}`, display: 'flex', gap: 6, flexWrap: 'wrap', flexShrink: 0 }}>
            {TEMPLATES.map(t => (
              <button key={t.id} onClick={() => loadTemplate(t.id)} style={s.chip} title={t.label}>{t.label}</button>
            ))}
          </div>

          {/* Input */}
          <div style={s.inputRow}>
            <textarea
              ref={textareaRef}
              style={s.textarea}
              rows={2}
              placeholder="Describe your retention rule… e.g. 'Find contacts with no activity for 7 years and anonymise them'"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
            />
            <button onClick={() => sendMessage()} disabled={streaming || !input.trim()} style={s.sendBtn}>Send</button>
          </div>
        </div>

        {/* Right panel — record preview + actions */}
        <div style={s.rightCol}>
          <div style={s.panelHdr}>
            <span style={{ fontSize: 14, fontWeight: 700, color: TEXT }}>Record Preview</span>
            {previewData && !previewData.error && (
              <span style={s.badge(previewData.total_size > 0 ? AMBER : GREEN)}>
                {previewData.total_size?.toLocaleString()} affected
              </span>
            )}
            {currentSoql && (
              <button
                onClick={() => runPreview(currentSoql, currentObject)}
                style={{ marginLeft: 'auto', background: 'transparent', border: `1px solid ${BORDER}`, color: TEXT_DIM, borderRadius: 6, padding: '3px 10px', fontSize: 11, cursor: 'pointer' }}
              >
                Refresh
              </button>
            )}
          </div>

          <div style={s.panel}>
            {!auth && (
              <div style={{ color: TEXT_DIM, fontSize: 13, textAlign: 'center', marginTop: 40 }}>
                Connect your Salesforce org to preview and act on records.
              </div>
            )}

            {auth && !previewData && !previewLoading && (
              <div style={{ color: TEXT_DIM, fontSize: 13, textAlign: 'center', marginTop: 40, lineHeight: 2 }}>
                Ask the agent a question or click a template.<br />
                Record preview will appear here.
              </div>
            )}

            {previewLoading && (
              <div style={{ color: TEXT_DIM, fontSize: 13, textAlign: 'center', marginTop: 40 }}>Fetching records…</div>
            )}

            {previewData?.error && (
              <div style={{ background: RED + '18', border: `1px solid ${RED}44`, borderRadius: 8, padding: 12, color: RED, fontSize: 13, marginTop: 8 }}>
                {previewData.error}
              </div>
            )}

            {previewData && !previewData.error && previewData.records && (
              <>
                {/* SOQL */}
                <div style={{ background: '#111827', border: `1px solid ${BORDER}`, borderRadius: 8, padding: '8px 12px', marginBottom: 12, fontFamily: 'monospace', fontSize: 11, color: '#a5f3fc', lineHeight: 1.5, wordBreak: 'break-all' }}>
                  {previewData.soql}
                </div>

                {previewData.records.length === 0 ? (
                  <div style={{ color: GREEN, fontSize: 13, textAlign: 'center', marginTop: 20 }}>✅ No records match this rule — nothing to action.</div>
                ) : (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={s.table}>
                      <thead>
                        <tr>{columns.slice(0, 5).map(c => <th key={c} style={s.th}>{c}</th>)}</tr>
                      </thead>
                      <tbody>
                        {previewData.records.slice(0, 50).map((r, i) => (
                          <tr key={i} style={{ background: i % 2 ? 'transparent' : '#ffffff08' }}>
                            {columns.slice(0, 5).map(c => (
                              <td key={c} style={s.td} title={String(r[c] ?? '')}>
                                {r[c] == null ? <span style={{ color: TEXT_DIM }}>—</span> : String(r[c]).slice(0, 30)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {previewData.total_size > 50 && (
                      <div style={{ color: TEXT_DIM, fontSize: 11, textAlign: 'center', marginTop: 8 }}>
                        Showing 50 of {previewData.total_size.toLocaleString()} records
                      </div>
                    )}
                  </div>
                )}
              </>
            )}

            {/* Action result */}
            {actionResult && (
              <div style={{
                marginTop: 12,
                background: actionResult.error ? RED + '18' : GREEN + '18',
                border: `1px solid ${actionResult.error ? RED : GREEN}44`,
                borderRadius: 8, padding: 12, fontSize: 13,
                color: actionResult.error ? RED : GREEN,
              }}>
                {actionResult.error
                  ? `Error: ${actionResult.error}`
                  : actionResult.type === 'anonymize'
                    ? `✅ Anonymised ${actionResult.updated} records`
                    : `✅ Deleted ${actionResult.deleted} records`}
                {actionResult.errors?.length > 0 && (
                  <div style={{ color: AMBER, marginTop: 6, fontSize: 11 }}>
                    {actionResult.errors.length} error(s) — some records may not have been updated.
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Action buttons */}
          <div style={s.actionBar}>
            {confirmPending ? (
              <>
                <div style={{ width: '100%', color: AMBER, fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                  ⚠️ Confirm {confirmPending.label} of {recordIds.length} records?
                </div>
                <button onClick={() => executeAction(confirmPending.type, true)} style={s.btn(RED, false)}>
                  Yes, {confirmPending.label}
                </button>
                <button onClick={() => setConfirmPending(null)} style={s.btn(TEXT_DIM, false)}>Cancel</button>
              </>
            ) : (
              <>
                <button
                  disabled={!hasRecords || actionLoading}
                  onClick={() => executeAction('anonymize')}
                  style={s.btn(AMBER, !hasRecords || actionLoading)}
                  title="Replace PII fields with anonymised values"
                >
                  {actionLoading ? 'Working…' : '🔒 Anonymise'}
                </button>
                <button
                  disabled={!hasRecords || actionLoading}
                  onClick={() => executeAction('delete')}
                  style={s.btn(RED, !hasRecords || actionLoading)}
                  title="Permanently delete these records"
                >
                  🗑 Delete
                </button>
                <button
                  disabled={!auth || actionLoading}
                  onClick={exportSAR}
                  style={s.btn(BLUE, !auth || actionLoading)}
                  title="Export all data for a specific individual (Subject Access Request)"
                >
                  📤 SAR Export
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
