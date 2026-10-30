import React, { useState, useEffect, useCallback } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import TopBar from './components/TopBar.jsx'
import Sidebar from './components/Sidebar.jsx'
import OrgDashboard from './pages/OrgDashboard.jsx'
import AgentChat from './pages/AgentChat.jsx'

import Dashboard from './pages/Dashboard.jsx'
import ScanReport from './pages/ScanReport.jsx'
import ConnectionsPage from './pages/ConnectionsPage.jsx'
import OrgScan from './pages/OrgScan.jsx'
import ScannerPage from './pages/ScannerPage.jsx'
import Login from './pages/Login.jsx'
import MigratePage from './pages/MigratePage.jsx'
import AssessmentPage from './pages/AssessmentPage.jsx'
import InfoPage from './pages/InfoPage.jsx'
import ObjectDetailPage from './pages/ObjectDetailPage.jsx'
import RecordsListPage from './pages/RecordsListPage.jsx'
import GdprPage from './pages/GdprPage.jsx'
import SecurityPage from './pages/SecurityPage.jsx'
import OrgCompare from './pages/OrgCompare.jsx'

const SIDEBAR_W = 190
const HEADER_H  = 52

export default function App() {
  const [auth, setAuth] = useState(null)
  const [agents, setAgents] = useState([])
  const [page, setPage] = useState('agents')
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [oauthError, setOauthError] = useState('')
  const [theme, setTheme] = useState(() => localStorage.getItem('sf-theme') || 'dark')
  const [objectDetailName, setObjectDetailName] = useState('')
  const [recordsListConfig, setRecordsListConfig] = useState(null)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  function toggleTheme() {
    setTheme(t => {
      const next = t === 'dark' ? 'light' : 'dark'
      localStorage.setItem('sf-theme', next)
      return next
    })
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const err = params.get('error')
    const desc = params.get('error_description')
    if (err) {
      setOauthError(`${err}${desc ? ': ' + decodeURIComponent(desc) : ''}`)
      setPage('connections')
      window.history.replaceState({}, '', window.location.pathname)
    }

    fetch('/auth/me', { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        setAuth(data || false)
        if (data) setPage('agents')
      })
      .catch(() => setAuth(false))
    fetch('/agents')
      .then(r => r.json())
      .then(setAgents)
      .catch(() => {})
  }, [])

  function handleSelectAgent(agent) {
    setSelectedAgent(agent)
    setPage('agents')
  }

  function handleNavigate(newPage, param) {
    setPage(newPage)
    setSelectedAgent(null)
    if (newPage === 'object-detail' && param) setObjectDetailName(param)
    if (newPage === 'records-list' && param) setRecordsListConfig(param)
  }

  function handleLogout() {
    setAuth(false)
    if (page === 'scanner') setPage('agents')
  }

  const mainStyle = {
    position: 'fixed',
    top: HEADER_H,
    left: SIDEBAR_W,
    right: 0,
    bottom: 0,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    background: 'var(--bg)',
  }

  return (
    <Routes>
      <Route path="/report/:scanId" element={
        auth ? <ScanReport /> : <Navigate to="/" replace />
      } />
      <Route path="/dashboard" element={<Navigate to="/" replace />} />
      <Route path="*" element={
        <div style={{ background: 'var(--bg)' }}>
          <TopBar auth={auth} onNavigate={handleNavigate} theme={theme} onToggleTheme={toggleTheme} onAuthChange={setAuth} />
          <Sidebar
            activePage={page}
            onNavigate={handleNavigate}
            auth={auth}
          />
          <div style={mainStyle}>
              {page === 'agents' && !selectedAgent && (
                <OrgDashboard
                  auth={auth || null}
                  onConnect={() => setPage('connections')}
                  onNavigate={handleNavigate}
                  onAuthChange={setAuth}
                />
              )}

              {page === 'agents' && selectedAgent && (
                <AgentChat
                  agent={selectedAgent}
                  auth={auth}
                  onBack={() => setSelectedAgent(null)}
                  onConnectOrg={() => { setPage('connections'); setSelectedAgent(null) }}
                />
              )}

              {page === 'scanner' && (
                <ScannerPage
                  auth={auth}
                  onConnectOrg={() => { setPage('connections'); setSelectedAgent(null) }}
                  onNavigate={handleNavigate}
                />
              )}

              {page === 'orgscan' && (
                <OrgScan
                  auth={auth}
                  onConnectOrg={() => { setPage('connections'); setSelectedAgent(null) }}
                />
              )}

              {page === 'connections' && (
                <ConnectionsPage
                  auth={auth}
                  onLogout={handleLogout}
                  onNavigate={handleNavigate}
                  onAuthChange={setAuth}
                  oauthError={oauthError}
                  onClearError={() => setOauthError('')}
                />
              )}

              {page === 'migrate' && (
                <MigratePage auth={auth} onAuthChange={setAuth} />
              )}

              {page === 'info' && (
                <InfoPage auth={auth} />
              )}

              {page === 'object-detail' && (
                <ObjectDetailPage
                  objectName={objectDetailName}
                  onBack={() => handleNavigate('agents')}
                />
              )}

              {page === 'records-list' && (
                <RecordsListPage
                  config={recordsListConfig}
                  onBack={() => handleNavigate('agents')}
                />
              )}

              {page === 'professor' && (
                <AgentChat
                  agent={{ id: 'general_expert', icon: '🎓', name: 'Professor' }}
                  auth={auth}
                  onBack={() => handleNavigate('agents')}
                  onConnectOrg={() => { setPage('connections'); setSelectedAgent(null) }}
                />
              )}

              {page === 'crm_agent' && (
                <AgentChat
                  agent={{ id: 'crm_agent', icon: '💬', name: 'CRM Assistant' }}
                  auth={auth}
                  onBack={() => handleNavigate('agents')}
                  onConnectOrg={() => { setPage('connections'); setSelectedAgent(null) }}
                />
              )}

              {page === 'rc_product_agent' && (
                <AgentChat
                  agent={{ id: 'rc_product_agent', icon: '🏗️', name: 'Revenue Cloud Product Builder' }}
                  auth={auth}
                  onBack={() => handleNavigate('agents')}
                  onConnectOrg={() => { setPage('connections'); setSelectedAgent(null) }}
                />
              )}

              {page === 'assessment' && (
                <AssessmentPage
                  auth={auth}
                  onConnectOrg={() => { setPage('connections'); setSelectedAgent(null) }}
                />
              )}

              {page === 'security' && (
                <SecurityPage auth={auth} onNavigate={handleNavigate} />
              )}

              {page === 'gdpr' && (
                <GdprPage
                  auth={auth}
                  onConnectOrg={() => { setPage('connections'); setSelectedAgent(null) }}
                />
              )}

              {page === 'compare' && (
                <OrgCompare onNavigate={handleNavigate} />
              )}
          </div>
        </div>
      } />
    </Routes>
  )
}
