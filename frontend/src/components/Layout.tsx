import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Code2,
  FolderKanban,
  FileBarChart,
  Gauge,
  LogOut,
  PenTool,
  ScanSearch,
  Settings,
  TestTube2,
  ListTodo,
  Bell,
} from 'lucide-react'

import { useAuth } from '../lib/AuthContext'
import './Layout.css'

const navItems = [
  { to: '/', labelKey: 'nav.dashboard', icon: Gauge, end: true },
  { to: '/projects', labelKey: 'nav.projects', icon: FolderKanban },
  { to: '/code-sources', labelKey: 'nav.code_sources', fallback: 'Codebase', icon: Code2 },
  { to: '/api-test-plans', labelKey: 'nav.api_tests', fallback: 'API 测试', icon: TestTube2 },
  { to: '/figma-designs', labelKey: 'nav.figma', fallback: 'Figma', icon: PenTool },
  { to: '/reports', labelKey: 'nav.reports', fallback: '报告', icon: FileBarChart },
  { to: '/analysis-jobs', labelKey: 'nav.analysis_jobs', fallback: '分析任务', icon: ListTodo },
  { to: '/notifications', labelKey: 'nav.notifications', fallback: '通知', icon: Bell },
  { to: '/settings', labelKey: 'nav.settings', icon: Settings },
]

export default function Layout() {
  const { t } = useTranslation()
  const { logout, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const isSprintWorkspace = location.pathname.startsWith('/sprint/')

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-brand">
          <span className="app-brand-mark"><ScanSearch size={20} strokeWidth={2.4} /></span>
          <span>ScopePilot</span>
        </div>

        <nav className="app-navigation" aria-label="主导航">
          {navItems.map(({ to, labelKey, fallback, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              title={fallback || t(labelKey as any)}
              className={({ isActive }) => `app-nav-item${isActive ? ' is-active' : ''}`}
            >
              <Icon size={19} strokeWidth={1.8} />
              <span>{fallback || t(labelKey as any)}</span>
            </NavLink>
          ))}
        </nav>

        <div className="app-sidebar-footer">
          <div className="app-user">
            <span className="app-avatar">{(user?.name || 'U').split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase()}</span>
            <span className="app-user-name">{user?.name || 'User'}</span>
          </div>
          <button className="app-logout" type="button" onClick={handleLogout}>
            <LogOut size={18} />
            <span>{t('nav.logout')}</span>
          </button>
        </div>
      </aside>

      <main className={`app-main${isSprintWorkspace ? ' app-main-workspace' : ''}`}>
        <Outlet />
      </main>
    </div>
  )
}
