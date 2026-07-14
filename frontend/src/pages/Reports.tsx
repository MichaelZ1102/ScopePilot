import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, Eye, FileClock, FileText, LoaderCircle, Search, ShieldAlert, X } from 'lucide-react'

import {
  listProjects,
  listReportSnapshots,
  listSprints,
  type Project,
  type ReportSnapshot,
  type Sprint,
} from '../lib/api'
import { getApiErrorMessage } from '../lib/client'
import './ReportWorkspace.css'

type SprintEntry = Sprint & { project: Project }

export default function Reports() {
  const navigate = useNavigate()
  const [entries, setEntries] = useState<SprintEntry[]>([])
  const [snapshots, setSnapshots] = useState<ReportSnapshot[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [selectedSnapshot, setSelectedSnapshot] = useState<ReportSnapshot | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      setError('')
      try {
        const projects = await listProjects()
        const sprintGroups = await Promise.all(
          projects.map(async (project) => {
            const sprints = await listSprints(project.id)
            return sprints.map((sprint) => ({ ...sprint, project }))
          }),
        )
        const loadedSnapshots = await listReportSnapshots()
        setEntries(sprintGroups.flat())
        setSnapshots(loadedSnapshots)
      } catch (requestError: unknown) {
        setError(getApiErrorMessage(requestError, '报告中心加载失败。'))
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return entries
    return entries.filter((entry) => (
      entry.name.toLowerCase().includes(normalized)
      || entry.project.name.toLowerCase().includes(normalized)
    ))
  }, [entries, query])

  if (loading) {
    return (
      <div className="loading-state">
        <span className="loading-state-icon"><LoaderCircle className="spin" size={22} /></span>
        <p>正在加载报告中心...</p>
      </div>
    )
  }

  return (
    <div className="workspace-page report-workspace-page">
      <header className="workspace-header">
        <div>
          <span className="workspace-kicker">Delivery Reports</span>
          <h1>报告中心</h1>
          <p>预览 Sprint 分析、核对 Ticket 审核状态，并发布固定版本报告。</p>
        </div>
        <label className="report-search">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索项目或 Sprint"
          />
        </label>
      </header>

      {error && <div className="inline-error">{error}</div>}

      <div className="metric-strip report-metrics">
        <div className="metric-item"><span>Sprint</span><strong>{entries.length}</strong></div>
        <div className="metric-item"><span>已完成分析</span><strong>{entries.filter((item) => item.analysis_status === 'done').length}</strong></div>
        <div className="metric-item"><span>已发布版本</span><strong>{snapshots.filter((item) => item.status === 'published').length}</strong></div>
      </div>

      {filtered.length === 0 && error ? null : filtered.length === 0 ? (
        <section className="empty-state">
          <span className="empty-state-icon"><FileText size={23} /></span>
          <h2>暂无可用报告</h2>
          <p>先导入 Sprint 并完成 Ticket 分析，报告会在这里集中展示。</p>
        </section>
      ) : (
        <section className="report-grid">
          {filtered.map((entry) => {
            const versions = snapshots.filter((snapshot) => snapshot.sprint_id === entry.id)
            const published = versions.find((snapshot) => snapshot.status === 'published')
            return (
              <article className="report-card" key={entry.id}>
                <div className="report-card-heading">
                  <span className="resource-icon"><FileText size={18} /></span>
                  <div>
                    <span>{entry.project.name}</span>
                    <h2>{entry.name}</h2>
                  </div>
                  <span className={`status-badge ${published ? 'is-success' : 'is-info'}`}>
                    {published ? `已发布 v${published.version}` : '草稿'}
                  </span>
                </div>
                <div className="report-card-stats">
                  <span><strong>{entry.total_tickets}</strong> Ticket</span>
                  <span><strong>{versions.length}</strong> 历史版本</span>
                </div>
                <div className="report-card-state">
                  {entry.analysis_status === 'done' ? <CheckCircle2 size={16} /> : <ShieldAlert size={16} />}
                  <span>{entry.analysis_status === 'done' ? '分析已完成，可以进入审核' : `分析状态：${entry.analysis_status}`}</span>
                </div>
                {versions.length > 0 && (
                  <div className="report-version-list">
                    <strong><FileClock size={15} /> 历史快照</strong>
                    {versions.map((snapshot) => (
                      <button type="button" key={snapshot.id} onClick={() => setSelectedSnapshot(snapshot)}>
                        <span>v{snapshot.version} · {snapshot.status === 'published' ? '已发布' : snapshot.status === 'archived' ? '已归档' : snapshot.status}</span>
                        <small>{formatDate(snapshot.published_at || snapshot.created_at)}</small>
                        <Eye size={14} />
                      </button>
                    ))}
                  </div>
                )}
                <button className="button button-primary" type="button" onClick={() => navigate(`/sprints/${entry.id}/report`)}>
                  查看当前草稿
                </button>
              </article>
            )
          })}
        </section>
      )}

      {selectedSnapshot && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setSelectedSnapshot(null)}>
          <div className="workspace-modal is-wide report-snapshot-modal" role="dialog" aria-modal="true" aria-labelledby="snapshot-title" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2 id="snapshot-title">{selectedSnapshot.title} · v{selectedSnapshot.version}</h2>
                <p>{selectedSnapshot.status === 'published' ? '已发布快照' : '已归档快照'} · {formatDate(selectedSnapshot.published_at || selectedSnapshot.created_at)}</p>
              </div>
              <button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={() => setSelectedSnapshot(null)}><X size={18} /></button>
            </div>
            <div className="modal-body">
              <p className="report-snapshot-notice">这是发布时保存的不可变内容，不会随当前 Sprint 草稿变化。</p>
              {selectedSnapshot.content ? (
                <pre className="report-snapshot-content">{selectedSnapshot.content}</pre>
              ) : (
                <div className="inline-error">此历史记录没有可读取的快照内容。</div>
              )}
              <div className="modal-actions"><button className="button" type="button" onClick={() => setSelectedSnapshot(null)}>关闭</button></div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function formatDate(value?: string | null) {
  if (!value) return '时间未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}
