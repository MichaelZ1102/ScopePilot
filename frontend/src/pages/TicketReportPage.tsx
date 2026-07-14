import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  Check,
  Clock3,
  Code2,
  Download,
  FileJson2,
  FileText,
  GitBranch,
  GitPullRequest,
  History,
  LoaderCircle,
  ListChecks,
  MessageSquare,
  PenTool,
  Pencil,
  Save,
  Send,
  TestTube2,
  UploadCloud,
  X,
} from 'lucide-react'

import {
  archiveTicketAnalysisRun,
  getTicketReport,
  addActionItem,
  addReportComment,
  addDeliveryLink,
  listTicketAnalysisRuns,
  reviseTicketAnalysis,
  ticketReportDownloadUrl,
  updateTicketReview,
  updateActionItem,
  updateReportComment,
  writebackJiraComment,
  writebackJiraLabels,
  writebackJiraTransition,
  type AnalysisRun,
  type TicketReport,
  type TicketReview,
} from '../lib/api'
import { getApiErrorMessage } from '../lib/client'
import { useAuth } from '../lib/AuthContext'
import './ReportWorkspace.css'

export default function TicketReportPage() {
  const { user } = useAuth()
  const ticketId = Number(useParams<{ ticketId: string }>().ticketId)
  const [report, setReport] = useState<TicketReport | null>(null)
  const [runs, setRuns] = useState<AnalysisRun[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [reviewComment, setReviewComment] = useState('')
  const [editMode, setEditMode] = useState(false)
  const [newComment, setNewComment] = useState('')
  const [newAction, setNewAction] = useState({ title: '', owner: '', due_at: '' })
  const [deliveryDraft, setDeliveryDraft] = useState({ url: '', pull_request: '', commit_sha: '', ci_status: 'unknown', release_version: '', actual_files: '' })
  const [jiraDraft, setJiraDraft] = useState({ comment: '', transition: '', labels: '' })
  const [editDraft, setEditDraft] = useState({ business_goal: '', implementation_plan: '', open_questions: '', assumptions: '' })
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    setError('')
    try {
      const loaded = await getTicketReport(ticketId)
      setReport(loaded)
      setReviewComment(loaded.review.comment || '')
      setEditDraft({
        business_goal: loaded.analysis.business_goal || '',
        implementation_plan: (loaded.analysis.implementation_plan || []).join('\n'),
        open_questions: (loaded.analysis.open_questions || []).join('\n'),
        assumptions: (loaded.analysis.assumptions || []).join('\n'),
      })
      setRuns(await listTicketAnalysisRuns(loaded.sprint.id, ticketId))
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Ticket 报告加载失败。'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (Number.isFinite(ticketId)) load()
  }, [ticketId])

  async function handleReview(status: TicketReview['status']) {
    if (!report) return
    setUpdating(true)
    setError('')
    try {
      const review = await updateTicketReview(
        report.sprint.id,
        ticketId,
        status,
        reviewComment,
      )
      setReport({ ...report, review })
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '审核状态更新失败。'))
    } finally {
      setUpdating(false)
    }
  }

  async function handleSaveRevision() {
    if (!report) return
    setUpdating(true)
    setError('')
    try {
      const splitLines = (value: string) => value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
      const result = await reviseTicketAnalysis(report.sprint.id, ticketId, {
        business_goal: editDraft.business_goal.trim(),
        implementation_plan: splitLines(editDraft.implementation_plan),
        open_questions: splitLines(editDraft.open_questions),
        assumptions: splitLines(editDraft.assumptions),
      })
      setReport({
        ...report,
        analysis: result.analysis,
        analysis_run: result.analysis_run,
        review: { ...report.review, status: 'unreviewed' },
      })
      setRuns([result.analysis_run, ...runs])
      setEditMode(false)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '分析修订保存失败。'))
    } finally {
      setUpdating(false)
    }
  }

  async function handleAddComment() {
    if (!report || !newComment.trim()) return
    setUpdating(true)
    try {
      const comment = await addReportComment(report.sprint.id, ticketId, newComment.trim())
      setReport({ ...report, collaboration: { ...report.collaboration, comments: [...report.collaboration.comments, comment] } })
      setNewComment('')
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '评论发送失败。'))
    } finally {
      setUpdating(false)
    }
  }

  async function handleCommentStatus(commentId: number, status: 'open' | 'resolved') {
    if (!report) return
    const comment = await updateReportComment(report.sprint.id, ticketId, commentId, status)
    setReport({ ...report, collaboration: { ...report.collaboration, comments: report.collaboration.comments.map((item) => item.id === commentId ? comment : item) } })
  }

  async function handleAddAction() {
    if (!report || !newAction.title.trim()) return
    setUpdating(true)
    try {
      const item = await addActionItem(report.sprint.id, ticketId, newAction.title.trim(), newAction.owner.trim(), newAction.due_at || undefined)
      setReport({ ...report, collaboration: { ...report.collaboration, action_items: [...report.collaboration.action_items, item] } })
      setNewAction({ title: '', owner: '', due_at: '' })
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '待办创建失败。'))
    } finally {
      setUpdating(false)
    }
  }

  async function handleActionStatus(actionItemId: number, status: 'open' | 'done') {
    if (!report) return
    const item = await updateActionItem(report.sprint.id, ticketId, actionItemId, { status })
    setReport({ ...report, collaboration: { ...report.collaboration, action_items: report.collaboration.action_items.map((current) => current.id === actionItemId ? item : current) } })
  }

  async function handleAddDelivery() {
    if (!report || !deliveryDraft.url.trim()) return
    setUpdating(true)
    try {
      await addDeliveryLink(report.sprint.id, ticketId, {
        provider: deliveryDraft.url.includes('gitlab') ? 'gitlab' : deliveryDraft.url.includes('bitbucket') ? 'bitbucket' : 'github',
        url: deliveryDraft.url.trim(),
        pull_request: deliveryDraft.pull_request.trim(),
        commit_sha: deliveryDraft.commit_sha.trim(),
        ci_status: deliveryDraft.ci_status,
        release_version: deliveryDraft.release_version.trim(),
        actual_files: deliveryDraft.actual_files.split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
      })
      setDeliveryDraft({ url: '', pull_request: '', commit_sha: '', ci_status: 'unknown', release_version: '', actual_files: '' })
      setReport(await getTicketReport(ticketId))
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '交付记录保存失败。'))
    } finally {
      setUpdating(false)
    }
  }

  async function handleJiraWriteback(type: 'comment' | 'transition' | 'labels') {
    if (!report) return
    setUpdating(true)
    setError('')
    try {
      if (type === 'comment') {
        await writebackJiraComment(report.sprint.id, ticketId, jiraDraft.comment)
        setJiraDraft({ ...jiraDraft, comment: '' })
      } else if (type === 'transition') {
        await writebackJiraTransition(report.sprint.id, ticketId, jiraDraft.transition)
        setJiraDraft({ ...jiraDraft, transition: '' })
      } else {
        const labels = jiraDraft.labels.split(',').map((item) => item.trim()).filter(Boolean)
        await writebackJiraLabels(report.sprint.id, ticketId, labels)
        setReport({ ...report, ticket: { ...report.ticket, labels } })
      }
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Jira 回写失败。'))
    } finally {
      setUpdating(false)
    }
  }

  async function handleSelectVersion(runId?: number) {
    setUpdating(true)
    setError('')
    try {
      setReport(await getTicketReport(ticketId, runId))
      setShowHistory(false)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '分析版本加载失败。'))
    } finally {
      setUpdating(false)
    }
  }

  async function handleArchiveRun(runId: number) {
    if (!report) return
    setUpdating(true)
    setError('')
    try {
      const archived = await archiveTicketAnalysisRun(report.sprint.id, ticketId, runId)
      setRuns(runs.map((run) => run.id === runId ? archived : run))
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '分析版本归档失败。'))
    } finally {
      setUpdating(false)
    }
  }

  if (loading) {
    return (
      <div className="loading-state">
        <span className="loading-state-icon"><LoaderCircle className="spin" size={22} /></span>
        <p>正在生成 Ticket 报告...</p>
      </div>
    )
  }
  if (!report) {
    return <div className="workspace-fatal" role="alert"><AlertTriangle size={26} /><strong>{error || '报告不存在。'}</strong></div>
  }

  const { ticket, analysis, artifacts, review } = report
  const canWrite = (user?.role === 'admin' || user?.role === 'member') && !report.is_historical
  const canApprove = user?.role === 'admin'
  return (
    <div className="workspace-page report-detail-page">
      <header className="report-detail-header">
        <div>
          <Link className="report-back-link" to={`/sprint/${report.sprint.id}`}>
            <ArrowLeft size={16} /> 返回 Sprint
          </Link>
          <div className="ticket-title-row">
            <span className="ticket-title-icon"><FileText size={18} /></span>
            <span>{ticket.key}</span>
            <ReviewBadge status={review.status} />
            {report.is_stale && <span className="status-badge is-warning">分析已过期</span>}
          </div>
          <h1>{ticket.summary}</h1>
          <p>{report.project.name} · {report.sprint.name}</p>
        </div>
        <div className="report-header-actions">
          {canWrite && <button className="button" type="button" onClick={() => setEditMode(!editMode)}>
            <Pencil size={16} /> 修订分析
          </button>}
          <button className="button" type="button" onClick={() => setShowHistory(!showHistory)}>
            <History size={16} /> 分析历史 ({runs.length})
          </button>
          <a className="button button-secondary" href={ticketReportDownloadUrl(ticketId, 'json')}>
            <FileJson2 size={16} /> JSON
          </a>
          <a className="button button-secondary" href={ticketReportDownloadUrl(ticketId, 'pdf')}>
            <Download size={16} /> PDF
          </a>
          <a className="button button-primary" href={ticketReportDownloadUrl(ticketId, 'md')}>
            <Download size={16} /> 下载 Markdown
          </a>
        </div>
      </header>

      {error && <div className="inline-error">{error}</div>}
      {report.is_stale && (
        <div className="report-warning">
          <AlertTriangle size={18} />
          <div><strong>这份分析需要更新</strong><p>{report.stale_reasons.join('；')}</p></div>
        </div>
      )}
      {report.is_historical && (
        <div className="report-warning">
          <History size={18} />
          <div><strong>正在查看历史分析 v{report.analysis_run?.version}</strong><p>历史版本为只读视图。</p></div>
          <button className="button" type="button" onClick={() => handleSelectVersion()}>返回当前版本</button>
        </div>
      )}

      {canWrite && editMode && (
        <section className="workspace-panel analysis-editor">
          <div className="panel-header"><div><h2>人工修订分析</h2><p>保存后会创建新版本，并重新进入审核流程。</p></div></div>
          <div className="analysis-editor-body">
            <label><span>用户目标</span><textarea rows={4} value={editDraft.business_goal} onChange={(event) => setEditDraft({ ...editDraft, business_goal: event.target.value })} /></label>
            <label><span>实现计划（每行一项）</span><textarea rows={6} value={editDraft.implementation_plan} onChange={(event) => setEditDraft({ ...editDraft, implementation_plan: event.target.value })} /></label>
            <label><span>待确认问题（每行一项）</span><textarea rows={4} value={editDraft.open_questions} onChange={(event) => setEditDraft({ ...editDraft, open_questions: event.target.value })} /></label>
            <label><span>分析假设（每行一项）</span><textarea rows={4} value={editDraft.assumptions} onChange={(event) => setEditDraft({ ...editDraft, assumptions: event.target.value })} /></label>
          </div>
          <div className="modal-actions">
            <button className="button" type="button" onClick={() => setEditMode(false)}>取消</button>
            <button className="button button-primary" type="button" onClick={handleSaveRevision} disabled={updating}><Save size={15} /> 保存新版本</button>
          </div>
        </section>
      )}

      {showHistory && (
        <section className="workspace-panel report-history-panel">
          <div className="panel-header"><div><h2>分析版本</h2><p>每次重新分析都会保留独立版本和输入来源。</p></div></div>
          <div className="history-list">
            {runs.map((run) => (
              <div className="history-row" key={run.id}>
                <span className="resource-icon"><Clock3 size={16} /></span>
                <div><strong>v{run.version} · {run.analysis_type}</strong><small>{new Date(run.created_at).toLocaleString('zh-CN')}</small></div>
                <span className="tag">{run.model || '规则分析'}</span>
                <button className="button button-small" type="button" onClick={() => handleSelectVersion(run.id)} disabled={updating}>查看</button>
                {user?.role === 'admin' && run.id !== runs[0]?.id && run.status !== 'archived' && (
                  <button className="button button-small" type="button" onClick={() => handleArchiveRun(run.id)} disabled={updating}>归档</button>
                )}
              </div>
            ))}
          </div>
          {runs.length >= 2 && <RunDiff current={runs[0]} previous={runs[1]} />}
        </section>
      )}

      <div className="report-layout">
        <main className="report-main">
          <ReportSection icon={FileText} title="原始需求">
            <p className="report-copy">{ticket.description || 'Jira 中没有提供详细描述。'}</p>
            <div className="metadata-grid">
              <Meta label="类型" value={ticket.issue_type || '-'} />
              <Meta label="状态" value={ticket.status || '-'} />
              <Meta label="优先级" value={ticket.priority || '-'} />
              <Meta label="负责人" value={ticket.assignee || '未分配'} />
              <Meta label="Story Point" value={String(ticket.story_points ?? '-')} />
            </div>
          </ReportSection>

          <ReportSection icon={BadgeCheck} title="需求理解与验收">
            <h3>用户目标</h3>
            <p className="report-copy">{analysis.business_goal || '尚未生成用户目标。'}</p>
            <h3>验收标准</h3>
            <ItemList items={ticket.acceptance_criteria?.length ? ticket.acceptance_criteria : [analysis.acceptance_criteria_summary].filter(Boolean)} />
          </ReportSection>

          <ReportSection icon={Code2} title="实现计划">
            <NumberedList items={analysis.implementation_plan || []} />
            <AnalysisGroups analysis={analysis} />
          </ReportSection>

          <ReportSection icon={BadgeCheck} title="分析依据与假设">
            {analysis.evidence?.length ? (
              <div className="evidence-list">
                {analysis.evidence.map((item, index) => (
                  <div key={`${item.claim}-${index}`}>
                    <span className={`tag is-${item.confidence}`}>{item.type} · {item.confidence}</span>
                    <strong>{item.claim}</strong>
                    <p>{item.source}{item.locator ? ` · ${item.locator}` : ''}</p>
                  </div>
                ))}
              </div>
            ) : <EmptyCopy text="当前分析版本没有逐项证据；重新分析后会按来源记录。" />}
            {analysis.assumptions?.length ? <><h3>假设</h3><ItemList items={analysis.assumptions} /></> : null}
          </ReportSection>

          <ReportSection icon={GitBranch} title="代码影响">
            {artifacts.code_impacts.length ? artifacts.code_impacts.map((impact) => (
              <div className="artifact-block" key={impact.id}>
                <p>{impact.summary}</p>
                {(impact.affected_files || []).map((file) => (
                  <div className="impact-file-row" key={`${impact.id}-${file.path}`}>
                    {repoFileUrl(artifacts.code_sources.find((source) => source.id === impact.code_source_id), impact.source_commit_sha, file.path)
                      ? <a href={repoFileUrl(artifacts.code_sources.find((source) => source.id === impact.code_source_id), impact.source_commit_sha, file.path)} target="_blank" rel="noreferrer"><code>{file.path}</code></a>
                      : <code>{file.path}</code>}
                    <span className="change-badge">{file.change_type}</span>
                    <span className="confidence">{Math.round(file.confidence * 100)}%</span>
                    {file.symbols?.length ? <small>{file.symbols.join('、')}</small> : null}
                    {file.reasons?.length ? <small>{file.reasons.join('；')}</small> : null}
                  </div>
                ))}
              </div>
            )) : <EmptyCopy text="尚未关联代码影响分析。" />}
          </ReportSection>

          <ReportSection icon={TestTube2} title="API 与测试影响">
            {artifacts.api_specs.length > 0 && (
              <div className="artifact-card-grid">
                {artifacts.api_specs.map((spec) => (
                  <div className="artifact-mini-card" key={spec.id}>
                    <strong>{spec.name}</strong><span>v{spec.version} · {spec.endpoint_count} 个端点</span>
                  </div>
                ))}
              </div>
            )}
            {artifacts.api_impacts?.map((impact) => (
              <div className="artifact-block" key={impact.id}>
                <h3>OpenAPI v{impact.spec_version} 核验</h3>
                <ItemList items={impact.impacts.map((item) => `${item.method} ${item.path} · ${item.change_type} · ${item.confirmation}`)} />
              </div>
            ))}
            {artifacts.test_plans.length > 0 && <ItemList items={artifacts.test_plans.map((plan) => `${plan.title} · ${plan.scenario_count} 个测试场景`)} />}
            {!artifacts.api_specs.length && !artifacts.api_impacts?.length && !artifacts.test_plans.length && <EmptyCopy text="尚未关联 OpenAPI 或测试计划。" />}
          </ReportSection>

          <ReportSection icon={PenTool} title="Figma 影响">
            {artifacts.figma_analyses.length ? artifacts.figma_analyses.map((item) => (
              <div className="artifact-block" key={item.id}>
                <h3>{item.file_name} · v{item.version || 1}</h3>
                <div className="metadata-grid">
                  <Meta label="分析范围" value={item.analysis_scope === 'selected_nodes' ? `Node ${item.figma_node_id}` : '整份文件'} />
                  <Meta label="Frame/组件" value={String(item.frame_count)} />
                  <Meta label="文本节点" value={String(item.text_node_count)} />
                  <Meta label="影响项" value={String(item.implications.length)} />
                </div>
                {item.selected_nodes?.length ? <ItemList items={item.selected_nodes.map((node) => `${node.type} · ${node.name || node.id} (${node.id})`)} /> : null}
                <ItemList items={item.implications.map((implication) => `[${priorityLabel(implication.priority)}] ${implication.title}：${implication.description}`)} />
                {item.preview_images && Object.entries(item.preview_images).length > 0 && (
                  <div className="artifact-card-grid">
                    {Object.entries(item.preview_images).slice(0, 4).map(([nodeId, imageUrl]) => (
                      <figure className="artifact-mini-card" style={{ margin: 0 }} key={nodeId}>
                        <img src={imageUrl} alt={`Figma 节点 ${nodeId} 预览`} style={{ width: '100%', maxHeight: 220, objectFit: 'contain', borderRadius: 7 }} />
                        <span>Node {nodeId}</span>
                      </figure>
                    ))}
                  </div>
                )}
                {item.preview_status === 'unavailable' && <p className="muted-copy">预览不可用：{item.preview_error || 'Figma 未返回可渲染图片。'}</p>}
              </div>
            )) : <EmptyCopy text="尚未关联 Figma 分析。" />}
          </ReportSection>

          <ReportSection icon={MessageSquare} title="审核讨论">
            <div className="comment-list">
              {report.collaboration.comments.map((comment) => (
                <div className={`comment-card${comment.status === 'resolved' ? ' is-resolved' : ''}`} key={comment.id}>
                  <div><strong>{comment.author_name}</strong><span>{new Date(comment.created_at).toLocaleString('zh-CN')}</span></div>
                  <p>{comment.body}</p>
                  {canWrite && <button type="button" onClick={() => handleCommentStatus(comment.id, comment.status === 'open' ? 'resolved' : 'open')}>{comment.status === 'open' ? '标记解决' : '重新打开'}</button>}
                </div>
              ))}
              {!report.collaboration.comments.length && <EmptyCopy text="暂无讨论。" />}
            </div>
            {canWrite && <div className="comment-composer"><textarea rows={3} value={newComment} onChange={(event) => setNewComment(event.target.value)} placeholder="输入评论，可使用 @成员名" /><button className="button button-primary" type="button" onClick={handleAddComment} disabled={updating || !newComment.trim()}>发送评论</button></div>}
          </ReportSection>

          <ReportSection icon={GitPullRequest} title="开发交付闭环">
            {report.collaboration.delivery_links.length ? (
              <div className="delivery-list">
                {report.collaboration.delivery_links.map((item) => (
                  <a href={item.url} target="_blank" rel="noreferrer" key={item.id}>
                    <strong>{item.provider} {item.pull_request || item.commit_sha.slice(0, 8)}</strong>
                    <span>CI: {item.ci_status}{item.release_version ? ` · Release ${item.release_version}` : ''}</span>
                  </a>
                ))}
              </div>
            ) : <EmptyCopy text="尚未关联 Pull Request、Commit 或发布版本。" />}
            <div className="delivery-comparison">
              <Meta label="预测文件" value={String(report.collaboration.delivery_comparison.predicted_files.length)} />
              <Meta label="实际文件" value={String(report.collaboration.delivery_comparison.actual_files.length)} />
              <Meta label="匹配文件" value={String(report.collaboration.delivery_comparison.matched_files.length)} />
              <Meta label="匹配率" value={report.collaboration.delivery_comparison.match_rate == null ? '-' : `${Math.round(report.collaboration.delivery_comparison.match_rate * 100)}%`} />
            </div>
            {canWrite && <div className="delivery-form">
              <input aria-label="Pull Request 或 Commit URL" type="url" value={deliveryDraft.url} onChange={(event) => setDeliveryDraft({ ...deliveryDraft, url: event.target.value })} placeholder="Pull Request / Commit URL" />
              <input aria-label="Pull Request 编号" value={deliveryDraft.pull_request} onChange={(event) => setDeliveryDraft({ ...deliveryDraft, pull_request: event.target.value })} placeholder="PR 编号，例如 #123" />
              <input aria-label="Commit SHA" value={deliveryDraft.commit_sha} onChange={(event) => setDeliveryDraft({ ...deliveryDraft, commit_sha: event.target.value })} placeholder="Commit SHA" />
              <select aria-label="CI 状态" value={deliveryDraft.ci_status} onChange={(event) => setDeliveryDraft({ ...deliveryDraft, ci_status: event.target.value })}><option value="unknown">CI 未知</option><option value="pending">CI 运行中</option><option value="passed">CI 通过</option><option value="failed">CI 失败</option></select>
              <input aria-label="发布版本" value={deliveryDraft.release_version} onChange={(event) => setDeliveryDraft({ ...deliveryDraft, release_version: event.target.value })} placeholder="发布版本" />
              <textarea aria-label="实际修改文件" rows={4} value={deliveryDraft.actual_files} onChange={(event) => setDeliveryDraft({ ...deliveryDraft, actual_files: event.target.value })} placeholder="实际修改文件，每行一个" />
              <button className="button" type="button" onClick={handleAddDelivery} disabled={updating || !deliveryDraft.url.trim()}>保存交付记录</button>
            </div>}
          </ReportSection>
        </main>

        <aside className="report-sidebar">
          <section className="review-card">
            <div className="review-card-heading"><BadgeCheck size={19} /><div><h2>分析审核</h2><p>审核结果绑定当前分析版本</p></div></div>
            <ReviewBadge status={review.status} />
            {canWrite && <textarea
              value={reviewComment}
              onChange={(event) => setReviewComment(event.target.value)}
              placeholder="填写审核意见；驳回时必填"
              rows={5}
            />}
            {canWrite && <div className="review-actions">
              <button className="button" type="button" disabled={updating} onClick={() => handleReview('in_review')}><Send size={15} /> 提交审核</button>
              {canApprove && <button className="button button-success" type="button" disabled={updating} onClick={() => handleReview('approved')}><Check size={15} /> 标记已核对</button>}
              {canApprove && <button className="button button-danger" type="button" disabled={updating} onClick={() => handleReview('rejected')}><X size={15} /> 驳回</button>}
            </div>}
            {review.reviewer_name && <small>最近操作：{review.reviewer_name}{review.updated_at ? ` · ${new Date(review.updated_at).toLocaleString('zh-CN')}` : ''}</small>}
          </section>

          <section className="review-card">
            <div className="review-card-heading"><UploadCloud size={19} /><div><h2>Jira 回写</h2><p>需要 Jira Token 具备写权限</p></div></div>
            {report.project.jira_url && <a href={`${report.project.jira_url}/browse/${ticket.key}`} target="_blank" rel="noreferrer">在 Jira 中打开 {ticket.key}</a>}
            {canWrite && <>
              <textarea rows={3} value={jiraDraft.comment} onChange={(event) => setJiraDraft({ ...jiraDraft, comment: event.target.value })} placeholder="回写 Jira 评论" />
              <button className="button" type="button" onClick={() => handleJiraWriteback('comment')} disabled={updating || !jiraDraft.comment.trim()}>发送评论</button>
              <input value={jiraDraft.transition} onChange={(event) => setJiraDraft({ ...jiraDraft, transition: event.target.value })} placeholder="状态转换名称或 ID" />
              <button className="button" type="button" onClick={() => handleJiraWriteback('transition')} disabled={updating || !jiraDraft.transition.trim()}>更新状态</button>
              <input value={jiraDraft.labels} onChange={(event) => setJiraDraft({ ...jiraDraft, labels: event.target.value })} placeholder={(ticket.labels || []).join(', ') || '标签，逗号分隔'} />
              <button className="button" type="button" onClick={() => handleJiraWriteback('labels')} disabled={updating}>更新标签</button>
            </>}
          </section>

          <section className="review-card">
            <div className="review-card-heading"><ListChecks size={19} /><div><h2>待确认事项</h2><p>分配负责人和截止时间</p></div></div>
            <div className="action-item-list">
              {report.collaboration.action_items.map((item) => (
                <label className={item.status === 'done' ? 'is-done' : ''} key={item.id}>
                  <input type="checkbox" checked={item.status === 'done'} disabled={!canWrite} onChange={() => handleActionStatus(item.id, item.status === 'done' ? 'open' : 'done')} />
                  <span><strong>{item.title}</strong><small>{item.owner || '未分配'}{item.due_at ? ` · ${item.due_at}` : ''}</small></span>
                </label>
              ))}
            </div>
            {canWrite && <>
              <input value={newAction.title} onChange={(event) => setNewAction({ ...newAction, title: event.target.value })} placeholder="新增待确认事项" />
              <input value={newAction.owner} onChange={(event) => setNewAction({ ...newAction, owner: event.target.value })} placeholder="负责人" />
              <input type="date" value={newAction.due_at} onChange={(event) => setNewAction({ ...newAction, due_at: event.target.value })} />
              <button className="button" type="button" onClick={handleAddAction} disabled={updating || !newAction.title.trim()}>添加待办</button>
            </>}
          </section>

          <section className="review-card">
            <div className="review-card-heading"><TestTube2 size={19} /><div><h2>复杂度与工作量</h2><p>来自当前分析版本</p></div></div>
            <div className="score-list">
              {Object.entries(analysis.score || {}).map(([key, value]) => (
                <div key={key}><span>{key.replace(/_/g, ' ')}</span><strong>{String(value)}</strong></div>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </div>
  )
}

function ReportSection({ icon: Icon, title, children }: { icon: typeof FileText; title: string; children: React.ReactNode }) {
  return <section className="workspace-panel report-section"><div className="panel-header"><div className="report-section-title"><span className="resource-icon"><Icon size={18} /></span><h2>{title}</h2></div></div><div className="report-section-body">{children}</div></section>
}

function Meta({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>
}

function ItemList({ items }: { items: string[] }) {
  return items.length ? <ul className="report-list">{items.map((item, index) => <li key={`${item}-${index}`}><Check size={15} /><span>{item}</span></li>)}</ul> : <EmptyCopy text="暂无内容。" />
}

function NumberedList({ items }: { items: string[] }) {
  return items.length ? <ol className="implementation-list">{items.map((item, index) => <li key={`${item}-${index}`}><span>{index + 1}</span><p>{item}</p></li>)}</ol> : <EmptyCopy text="尚未生成实现计划。" />
}

function EmptyCopy({ text }: { text: string }) {
  return <p className="muted-copy">{text}</p>
}

function priorityLabel(priority: string) {
  return ({ high: '高', medium: '中', low: '低' } as Record<string, string>)[priority] || priority
}

function repoFileUrl(source: TicketReport['artifacts']['code_sources'][number] | undefined, revision: string | undefined, path: string) {
  if (!source?.repo_url || source.provider === 'local') return ''
  const base = source.repo_url.replace(/\.git$/, '').replace(/\/$/, '')
  const ref = revision || source.default_branch || 'main'
  if (source.provider === 'gitlab') return `${base}/-/blob/${ref}/${path}`
  if (source.provider === 'bitbucket') return `${base}/src/${ref}/${path}`
  return `${base}/blob/${ref}/${path}`
}

function ReviewBadge({ status }: { status: TicketReview['status'] }) {
  const labels = { unreviewed: '未审核', in_review: '审核中', approved: '已核对', rejected: '已驳回' }
  return <span className={`review-badge is-${status}`}>{labels[status]}</span>
}

function AnalysisGroups({ analysis }: { analysis: TicketReport['analysis'] }) {
  const groups = [
    ['后端功能', analysis.backend_features],
    ['API 候选', analysis.api_candidates],
    ['数据库变更', analysis.db_changes],
    ['校验规则', analysis.validation_rules],
    ['外部依赖', analysis.external_dependencies],
    ['待确认事项', analysis.open_questions],
  ] as const
  return <div className="analysis-group-grid">{groups.filter(([, items]) => items?.length).map(([title, items]) => <div className="analysis-group" key={title}><h3>{title}</h3><ItemList items={items || []} /></div>)}</div>
}

function RunDiff({ current, previous }: { current: AnalysisRun; previous: AnalysisRun }) {
  const fields = ['backend_features', 'api_candidates', 'db_changes', 'implementation_plan', 'open_questions']
  const changes = fields.map((field) => {
    const currentItems = Array.isArray(current.result[field]) ? current.result[field] as string[] : []
    const previousItems = Array.isArray(previous.result[field]) ? previous.result[field] as string[] : []
    return {
      field,
      added: currentItems.filter((item) => !previousItems.includes(item)),
      removed: previousItems.filter((item) => !currentItems.includes(item)),
    }
  }).filter((item) => item.added.length || item.removed.length)
  return (
    <div className="run-diff">
      <h3>v{previous.version} → v{current.version} 变化</h3>
      {changes.length ? changes.map((change) => (
        <div key={change.field}>
          <strong>{change.field.replace(/_/g, ' ')}</strong>
          {change.added.map((item) => <p className="diff-added" key={`add-${item}`}>+ {item}</p>)}
          {change.removed.map((item) => <p className="diff-removed" key={`remove-${item}`}>− {item}</p>)}
        </div>
      )) : <p className="muted-copy">主要结构化字段没有变化。</p>}
    </div>
  )
}
