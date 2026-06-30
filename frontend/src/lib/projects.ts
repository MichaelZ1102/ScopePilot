import api from './client'
import type { Project } from './types'

export async function listProjects() { const r = await api.get('/projects/'); return r.data as Project[] }
export async function createProject(d: { name: string; jira_url: string; jira_email: string; jira_api_token: string; jira_project_key: string }) { const r = await api.post('/projects/', d); return r.data as Project }
export async function getProject(id: number) { const r = await api.get(`/projects/${id}`); return r.data as Project }
export async function updateProject(id: number, d: Partial<{ name: string; jira_url: string; jira_email: string; jira_api_token: string; jira_project_key: string }>) { const r = await api.put(`/projects/${id}`, d); return r.data as Project }
export async function deleteProject(id: number) { await api.delete(`/projects/${id}`) }
