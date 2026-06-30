import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import api from './api'

interface AuthContextType {
  isLoggedIn: boolean
  isLoading: boolean
  checkAuth: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  const checkAuth = async () => {
    try {
      await api.get('/auth/me')
      setIsLoggedIn(true)
    } catch {
      setIsLoggedIn(false)
    } finally {
      setIsLoading(false)
    }
  }

  const logout = async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      // ignore logout errors
    } finally {
      setIsLoggedIn(false)
    }
  }

  useEffect(() => {
    checkAuth()
    const handler = () => {
      setIsLoggedIn(false)
      setIsLoading(false)
    }
    window.addEventListener('auth:logout', handler)
    return () => window.removeEventListener('auth:logout', handler)
  }, [])

  return (
    <AuthContext.Provider value={{ isLoggedIn, isLoading, checkAuth, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
