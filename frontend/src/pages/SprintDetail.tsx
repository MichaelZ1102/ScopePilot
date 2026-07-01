import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  AlertCircle,
  ArrowLeft,
  BadgeCheck,
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
  getProject,
  getSprint,
  includeTicketInReport,
  triggerAnalysis,
  type Project,
  type SprintDetail as SprintDetailData,
  type TicketAnalysis,
  type TicketDetail,
} from '../lib/api'
import { getApiErrorMessage } from '../lib/client'
import './SprintWorkspace.css'

type AnalysisTab = 'requirements' | 'code' | 'api' | 'figma'
type AnalysisFilter = 'all' | 'analyzed' | 'pending'

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
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const sprintId = Number(id)

  const [sprint, setSprint] = useState<SprintDetailData | null>(null)
  const [project, setProject] = useState<Project | null>(null)
  const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState<AnalysisTab>('requirements')
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [analysisFilter, setAnalysisFilter] = useState<AnalysisFilter>('all')
  const [loading, setLoading] = useState(true)
  const [analyzingSprint, setAnalyzingSprint] = useState(false)
  const [analyzingTicketId, setAnalyzingTicketId] = useState<number | null>(null)
  const [reportUpdating, setReportUpdating] = useState(false)
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
      setProject(await getProject(loadedSprint.project_id))
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Sprint 加载失败。'))
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [sprintId])

  useEffect(() => {
    loadWorkspace()
  }, [loadWorkspace])

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

  const filteredTickets = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    return (sprint?.tickets || []).filter((ticket) => {
      const analysis = ticket.analysis_data || analysisByTicketKey.get(ticket.key)
      const matchesSearch = !query
        || ticket.key.toLowerCase().includes(query)
        || ticket.summary.toLowerCase().includes(query)
      const matchesStatus = statusFilter === 'all' || ticket.status === statusFilter
      const matchesAnalysis = analysisFilter === 'all'
        || (analysisFilter === 'analyzed' && Boolean(analysis))
        || (analysisFilter === 'pending' && !analysis)
      return matchesSearch && matchesStatus && matchesAnalysis
    })
  }, [analysisByTicketKey, analysisFilter, searchQuery, sprint, statusFilter])

  useEffect(() => {
    if (filteredTickets.length === 0) return
    if (!filteredTickets.some((ticket) => ticket.id === selectedTicketId)) {
      setSelectedTicketId(filteredTickets[0].id)
    }
  }, [filteredTickets, selectedTicketId])

  const selectedTicket = sprint?.tickets.find((ticket) => ticket.id === selectedTicketId) || null
  const selectedAnalysis = findAnalysis(sprint, selectedTicket)

  async function handleAnalyzeSprint() {
    if (!sprint) return
    setAnalyzingSprint(true)
    setMessage('')
    setError('')
    try {
      await triggerAnalysis(sprint.id)
      setSprint((current) => current ? { ...current, analysis_status: 'running' } : current)

      for (let attempt = 0; attempt < 60; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 2000))
        const latest = await getSprint(sprint.id)
        setSprint(latest)
        if (latest.analysis_status !== 'running') break
      }
      setMessage('Sprint 分析已更新。')
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
          <div className="sprint-selector">
            <span>{sprint.name}</span>
            <ChevronDown size={15} />
          </div>
          <button className="button button-primary" type="button" onClick={handleAnalyzeSprint} disabled={analyzingSprint}>
            {analyzingSprint ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />}
            {analyzingSprint ? '正在分析 Sprint' : '分析全部 Ticket'}
          </button>
        </div>
      </header>

      {(message || error) && (
        <div className={`workspace-toast${error ? ' is-error' : ''}`}>
          {error ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
          <span>{error || message}</span>
          <button type="button" onClick={() => { setMessage(''); setError('') }}>关闭</button>
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
              <button className="icon-button filter-button" type="button" title="筛选条件" aria-label="筛选条件">
                <Filter size={17} />
              </button>
            </div>
          </div>

          <div className="ticket-list-heading" aria-hidden="true">
            <span>Ticket</span>
            <span>优先级</span>
            <span>分析状态</span>
          </div>

          <div className="ticket-list">
            {filteredTickets.map((ticket) => {
              const analysis = ticket.analysis_data || analysisByTicketKey.get(ticket.key) || null
              const active = ticket.id === selectedTicketId
              return (
                <button
                  className={`ticket-row${active ? ' is-selected' : ''}`}
                  type="button"
                  key={ticket.id}
                  onClick={() => {
                    setSelectedTicketId(ticket.id)
                    setActiveTab('requirements')
                  }}
                >
                  <span className="ticket-main">
                    <span className="ticket-key"><FileText size={15} /> {ticket.key}</span>
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
              )
            })}
            {filteredTickets.length === 0 && (
              <div className="ticket-empty">
                <Search size={24} />
                <strong>没有匹配的 Ticket</strong>
                <span>调整关键词或筛选条件后重试。</span>
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
                    type="button"
                    role="tab"
                    aria-selected={activeTab === tabId}
                    className={activeTab === tabId ? 'is-active' : ''}
                    onClick={() => setActiveTab(tabId)}
                  >
                    <Icon size={17} />
                    {label}
                  </button>
                ))}
              </div>

              <div className="analysis-content">
                {activeTab === 'requirements' && (
                  <RequirementsPanel ticket={selectedTicket} analysis={selectedAnalysis} onAnalyze={handleAnalyzeTicket} loading={analyzingTicketId === selectedTicket.id} />
                )}
                {activeTab === 'code' && (
                  <CodeImpactPanel
                    ticketId={selectedTicket.id}
                    sprintId={selectedTicket.sprint_id}
                    summary={selectedTicket.summary}
                    description={selectedTicket.description}
                  />
                )}
                {activeTab === 'api' && (
                  <ApiPanel analysis={selectedAnalysis} />
                )}
                {activeTab === 'figma' && (
                  <FigmaPanel ticket={selectedTicket} onOpen={() => navigate('/figma-designs')} />
                )}
              </div>

              <footer className="analysis-actions">
                <button className="button button-secondary" type="button" onClick={handleAnalyzeTicket} disabled={analyzingTicketId === selectedTicket.id}>
                  {analyzingTicketId === selectedTicket.id ? <LoaderCircle className="spin" size={17} /> : <RefreshCw size={17} />}
                  {selectedAnalysis ? '重新分析 Ticket' : '分析 Ticket'}
                </button>
                <button className={`button ${selectedTicket.report_included === false ? 'button-primary' : 'button-success'}`} type="button" onClick={handleToggleReport} disabled={reportUpdating}>
                  {reportUpdating ? <LoaderCircle className="spin" size={17} /> : selectedTicket.report_included === false ? <FileText size={17} /> : <Check size={17} />}
                  {selectedTicket.report_included === false ? '加入报告' : '移出报告'}
                </button>
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

function Metadata({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="metadata-item">
      <span>{label}</span>
      <strong className={accent ? 'metadata-accent' : ''}>{value}</strong>
    </div>
  )
}

function RequirementsPanel({ ticket, analysis, onAnalyze, loading }: {
  ticket: TicketDetail
  analysis: TicketAnalysis | null
  onAnalyze: () => void
  loading: boolean
}) {
  if (!analysis) {
    return (
      <div className="analysis-empty full-pane">
        <Sparkles size={30} />
        <strong>当前 Ticket 尚未分析</strong>
        <span>AI 将结合 Jira 描述、验收标准和评论生成结构化分析。</span>
        <button className="button button-primary" type="button" onClick={onAnalyze} disabled={loading}>
          {loading ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />}
          开始分析
        </button>
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

function ApiPanel({ analysis }: { analysis: TicketAnalysis | null }) {
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
