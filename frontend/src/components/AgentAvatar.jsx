import React from 'react'
import robotIcon from '../assets/robot-agent.png'

export const AGENT_COLORS = {
  apex_expert:          '#06b6d4',
  flow_expert:          '#06b6d4',
  omniscript_expert:    '#06b6d4',
  dataraptor_expert:    '#06b6d4',
  integration_expert:   '#06b6d4',
  pricing_expert:       '#06b6d4',
  general_expert:       '#06b6d4',
}

export const AGENT_SHORT_NAMES = {
  apex_expert:          'Apex',
  flow_expert:          'Flow',
  omniscript_expert:    'OmniScript',
  dataraptor_expert:    'DataRaptor',
  integration_expert:   'Integ. Proc',
  pricing_expert:       'Pricing',
  general_expert:       'Architect',
}

export default function AgentAvatar({ agentId, size = 44, active = false }) {
  const color = AGENT_COLORS[agentId] || '#06b6d4'
  const label = AGENT_SHORT_NAMES[agentId] || agentId

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 4,
      padding: '6px 4px 4px',
      borderRadius: 12,
      border: active ? ('1.5px solid ' + color) : '1.5px solid transparent',
      background: active ? 'rgba(6,182,212,0.12)' : 'transparent',
      transition: 'all 0.15s',
      width: 68,
      cursor: 'pointer',
    }}>
      <img
        src={robotIcon}
        alt={label}
        width={size}
        height={size}
        style={{
          display: 'block',
          imageRendering: 'crisp-edges',
          filter: active ? 'drop-shadow(0 0 6px rgba(6,182,212,0.7))' : 'none',
          transition: 'filter 0.15s',
          userSelect: 'none',
          pointerEvents: 'none',
        }}
        draggable={false}
      />
      <span style={{
        fontSize: 9.5,
        fontWeight: 600,
        color: active ? color : '#4a9a9a',
        letterSpacing: '0.02em',
        textAlign: 'center',
        lineHeight: 1.2,
        userSelect: 'none',
        transition: 'color 0.15s',
        whiteSpace: 'nowrap',
      }}>
        {label}
      </span>
    </div>
  )
}
