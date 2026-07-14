import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  Braces,
  CheckCircle2,
  ChevronRight,
  FileSearch,
  FileText,
  FolderKanban,
  Import,
  LoaderCircle,
  PenTool,
  Plus,
  ScanSearch,
  Sparkles,
  TestTube2,
  X,
} from 'lucide-react'

import {
  importSprint,
  listProjects,
  listSprints,
  type Project,
  type Sprint,
} from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { getApiErrorMessage } from '../lib/client'
import './DashboardWorkspace.css'

const workflowSteps = [
  { icon: FolderKanban, title: '连接 Jira 项目', description: '保存项目与 Jira 访问配置' },
  { icon: Import, title: '导入 Sprint', description: '同步 Ticket、描述与验收标准' },
  { icon: Sparkles, title: '运行 AI 分析', description: '提炼需求并识别实现影响' },
  { icon: FileText, title: '生成分析报告', description: '核对结果并分享给团队' },
]

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [sprintsMap, setSprintsMap] = useState<Record<number, Sprint[]>>({})
  const [loading, setLoading] = useState(true)
  const [importProject, setImportProject] = useState<Project | null>(null)
  const [sprintName, setSprintName] = useState('')
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState('')
  const isAdmin = user?.role === 'admin'
  const canImport = isAdmin || user?.role === 'member'

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    setError('')
    try {
      const loadedProjects = await listProjects()
      setProjects(loadedProjects)
      const entries = await Promise.all(
        loadedProjects.map(async (project) => {
          try {
            return [project.id, await listSprints(project.id), false] as const
          } catch {
            return [project.id, [] as Sprint[], true] as const
          }
        }),
      )
      setSprintsMap(Object.fromEntries(entries.map(([projectId, sprints]) => [projectId, sprints])))
      if (entries.some(([, , failed]) => failed)) {
        setError('部分项目的 Sprint 数据加载失败，请稍后刷新重试。')
      }
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '仪表盘数据加载失败。'))
    } finally {
      setLoading(false)
    }
  }

  async function handleImport() {
    if (!canImport) {
      setError('当前角色没有导入 Sprint 的权限。')
      return
    }
    if (!importProject || !sprintName.trim()) return
    setImporting(true)
    setError('')
    try {
      const sprint = await importSprint(importProject.id, sprintName.trim())
      setImportProject(null)
      setSprintName('')
      navigate(`/sprint/${sprint.id}`)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Sprint 导入失败。'))
    } finally {
      setImporting(false)
    }
  }

  const allSprints = useMemo(
    () => Object.values(sprintsMap).flat(),
    [sprintsMap],
  )
  const activeSprints = allSprints.filter((sprint) => sprint.state === 'active').length
  const analyzedSprints = allSprints.filter((sprint) => sprint.analysis_status === 'done').length
  const totalTickets = allSprints.reduce((sum, sprint) => sum + sprint.total_tickets, 0)

  if (loading) {
    return (
      <div className="dashboard-loading">
        <LoaderCircle className="spin" size={23} />
        <span>正在加载分析主页...</span>
      </div>
    )
  }

  return (
    <div className="dashboard-workspace">
      <header className="dashboard-header">
        <div>
          <span className="dashboard-eyebrow">ScopePilot Workspace</span>
          <h1>分析主页</h1>
          <p>从 Jira Sprint 到需求、代码、API 与设计影响的一站式分析。</p>
        </div>
        {isAdmin && <button className="button button-primary" type="button" onClick={() => navigate('/projects')}>
          <Plus size={17} />
          创建项目
        </button>}
      </header>

      {error && (
        <div className="dashboard-error">
          <span>{error}</span>
          <button type="button" onClick={() => setError('')}>关闭</button>
        </div>
      )}

      {projects.length === 0 && error ? null : projects.length === 0 ? (
        <EmptyDashboard canCreate={isAdmin} onCreate={() => navigate('/projects')} />
      ) : (
        <>
          <section className="dashboard-metrics" aria-label="Workspace metrics">
            <Metric label="项目" value={projects.length} detail="已连接 Jira" icon={FolderKanban} />
            <Metric label="活跃 Sprint" value={activeSprints} detail={`共 ${allSprints.length} 个 Sprint`} icon={ScanSearch} />
            <Metric label="Ticket" value={totalTickets} detail="已同步到工作区" icon={FileSearch} />
            <Metric label="已完成分析" value={analyzedSprints} detail="可生成报告" icon={CheckCircle2} />
          </section>

          <section className="dashboard-section">
            <div className="dashboard-section-header">
              <div>
                <h2>项目与 Sprint</h2>
                <p>选择 Sprint 进入单票分析工作台，或从 Jira 导入新的 Sprint。</p>
              </div>
              <button className="text-button" type="button" onClick={() => navigate('/projects')}>
                管理项目 <ArrowRight size={15} />
              </button>
            </div>

            <div className="project-list">
              <div className="project-list-heading" aria-hidden="true">
                <span>项目</span>
                <span>Jira Key</span>
                <span>Sprint</span>
                <span>最近状态</span>
                <span>操作</span>
              </div>
              {projects.map((project) => {
                const sprints = sprintsMap[project.id] || []
                const latestSprint = sprints[sprints.length - 1]
                return (
                  <div className="project-row" key={project.id}>
                    <div className="project-name">
                      <span><FolderKanban size={18} /></span>
                      <strong>{project.name}</strong>
                    </div>
                    <code>{project.jira_project_key}</code>
                    <span>{sprints.length}</span>
                    <span className={`sprint-state is-${latestSprint?.analysis_status || 'pending'}`}>
                      {latestSprint ? analysisLabel(latestSprint.analysis_status) : '尚未导入'}
                    </span>
                    <div className="project-actions">
                      {latestSprint && (
                        <button className="button button-secondary" type="button" onClick={() => navigate(`/sprint/${latestSprint.id}`)}>
                          继续分析 <ChevronRight size={15} />
                        </button>
                      )}
                      {canImport && <button className="button button-primary" type="button" onClick={() => { setImportProject(project); setSprintName('') }}>
                        <Import size={15} /> 导入 Sprint
                      </button>}
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          <section className="dashboard-section source-overview">
            <div className="dashboard-section-header">
              <div>
                <h2>影响分析数据源</h2>
                <p>按需连接代码、接口与设计数据，为 Ticket 分析补充证据。</p>
              </div>
            </div>
            <div className="source-links">
              <SourceLink icon={Braces} title="Codebase" description="扫描仓库并定位受影响文件" onClick={() => navigate('/code-sources')} />
              <SourceLink icon={TestTube2} title="API 测试" description="导入 OpenAPI 并生成测试计划" onClick={() => navigate('/api-test-plans')} />
              <SourceLink icon={PenTool} title="Figma" description="分析设计稿与后端实现影响" onClick={() => navigate('/figma-designs')} />
            </div>
          </section>
        </>
      )}

      {canImport && importProject && (
        <div className="dashboard-modal-backdrop" role="presentation" onMouseDown={() => setImportProject(null)}>
          <div className="dashboard-modal" role="dialog" aria-modal="true" aria-labelledby="import-sprint-title" onMouseDown={(event) => event.stopPropagation()}>
            <div className="dashboard-modal-header">
              <div>
                <h2 id="import-sprint-title">导入 Sprint</h2>
                <p>从 {importProject.name} 的 Jira 项目同步 Sprint 与 Ticket。</p>
              </div>
              <button className="icon-button" type="button" aria-label="关闭" title="关闭" onClick={() => setImportProject(null)}>
                <X size={18} />
              </button>
            </div>
            <label className="dashboard-field">
              <span>Sprint 名称</span>
              <input
                type="text"
                placeholder="例如：LPRO Sprint 0707"
                value={sprintName}
                onChange={(event) => setSprintName(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && handleImport()}
                autoFocus
              />
            </label>
            <div className="dashboard-modal-actions">
              <button className="button button-secondary" type="button" onClick={() => setImportProject(null)}>取消</button>
              <button className="button button-primary" type="button" onClick={handleImport} disabled={importing || !sprintName.trim()}>
                {importing ? <LoaderCircle className="spin" size={16} /> : <Import size={16} />}
                {importing ? '正在导入' : '导入 Sprint'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function EmptyDashboard({ canCreate, onCreate }: { canCreate: boolean; onCreate: () => void }) {
  return (
    <section className="dashboard-empty">
      <div className="empty-intro">
        <span className="empty-icon"><ScanSearch size={25} /></span>
        <div>
          <span className="dashboard-eyebrow">开始使用 ScopePilot</span>
          <h2>完成第一次 Sprint 影响分析</h2>
          <p>{canCreate
            ? '先连接 Jira 项目，然后导入 Sprint。ScopePilot 会按 Ticket 提炼需求，并关联代码、API 与设计影响。'
            : '当前工作区还没有项目，请联系管理员创建并连接 Jira 项目。'}</p>
        </div>
        {canCreate && <button className="button button-primary empty-primary-action" type="button" onClick={onCreate}>
          <Plus size={17} />
          创建并连接项目
        </button>}
      </div>

      <div className="workflow-steps">
        {workflowSteps.map(({ icon: Icon, title, description }, index) => (
          <div className="workflow-step" key={title}>
            <div className="workflow-step-top">
              <span className="workflow-step-icon"><Icon size={19} /></span>
              <span className="workflow-step-number">0{index + 1}</span>
            </div>
            <strong>{title}</strong>
            <p>{description}</p>
            {index < workflowSteps.length - 1 && <ChevronRight className="workflow-arrow" size={17} />}
          </div>
        ))}
      </div>

      {canCreate && <div className="empty-footer">
        <span>已有项目？</span>
        <button type="button" onClick={onCreate}>前往项目页配置 Jira <ArrowRight size={15} /></button>
      </div>}
    </section>
  )
}

function Metric({ label, value, detail, icon: Icon }: {
  label: string
  value: number
  detail: string
  icon: typeof FolderKanban
}) {
  return (
    <div className="dashboard-metric">
      <span className="metric-icon"><Icon size={18} /></span>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </div>
  )
}

function SourceLink({ icon: Icon, title, description, onClick }: {
  icon: typeof Braces
  title: string
  description: string
  onClick: () => void
}) {
  return (
    <button className="source-link" type="button" onClick={onClick}>
      <span><Icon size={19} /></span>
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
      <ChevronRight size={17} />
    </button>
  )
}

function analysisLabel(status: string) {
  const labels: Record<string, string> = {
    done: '分析完成',
    running: '分析中',
    partial: '部分完成',
    failed: '分析失败',
    pending: '待分析',
  }
  return labels[status] || status
}
