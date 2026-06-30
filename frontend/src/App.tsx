import { type ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './lib/AuthContext'
import Layout from './components/Layout'
import LoginPage from './components/LoginPage'
import Dashboard from './pages/Dashboard'
import SprintDetail from './pages/SprintDetail'
import Projects from './pages/Projects'
import Settings from './pages/Settings'
import CodeSources from './pages/CodeSources'
import ApiTestPlans from './pages/ApiTestPlans'
import FigmaDesigns from './pages/FigmaDesigns'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isLoggedIn, isLoading } = useAuth()

  if (isLoading) return <div style={{display:'flex',justifyContent:'center',alignItems:'center',height:'100vh',color:'#888'}}>验证中...</div>
  if (!isLoggedIn) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AppContent() {
  const { isLoggedIn, isLoading } = useAuth()

  if (isLoading) return null

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
        <Route path="/code-sources" element={<CodeSources />} />
        <Route path="/api-test-plans" element={<ApiTestPlans />} />
        <Route path="/figma-designs" element={<FigmaDesigns />} />
      </Route>
      <Route path="*" element={<Navigate to={isLoggedIn ? '/' : '/login'} replace />} />
    </Routes>
  )
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

export default App
