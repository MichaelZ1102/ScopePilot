import { type ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { LoaderCircle } from 'lucide-react'
import { useAuth } from './lib/AuthContext'
import Layout from './components/Layout'
import LoginPage from './components/LoginPage'
import Dashboard from './pages/Dashboard'
import SprintDetail from './pages/SprintDetail'
import Projects from './pages/Projects'
import Settings from './pages/Settings'
import CodeSources from './pages/CodeSources'
import ApiTestPlans from './pages/ApiTestPlans'
import FigmaDesigns from './pages/FigmaDesigns'
import SharedReportPage from './pages/SharedReportPage'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isLoggedIn, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="loading-state" style={{ minHeight: '100vh', border: 0, borderRadius: 0 }}>
        <span className="loading-state-icon"><LoaderCircle className="spin" size={22} /></span>
        <p>正在检查登录状态...</p>
      </div>
    )
  }
  if (!isLoggedIn) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AppContent() {
  const { isLoggedIn, isLoading } = useAuth()

  if (isLoading) return null

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/shared/:token" element={<SharedReportPage />} />
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
        <Route path="/code-sources" element={<CodeSources />} />
        <Route path="/api-test-plans" element={<ApiTestPlans />} />
        <Route path="/figma-designs" element={<FigmaDesigns />} />
      </Route>
      <Route path="*" element={<Navigate to={isLoggedIn ? '/' : '/login'} replace />} />
    </Routes>
  )
}

function App() {
  return <AppContent />
}

export default App
