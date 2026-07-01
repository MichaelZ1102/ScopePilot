import api from './client'
import type { Sprint, SprintDetail, TicketAnalysis, TicketDetail } from './types'

export async function importSprint(project_id: number, sprint_name: string) { const r = await api.post('/sprints/import', { project_id, sprint_name }); return r.data as SprintDetail }
export async function listSprints(project_id: number) { const r = await api.get('/sprints/', { params: { project_id } }); return r.data as Sprint[] }
export async function getSprint(sprint_id: number) { const r = await api.get(`/sprints/${sprint_id}`); return r.data as SprintDetail }
export async function triggerAnalysis(sprint_id: number) { const r = await api.post(`/analysis/sprints/${sprint_id}/analyze`); return r.data as SprintDetail }
export async function getAnalysis(sprint_id: number) { const r = await api.get(`/analysis/sprints/${sprint_id}/analysis`); return r.data as SprintDetail }
export async function analyzeTicket(sprint_id: number, ticket_id: number) {
  const r = await api.post(`/analysis/sprints/${sprint_id}/tickets/${ticket_id}/analyze`)
  return r.data as { ticket_id: number; ticket_key: string; analysis: TicketAnalysis }
}
export async function listTickets(sprint_id: number) { const r = await api.get(`/tickets/${sprint_id}/tickets`); return r.data as TicketDetail[] }
export async function getTicket(sprint_id: number, ticket_id: number) { const r = await api.get(`/tickets/${sprint_id}/tickets/${ticket_id}`); return r.data as TicketDetail }
