import { lazy, Suspense, type ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { LoaderCircle } from 'lucide-react'
import { useAuth } from './lib/AuthContext'
import Layout from './components/Layout'
import LoginPage from './components/LoginPage'
import SharedReportPage from './pages/SharedReportPage'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const SprintDetail = lazy(() => import('./pages/SprintDetail'))
const Projects = lazy(() => import('./pages/Projects'))
const Settings = lazy(() => import('./pages/Settings'))
const CodeSources = lazy(() => import('./pages/CodeSources'))
const ApiTestPlans = lazy(() => import('./pages/ApiTestPlans'))
const FigmaDesigns = lazy(() => import('./pages/FigmaDesigns'))
const Reports = lazy(() => import('./pages/Reports'))
const TicketReportPage = lazy(() => import('./pages/TicketReportPage'))
const SprintReportPage = lazy(() => import('./pages/SprintReportPage'))
const AnalysisJobs = lazy(() => import('./pages/AnalysisJobs'))
const Notifications = lazy(() => import('./pages/Notifications'))

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
    <Suspense fallback={<div className="loading-state"><span className="loading-state-icon"><LoaderCircle className="spin" size={22} /></span><p>正在加载页面...</p></div>}>
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
        <Route path="/reports" element={<Reports />} />
        <Route path="/analysis-jobs" element={<AnalysisJobs />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/tickets/:ticketId/report" element={<TicketReportPage />} />
        <Route path="/sprints/:sprintId/report" element={<SprintReportPage />} />
      </Route>
      <Route path="*" element={<Navigate to={isLoggedIn ? '/' : '/login'} replace />} />
      </Routes>
    </Suspense>
  )
}

function App() {
  return <AppContent />
}

export default App
