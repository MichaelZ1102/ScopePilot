import api from './client'
import type { CodeSource, RepoSnapshot, CodeImpact } from './types'

export async function listCodeSources() { const r = await api.get('/code-sources/'); return r.data as CodeSource[] }
export async function createCodeSource(d: { name: string; provider: string; repo_url: string; default_branch?: string; access_token?: string }) { const r = await api.post('/code-sources/', d); return r.data as CodeSource }
export async function scanCodeSource(id: number) { const r = await api.post(`/code-sources/${id}/scan`); return r.data as RepoSnapshot }
export const scanRepository = scanCodeSource
export async function deleteCodeSource(id: number) { await api.delete(`/code-sources/${id}`) }
export async function getLatestSnapshot(id: number) { const r = await api.get(`/code-sources/${id}/snapshot`); return r.data as RepoSnapshot | null }
export async function analyzeCodeImpact(sourceId: number, ticketId: number, sprintId: number, summary?: string, description?: string) {
  const r = await api.post(`/code-sources/${sourceId}/impact/${ticketId}`, null, {
    params: { sprint_id: sprintId, summary: summary || '', description: description || '' },
  })
  return r.data as CodeImpact
}
export async function getTicketCodeImpact(ticketId: number) {
  const r = await api.get(`/code-sources/impact/ticket/${ticketId}`)
  return r.data as CodeImpact
}
