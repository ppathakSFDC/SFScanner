import React, { useState, useRef, useEffect } from 'react'
import ApiKeyModal from '../components/ApiKeyModal.jsx'

// Dark-navy palette matching OrgScan page
const NAV_BG   = 'var(--nav-bg)'
const SURFACE  = 'var(--nav-surface)'
const CARD     = 'var(--nav-card)'
const BORDER   = 'var(--nav-border)'
const TEXT     = 'var(--text)'
const TEXT_MID = 'var(--text-mid)'
const TEXT_DIM = 'var(--text-dim)'
const ACCENT   = '#06b6d4'

const s = {
  page: {
    height: '100%',
    background: NAV_BG,
    display: 'flex',
    flexDirection: 'column',
  },
  header: {
    background: SURFACE,
    borderBottom: `1px solid ${BORDER}`,
    padding: '12px 24px',
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    flexShrink: 0,
  },
  backBtn: {
    background: 'transparent',
    border: `1px solid ${BORDER}`,
    borderRadius: 8,
    color: TEXT_MID,
    padding: '5px 12px',
    cursor: 'pointer',
    fontSize: 13,
  },
  agentIcon: { fontSize: 24 },
  agentName: { fontSize: 16, fontWeight: 700, color: TEXT, flex: 1 },
  keyBtn: {
    padding: '5px 12px',
    background: 'transparent',
    border: `1px solid ${BORDER}`,
    borderRadius: 8,
    color: TEXT_MID,
    fontSize: 12,
    cursor: 'pointer',
    display: 'flex', alignItems: 'center', gap: 5,
    transition: 'border-color 0.15s',
  },
  modelSelect: {
    background: 'var(--nav-surface, #1e2535)',
    border: `1px solid ${BORDER}`,
    borderRadius: 8,
    color: TEXT_MID,
    fontSize: 12,
    padding: '5px 10px',
    cursor: 'pointer',
    outline: 'none',
    appearance: 'none',
    WebkitAppearance: 'none',
    paddingRight: 24,
    maxWidth: 180,
  },
  modelWrap: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
  },
  modelCaret: {
    position: 'absolute',
    right: 8,
    pointerEvents: 'none',
    color: TEXT_DIM,
    fontSize: 10,
  },
  badge: {
    fontSize: 11,
    color: '#86efac',
    background: 'rgba(34,197,94,0.1)',
    border: '1px solid rgba(34,197,94,0.25)',
    borderRadius: 12,
    padding: '3px 10px',
    display: 'flex',
    alignItems: 'center',
    gap: 5,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: '#22c55e',
  },
  banner: {
    background: 'rgba(99,102,241,0.08)',
    borderBottom: '1px solid rgba(99,102,241,0.2)',
    padding: '10px 24px',
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    flexShrink: 0,
  },
  bannerText: { fontSize: 13, color: '#67e8f9', flex: 1 },
  bannerBtn: {
    padding: '5px 14px',
    background: `linear-gradient(135deg, ${ACCENT}, #0891b2)`,
    border: 'none',
    borderRadius: 6,
    color: 'white',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  messages: {
    flex: 1,
    overflowY: 'auto',
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  empty: {
    textAlign: 'center',
    color: TEXT_DIM,
    fontSize: 14,
    marginTop: 40,
  },
  bubble: (role, isError) => ({
    maxWidth: '72%',
    alignSelf: role === 'user' ? 'flex-end' : 'flex-start',
    background: isError
      ? 'rgba(239,68,68,0.08)'
      : role === 'user'
        ? `linear-gradient(135deg, ${ACCENT}, #0891b2)`
        : CARD,
    border: isError
      ? '1px solid rgba(239,68,68,0.3)'
      : role === 'user' ? 'none' : `1px solid ${BORDER}`,
    borderRadius: role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
    padding: '10px 14px',
    color: isError ? '#fca5a5' : TEXT,
    fontSize: 14,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  }),
  typing: {
    alignSelf: 'flex-start',
    background: CARD,
    border: `1px solid ${BORDER}`,
    borderRadius: '14px 14px 14px 4px',
    padding: '10px 16px',
    display: 'flex',
    gap: 4,
    alignItems: 'center',
  },
  typingDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: ACCENT,
    animation: 'pulse 1.2s ease-in-out infinite',
  },
  inputRow: {
    padding: '16px 24px',
    background: SURFACE,
    borderTop: `1px solid ${BORDER}`,
    display: 'flex',
    gap: 10,
    flexShrink: 0,
  },
  textarea: {
    flex: 1,
    background: NAV_BG,
    border: `1px solid ${BORDER}`,
    borderRadius: 10,
    color: TEXT,
    fontSize: 14,
    padding: '10px 14px',
    resize: 'none',
    outline: 'none',
    fontFamily: 'inherit',
    lineHeight: 1.5,
    maxHeight: 120,
    overflowY: 'auto',
  },
  sendBtn: (disabled) => ({
    padding: '10px 20px',
    background: disabled ? SURFACE : `linear-gradient(135deg, ${ACCENT}, #0891b2)`,
    border: disabled ? `1px solid ${BORDER}` : 'none',
    borderRadius: 10,
    color: disabled ? TEXT_DIM : 'white',
    fontSize: 14,
    fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer',
    flexShrink: 0,
  }),
}

const TOOL_AGENTS = new Set(['crm_agent', 'rc_product_agent'])

const STORAGE_KEY = 'sf-selected-model'

