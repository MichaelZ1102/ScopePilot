import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import api from './api'
import type { User } from './types'

interface AuthContextType {
  isLoggedIn: boolean
  isLoading: boolean
  user: User | null
  checkAuth: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [user, setUser] = useState<User | null>(null)

  const checkAuth = async () => {
    try {
      const response = await api.get('/auth/me')
      setUser(response.data)
      setIsLoggedIn(true)
    } catch {
      setUser(null)
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
      setUser(null)
    }
  }

  useEffect(() => {
    checkAuth()
    const handler = () => {
      setIsLoggedIn(false)
      setUser(null)
      setIsLoading(false)
    }
    window.addEventListener('auth:logout', handler)
    return () => window.removeEventListener('auth:logout', handler)
  }, [])

  return (
    <AuthContext.Provider value={{ isLoggedIn, isLoading, user, checkAuth, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
