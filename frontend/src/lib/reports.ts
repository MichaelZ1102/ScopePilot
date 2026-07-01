import api from './client'

export async function includeTicketInReport(sprintId: number, ticketId: number) {
  const response = await api.post(`/reports/${sprintId}/tickets/${ticketId}`)
  return response.data as { ticket_id: number; report_included: true }
}

export async function excludeTicketFromReport(sprintId: number, ticketId: number) {
  const response = await api.delete(`/reports/${sprintId}/tickets/${ticketId}`)
  return response.data as { ticket_id: number; report_included: false }
}
