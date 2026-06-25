import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Auto-inject Bearer token from localStorage
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// --- Types ---
export interface User {
  id: number
  email: string
  name: string
  role: string
}

export interface Workspace {
  id: number
  name: string
  created_at: string
}

export interface Project {
  id: number
  name: string
  jira_url: string
  jira_project_key: string
  created_at: string
}

export interface Sprint {
  id: number
  name: string
  state: string
  total_tickets: number
  analysis_status: string
  imported_at?: string
}

export interface SprintDetail extends Sprint {
  project_id: number
  jira_sprint_id: number
  started_at?: string
  ended_at?: string
  tickets: TicketDetail[]
}

export interface Ticket {
  id: number
  key: string
  summary: string
  issue_type?: string
  status?: string
  priority?: string
  assignee?: string
}

export interface TicketDetail extends Ticket {
  sprint_id: number
  description?: string
  labels?: string[]
  story_points?: number
  acceptance_criteria?: string[]
  comments?: Record<string, unknown>[]
  figma_links?: string[]
  created_at?: string
}

// --- Auth ---
export async function login(email: string, password: string) {
  const res = await api.post('/auth/login', { email, password })
  return res.data as { access_token: string; token_type: string; user: User }
}

export async function register(
  email: string,
  name: string,
  password: string,
  workspace_name = 'My Workspace',
) {
  const res = await api.post('/auth/register', {
    email,
    name,
    password,
    workspace_name,
  })
  return res.data as {
    access_token: string
    token_type: string
    user: User
    workspace: Workspace
  }
}

export async function getMe() {
  const res = await api.get('/auth/me')
  return res.data as User
}

// --- Projects ---
export async function listProjects() {
  const res = await api.get('/projects/')
  return res.data as Project[]
}

export async function createProject(data: {
  name: string
  jira_url: string
  jira_email: string
  jira_api_token: string
  jira_project_key: string
}) {
  const res = await api.post('/projects/', data)
  return res.data as Project
}

export async function getProject(id: number) {
  const res = await api.get(`/projects/${id}`)
  return res.data as Project
}

export async function updateProject(
  id: number,
  data: Partial<{
    name: string
    jira_url: string
    jira_email: string
    jira_api_token: string
    jira_project_key: string
  }>,
) {
  const res = await api.put(`/projects/${id}`, data)
  return res.data as Project
}

export async function deleteProject(id: number) {
  await api.delete(`/projects/${id}`)
}

// --- Sprints ---
export async function importSprint(project_id: number, sprint_name: string) {
  const res = await api.post('/sprints/import', { project_id, sprint_name })
  return res.data as SprintDetail
}

export async function listSprints(project_id: number) {
  const res = await api.get('/sprints/', { params: { project_id } })
  return res.data as Sprint[]
}

export async function getSprint(sprint_id: number) {
  const res = await api.get(`/sprints/${sprint_id}`)
  return res.data as SprintDetail
}

// --- Tickets ---
export async function listTickets(sprint_id: number) {
  const res = await api.get(`/tickets/${sprint_id}/tickets`)
  return res.data as TicketDetail[]
}

export async function getTicket(sprint_id: number, ticket_id: number) {
  const res = await api.get(`/tickets/${sprint_id}/tickets/${ticket_id}`)
  return res.data as TicketDetail
}

export default api
