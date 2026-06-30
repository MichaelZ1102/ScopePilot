import api from './client'

export async function listApiSpecs() { const r = await api.get('/api-tests/specs'); return r.data }
export async function listSpecs() { return listApiSpecs() }
export async function createApiSpec(d: { name: string; source_url?: string; spec_content?: string }) { const r = await api.post('/api-tests/specs', d); return r.data }
export async function importSpecFromUrl(url: string, name: string) { const r = await api.post('/api-tests/specs/from-url', { url, name }); return r.data }
export async function importSpecFromContent(content: string, name: string) { const r = await api.post('/api-tests/specs/from-content', { content, name }); return r.data }
export async function deleteApiSpec(id: number) { await api.delete(`/api-tests/specs/${id}`) }
export async function deleteSpec(id: number) { return deleteApiSpec(id) }
export async function generateTestPlan(spec_id: number) { const r = await api.post(`/api-tests/specs/${spec_id}/generate`); return r.data }
export async function listTestPlans(spec_id?: number) { const r = spec_id ? await api.get(`/api-tests/specs/${spec_id}/plans`) : await api.get('/api-tests/plans'); return r.data }
export async function getTestPlan(plan_id: number) { const r = await api.get(`/api-tests/plans/${plan_id}`); return r.data }
export async function exportPlanMarkdown(plan_id: number) { const r = await api.get(`/api-tests/plans/${plan_id}/export/markdown`); return r.data }
export async function exportPlanPostman(plan_id: number) { const r = await api.get(`/api-tests/plans/${plan_id}/export/postman`); return r.data }
