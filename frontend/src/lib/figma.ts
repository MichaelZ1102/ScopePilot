import api from './client'

export async function analyzeFigmaDesign(url: string, token: string, ticket_summary?: string, context?: { project_id?: number; ticket_id?: number; figma_node_id?: string }) { const r = await api.post('/figma/analyze', { figma_url: url, figma_token: token, ticket_summary: ticket_summary || '', ...context }); return r.data }
export async function listFigmaAnalyses() { const r = await api.get('/figma/analyses'); return r.data }
export async function deleteFigmaAnalysis(id: number) { await api.delete(`/figma/analyses/${id}`) }
