import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Copy,
  CreditCard,
  Languages,
  ScrollText,
  Webhook,
  Link2,
  Plus,
  Settings2,
  Trash2,
  Users,
  X,
} from 'lucide-react'

import {
  addMember,
  getBilling,
  getUsage,
  listMembers,
  listAuditLogs,
  createWebhook,
  deleteWebhook,
  listWebhooks,
  listSharedReports,
  listTiers,
  removeMember,
  revokeShare,
  shareReport,
  upgradeTier,
  updateMemberRole,
  type BillingTier,
  type AuditLog,
  type SharedReport,
  type TeamMember,
  type UsageData,
  type WebhookSubscription,
} from '../lib/api'
import { getApiErrorMessage } from '../lib/client'
import { useAuth } from '../lib/AuthContext'

type SettingsTab = 'general' | 'billing' | 'team' | 'sharing' | 'audit' | 'webhooks'

const tabItems = [
  { id: 'general' as const, label: '通用', icon: Settings2 },
  { id: 'billing' as const, label: '计费与用量', icon: CreditCard },
  { id: 'team' as const, label: '团队', icon: Users },
  { id: 'sharing' as const, label: '报告共享', icon: Link2 },
  { id: 'audit' as const, label: '审计日志', icon: ScrollText },
  { id: 'webhooks' as const, label: 'Webhook', icon: Webhook },
]