export default function AgentChat({ agent, auth, onBack, onConnectOrg }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [showKeyModal, setShowKeyModal] = useState(false)
  const [availableModels, setAvailableModels] = useState([])
  const [selectedModel, setSelectedModel] = useState(() => localStorage.getItem(STORAGE_KEY) || '')
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    fetch('/agents/available-models')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return
        setAvailableModels(data.models || [])
        if (!selectedModel) setSelectedModel(data.active || '')
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (selectedModel) localStorage.setItem(STORAGE_KEY, selectedModel)
  }, [selectedModel])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendMessage() {
    const text = input.trim()
    if (!text || streaming) return

    const userMsg = { role: 'user', content: text }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInput('')
    setStreaming(true)

    const assistantMsg = { role: 'assistant', content: '' }
    setMessages(prev => [...prev, assistantMsg])

    try {
      const chatPath = TOOL_AGENTS.has(agent.id) ? '/chat/tool/' : '/chat/'
      const res = await fetch(chatPath + agent.id, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          messages: newMessages,
          org_context: !!auth,
          model: selectedModel || undefined,
        }),
      })

      if (res.status === 401) {
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { ...updated[updated.length - 1], content: '⚠️ Salesforce session expired. Go to Settings → reconnect your org with a fresh sid cookie.', isError: true }
          return updated
        })
        setStreaming(false)
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

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
            if (parsed.tool_call) {
              const label = `🔧 ${parsed.tool_call.name}${parsed.tool_call.input?.soql ? ': ' + parsed.tool_call.input.soql.slice(0, 80) + '…' : parsed.tool_call.input?.object_name ? ': ' + parsed.tool_call.input.object_name : ''}`
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                const calls = last.toolCalls ? [...last.toolCalls, label] : [label]
                updated[updated.length - 1] = { ...last, toolCalls: calls }
                return updated
              })
            } else if (parsed.text) {
              setMessages(prev => {
                const updated = [...prev]
                updated[updated.length - 1] = { ...updated[updated.length - 1], content: updated[updated.length - 1].content + parsed.text }
                return updated
              })
            } else if (parsed.error) {
              setMessages(prev => {
                const updated = [...prev]
                updated[updated.length - 1] = { ...updated[updated.length - 1], content: '⚠️ ' + parsed.error, isError: true }
                return updated
              })
            }
          } catch (_) {}
        }
      }
    } catch (err) {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: 'Error: ' + err.message,
        }
        return updated
      })
    } finally {
      setStreaming(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div style={s.page}>
      {showKeyModal && <ApiKeyModal onClose={() => setShowKeyModal(false)} />}
      <div style={s.header}>
        <button style={s.backBtn} onClick={onBack}>← Back</button>
        <span style={s.agentIcon}>{agent.icon}</span>
        <span style={s.agentName}>{agent.name}</span>
        {auth && (
          <div style={s.badge}>
            <div style={s.dot} />
            Org connected
          </div>
        )}
        {availableModels.length > 1 && (
          <div style={s.modelWrap}>
            <select
              style={s.modelSelect}
              value={selectedModel}
              onChange={e => setSelectedModel(e.target.value)}
              title="Switch AI model"
            >
              {availableModels.map(m => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
            <span style={s.modelCaret}>▾</span>
          </div>
        )}
        <button style={s.keyBtn} onClick={() => setShowKeyModal(true)}>
          🔑 API Key
        </button>
      </div>

      {!auth && (
        <div style={s.banner}>
          <span style={s.bannerText}>
            Connect your Salesforce org for org-specific answers and component analysis.
          </span>
          <button style={s.bannerBtn} onClick={onConnectOrg}>
            Connect Org
          </button>
        </div>
      )}

      <div style={s.messages}>
        {messages.length === 0 && (
          <div style={s.empty}>
            Ask {agent.name} anything about Salesforce…
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} style={s.bubble(msg.role, msg.isError)}>
            {msg.toolCalls && msg.toolCalls.length > 0 && (
              <div style={{ marginBottom: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {msg.toolCalls.map((tc, j) => (
                  <div key={j} style={{
                    fontSize: 11, color: '#67e8f9',
                    background: 'rgba(6,182,212,0.08)',
                    border: '1px solid rgba(6,182,212,0.2)',
                    borderRadius: 6, padding: '3px 8px',
                    fontFamily: 'monospace', whiteSpace: 'nowrap',
                    overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>{tc}</div>
                ))}
              </div>
            )}
            {msg.content || (streaming && i === messages.length - 1 ? (
              <div style={s.typing}>
                <div style={{ ...s.typingDot, animationDelay: '0ms' }} />
                <div style={{ ...s.typingDot, animationDelay: '200ms' }} />
                <div style={{ ...s.typingDot, animationDelay: '400ms' }} />
              </div>
            ) : '')}
          </div>
        ))}
        {streaming && messages[messages.length - 1]?.content === '' && (
          <div style={s.typing}>
            <div style={{ ...s.typingDot }} />
            <div style={{ ...s.typingDot, animationDelay: '200ms' }} />
            <div style={{ ...s.typingDot, animationDelay: '400ms' }} />
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div style={s.inputRow}>
        <textarea
          ref={textareaRef}
          style={s.textarea}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
          rows={1}
          disabled={streaming}
        />
        <button
          style={s.sendBtn(!input.trim() || streaming)}
          onClick={sendMessage}
          disabled={!input.trim() || streaming}
        >
          {streaming ? '…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
