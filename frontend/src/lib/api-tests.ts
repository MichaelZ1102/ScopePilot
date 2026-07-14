import api from './client'

export async function listApiSpecs(projectId?: number) { const r = await api.get('/api-tests/specs', { params: projectId ? { project_id: projectId } : undefined }); return r.data }
export async function listSpecs(projectId?: number) { return listApiSpecs(projectId) }
export async function importSpecFromUrl(url: string, name: string, project_id?: number, service_name?: string) { const r = await api.post('/api-tests/specs/from-url', { url, name, project_id, service_name: service_name || '' }); return r.data }
export async function importSpecFromContent(content: string, name: string, project_id?: number, service_name?: string) { const r = await api.post('/api-tests/specs/from-content', { content, name, project_id, service_name: service_name || '' }); return r.data }
export async function deleteApiSpec(id: number) { await api.delete(`/api-tests/specs/${id}`) }
export async function deleteSpec(id: number) { return deleteApiSpec(id) }
export async function generateTestPlan(spec_id: number, ticket_ids?: number[]) { const r = await api.post(`/api-tests/specs/${spec_id}/generate`, { ticket_ids: ticket_ids || null }); return r.data }
export async function listTestPlans(projectId?: number) { const r = await api.get('/api-tests/plans', { params: projectId ? { project_id: projectId } : undefined }); return r.data }
export async function getTestPlan(plan_id: number) { const r = await api.get(`/api-tests/plans/${plan_id}`); return r.data }
export async function exportPlanMarkdown(plan_id: number) { const r = await api.get(`/api-tests/plans/${plan_id}/export/markdown`); return r.data }
export async function exportPlanPostman(plan_id: number) { const r = await api.get(`/api-tests/plans/${plan_id}/export/postman`); return r.data }
export async function analyzeTicketApiImpact(spec_id: number, ticket_id: number) { const r = await api.post(`/api-tests/specs/${spec_id}/impact/${ticket_id}`); return r.data }
