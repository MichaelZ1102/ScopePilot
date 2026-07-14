import { useCallback, useEffect, useMemo, useState, type KeyboardEvent } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  AlertCircle,
  ArrowLeft,
  BadgeCheck,
  ClipboardCheck,
  CloudDownload,
  Check,
  CheckCircle2,
  ChevronDown,
  Circle,
  Code2,
  FileText,
  Filter,
  LoaderCircle,
  PenTool,
  RefreshCw,
  Search,
  Sparkles,
  Target,
  TestTube2,
} from 'lucide-react'

import CodeImpactPanel from '../components/CodeImpactPanel'
import {
  analyzeTicket,
  excludeTicketFromReport,
  getAnalysisJob,
  getProject,
  getSprint,
  includeTicketInReport,
  listSprints,
  syncSprint,
  triggerAnalysis,
  updateTicketReview,
  type Project,
  type AnalysisJob,
  type SprintDetail as SprintDetailData,
  type TicketAnalysis,
  type TicketDetail,
  type Sprint,
  type TicketReview,
} from '../lib/api'
import { getApiErrorMessage } from '../lib/client'
import { useAuth } from '../lib/AuthContext'
import './SprintWorkspace.css'

type AnalysisTab = 'requirements' | 'code' | 'api' | 'figma'
type AnalysisFilter = 'all' | 'analyzed' | 'pending'
type ReviewFilter = 'all' | TicketReview['status'] | 'stale'
type TicketSort = 'priority' | 'key' | 'assignee' | 'story_points'

const tabs: Array<{ id: AnalysisTab; label: string; icon: typeof Target }> = [
  { id: 'requirements', label: '需求理解', icon: Target },
  { id: 'code', label: '代码影响', icon: Code2 },
  { id: 'api', label: 'API 影响', icon: TestTube2 },
  { id: 'figma', label: 'Figma 影响', icon: PenTool },
]

function findAnalysis(sprint: SprintDetailData | null, ticket: TicketDetail | null) {
  if (!sprint || !ticket) return null
  if (ticket.analysis_data) return ticket.analysis_data
  return sprint.analysis_data?.ticket_analyses.find(
    (analysis) => analysis.ticket_key === ticket.key,
  ) || null
}

function analysisState(analysis: TicketAnalysis | null) {
  return analysis ? '已分析' : '未分析'
}

function priorityClass(priority?: string) {
  const normalized = (priority || '').toLowerCase()
  if (normalized === 'highest' || normalized === 'high') return 'is-high'
  if (normalized === 'lowest' || normalized === 'low') return 'is-low'
  return 'is-medium'
}

