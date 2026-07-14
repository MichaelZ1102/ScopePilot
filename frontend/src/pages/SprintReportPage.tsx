import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, CheckCircle2, Download, FileText, Link2, LoaderCircle, Send, ShieldCheck } from 'lucide-react'

import {
  archiveReportSnapshot,
  getSprintReport,
  listReportSnapshots,
  publishSprintReport,
  publishSprintToConfluence,
  shareReport,
  sprintReportDownloadUrl,
  type ReportSnapshot,
  type SprintReport,
} from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { getApiErrorMessage } from '../lib/client'
import './ReportWorkspace.css'

export default function SprintReportPage() {
  const { user } = useAuth()
  const sprintId = Number(useParams<{ sprintId: string }>().sprintId)
  const navigate = useNavigate()
  const [report, setReport] = useState<SprintReport | null>(null)
  const [published, setPublished] = useState<ReportSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [showConfluence, setShowConfluence] = useState(false)
  const [confluence, setConfluence] = useState({ space_key: '', title: '', parent_page_id: '' })

  useEffect(() => {
    Promise.all([getSprintReport(sprintId), listReportSnapshots()])
      .then(([loadedReport, snapshots]) => {
        setReport(loadedReport)
        setPublished(
          snapshots.find((snapshot) => (
            snapshot.sprint_id === sprintId && snapshot.status === 'published'
          )) || null,
        )
      })
      .catch((requestError) => setError(getApiErrorMessage(requestError, 'Sprint 报告加载失败。')))
      .finally(() => setLoading(false))
  }, [sprintId])

  async function handlePublish() {
    setWorking(true)
    setError('')
    setMessage('')
    try {
      const snapshot = await publishSprintReport(sprintId)
      setPublished(snapshot)
      setMessage(`报告 v${snapshot.version} 已发布。`)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '发布失败，请先完成所有 Ticket 审核。'))
    } finally {
      setWorking(false)
    }
  }

  async function handleShare() {
    setWorking(true)
    setError('')
    try {
      const shared = await shareReport(sprintId, report?.title || 'Sprint 分析报告')
      const url = `${window.location.origin}/shared/${shared.share_token}`
      await navigator.clipboard.writeText(url)
      setMessage('分享链接已创建并复制。')
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '分享失败，请先发布报告并检查套餐权限。'))
    } finally {
      setWorking(false)
    }
  }

  async function handleConfluence() {
    setWorking(true)
    setError('')
    try {
      const result = await publishSprintToConfluence(sprintId, {
        ...confluence,
        title: confluence.title || report?.title || 'ScopePilot Report',
      })
      setMessage(`Confluence 页面已创建：${result.title || result.id}`)
      setShowConfluence(false)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Confluence 发布失败。'))
    } finally {
      setWorking(false)
    }
  }

  async function handleArchive() {
    if (!published) return
    setWorking(true)
    setError('')
    try {
      await archiveReportSnapshot(published.id)
      setPublished(null)
      setMessage('当前已发布版本已归档。')
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '归档失败。'))
    } finally {
      setWorking(false)
    }
  }

  if (loading) return <div className="loading-state"><span className="loading-state-icon"><LoaderCircle className="spin" size={22} /></span><p>正在汇总 Sprint 报告...</p></div>
  if (!report) return <div className="workspace-fatal" role="alert"><AlertTriangle size={26} /><strong>{error || '报告不存在。'}</strong></div>

  const approved = report.review_counts.approved || 0
  const total = report.tickets.length
  const isAdmin = user?.role === 'admin'
  const canShare = user?.role === 'admin' || user?.role === 'member'
  return (
    <div className="workspace-page report-detail-page">
      <header className="report-detail-header">
        <div>
          <Link className="report-back-link" to="/reports"><ArrowLeft size={16} /> 返回报告中心</Link>
          <span className="workspace-kicker">{report.project.name}</span>
          <h1>{report.title}</h1>
          <p>生成时间：{new Date(report.generated_at).toLocaleString('zh-CN')}</p>
        </div>
        <div className="report-header-actions">
          <a className="button button-secondary" href={sprintReportDownloadUrl(sprintId)}><Download size={16} /> 下载 Markdown</a>
          <a className="button button-secondary" href={sprintReportDownloadUrl(sprintId, 'pdf')}><Download size={16} /> PDF</a>
          <a className="button button-secondary" href={sprintReportDownloadUrl(sprintId, 'csv')}><Download size={16} /> CSV</a>
          {canShare && <button className="button" type="button" onClick={() => setShowConfluence(!showConfluence)}>Confluence</button>}
          {isAdmin && <button className="button button-primary" type="button" onClick={handlePublish} disabled={working}><ShieldCheck size={16} /> {working ? '处理中' : '发布报告'}</button>}
          {isAdmin && published && <button className="button" type="button" onClick={handleArchive} disabled={working}>归档 v{published.version}</button>}
          {canShare && <button className="button button-success" type="button" onClick={handleShare} disabled={working || !published}><Link2 size={16} /> 分享</button>}
        </div>
      </header>

      {error && <div className="inline-error">{error}</div>}
      {message && <div className="workspace-toast"><CheckCircle2 size={16} /><span>{message}</span></div>}
      {showConfluence && (
        <section className="workspace-panel analysis-editor">
          <div className="panel-header"><div><h2>发布到 Confluence</h2><p>使用当前项目的 Atlassian 账号和 Token。</p></div></div>
          <div className="analysis-editor-body">
            <label><span>Space Key</span><input value={confluence.space_key} onChange={(event) => setConfluence({ ...confluence, space_key: event.target.value })} /></label>
            <label><span>页面标题</span><input value={confluence.title} onChange={(event) => setConfluence({ ...confluence, title: event.target.value })} placeholder={report.title} /></label>
            <label><span>父页面 ID（可选）</span><input value={confluence.parent_page_id} onChange={(event) => setConfluence({ ...confluence, parent_page_id: event.target.value })} /></label>
          </div>
          <div className="modal-actions"><button className="button" type="button" onClick={() => setShowConfluence(false)}>取消</button><button className="button button-primary" type="button" onClick={handleConfluence} disabled={working || !confluence.space_key}>发布</button></div>
        </section>
      )}

      <div className="metric-strip report-metrics">
        <div className="metric-item"><span>报告 Ticket</span><strong>{total}</strong></div>
        <div className="metric-item"><span>已核对</span><strong>{approved}</strong></div>
        <div className="metric-item"><span>审核中</span><strong>{report.review_counts.in_review || 0}</strong></div>
        <div className="metric-item"><span>过期分析</span><strong>{report.stale_ticket_count}</strong></div>
      </div>

      {(approved !== total || report.stale_ticket_count > 0) && (
        <div className="report-warning">
          <AlertTriangle size={18} />
          <div><strong>报告尚不满足发布条件</strong><p>所有已加入报告的 Ticket 都必须核对完成，且分析不能过期。</p></div>
        </div>
      )}

      <section className="workspace-panel report-section">
        <div className="panel-header"><div className="report-section-title"><span className="resource-icon"><FileText size={18} /></span><h2>Sprint 目标与风险</h2></div></div>
        <div className="report-section-body">
          <p className="report-copy">{report.summary.summary || '尚未生成 Sprint 汇总。'}</p>
          {report.summary.risk_map?.length > 0 && (
            <div className="risk-list">
              {report.summary.risk_map.map((risk, index) => (
                <div key={`${String(risk.ticket)}-${index}`}><span className={`tag is-${String(risk.level)}`}>{String(risk.level)}</span><strong>{String(risk.ticket)}</strong><p>{String(risk.description)}</p></div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="workspace-panel report-section">
        <div className="panel-header"><div><h2>执行顺序与代码冲突</h2><p>结合 Sprint 建议顺序和各 Ticket 的代码影响结果。</p></div></div>
        <div className="report-section-body dependency-view">
          <div>
            <h3>建议执行顺序</h3>
            {report.dependency_graph.length ? report.dependency_graph.map((edge, index) => (
              <div className="dependency-edge" key={`${edge.from}-${edge.to}-${index}`}><strong>{edge.from}</strong><span>→</span><strong>{edge.to}</strong></div>
            )) : <p className="muted-copy">暂无可用执行顺序。</p>}
          </div>
          <div>
            <h3>共享文件冲突</h3>
            {report.code_conflicts.length ? report.code_conflicts.map((conflict) => (
              <div className="conflict-row" key={conflict.path}><code>{conflict.path}</code><span>{conflict.tickets.join('、')}</span></div>
            )) : <p className="muted-copy">当前没有识别到多个 Ticket 修改同一文件。</p>}
          </div>
        </div>
      </section>

      <section className="workspace-panel report-section">
        <div className="panel-header"><div><h2>Ticket 报告</h2><p>选择 Ticket 查看需求、代码、API、Figma 和审核详情。</p></div></div>
        <div className="sprint-report-ticket-list">
          {report.tickets.map((item) => (
            <button className="sprint-report-ticket" type="button" key={item.ticket.id} onClick={() => navigate(`/tickets/${item.ticket.id}/report`)}>
              <span className="resource-icon"><FileText size={16} /></span>
              <div><span>{item.ticket.key}</span><strong>{item.ticket.summary}</strong></div>
              <span className={`review-badge is-${item.review.status}`}>{reviewLabel(item.review.status)}</span>
              {item.is_stale && <span className="status-badge is-warning">已过期</span>}
              <Send size={16} />
            </button>
          ))}
        </div>
      </section>
    </div>
  )
}

function reviewLabel(status: string) {
  return ({ unreviewed: '未审核', in_review: '审核中', approved: '已核对', rejected: '已驳回' } as Record<string, string>)[status] || status
}
