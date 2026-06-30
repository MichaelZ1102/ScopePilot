import { useState, useEffect } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { getMe } from '../lib/auth'
import type { User } from '../lib/types'

export default function Layout() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(null)

  useEffect(() => {
    getMe().then(setUser).catch(() => setUser(null))
  }, [])

  const handleLogout = async () => {
    try {
      await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' })
    } catch { /* ignore */ }
    navigate('/login')
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', margin: 0 }}>
      <nav style={{
        width: 240,
        background: '#1a1a2e',
        color: '#fff',
        padding: '1.5rem 0',
        display: 'flex',
        flexDirection: 'column',
      }}>
        <h1 style={{ fontSize: '1.25rem', padding: '0 1.25rem', marginBottom: '2rem' }}>
          {t('app.title')}
        </h1>
        <NavLink
          to="/"
          end
          style={({ isActive }) => ({
            padding: '0.75rem 1.25rem',
            color: isActive ? '#fff' : '#aaa',
            background: isActive ? 'rgba(255,255,255,0.1)' : 'transparent',
            textDecoration: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.95rem',
            borderLeft: isActive ? '3px solid #4fc3f7' : '3px solid transparent',
          })}
        >
          <span>📊</span>
          {t('nav.dashboard')}
        </NavLink>
        <NavLink
          to="/projects"
          style={({ isActive }) => ({
            padding: '0.75rem 1.25rem',
            color: isActive ? '#fff' : '#aaa',
            background: isActive ? 'rgba(255,255,255,0.1)' : 'transparent',
            textDecoration: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.95rem',
            borderLeft: isActive ? '3px solid #4fc3f7' : '3px solid transparent',
          })}
        >
          <span>📁</span>
          {t('nav.projects')}
        </NavLink>
        <NavLink
          to="/settings"
          style={({ isActive }) => ({
            padding: '0.75rem 1.25rem',
            color: isActive ? '#fff' : '#aaa',
            background: isActive ? 'rgba(255,255,255,0.1)' : 'transparent',
            textDecoration: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.95rem',
            borderLeft: isActive ? '3px solid #4fc3f7' : '3px solid transparent',
          })}
        >
          <span>⚙️</span>
          {t('nav.settings')}
        </NavLink>
        <NavLink
          to="/code-sources"
          style={({ isActive }) => ({
            padding: '0.75rem 1.25rem',
            color: isActive ? '#fff' : '#aaa',
            background: isActive ? 'rgba(255,255,255,0.1)' : 'transparent',
            textDecoration: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.95rem',
            borderLeft: isActive ? '3px solid #4fc3f7' : '3px solid transparent',
          })}
        >
          <span>📂</span>
          {t('nav.code_sources' as any, 'Codebase')}
        </NavLink>
        <NavLink
          to="/api-test-plans"
          style={({ isActive }) => ({
            padding: '0.75rem 1.25rem',
            color: isActive ? '#fff' : '#aaa',
            background: isActive ? 'rgba(255,255,255,0.1)' : 'transparent',
            textDecoration: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.95rem',
            borderLeft: isActive ? '3px solid #4fc3f7' : '3px solid transparent',
          })}
        >
          <span>🧪</span>
          {t('nav.api_tests' as any, 'API Tests')}
        </NavLink>
        <NavLink
          to="/figma-designs"
          style={({ isActive }) => ({
            padding: '0.75rem 1.25rem',
            color: isActive ? '#fff' : '#aaa',
            background: isActive ? 'rgba(255,255,255,0.1)' : 'transparent',
            textDecoration: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.95rem',
            borderLeft: isActive ? '3px solid #4fc3f7' : '3px solid transparent',
          })}
        >
          <span>🎨</span>
          {t('nav.figma' as any, 'Figma')}
        </NavLink>
        <div style={{ flex: 1 }} />
        <div style={{ padding: '0.75rem 1.25rem', color: '#666', fontSize: '0.85rem' }}>
          {user?.name || user?.email || ''}
        </div>
        <div
          onClick={handleLogout}
          style={{
            padding: '0.75rem 1.25rem',
            color: '#e74c3c',
            cursor: 'pointer',
            fontSize: '0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <span>🚪</span>
          {t('nav.logout')}
        </div>
      </nav>
      <main style={{ flex: 1, padding: '2rem', background: '#f5f5f5', overflow: 'auto' }}>
        <Outlet />
      </main>
    </div>
  )
}