export default function Settings() {
  const { t, i18n } = useTranslation()
  const { user } = useAuth()
  const [tab, setTab] = useState<SettingsTab>('general')
  const [billing, setBilling] = useState<{ tier?: string } | null>(null)
  const [tiers, setTiers] = useState<BillingTier[]>([])
  const [usage, setUsage] = useState<UsageData | null>(null)
  const [members, setMembers] = useState<TeamMember[]>([])
  const [showInvite, setShowInvite] = useState(false)
  const [inviteForm, setInviteForm] = useState({ email: '', name: '', role: 'member' })
  const [sharedReports, setSharedReports] = useState<SharedReport[]>([])
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([])
  const [webhooks, setWebhooks] = useState<WebhookSubscription[]>([])
  const [webhookForm, setWebhookForm] = useState({ name: '', provider: 'generic', url: '', events: '*', secret: '' })
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
      } else if (tab === 'audit') {
        setAuditLogs(await listAuditLogs())
      } else if (tab === 'webhooks') {
        setWebhooks(await listWebhooks())
      }
    } catch {
      // Keep the current tab usable when an optional settings endpoint is unavailable.
    }
  }

  async function handleUpgrade(tier: string) {
    try {
      await upgradeTier(tier)
      await loadData()
      alert('升级成功！')
    } catch (error: unknown) {
      alert(getApiErrorMessage(error, 'Upgrade failed'))
    }
  }

  async function handleInvite() {
    try {
      const member = await addMember(inviteForm.email, inviteForm.name, inviteForm.role)
      if (member.invite_token) {
        const inviteUrl = `${window.location.origin}/login?email=${encodeURIComponent(member.email)}&token=${encodeURIComponent(member.invite_token)}`
        await navigator.clipboard.writeText(inviteUrl)
        alert('邀请链接已复制，请发送给团队成员。')
      }
      setShowInvite(false)
      setInviteForm({ email: '', name: '', role: 'member' })
      await loadData()
    } catch (error: unknown) {
      alert(getApiErrorMessage(error, 'Invite failed'))
    }
  }

  async function handleRemoveMember(id: number) {
    if (!confirm('确定移除此成员？')) return
    try {
      await removeMember(id)
      await loadData()
    } catch {
      alert('操作失败')
    }
  }

  async function handleMemberRole(id: number, role: string) {
    try {
      await updateMemberRole(id, role)
      await loadData()
    } catch (error: unknown) {
      alert(getApiErrorMessage(error, '角色更新失败'))
    }
  }

  async function handleShare() {
    try {
      await shareReport(Number(shareForm.sprint_id), shareForm.title, shareForm.password)
      setShowShare(false)
      setShareForm({ sprint_id: '', title: '', password: '' })
      await loadData()
    } catch (error: unknown) {
      alert(getApiErrorMessage(error, 'Share failed'))
    }
  }

  async function handleRevoke(id: number) {
    if (!confirm('确定撤销此分享链接？')) return
    try {
      await revokeShare(id)
      await loadData()
    } catch {
      alert('操作失败')
    }
  }

  async function handleCreateWebhook() {
    try {
      await createWebhook({
        name: webhookForm.name,
        provider: webhookForm.provider,
        url: webhookForm.url,
        events: webhookForm.events.split(',').map((item) => item.trim()).filter(Boolean),
        secret: webhookForm.secret,
      })
      setWebhookForm({ name: '', provider: 'generic', url: '', events: '*', secret: '' })
      await loadData()
    } catch (error: unknown) {
      alert(getApiErrorMessage(error, 'Webhook 创建失败'))
    }
  }

  async function handleDeleteWebhook(id: number) {
    await deleteWebhook(id)
    await loadData()
  }

  function handleLanguageChange(event: React.ChangeEvent<HTMLSelectElement>) {
    i18n.changeLanguage(event.target.value)
    localStorage.setItem('locale', event.target.value)
  }

  return (
    <div className="workspace-page">
      <header className="workspace-header">
        <div>
          <span className="workspace-kicker">Workspace Administration</span>
          <h1>设置</h1>
          <p>{t('settings.description')}</p>
        </div>
      </header>

      <div className="settings-layout">
        <nav className="settings-nav" aria-label="Settings sections">
          {tabItems.filter((item) => !['audit', 'webhooks'].includes(item.id) || user?.role === 'admin').map(({ id, label, icon: Icon }) => (
            <button className={tab === id ? 'is-active' : ''} type="button" key={id} onClick={() => setTab(id)}>
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>

        <main className="workspace-panel">
          {tab === 'general' && (
            <section className="settings-section">
              <div className="settings-section-header">
                <div>
                  <h2>{t('settings.lang_label')}</h2>
                  <p>设置工作台界面和系统提示使用的语言。</p>
                </div>
                <span className="resource-icon"><Languages size={18} /></span>
              </div>
              <label className="form-field" style={{ maxWidth: 320 }}>
                <span>界面语言</span>
                <select value={i18n.language} onChange={handleLanguageChange}>
                  <option value="zh">{t('settings.lang_zh')}</option>
                  <option value="en">{t('settings.lang_en')}</option>
                </select>
              </label>
            </section>
          )}

          {tab === 'billing' && (
            <>
              {usage && (
                <section className="settings-section">
                  <div className="settings-section-header">
                    <div>
                      <h2>本月用量</h2>
                      <p>查看当前套餐中各项资源的使用情况。</p>
                    </div>
                  </div>
                  <div className="usage-grid">
                    {usageItems(usage).map((item) => (
                      <div className="usage-item" key={item.label}>
                        <strong>{item.current}/{item.max}</strong>
                        <span>{item.label}</span>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              <section className="settings-section">
                <div className="settings-section-header">
                  <div>
                    <h2>套餐选择</h2>
                    <p>按团队规模和每月分析量选择套餐。</p>
                  </div>
                </div>
                <div className="tier-grid">
                  {tiers.map((tier) => {
                    const isActive = billing?.tier === tier.id
                    return (
                      <article className={`tier-card${isActive ? ' is-active' : ''}`} key={tier.id}>
                        <div className="detail-card-head">
                          <h3>{tier.name}</h3>
                          {isActive && <span className="status-badge is-info">当前套餐</span>}
                        </div>
                        <div className="tier-price">¥{tier.price_monthly}<span>/月</span></div>
                        <ul>
                          <li>最多 {tier.max_members} 个成员</li>
                          <li>{tier.max_projects} 个项目</li>
                          <li>{tier.max_analyses_per_month} 次分析/月</li>
                          <li>{tier.report_sharing ? '支持报告共享' : '不支持报告共享'}</li>
                          <li>导出：{tier.export_formats.join(', ')}</li>
                          <li>支持：{tier.support}</li>
                        </ul>
                        {!isActive && tier.id !== 'free' && (
                          <button className="button button-primary" type="button" onClick={() => handleUpgrade(tier.id)} disabled={user?.role !== 'admin'}>
                            升级到 {tier.name}
                          </button>
                        )}
                      </article>
                    )
                  })}
                </div>
              </section>
            </>
          )}

          {tab === 'team' && (
            <section className="settings-section">
              <div className="settings-section-header">
                <div>
                  <h2>团队成员</h2>
                  <p>管理可访问 ScopePilot 工作区的成员与角色。</p>
                </div>
                {user?.role === 'admin' && <button className="button button-primary button-small" type="button" onClick={() => setShowInvite(true)}>
                  <Plus size={14} /> 邀请成员
                </button>}
              </div>
              {members.length === 0 ? (
                <div className="empty-state">
                  <span className="empty-state-icon"><Users size={22} /></span>
                  <h2>暂无团队成员</h2>
                  <p>邀请成员后，可按管理员、成员或观察者分配访问权限。</p>
                </div>
              ) : (
                <div className="data-list">
                  {members.map((member) => (
                    <div className="data-row" key={member.id}>
                      <div>
                        <h3>{member.name}</h3>
                        <p>{member.email}</p>
                        <small>{member.status === 'invited' ? '等待接受邀请' : '已加入'}</small>
                      </div>
                      <div className="row-actions">
                        {user?.role === 'admin' ? (
                          <select value={member.role} onChange={(event) => handleMemberRole(member.id, event.target.value)}>
                            <option value="admin">管理员</option>
                            <option value="member">成员</option>
                            <option value="viewer">观察者</option>
                          </select>
                        ) : <span className={`status-badge ${roleClass(member.role)}`}>{roleLabel(member.role)}</span>}
                        {user?.role === 'admin' && <button className="button button-danger button-small" type="button" onClick={() => handleRemoveMember(member.id)}>
                          <Trash2 size={13} /> 移除
                        </button>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {tab === 'sharing' && (
            <section className="settings-section">
              <div className="settings-section-header">
                <div>
                  <h2>已分享的报告</h2>
                  <p>管理公开或受密码保护的 Sprint 分析报告链接。</p>
                </div>
                <button className="button button-primary button-small" type="button" onClick={() => setShowShare(true)}>
                  <Plus size={14} /> 分享报告
                </button>
              </div>
              {sharedReports.length === 0 ? (
                <div className="empty-state">
                  <span className="empty-state-icon"><Link2 size={22} /></span>
                  <h2>暂无分享报告</h2>
                  <p>选择 Sprint 并创建分享链接后，可将分析结果提供给外部协作者查看。</p>
                </div>
              ) : (
                <div className="data-list">
                  {sharedReports.map((report) => (
                    <div className="data-row" key={report.id}>
                      <div>
                        <h3>{report.title}</h3>
                        <p>查看 {report.view_count} 次 · {report.is_password_protected ? '密码保护' : '公开访问'} · 到期 {new Date(report.expires_at).toLocaleDateString('zh-CN')}</p>
                      </div>
                      <div className="row-actions">
                        <button className="button button-small" type="button" onClick={() => copyReportLink(report.share_token)}>
                          <Copy size={13} /> 复制链接
                        </button>
                        <button className="button button-danger button-small" type="button" onClick={() => handleRevoke(report.id)} disabled={!report.is_active}>
                          {report.is_active ? '撤销' : '已撤销'}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {tab === 'audit' && (
            <section className="settings-section">
              <div className="settings-section-header">
                <div><h2>工作区审计日志</h2><p>记录配置、分析、审核、发布和分享操作。</p></div>
              </div>
              {auditLogs.length === 0 ? (
                <div className="empty-state"><span className="empty-state-icon"><ScrollText size={22} /></span><h2>暂无审计记录</h2><p>执行受审计操作后，记录会显示在这里。</p></div>
              ) : (
                <div className="data-list">
                  {auditLogs.map((item) => (
                    <div className="data-row" key={item.id}>
                      <div><h3>{item.action}</h3><p>{item.actor_name || `User #${item.actor_id}`} · {item.resource_type}{item.resource_id ? ` #${item.resource_id}` : ''}</p></div>
                      <div><span className="status-badge is-info">{new Date(item.created_at).toLocaleString('zh-CN')}</span></div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {tab === 'webhooks' && (
            <section className="settings-section">
              <div className="settings-section-header"><div><h2>事件 Webhook</h2><p>将分析、审核、同步和报告事件发送到通用地址、Slack 或 Teams。</p></div></div>
              <div className="form-grid" style={{ paddingBottom: 18 }}>
                <label className="form-field"><span>名称</span><input value={webhookForm.name} onChange={(event) => setWebhookForm({ ...webhookForm, name: event.target.value })} placeholder="Delivery notifications" /></label>
                <label className="form-field"><span>提供商</span><select value={webhookForm.provider} onChange={(event) => setWebhookForm({ ...webhookForm, provider: event.target.value })}><option value="generic">Generic</option><option value="slack">Slack</option><option value="teams">Teams</option></select></label>
                <label className="form-field is-wide"><span>URL</span><input type="url" value={webhookForm.url} onChange={(event) => setWebhookForm({ ...webhookForm, url: event.target.value })} placeholder="https://..." /></label>
                <label className="form-field"><span>事件</span><input value={webhookForm.events} onChange={(event) => setWebhookForm({ ...webhookForm, events: event.target.value })} placeholder="* 或逗号分隔" /></label>
                <label className="form-field"><span>签名 Secret</span><input type="password" value={webhookForm.secret} onChange={(event) => setWebhookForm({ ...webhookForm, secret: event.target.value })} /></label>
              </div>
              <button className="button button-primary" type="button" onClick={handleCreateWebhook} disabled={!webhookForm.name || !webhookForm.url}>创建 Webhook</button>
              <div className="data-list" style={{ marginTop: 18 }}>
                {webhooks.map((item) => (
                  <div className="data-row" key={item.id}>
                    <div><h3>{item.name}</h3><p>{item.provider} · {item.events.join(', ')}</p></div>
                    <button className="button button-danger button-small" type="button" onClick={() => handleDeleteWebhook(item.id)}><Trash2 size={13} /> 删除</button>
                  </div>
                ))}
              </div>
            </section>
          )}
        </main>
      </div>

      {showInvite && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setShowInvite(false)}>
          <div className="workspace-modal" role="dialog" aria-modal="true" aria-labelledby="invite-title" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div><h2 id="invite-title">邀请成员</h2><p>新增一个工作区成员并分配角色。</p></div>
              <button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={() => setShowInvite(false)}><X size={18} /></button>
            </div>
            <div className="modal-body">
              <div className="form-grid">
                <label className="form-field is-wide"><span>邮箱</span><input type="email" value={inviteForm.email} onChange={(event) => setInviteForm({ ...inviteForm, email: event.target.value })} placeholder="colleague@company.com" /></label>
                <label className="form-field"><span>名称</span><input type="text" value={inviteForm.name} onChange={(event) => setInviteForm({ ...inviteForm, name: event.target.value })} placeholder="姓名" /></label>
                <label className="form-field"><span>角色</span><select value={inviteForm.role} onChange={(event) => setInviteForm({ ...inviteForm, role: event.target.value })}><option value="member">成员</option><option value="admin">管理员</option><option value="viewer">观察者</option></select></label>
              </div>
              <div className="modal-actions">
                <button className="button" type="button" onClick={() => setShowInvite(false)}>取消</button>
                <button className="button button-primary" type="button" onClick={handleInvite} disabled={!inviteForm.email || !inviteForm.name}>邀请</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showShare && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setShowShare(false)}>
          <div className="workspace-modal" role="dialog" aria-modal="true" aria-labelledby="share-title" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div><h2 id="share-title">分享报告</h2><p>为指定 Sprint 创建受控的外部访问链接。</p></div>
              <button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={() => setShowShare(false)}><X size={18} /></button>
            </div>
            <div className="modal-body">
              <div className="form-grid">
                <label className="form-field"><span>Sprint ID</span><input type="number" value={shareForm.sprint_id} onChange={(event) => setShareForm({ ...shareForm, sprint_id: event.target.value })} placeholder="Sprint ID" /></label>
                <label className="form-field"><span>访问密码</span><input type="text" value={shareForm.password} onChange={(event) => setShareForm({ ...shareForm, password: event.target.value })} placeholder="可选" /></label>
                <label className="form-field is-wide"><span>报告标题</span><input type="text" value={shareForm.title} onChange={(event) => setShareForm({ ...shareForm, title: event.target.value })} placeholder="Sprint 分析报告" /></label>
              </div>
              <div className="modal-actions">
                <button className="button" type="button" onClick={() => setShowShare(false)}>取消</button>
                <button className="button button-primary" type="button" onClick={handleShare} disabled={!shareForm.sprint_id || !shareForm.title}>创建分享链接</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function usageItems(usage: UsageData) {
  return [
    { label: 'AI 分析', current: usage.current.analyses_run, max: usage.limits.max_analyses_per_month },
    { label: '仓库扫描', current: usage.current.repo_scans, max: usage.limits.max_repo_scans },
    { label: 'API Spec', current: usage.current.api_specs_imported, max: usage.limits.max_api_specs },
    { label: 'Figma 分析', current: usage.current.figma_analyses, max: usage.limits.max_figma_analyses },
    { label: '活跃成员', current: usage.current.members_active, max: usage.limits.max_members },
  ]
}

function roleLabel(role: string) {
  const labels: Record<string, string> = { admin: '管理员', member: '成员', viewer: '观察者' }
  return labels[role] || role
}

function roleClass(role: string) {
  if (role === 'admin') return 'is-danger'
  if (role === 'member') return 'is-info'
  return ''
}

async function copyReportLink(token: string) {
  await navigator.clipboard.writeText(`${window.location.origin}/shared/${token}`)
  alert('链接已复制！')
}
