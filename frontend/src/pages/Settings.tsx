import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  getBilling, listTiers, upgradeTier, getUsage,
  listMembers, addMember, removeMember,
  listSharedReports, shareReport, revokeShare,
  type BillingTier, type UsageData, type TeamMember, type SharedReport,
} from '../lib/api'
import { getApiErrorMessage } from '../lib/client'

const styles: any = {
  page: { maxWidth: 900, margin: '0 auto' },
  title: { fontSize: '1.5rem', fontWeight: 700, color: '#1a1a2e', marginBottom: '0.5rem' },
  desc: { color: '#888', fontSize: '0.9rem', marginBottom: '2rem' },
  section: { background: '#fff', borderRadius: 12, padding: '1.5rem', marginBottom: '1.5rem', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' },
  sectionTitle: { fontSize: '1.1rem', fontWeight: 600, color: '#1a1a2e', marginBottom: '1rem' },
  btn: { padding: '0.45rem 1rem', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: '0.85rem', fontWeight: 500, color: '#fff' },
  btnPrimary: { background: '#4fc3f7' },
  btnDanger: { background: '#e74c3c' },
  btnSmall: { padding: '0.3rem 0.7rem', fontSize: '0.8rem' },
  btnOutline: { background: 'transparent', border: '1px solid #1a1a2e', color: '#1a1a2e' },
  input: { padding: '0.5rem 0.75rem', borderRadius: 6, border: '1px solid #ddd', fontSize: '0.88rem', boxSizing: 'border-box' as const },
  select: { padding: '0.5rem 0.75rem', borderRadius: 6, border: '1px solid #ddd', fontSize: '0.88rem', background: '#fff' },
  badge: (role: string) => {
    const colors: Record<string, string> = { admin: '#e74c3c', member: '#4fc3f7', viewer: '#90a4ae' }
    return { display: 'inline-block', padding: '0.1rem 0.4rem', borderRadius: 4, background: colors[role] || '#eee', color: '#fff', fontSize: '0.72rem', fontWeight: 500 }
  },
  tierCard: (active: boolean) => ({
    border: active ? '2px solid #4fc3f7' : '1px solid #eee',
    borderRadius: 10, padding: '1.25rem', cursor: 'pointer',
    background: active ? '#f8fbff' : '#fff',
    flex: 1, minWidth: 180,
  }),
  modalOverlay: { position: 'fixed' as const, inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 },
  modal: { background: '#fff', borderRadius: 12, padding: '2rem', width: '100%', maxWidth: 440, boxShadow: '0 8px 32px rgba(0,0,0,0.2)' },
  modalTitle: { fontSize: '1.2rem', fontWeight: 600, marginBottom: '1rem', color: '#1a1a2e' },
  modalActions: { display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' as const, marginTop: '1rem' },
  label: { display: 'block', color: '#555', fontSize: '0.85rem', fontWeight: 500, marginBottom: '0.3rem' },
}

export default function Settings() {
  const { t, i18n } = useTranslation()
  const [tab, setTab] = useState<'general' | 'billing' | 'team' | 'sharing'>('general')

  // Billing
  const [billing, setBilling] = useState<any>(null)
  const [tiers, setTiers] = useState<BillingTier[]>([])
  const [usage, setUsage] = useState<UsageData | null>(null)

  // Members
  const [members, setMembers] = useState<TeamMember[]>([])
  const [showInvite, setShowInvite] = useState(false)
  const [inviteForm, setInviteForm] = useState({ email: '', name: '', role: 'member' })

  // Sharing
  const [sharedReports, setSharedReports] = useState<SharedReport[]>([])
  const [showShare, setShowShare] = useState(false)
  const [shareForm, setShareForm] = useState({ sprint_id: '', title: '', password: '' })

  useEffect(() => { loadData() }, [tab])

  async function loadData() {
    try {
      if (tab === 'billing') {
        setBilling(await getBilling())
        setTiers(await listTiers())
        setUsage(await getUsage())
      } else if (tab === 'team') {
        setMembers(await listMembers())
      } else if (tab === 'sharing') {
        setSharedReports(await listSharedReports())
      }
    } catch { /* ignore */ }
  }

  async function handleUpgrade(tier: string) {
    try { await upgradeTier(tier); await loadData(); alert('升级成功！') }
    catch (err: unknown) { alert(getApiErrorMessage(err, 'Upgrade failed')) }
  }

  async function handleInvite() {
    try {
      await addMember(inviteForm.email, inviteForm.name, inviteForm.role)
      setShowInvite(false); setInviteForm({ email: '', name: '', role: 'member' })
      await loadData()
    } catch (err: unknown) { alert(getApiErrorMessage(err, 'Invite failed')) }
  }

  async function handleRemoveMember(id: number) {
    if (!confirm('确定移除此成员？')) return
    try { await removeMember(id); await loadData() } catch { alert('操作失败') }
  }

  async function handleShare() {
    try {
      await shareReport(Number(shareForm.sprint_id), shareForm.title, shareForm.password)
      setShowShare(false); setShareForm({ sprint_id: '', title: '', password: '' })
      await loadData()
    } catch (err: unknown) { alert(getApiErrorMessage(err, 'Share failed')) }
  }

  async function handleRevoke(id: number) {
    if (!confirm('确定撤销此分享链接？')) return
    try { await revokeShare(id); await loadData() } catch { alert('操作失败') }
  }

  const handleLangChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    i18n.changeLanguage(e.target.value)
    localStorage.setItem('locale', e.target.value)
  }

  const tabs = [
    { id: 'general', label: '⚙️ 通用' },
    { id: 'billing', label: '💳 计费与用量' },
    { id: 'team', label: '👥 团队' },
    { id: 'sharing', label: '🔗 报告共享' },
  ]

  return (
    <div style={styles.page}>
      <h2 style={styles.title}>{t('settings.title')}</h2>
      <p style={styles.desc}>{t('settings.description')}</p>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        {tabs.map(tabItem => (
          <button key={tabItem.id} onClick={() => setTab(tabItem.id as any)}
            style={{ padding: '0.5rem 1.2rem', borderRadius: 6, cursor: 'pointer', fontSize: '0.85rem', fontWeight: 500, border: 'none', background: tab === tabItem.id ? '#1a1a2e' : '#eee', color: tab === tabItem.id ? '#fff' : '#333' }}>
            {tabItem.label}
          </button>
        ))}
      </div>

      {tab === 'general' && (
        <div style={styles.section}>
          <div style={styles.sectionTitle}>🌐 {t('settings.lang_label')}</div>
          <select style={styles.select} value={i18n.language} onChange={handleLangChange}>
            <option value="zh">{t('settings.lang_zh')}</option>
            <option value="en">{t('settings.lang_en')}</option>
          </select>
        </div>
      )}

      {tab === 'billing' && (
        <>
          {usage && (
            <div style={styles.section}>
              <div style={styles.sectionTitle}>📊 本月用量</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: '1rem' }}>
                {[
                  { label: 'AI 分析', current: usage.current.analyses_run, max: usage.limits.max_analyses_per_month },
                  { label: '仓库扫描', current: usage.current.repo_scans, max: usage.limits.max_repo_scans },
                  { label: 'API Spec', current: usage.current.api_specs_imported, max: usage.limits.max_api_specs },
                  { label: 'Figma 分析', current: usage.current.figma_analyses, max: usage.limits.max_figma_analyses },
                  { label: '活跃成员', current: usage.current.members_active, max: usage.limits.max_members },
                ].map(item => (
                  <div key={item.label} style={{ background: '#f8faff', borderRadius: 8, padding: '0.75rem', textAlign: 'center' as const }}>
                    <div style={{ fontSize: '1.3rem', fontWeight: 700, color: item.current >= item.max ? '#e74c3c' : '#1a1a2e' }}>
                      {item.current}/{item.max}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#888' }}>{item.label}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div style={styles.section}>
            <div style={styles.sectionTitle}>💳 套餐选择</div>
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              {tiers.map(tier => {
                const isActive = billing?.tier === tier.id
                return (
                  <div key={tier.id} style={styles.tierCard(isActive)}>
                    <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#1a1a2e', marginBottom: '0.3rem' }}>
                      {tier.name}
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#4fc3f7', marginBottom: '1rem' }}>
                      ¥{tier.price_monthly}<span style={{ fontSize: '0.8rem', color: '#888' }}>/月</span>
                    </div>
                    <ul style={{ fontSize: '0.8rem', color: '#555', paddingLeft: '1.2rem', lineHeight: 1.8 }}>
                      <li>最多 {tier.max_members} 个成员</li>
                      <li>{tier.max_projects} 个项目</li>
                      <li>{tier.max_analyses_per_month} 次分析/月</li>
                      <li>{tier.report_sharing ? '✅ 报告共享' : '❌ 报告共享'}</li>
                      <li>导出: {tier.export_formats.join(', ')}</li>
                      <li>支持: {tier.support}</li>
                    </ul>
                    {isActive ? (
                      <div style={{ textAlign: 'center', padding: '0.4rem', background: '#e8f4fd', borderRadius: 6, fontSize: '0.85rem', color: '#4fc3f7' }}>当前套餐</div>
                    ) : tier.id !== 'free' ? (
                      <button style={{ ...styles.btn, ...styles.btnPrimary, width: '100%', marginTop: '0.5rem' }} onClick={() => handleUpgrade(tier.id)}>
                        升级到 {tier.name}
                      </button>
                    ) : null}
                  </div>
                )
              })}
            </div>
          </div>
        </>
      )}

      {tab === 'team' && (
        <div style={styles.section}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div style={styles.sectionTitle}>👥 团队成员 ({members.length})</div>
            <button style={{ ...styles.btn, ...styles.btnPrimary }} onClick={() => setShowInvite(true)}>+ 邀请成员</button>
          </div>
          {members.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#888', fontSize: '0.9rem' }}>暂无团队成员</div>
          ) : (
            <div>
              {members.map(m => (
                <div key={m.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem 0', borderBottom: '1px solid #f0f0f0' }}>
                  <div>
                    <div style={{ fontWeight: 500, color: '#1a1a2e' }}>{m.name}</div>
                    <div style={{ fontSize: '0.82rem', color: '#888' }}>{m.email}</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={styles.badge(m.role)}>{m.role}</span>
                    <button style={{ ...styles.btn, ...styles.btnDanger, ...styles.btnSmall }} onClick={() => handleRemoveMember(m.id)}>移除</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'sharing' && (
        <div style={styles.section}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div style={styles.sectionTitle}>🔗 已分享的报告</div>
            <button style={{ ...styles.btn, ...styles.btnPrimary }} onClick={() => setShowShare(true)}>+ 分享报告</button>
          </div>
          {sharedReports.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#888', fontSize: '0.9rem' }}>暂无分享的报告</div>
          ) : (
            <div>
              {sharedReports.map(sr => (
                <div key={sr.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem 0', borderBottom: '1px solid #f0f0f0' }}>
                  <div>
                    <div style={{ fontWeight: 500, color: '#1a1a2e' }}>{sr.title}</div>
                    <div style={{ fontSize: '0.82rem', color: '#888' }}>
                      查看 {sr.view_count} 次 · {sr.is_password_protected ? '🔒 密码保护' : '🔓 公开'} · 到期 {new Date(sr.expires_at).toLocaleDateString('zh-CN')}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button style={{ ...styles.btn, ...styles.btnSmall, background: '#90a4ae' }}
                      onClick={() => { navigator.clipboard.writeText(`${window.location.origin}/shared/${sr.share_token}`); alert('链接已复制！') }}>
                      复制链接
                    </button>
                    <button style={{ ...styles.btn, ...styles.btnDanger, ...styles.btnSmall }} onClick={() => handleRevoke(sr.id)}>
                      {sr.is_active ? '撤销' : '已撤销'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Invite Modal */}
      {showInvite && (
        <div style={styles.modalOverlay} onClick={() => setShowInvite(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalTitle}>邀请成员</div>
            <label style={styles.label}>邮箱</label>
            <input style={{ ...styles.input, width: '100%', marginBottom: '0.75rem' }} type="email" value={inviteForm.email} onChange={e => setInviteForm({ ...inviteForm, email: e.target.value })} placeholder="colleague@company.com" />
            <label style={styles.label}>名称</label>
            <input style={{ ...styles.input, width: '100%', marginBottom: '0.75rem' }} type="text" value={inviteForm.name} onChange={e => setInviteForm({ ...inviteForm, name: e.target.value })} placeholder="姓名" />
            <label style={styles.label}>角色</label>
            <select style={{ ...styles.select, width: '100%', marginBottom: '1rem' }} value={inviteForm.role} onChange={e => setInviteForm({ ...inviteForm, role: e.target.value })}>
              <option value="member">成员</option>
              <option value="admin">管理员</option>
              <option value="viewer">观察者</option>
            </select>
            <div style={styles.modalActions}>
              <button style={{ ...styles.btn, background: '#ccc', color: '#333' }} onClick={() => setShowInvite(false)}>取消</button>
              <button style={{ ...styles.btn, ...styles.btnPrimary }} onClick={handleInvite} disabled={!inviteForm.email || !inviteForm.name}>邀请</button>
            </div>
          </div>
        </div>
      )}

      {/* Share Modal */}
      {showShare && (
        <div style={styles.modalOverlay} onClick={() => setShowShare(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalTitle}>分享报告</div>
            <label style={styles.label}>Sprint ID</label>
            <input style={{ ...styles.input, width: '100%', marginBottom: '0.75rem' }} type="number" value={shareForm.sprint_id} onChange={e => setShareForm({ ...shareForm, sprint_id: e.target.value })} placeholder="sprint_id" />
            <label style={styles.label}>标题</label>
            <input style={{ ...styles.input, width: '100%', marginBottom: '0.75rem' }} type="text" value={shareForm.title} onChange={e => setShareForm({ ...shareForm, title: e.target.value })} placeholder="Sprint 分析报告" />
            <label style={styles.label}>访问密码 (可选)</label>
            <input style={{ ...styles.input, width: '100%', marginBottom: '1rem' }} type="text" value={shareForm.password} onChange={e => setShareForm({ ...shareForm, password: e.target.value })} placeholder="留空公开" />
            <div style={styles.modalActions}>
              <button style={{ ...styles.btn, background: '#ccc', color: '#333' }} onClick={() => setShowShare(false)}>取消</button>
              <button style={{ ...styles.btn, ...styles.btnPrimary }} onClick={handleShare} disabled={!shareForm.sprint_id || !shareForm.title}>分享</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
