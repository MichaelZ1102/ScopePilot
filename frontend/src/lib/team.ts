import api from './client'

export async function listMembers() { const r = await api.get('/team/members'); return r.data }
export async function addMember(email: string, name: string, role?: string) { const r = await api.post('/team/members', { email, name, role: role || 'member' }); return r.data }
export async function updateMemberRole(mid: number, role: string) { const r = await api.patch(`/team/members/${mid}/role`, { role }); return r.data }
export async function removeMember(mid: number) { await api.delete(`/team/members/${mid}`) }
export async function getBilling() { const r = await api.get('/team/billing'); return r.data }
export async function upgradeTier(tier: string) { const r = await api.post('/team/billing/upgrade', { tier }); return r.data }
export async function getUsage() { const r = await api.get('/team/usage'); return r.data }
export async function listTiers() { const r = await api.get('/team/tiers'); return r.data }
export async function shareReport(sprintId: number, title: string, password?: string) { const r = await api.post('/team/share', { sprint_id: sprintId, title, password: password || '' }); return r.data }
export async function listSharedReports() { const r = await api.get('/team/shared'); return r.data }
export async function accessSharedReport(token: string, password?: string) { const r = await api.post(`/team/shared/access/${token}`, { password: password || '' }); return r.data }
export async function revokeShare(shareId: number) { await api.delete(`/team/shared/${shareId}`) }
