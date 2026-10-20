import React, { useState, useEffect } from 'react'

const s = {
  page: {
    minHeight: 'calc(100vh - 56px)',
    background: '#050c0c',
    padding: '32px 24px',
  },
  header: {
    maxWidth: 900,
    margin: '0 auto 32px',
  },
  title: { fontSize: 26, fontWeight: 700, color: '#f1f5f9', marginBottom: 6 },
  subtitle: { color: '#94a3b8', fontSize: 15 },
  grid: {
    maxWidth: 900,
    margin: '0 auto',
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
    gap: 16,
  },
  card: {
    background: '#0d1e1e',
    border: '1px solid #0f2e2e',
    borderRadius: 14,
    padding: 24,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    transition: 'border-color 0.2s',
    cursor: 'default',
  },
  cardHover: { borderColor: '#06b6d4' },
  icon: { fontSize: 36, lineHeight: 1 },
  name: { fontSize: 17, fontWeight: 700, color: '#f1f5f9' },
  desc: { fontSize: 13, color: '#94a3b8', lineHeight: 1.55, flex: 1 },
  tags: { display: 'flex', flexWrap: 'wrap', gap: 6 },
  tag: {
    fontSize: 11,
    fontWeight: 600,
    color: '#67e8f9',
    background: 'rgba(99,102,241,0.12)',
    border: '1px solid rgba(99,102,241,0.25)',
    borderRadius: 4,
    padding: '2px 8px',
  },
  btn: {
    marginTop: 4,
    padding: '9px 16px',
    background: 'linear-gradient(135deg, #06b6d4, #0891b2)',
    border: 'none',
    borderRadius: 8,
    color: 'white',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    width: '100%',
  },
  loading: {
    color: '#94a3b8',
    textAlign: 'center',
    padding: 60,
    fontSize: 15,
  },
}

function AgentCard({ agent, onSelect }) {
  const [hovered, setHovered] = useState(false)
  return (
    <div
      style={{ ...s.card, ...(hovered ? s.cardHover : {}) }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div style={s.icon}>{agent.icon}</div>
      <div style={s.name}>{agent.name}</div>
      <div style={s.desc}>{agent.description}</div>
      <div style={s.tags}>
        {agent.tags.slice(0, 4).map(tag => (
          <span key={tag} style={s.tag}>{tag}</span>
        ))}
      </div>
      <button style={s.btn} onClick={() => onSelect(agent)}>
        Chat
      </button>
    </div>
  )
}

export default function AgentsPage({ onSelectAgent }) {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/agents')
      .then(r => r.json())
      .then(data => { setAgents(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div style={s.page}>
      <div style={s.header}>
        <h1 style={s.title}>AI Agents</h1>
        <p style={s.subtitle}>
          Choose a specialist agent to chat with. Connect your Salesforce org for org-specific answers.
        </p>
      </div>
      {loading ? (
        <div style={s.loading}>Loading agents…</div>
      ) : (
        <div style={s.grid}>
          {agents.map(agent => (
            <AgentCard key={agent.id} agent={agent} onSelect={onSelectAgent} />
          ))}
        </div>
      )}
    </div>
  )
}
