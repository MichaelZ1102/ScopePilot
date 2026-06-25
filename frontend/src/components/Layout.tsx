import { Outlet, NavLink } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/projects', label: 'Projects', icon: '📁' },
  { to: '/settings', label: 'Settings', icon: '⚙️' },
]

export default function Layout() {
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
          🚀 ScopePilot
        </h1>
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
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
            <span>{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <main style={{ flex: 1, padding: '2rem', background: '#f5f5f5', overflow: 'auto' }}>
        <Outlet />
      </main>
    </div>
  )
}