export default function SprintDetail() {
  const { user } = useAuth()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const sprintId = Number(id)

  const [sprint, setSprint] = useState<SprintDetailData | null>(null)
  const [project, setProject] = useState<Project | null>(null)
  const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null)
  const [sprintOptions, setSprintOptions] = useState<Sprint[]>([])
  const [activeTab, setActiveTab] = useState<AnalysisTab>('requirements')
  const [searchQuery, setSearchQuery] = useState(searchParams.get('q') || '')
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || 'all')
  const [analysisFilter, setAnalysisFilter] = useState<AnalysisFilter>((searchParams.get('analysis') as AnalysisFilter) || 'all')
  const [priorityFilter, setPriorityFilter] = useState(searchParams.get('priority') || 'all')
  const [assigneeFilter, setAssigneeFilter] = useState(searchParams.get('assignee') || 'all')
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>((searchParams.get('review') as ReviewFilter) || 'all')
  const [sortBy, setSortBy] = useState<TicketSort>((searchParams.get('sort') as TicketSort) || 'priority')
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false)
  const [selectedTicketIds, setSelectedTicketIds] = useState<number[]>([])
  const [page, setPage] = useState(1)
  const [batchWorking, setBatchWorking] = useState(false)
  const [loading, setLoading] = useState(true)
  const [analyzingSprint, setAnalyzingSprint] = useState(false)
  const [analysisJob, setAnalysisJob] = useState<AnalysisJob | null>(null)
  const [analyzingTicketId, setAnalyzingTicketId] = useState<number | null>(null)
  const [reportUpdating, setReportUpdating] = useState(false)
  const [reviewUpdating, setReviewUpdating] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const loadWorkspace = useCallback(async (showLoading = true) => {
    if (!Number.isFinite(sprintId)) return
    if (showLoading) setLoading(true)
    setError('')
    try {
      const loadedSprint = await getSprint(sprintId)
      setSprint(loadedSprint)
      setSelectedTicketId((current) => {
        if (current && loadedSprint.tickets.some((ticket) => ticket.id === current)) return current
        return loadedSprint.tickets[0]?.id || null
      })
      const loadedProject = await getProject(loadedSprint.project_id)
      setProject(loadedProject)
      setSprintOptions(await listSprints(loadedSprint.project_id))
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Sprint 加载失败。'))
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [sprintId])

  useEffect(() => {
    loadWorkspace()
  }, [loadWorkspace])

  useEffect(() => {
    const jobId = sprint?.latest_analysis_job_id
    if (!jobId || sprint?.analysis_status !== 'running') return
    let disposed = false

    async function refreshJob() {
      try {
        const job = await getAnalysisJob(jobId as number)
        if (disposed) return
        setAnalysisJob(job)
        if (['done', 'failed', 'cancelled'].includes(job.status)) {
          await loadWorkspace(false)
          if (disposed) return
          if (job.status === 'done') setMessage(`分析任务 #${job.id} 已完成。`)
          else setError(job.error_message || `分析任务 #${job.id} ${job.status === 'cancelled' ? '已取消' : '失败'}。`)
        }
      } catch (requestError) {
        if (!disposed) setError(getApiErrorMessage(requestError, `分析任务 #${jobId} 状态加载失败。`))
      }
    }

    refreshJob()
    const timer = window.setInterval(refreshJob, 3000)
    return () => {
      disposed = true
      window.clearInterval(timer)
    }
  }, [loadWorkspace, sprint?.analysis_status, sprint?.latest_analysis_job_id])

  const analysisByTicketKey = useMemo(() => {
    const entries = sprint?.analysis_data?.ticket_analyses || []
    return new Map(entries.map((analysis) => [analysis.ticket_key, analysis]))
  }, [sprint])

  const statuses = useMemo(() => {
    const values = new Set(
      (sprint?.tickets || []).map((ticket) => ticket.status).filter(Boolean) as string[],
    )
    return Array.from(values).sort()
  }, [sprint])

  const priorities = useMemo(() => Array.from(new Set(
    (sprint?.tickets || []).map((ticket) => ticket.priority).filter(Boolean) as string[],
  )).sort(), [sprint])

  const assignees = useMemo(() => Array.from(new Set(
    (sprint?.tickets || []).map((ticket) => ticket.assignee).filter(Boolean) as string[],
  )).sort(), [sprint])

  const filteredTickets = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    const priorityRank: Record<string, number> = { highest: 0, high: 1, medium: 2, low: 3, lowest: 4 }
    return (sprint?.tickets || []).filter((ticket) => {
      const analysis = ticket.analysis_data || analysisByTicketKey.get(ticket.key)
      const matchesSearch = !query
        || ticket.key.toLowerCase().includes(query)
        || ticket.summary.toLowerCase().includes(query)
      const matchesStatus = statusFilter === 'all' || ticket.status === statusFilter
      const matchesAnalysis = analysisFilter === 'all'
        || (analysisFilter === 'analyzed' && Boolean(analysis))
        || (analysisFilter === 'pending' && !analysis)
      const matchesPriority = priorityFilter === 'all' || ticket.priority === priorityFilter
      const matchesAssignee = assigneeFilter === 'all' || ticket.assignee === assigneeFilter
      const reviewStatus = ticket.review_data?.status || 'unreviewed'
      const matchesReview = reviewFilter === 'all'
        || (reviewFilter === 'stale' && ticket.analysis_status === 'stale')
        || reviewStatus === reviewFilter
      return matchesSearch && matchesStatus && matchesAnalysis && matchesPriority && matchesAssignee && matchesReview
    }).sort((left, right) => {
      if (sortBy === 'key') return left.key.localeCompare(right.key)
      if (sortBy === 'assignee') return (left.assignee || '').localeCompare(right.assignee || '')
      if (sortBy === 'story_points') return (right.story_points || 0) - (left.story_points || 0)
      return (priorityRank[(left.priority || '').toLowerCase()] ?? 99) - (priorityRank[(right.priority || '').toLowerCase()] ?? 99)
    })
  }, [analysisByTicketKey, analysisFilter, assigneeFilter, priorityFilter, reviewFilter, searchQuery, sortBy, sprint, statusFilter])

  const pageSize = 50
  const totalPages = Math.max(1, Math.ceil(filteredTickets.length / pageSize))
  const pagedTickets = filteredTickets.slice((page - 1) * pageSize, page * pageSize)

  useEffect(() => {
    setPage(1)
  }, [searchQuery, statusFilter, analysisFilter, priorityFilter, assigneeFilter, reviewFilter, sortBy])

  useEffect(() => {
    const filteredIds = new Set(filteredTickets.map((ticket) => ticket.id))
    setSelectedTicketIds((current) => current.filter((ticketId) => filteredIds.has(ticketId)))
  }, [filteredTickets])

  useEffect(() => {
    const next: Record<string, string> = {}
    if (searchQuery) next.q = searchQuery
    if (statusFilter !== 'all') next.status = statusFilter
    if (analysisFilter !== 'all') next.analysis = analysisFilter
    if (priorityFilter !== 'all') next.priority = priorityFilter
    if (assigneeFilter !== 'all') next.assignee = assigneeFilter
    if (reviewFilter !== 'all') next.review = reviewFilter
    if (sortBy !== 'priority') next.sort = sortBy
    setSearchParams(next, { replace: true })
  }, [analysisFilter, assigneeFilter, priorityFilter, reviewFilter, searchQuery, setSearchParams, sortBy, statusFilter])

  useEffect(() => {
    if (filteredTickets.length === 0) return
    if (!filteredTickets.some((ticket) => ticket.id === selectedTicketId)) {
      setSelectedTicketId(filteredTickets[0].id)
    }
  }, [filteredTickets, selectedTicketId])

  const selectedTicket = sprint?.tickets.find((ticket) => ticket.id === selectedTicketId) || null
  const selectedAnalysis = findAnalysis(sprint, selectedTicket)
  const canWrite = user?.role === 'admin' || user?.role === 'member'
  const canApprove = user?.role === 'admin'

  async function handleAnalyzeSprint() {
    if (!sprint) return
    setAnalyzingSprint(true)
    setMessage('')
    setError('')
    try {
      const updated = await triggerAnalysis(sprint.id)
      setSprint(updated)
      setAnalysisJob(null)
      setMessage(updated.latest_analysis_job_id
        ? `分析任务 #${updated.latest_analysis_job_id} 已提交，可在分析任务中心查看进度。`
        : '分析任务已提交，可在分析任务中心查看进度。')
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Sprint 分析启动失败。'))
    } finally {
      setAnalyzingSprint(false)
    }
  }

  async function handleAnalyzeTicket() {
    if (!sprint || !selectedTicket) return
    setAnalyzingTicketId(selectedTicket.id)
    setMessage('')
    setError('')
    try {
      await analyzeTicket(sprint.id, selectedTicket.id)
      await loadWorkspace(false)
      setMessage(`${selectedTicket.key} 已重新分析。`)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Ticket 分析失败。'))
    } finally {
      setAnalyzingTicketId(null)
    }
  }

  async function handleToggleReport() {
    if (!sprint || !selectedTicket) return
    setReportUpdating(true)
    setMessage('')
    setError('')
    try {
      const nextIncluded = selectedTicket.report_included === false
      if (nextIncluded) {
        await includeTicketInReport(sprint.id, selectedTicket.id)
      } else {
        await excludeTicketFromReport(sprint.id, selectedTicket.id)
      }
      setSprint((current) => {
        if (!current) return current
        return {
          ...current,
          tickets: current.tickets.map((ticket) => (
            ticket.id === selectedTicket.id
              ? { ...ticket, report_included: nextIncluded }
              : ticket
          )),
        }
      })
      setMessage(nextIncluded ? 'Ticket 已加入报告。' : 'Ticket 已移出报告。')
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '报告选择更新失败。'))
    } finally {
      setReportUpdating(false)
    }
  }

  async function handleReview(status: TicketReview['status']) {
    if (!sprint || !selectedTicket) return
    setReviewUpdating(true)
    setError('')
    setMessage('')
    try {
      const review = await updateTicketReview(sprint.id, selectedTicket.id, status)
      setSprint((current) => current ? {
        ...current,
        tickets: current.tickets.map((ticket) => (
          ticket.id === selectedTicket.id ? { ...ticket, review_data: review } : ticket
        )),
      } : current)
      setMessage(status === 'approved' ? 'Ticket 已标记为核对完成。' : 'Ticket 已提交审核。')
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '审核状态更新失败。'))
    } finally {
      setReviewUpdating(false)
    }
  }

  async function handleSyncSprint() {
    if (!sprint) return
    setSyncing(true)
    setError('')
    setMessage('')
    try {
      const result = await syncSprint(sprint.id)
      setSprint(result.sprint)
      const summary = result.summary || {}
      setMessage(`Jira 同步完成：新增 ${summary.added?.length || 0}，更新 ${summary.updated?.length || 0}，移除 ${summary.removed?.length || 0}。`)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Jira 同步失败。'))
    } finally {
      setSyncing(false)
    }
  }

  function toggleTicketSelection(ticketId: number) {
    setSelectedTicketIds((current) => (
      current.includes(ticketId)
        ? current.filter((id) => id !== ticketId)
        : [...current, ticketId]
    ))
  }

  function selectTicket(ticketId: number) {
    setSelectedTicketId(ticketId)
    setActiveTab('requirements')
  }

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, tabId: AnalysisTab) {
    const currentIndex = tabs.findIndex((tabItem) => tabItem.id === tabId)
    let nextIndex = currentIndex
    if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % tabs.length
    else if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + tabs.length) % tabs.length
    else if (event.key === 'Home') nextIndex = 0
    else if (event.key === 'End') nextIndex = tabs.length - 1
    else return

    event.preventDefault()
    const nextTab = tabs[nextIndex].id
    setActiveTab(nextTab)
    window.requestAnimationFrame(() => document.getElementById(`ticket-tab-${nextTab}`)?.focus())
  }

  async function handleBatchAnalyze() {
    if (!sprint || selectedTicketIds.length === 0) return
    setBatchWorking(true)
    setError('')
    try {
      for (const ticketId of selectedTicketIds) {
        await analyzeTicket(sprint.id, ticketId)
      }
      await loadWorkspace(false)
      setMessage(`已重新分析 ${selectedTicketIds.length} 个 Ticket。`)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '批量分析失败。'))
    } finally {
      setBatchWorking(false)
    }
  }

  async function handleBatchReview() {
    if (!sprint || selectedTicketIds.length === 0) return
    setBatchWorking(true)
    setError('')
    try {
      for (const ticketId of selectedTicketIds) {
        await updateTicketReview(sprint.id, ticketId, 'in_review')
      }
      await loadWorkspace(false)
      setMessage(`已提交 ${selectedTicketIds.length} 个 Ticket 进入审核。`)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '批量提交审核失败。'))
    } finally {
      setBatchWorking(false)
    }
  }

  async function handleBatchReport(include: boolean) {
    if (!sprint || selectedTicketIds.length === 0) return
    setBatchWorking(true)
    setError('')
    try {
      for (const ticketId of selectedTicketIds) {
        if (include) await includeTicketInReport(sprint.id, ticketId)
        else await excludeTicketFromReport(sprint.id, ticketId)
      }
      await loadWorkspace(false)
      setMessage(`已${include ? '加入' : '移出'}报告：${selectedTicketIds.length} 个 Ticket。`)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '批量更新报告失败。'))
    } finally {
      setBatchWorking(false)
    }
  }

  if (loading) {
    return (
      <div className="workspace-loading">
        <LoaderCircle className="spin" size={24} />
        <span>正在加载 Sprint 工作台...</span>
      </div>
    )
  }

  if (!sprint) {
    return (
      <div className="workspace-fatal">
        <AlertCircle size={28} />
        <strong>{error || 'Sprint 不存在。'}</strong>
        <button className="button button-secondary" type="button" onClick={() => navigate('/')}>
          <ArrowLeft size={16} /> 返回仪表盘
        </button>
      </div>
    )
  }

  return (
    <div className="sprint-workspace">
      <header className="workspace-topbar">
        <button className="breadcrumb-back" type="button" onClick={() => navigate('/')}>
          <ArrowLeft size={16} />
        </button>
        <div className="workspace-breadcrumb">
          <button type="button" onClick={() => navigate('/projects')}>项目</button>
          <span>/</span>
          <strong>{project?.name || '项目'}</strong>
          <span>/</span>
          <strong>{sprint.name}</strong>
        </div>
        <div className="workspace-topbar-actions">
          <label className="sprint-selector">
            <select aria-label="切换 Sprint" value={sprint.id} onChange={(event) => navigate(`/sprint/${event.target.value}`)}>
              {sprintOptions.map((option) => <option value={option.id} key={option.id}>{option.name}</option>)}
            </select>
            <ChevronDown size={15} />
          </label>
          {canWrite && <button className="button button-secondary" type="button" onClick={handleSyncSprint} disabled={syncing}>
            {syncing ? <LoaderCircle className="spin" size={17} /> : <CloudDownload size={17} />}
            {syncing ? '同步中' : '同步 Jira'}
          </button>}
          {canWrite && <button className="button button-primary" type="button" onClick={handleAnalyzeSprint} disabled={analyzingSprint || sprint.analysis_status === 'running'}>
            {(analyzingSprint || sprint.analysis_status === 'running') ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />}
            {analyzingSprint ? '正在提交任务' : sprint.analysis_status === 'running' ? '分析任务进行中' : '分析全部 Ticket'}
          </button>}
        </div>
      </header>

      {(message || error) && (
        <div className={`workspace-toast${error ? ' is-error' : ''}`}>
          {error ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
          <span>{error || message}</span>
          <button type="button" onClick={() => { setMessage(''); setError('') }}>关闭</button>
        </div>
      )}

      {sprint.analysis_status === 'running' && (
        <div className="workspace-toast">
          <LoaderCircle className="spin" size={16} />
          <span>
            {analysisJob
              ? `任务 #${analysisJob.id}：${analysisJob.progress_current}/${analysisJob.progress_total} Ticket，状态 ${analysisJob.status}`
              : `分析任务 #${sprint.latest_analysis_job_id || '-'} 正在队列中。`}
          </span>
          <button type="button" onClick={() => navigate('/analysis-jobs')}>查看任务中心</button>
        </div>
      )}

      <div className="workspace-body">
        <aside className="ticket-pane">
          <div className="ticket-pane-header">
            <div>
              <h2>Ticket 列表</h2>
              <span>{filteredTickets.length} / {sprint.tickets.length}</span>
            </div>
            <div className="ticket-search">
              <Search size={17} />
              <input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="搜索 Ticket key 或摘要..."
                aria-label="搜索 Ticket"
              />
            </div>
            <div className="ticket-filters">
              <label>
                <span>状态</span>
                <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                  <option value="all">全部</option>
                  {statuses.map((status) => <option value={status} key={status}>{status}</option>)}
                </select>
                <ChevronDown size={14} />
              </label>
              <label>
                <span>分析</span>
                <select value={analysisFilter} onChange={(event) => setAnalysisFilter(event.target.value as AnalysisFilter)}>
                  <option value="all">全部</option>
                  <option value="analyzed">已分析</option>
                  <option value="pending">未分析</option>
                </select>
                <ChevronDown size={14} />
              </label>
              <button className={`icon-button filter-button${showAdvancedFilters ? ' is-active' : ''}`} type="button" title="筛选条件" aria-label="筛选条件" onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}>
                <Filter size={17} />
              </button>
            </div>
            {showAdvancedFilters && (
              <div className="advanced-ticket-filters">
                <label><span>优先级</span><select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)}><option value="all">全部</option>{priorities.map((priority) => <option value={priority} key={priority}>{priority}</option>)}</select></label>
                <label><span>负责人</span><select value={assigneeFilter} onChange={(event) => setAssigneeFilter(event.target.value)}><option value="all">全部</option>{assignees.map((assignee) => <option value={assignee} key={assignee}>{assignee}</option>)}</select></label>
                <label><span>审核</span><select value={reviewFilter} onChange={(event) => setReviewFilter(event.target.value as ReviewFilter)}><option value="all">全部</option><option value="unreviewed">未审核</option><option value="in_review">审核中</option><option value="approved">已核对</option><option value="rejected">已驳回</option><option value="stale">分析已过期</option></select></label>
                <label><span>排序</span><select value={sortBy} onChange={(event) => setSortBy(event.target.value as TicketSort)}><option value="priority">优先级</option><option value="key">Ticket Key</option><option value="assignee">负责人</option><option value="story_points">Story Point</option></select></label>
              </div>
            )}
            {canWrite && selectedTicketIds.length > 0 && (
              <div className="ticket-batch-toolbar">
                <strong>已选 {selectedTicketIds.length}</strong>
                <button type="button" onClick={handleBatchAnalyze} disabled={batchWorking}>重新分析</button>
                <button type="button" onClick={handleBatchReview} disabled={batchWorking}>提交审核</button>
                <button type="button" onClick={() => handleBatchReport(true)} disabled={batchWorking}>加入报告</button>
                <button type="button" onClick={() => handleBatchReport(false)} disabled={batchWorking}>移出报告</button>
                <button type="button" onClick={() => setSelectedTicketIds([])}>清除</button>
              </div>
            )}
          </div>

          <div className="ticket-list-heading" aria-hidden="true">
            <span>Ticket</span>
            <span>优先级</span>
            <span>分析状态</span>
          </div>

          <div className="ticket-list">
            {pagedTickets.map((ticket) => {
              const analysis = ticket.analysis_data || analysisByTicketKey.get(ticket.key) || null
              const active = ticket.id === selectedTicketId
              return (
                <div
                  className={`ticket-row${active ? ' is-selected' : ''}${canWrite ? ' has-selection' : ''}`}
                  key={ticket.id}
                >
                  {canWrite && <input
                    className="ticket-row-checkbox"
                    type="checkbox"
                    checked={selectedTicketIds.includes(ticket.id)}
                    onChange={() => toggleTicketSelection(ticket.id)}
                    aria-label={`选择 ${ticket.key}`}
                  />}
                  <button
                    className="ticket-row-open"
                    type="button"
                    onClick={() => selectTicket(ticket.id)}
                    aria-label={`打开 ${ticket.key}：${ticket.summary}`}
                    aria-current={active ? 'true' : undefined}
                  >
                    <span className="ticket-main">
                      <span className="ticket-key">
                      <FileText size={15} /> {ticket.key}
                      </span>
                      <strong>{ticket.summary}</strong>
                    </span>
                    <span className={`priority-indicator ${priorityClass(ticket.priority)}`}>
                      <span />
                      {ticket.priority || '未设置'}
                    </span>
                    <span className={`analysis-indicator${analysis ? ' is-complete' : ''}`}>
                      {analysis ? <CheckCircle2 size={15} /> : <Circle size={15} />}
                      {analysisState(analysis)}
                    </span>
                  </button>
                </div>
              )
            })}
            {filteredTickets.length === 0 && (
              <div className="ticket-empty">
                <Search size={24} />
                <strong>没有匹配的 Ticket</strong>
                <span>调整关键词或筛选条件后重试。</span>
              </div>
            )}
            {filteredTickets.length > pageSize && (
              <div className="ticket-pagination">
                <button type="button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>上一页</button>
                <span>{page} / {totalPages}</span>
                <button type="button" disabled={page >= totalPages} onClick={() => setPage((current) => current + 1)}>下一页</button>
              </div>
            )}
          </div>
        </aside>

        <section className="analysis-pane">
          {selectedTicket ? (
            <>
              <div className="ticket-detail-header">
                <div className="ticket-title-row">
                  <span className="ticket-title-icon"><FileText size={18} /></span>
                  <span>{selectedTicket.key}</span>
                  {selectedTicket.report_included !== false && (
                    <span className="report-badge"><BadgeCheck size={14} /> 已在报告</span>
                  )}
                  <span className={`review-badge is-${selectedTicket.review_data?.status || 'unreviewed'}`}>
                    {reviewStateLabel(selectedTicket.review_data?.status)}
                  </span>
                  {selectedTicket.analysis_status === 'stale' && <span className="status-badge is-warning">分析已过期</span>}
                </div>
                <h1>{selectedTicket.summary}</h1>
                <div className="ticket-metadata">
                  <Metadata label="项目" value={project?.name || '-'} />
                  <Metadata label="类型" value={selectedTicket.issue_type || '-'} />
                  <Metadata label="优先级" value={selectedTicket.priority || '-'} />
                  <Metadata label="状态" value={selectedTicket.status || '-'} accent />
                  <Metadata label="负责人" value={selectedTicket.assignee || '未分配'} />
                </div>
              </div>

              <div className="analysis-tabs" role="tablist" aria-label="Ticket 分析">
                {tabs.map(({ id: tabId, label, icon: Icon }) => (
                  <button
                    key={tabId}
                    id={`ticket-tab-${tabId}`}
                    type="button"
                    role="tab"
                    aria-selected={activeTab === tabId}
                    aria-controls="ticket-analysis-panel"
                    tabIndex={activeTab === tabId ? 0 : -1}
                    className={activeTab === tabId ? 'is-active' : ''}
                    onClick={() => setActiveTab(tabId)}
                    onKeyDown={(event) => handleTabKeyDown(event, tabId)}
                  >
                    <Icon size={17} />
                    {label}
                  </button>
                ))}
              </div>

              <div className="analysis-content" id="ticket-analysis-panel" role="tabpanel" aria-labelledby={`ticket-tab-${activeTab}`}>
                {activeTab === 'requirements' && (
                  <RequirementsPanel ticket={selectedTicket} analysis={selectedAnalysis} onAnalyze={handleAnalyzeTicket} loading={analyzingTicketId === selectedTicket.id} readOnly={!canWrite} />
                )}
                {activeTab === 'code' && (
                  <CodeImpactPanel
                    projectId={sprint.project_id}
                    ticketId={selectedTicket.id}
                    sprintId={selectedTicket.sprint_id}
                    summary={selectedTicket.summary}
                    description={selectedTicket.description}
                    readOnly={!canWrite}
                  />
                )}
                {activeTab === 'api' && (
                  <ApiPanel
                    analysis={selectedAnalysis}
                    onOpen={() => navigate(
                      `/api-test-plans?project_id=${sprint.project_id}&ticket_id=${selectedTicket.id}`,
                    )}
                  />
                )}
                {activeTab === 'figma' && (
                  <FigmaPanel
                    ticket={selectedTicket}
                    onOpen={() => navigate(
                      `/figma-designs?project_id=${sprint.project_id}&ticket_id=${selectedTicket.id}&summary=${encodeURIComponent(selectedTicket.summary)}`,
                    )}
                  />
                )}
              </div>

              <footer className="analysis-actions">
                {canWrite && <button className="button button-secondary" type="button" onClick={handleAnalyzeTicket} disabled={analyzingTicketId === selectedTicket.id}>
                  {analyzingTicketId === selectedTicket.id ? <LoaderCircle className="spin" size={17} /> : <RefreshCw size={17} />}
                  {selectedAnalysis ? '重新分析 Ticket' : '分析 Ticket'}
                </button>}
                <button className="button button-secondary" type="button" onClick={() => navigate(`/tickets/${selectedTicket.id}/report`)}>
                  <FileText size={17} />
                  查看完整报告
                </button>
                {canWrite && <button className="button button-success" type="button" onClick={() => handleReview(canApprove && selectedTicket.review_data?.status === 'in_review' ? 'approved' : 'in_review')} disabled={reviewUpdating || !selectedAnalysis || selectedTicket.review_data?.status === 'approved'}>
                  {reviewUpdating ? <LoaderCircle className="spin" size={17} /> : <ClipboardCheck size={17} />}
                  {canApprove && selectedTicket.review_data?.status === 'in_review' ? '标记已核对' : selectedTicket.review_data?.status === 'approved' ? '已核对' : '提交审核'}
                </button>}
                {canWrite && <button className={`button ${selectedTicket.report_included === false ? 'button-primary' : 'button-success'}`} type="button" onClick={handleToggleReport} disabled={reportUpdating}>
                  {reportUpdating ? <LoaderCircle className="spin" size={17} /> : selectedTicket.report_included === false ? <FileText size={17} /> : <Check size={17} />}
                  {selectedTicket.report_included === false ? '加入报告' : '移出报告'}
                </button>}
              </footer>
            </>
          ) : (
            <div className="analysis-empty full-pane">
              <FileText size={30} />
              <strong>选择一个 Ticket</strong>
              <span>从左侧列表选择 Ticket 查看详细分析。</span>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function reviewStateLabel(status?: TicketReview['status']) {
  return ({
    unreviewed: '未审核',
    in_review: '审核中',
    approved: '已核对',
    rejected: '已驳回',
  } as Record<string, string>)[status || 'unreviewed']
}

function Metadata({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="metadata-item">
      <span>{label}</span>
      <strong className={accent ? 'metadata-accent' : ''}>{value}</strong>
    </div>
  )
}

function RequirementsPanel({ ticket, analysis, onAnalyze, loading, readOnly }: {
  ticket: TicketDetail
  analysis: TicketAnalysis | null
  onAnalyze: () => void
  loading: boolean
  readOnly: boolean
}) {
  if (!analysis) {
    return (
      <div className="analysis-empty full-pane">
        <Sparkles size={30} />
        <strong>当前 Ticket 尚未分析</strong>
        <span>AI 将结合 Jira 描述、验收标准和评论生成结构化分析。</span>
        {!readOnly && <button className="button button-primary" type="button" onClick={onAnalyze} disabled={loading}>
          {loading ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />}
          开始分析
        </button>}
      </div>
    )
  }

  const acceptanceItems = ticket.acceptance_criteria?.length
    ? ticket.acceptance_criteria
    : analysis.acceptance_criteria_summary
      ? [analysis.acceptance_criteria_summary]
      : []

  return (
    <div className="requirements-view">
      <AnalysisSection icon={Target} title="用户目标">
        <p>{analysis.business_goal || 'AI 未识别到明确的用户目标。'}</p>
      </AnalysisSection>

      <AnalysisSection icon={BadgeCheck} title="验收标准">
        {acceptanceItems.length > 0 ? (
          <ul className="analysis-checklist">
            {acceptanceItems.map((item, index) => (
              <li key={`${item}-${index}`}><Check size={16} /> <span>{item}</span></li>
            ))}
          </ul>
        ) : (
          <p className="muted-copy">Jira 中没有明确的验收标准。</p>
        )}
      </AnalysisSection>

      <AnalysisSection icon={Code2} title="实现建议">
        {analysis.implementation_plan.length > 0 ? (
          <ol className="implementation-list">
            {analysis.implementation_plan.map((step, index) => (
              <li key={`${step}-${index}`}><span>{index + 1}</span><p>{step}</p></li>
            ))}
          </ol>
        ) : (
          <p className="muted-copy">AI 未生成实现建议。</p>
        )}
      </AnalysisSection>

      {(analysis.open_questions.length > 0 || analysis.external_dependencies.length > 0) && (
        <AnalysisSection icon={AlertCircle} title="待确认事项">
          <ul className="plain-list">
            {[...analysis.open_questions, ...analysis.external_dependencies].map((item, index) => (
              <li key={`${item}-${index}`}>{item}</li>
            ))}
          </ul>
        </AnalysisSection>
      )}
    </div>
  )
}

function AnalysisSection({ icon: Icon, title, children }: {
  icon: typeof Target
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="analysis-section">
      <div className="analysis-section-heading">
        <span className="analysis-section-icon"><Icon size={20} /></span>
        <h3>{title}</h3>
      </div>
      <div className="analysis-section-body">{children}</div>
    </section>
  )
}

function ApiPanel({ analysis, onOpen }: { analysis: TicketAnalysis | null; onOpen: () => void }) {
  if (!analysis) {
    return (
      <div className="analysis-empty full-pane">
        <TestTube2 size={30} />
        <strong>先完成 Ticket 分析</strong>
        <span>AI 分析完成后会展示候选接口、验证规则和测试建议。</span>
      </div>
    )
  }

  const apiTests = analysis.api_tests || []
  return (
    <div className="requirements-view">
      <AnalysisSection icon={TestTube2} title="候选接口">
        {analysis.api_candidates.length > 0 ? (
          <div className="api-chip-list">
            {analysis.api_candidates.map((candidate) => <code key={candidate}>{candidate}</code>)}
          </div>
        ) : <p className="muted-copy">未识别到需要新增或调整的 API。</p>}
      </AnalysisSection>

      <AnalysisSection icon={BadgeCheck} title="验证规则">
        {analysis.validation_rules.length > 0 ? (
          <ul className="plain-list">{analysis.validation_rules.map((rule) => <li key={rule}>{rule}</li>)}</ul>
        ) : <p className="muted-copy">未生成额外验证规则。</p>}
      </AnalysisSection>

      <AnalysisSection icon={TestTube2} title="测试建议">
        {apiTests.length > 0 ? (
          <ul className="plain-list">
            {apiTests.map((test, index) => (
              <li key={index}>{typeof test === 'string' ? test : String(test.scenario_name || test.endpoint || test.description || `测试场景 ${index + 1}`)}</li>
            ))}
          </ul>
        ) : <p className="muted-copy">当前 Ticket 没有 API 测试建议。</p>}
      </AnalysisSection>
      <div className="analysis-empty figma-cta">
        <TestTube2 size={28} />
        <strong>需要用真实 OpenAPI 核验接口影响？</strong>
        <span>前往 API 测试页选择当前项目的 Spec，生成并关联当前 Ticket 的测试计划。</span>
        <button className="button button-secondary" type="button" onClick={onOpen}>打开 API 测试</button>
      </div>
    </div>
  )
}

function FigmaPanel({ ticket, onOpen }: { ticket: TicketDetail; onOpen: () => void }) {
  const links = ticket.figma_links || []
  return (
    <div className="requirements-view">
      <AnalysisSection icon={PenTool} title="关联设计">
        {links.length > 0 ? (
          <div className="figma-link-list">
            {links.map((link) => (
              <a href={link} target="_blank" rel="noreferrer" key={link}>{link}</a>
            ))}
          </div>
        ) : (
          <p className="muted-copy">Jira Ticket 中没有识别到 Figma 链接。</p>
        )}
      </AnalysisSection>
      <div className="analysis-empty figma-cta">
        <PenTool size={28} />
        <strong>需要分析设计稿的后端影响？</strong>
        <span>前往 Figma 分析页输入设计链接，并使用当前 Ticket 摘要作为分析上下文。</span>
        <button className="button button-secondary" type="button" onClick={onOpen}>打开 Figma 分析</button>
      </div>
    </div>
  )
}
