import api from './client'
import type { User, Workspace } from './types'

export async function login(email: string, password: string) {
  const res = await api.post('/auth/login', { email, password })
  return res.data as { access_token: string; token_type: string; user: User }
}
export async function register(email: string, name: string, password: string, workspace_name = 'My Workspace') {
  const res = await api.post('/auth/register', { email, name, password, workspace_name })
  return res.data as { access_token: string; token_type: string; user: User; workspace: Workspace }
}
export async function getMe() {
  const res = await api.get('/auth/me')
  return res.data as User
}
