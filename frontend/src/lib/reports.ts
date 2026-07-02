import api from './client'
import type { ActionItem, AnalysisRun, DeliveryLink, ReportComment, ReportSnapshot, SprintReport, TicketArtifactLink, TicketReport, TicketReview } from './types'

export async function includeTicketInReport(sprintId: number, ticketId: number) {
  const response = await api.post(`/reports/${sprintId}/tickets/${ticketId}`)
  return response.data as { ticket_id: number; report_included: true }
}

export async function excludeTicketFromReport(sprintId: number, ticketId: number) {
  const response = await api.delete(`/reports/${sprintId}/tickets/${ticketId}`)
  return response.data as { ticket_id: number; report_included: false }
}

export async function getTicketReport(ticketId: number, analysisRunId?: number) {
  const response = await api.get(`/tickets/${ticketId}/report`, {
    params: analysisRunId ? { analysis_run_id: analysisRunId } : undefined,
  })
  return response.data as TicketReport
}

export async function listTicketAnalysisRuns(sprintId: number, ticketId: number) {
  const response = await api.get(`/tickets/${sprintId}/tickets/${ticketId}/analysis-runs`)
  return response.data as AnalysisRun[]
}

export async function archiveTicketAnalysisRun(sprintId: number, ticketId: number, runId: number) {
  const response = await api.post(`/tickets/${sprintId}/tickets/${ticketId}/analysis-runs/${runId}/archive`)
  return response.data as AnalysisRun
}

export async function updateTicketReview(
  sprintId: number,
  ticketId: number,
  status: TicketReview['status'],
  comment = '',
) {
  const response = await api.put(`/tickets/${sprintId}/tickets/${ticketId}/review`, { status, comment })
  return response.data as TicketReview
}

export async function reviseTicketAnalysis(
  sprintId: number,
  ticketId: number,
  updates: Partial<Pick<TicketReport['analysis'], 'business_goal' | 'implementation_plan' | 'open_questions' | 'assumptions'>>,
) {
  const response = await api.patch(`/tickets/${sprintId}/tickets/${ticketId}/analysis`, updates)
  return response.data as { analysis: TicketReport['analysis']; analysis_run: AnalysisRun }
}

export async function listTicketArtifacts(sprintId: number, ticketId: number) {
  const response = await api.get(`/tickets/${sprintId}/tickets/${ticketId}/artifacts`)
  return response.data as TicketArtifactLink[]
}

export async function linkTicketArtifact(
  sprintId: number,
  ticketId: number,
  artifact_type: TicketArtifactLink['artifact_type'],
  artifact_id: number,
) {
  const response = await api.post(`/tickets/${sprintId}/tickets/${ticketId}/artifacts`, { artifact_type, artifact_id })
  return response.data as TicketArtifactLink
}

export async function getSprintReport(sprintId: number) {
  const response = await api.get(`/reports/${sprintId}/structured`)
  return response.data as SprintReport
}

export async function publishSprintReport(sprintId: number) {
  const response = await api.post(`/reports/${sprintId}/publish`)
  return response.data as ReportSnapshot
}

export async function listReportSnapshots() {
  const response = await api.get('/reports/')
  return response.data as ReportSnapshot[]
}

export async function archiveReportSnapshot(snapshotId: number) {
  const response = await api.post(`/reports/snapshots/${snapshotId}/archive`)
  return response.data as ReportSnapshot
}

export async function addReportComment(sprintId: number, ticketId: number, body: string) {
  const response = await api.post(`/tickets/${sprintId}/tickets/${ticketId}/comments`, { body })
  return response.data as ReportComment
}

export async function updateReportComment(sprintId: number, ticketId: number, commentId: number, status: ReportComment['status']) {
  const response = await api.patch(`/tickets/${sprintId}/tickets/${ticketId}/comments/${commentId}`, { status })
  return response.data as ReportComment
}

export async function addActionItem(sprintId: number, ticketId: number, title: string, owner = '', due_at?: string) {
  const response = await api.post(`/tickets/${sprintId}/tickets/${ticketId}/action-items`, { title, owner, due_at })
  return response.data as ActionItem
}

export async function updateActionItem(sprintId: number, ticketId: number, actionItemId: number, updates: Partial<Pick<ActionItem, 'status' | 'owner' | 'due_at'>>) {
  const response = await api.patch(`/tickets/${sprintId}/tickets/${ticketId}/action-items/${actionItemId}`, updates)
  return response.data as ActionItem
}

export async function addDeliveryLink(
  sprintId: number,
  ticketId: number,
  data: Omit<DeliveryLink, 'id' | 'ticket_id' | 'created_at'>,
) {
  const response = await api.post(`/tickets/${sprintId}/tickets/${ticketId}/delivery-links`, data)
  return response.data as DeliveryLink
}

export async function writebackJiraComment(sprintId: number, ticketId: number, body: string) {
  const response = await api.post(`/tickets/${sprintId}/tickets/${ticketId}/jira/comment`, { body })
  return response.data
}

export async function writebackJiraTransition(sprintId: number, ticketId: number, transition: string) {
  const response = await api.post(`/tickets/${sprintId}/tickets/${ticketId}/jira/transition`, { transition })
  return response.data
}

export async function writebackJiraLabels(sprintId: number, ticketId: number, labels: string[]) {
  const response = await api.put(`/tickets/${sprintId}/tickets/${ticketId}/jira/labels`, { labels })
  return response.data
}

export function ticketReportDownloadUrl(ticketId: number, fmt: 'md' | 'json' | 'pdf' | 'jira' | 'postman' = 'md') {
  return `/api/v1/tickets/${ticketId}/report/export?fmt=${fmt}`
}

export function sprintReportDownloadUrl(sprintId: number, fmt: 'md' | 'pdf' | 'json' | 'csv' | 'jira' = 'md') {
  return `/api/v1/reports/${sprintId}/export?fmt=${fmt}`
}

export async function publishSprintToConfluence(sprintId: number, data: { space_key: string; title: string; parent_page_id?: string }) {
  const response = await api.post(`/reports/${sprintId}/confluence`, data)
  return response.data
}
