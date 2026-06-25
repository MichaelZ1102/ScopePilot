import { useState, useEffect, type ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import LoginPage from './components/LoginPage'
import Dashboard from './pages/Dashboard'
import SprintDetail from './pages/SprintDetail'
import Projects from './pages/Projects'
import Settings from './pages/Settings'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const token = localStorage.getItem('token')
  if (!token) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

function App() {
  const [ready, setReady] = useState(false)
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('token'))

  useEffect(() => {
    // Listen for auth changes across the app
    const checkAuth = () => {
      const hasToken = !!localStorage.getItem('token')
      setIsLoggedIn(hasToken)
    }

    // Check on mount
    checkAuth()
    setReady(true)

    // Listen for storage events (in case token changes in another tab)
    window.addEventListener('storage', checkAuth)
    return () => window.removeEventListener('storage', checkAuth)
  }, [])

  if (!ready) return null

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/sprint/:id" element={<SprintDetail />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to={isLoggedIn ? '/' : '/login'} replace />} />
    </Routes>
  )
}

export default App
