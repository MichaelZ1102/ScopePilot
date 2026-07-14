import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Braces,
  ExternalLink,
  LoaderCircle,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from 'lucide-react'

import {
  createCodeSource,
  deleteCodeSource,
  getLatestSnapshot,
  listCodeSources,
  listProjects,
  scanRepository,
  type CodeSource,
  type Project,
  type RepoSnapshot,
} from '../lib/api'
import { getApiErrorMessage } from '../lib/client'
import { useAuth } from '../lib/AuthContext'

const emptyForm = {
  project_id: '',
  name: '',
  provider: 'github',
  repo_url: '',
  default_branch: 'main',
  access_token: '',
}

export default function CodeSources() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedProjectId = Number(searchParams.get('project_id'))
  const projectId = Number.isFinite(requestedProjectId) && requestedProjectId > 0 ? requestedProjectId : undefined
  const [sources, setSources] = useState<CodeSource[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [snapshots, setSnapshots] = useState<Record<number, RepoSnapshot | null>>({})
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [creating, setCreating] = useState(false)
  const [scanningId, setScanningId] = useState<number | null>(null)
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')

  useEffect(() => { loadSources() }, [projectId])

  async function loadSources() {
    setLoading(true)
    setLoadError('')
    try {
      const [loadedSources, loadedProjects] = await Promise.all([listCodeSources(projectId), listProjects()])
      setSources(loadedSources)
      setProjects(loadedProjects)
      const entries = await Promise.all(
        loadedSources.map(async (source) => {
          try {
            return [source.id, await getLatestSnapshot(source.id)] as const
          } catch {
            return [source.id, null] as const
          }
        }),
      )
      setSnapshots(Object.fromEntries(entries))
    } catch (error: unknown) {
      setSources([])
      setLoadError(getApiErrorMessage(error, '代码源加载失败，请稍后重试。'))
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate() {
    setCreating(true)
    setActionError('')
    try {
      await createCodeSource({ ...form, project_id: Number(form.project_id) })
      setShowCreate(false)
      setForm(emptyForm)
      await loadSources()
    } catch (error: unknown) {
      setActionError(getApiErrorMessage(error, '创建失败'))
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(id: number) {
    if (!confirm('确定要删除该代码源吗？')) return
    try {
      await deleteCodeSource(id)
      await loadSources()
    } catch (error: unknown) {
      setActionError(getApiErrorMessage(error, '删除失败'))
    }
  }

  async function handleScan(id: number) {
    setScanningId(id)
    setActionError('')
    try {
      const snapshot = await scanRepository(id)
      setSnapshots((current) => ({ ...current, [id]: snapshot }))
      await loadSources()
    } catch (error: unknown) {
      setActionError(getApiErrorMessage(error, '扫描失败'))
    } finally {
      setScanningId(null)
    }
  }

  if (loading) {
    return (
      <div className="loading-state">
        <span className="loading-state-icon"><LoaderCircle className="spin" size={22} /></span>
        <p>正在加载代码源...</p>
      </div>
    )
  }
  const canWrite = user?.role === 'admin' || user?.role === 'member'

  return (
    <div className="workspace-page">
      <header className="workspace-header">
        <div>
          <span className="workspace-kicker">Code Impact Sources</span>
          <h1>Codebase</h1>
          <p>连接代码仓库并生成快照，为 Ticket 分析提供文件、语言和提交证据。</p>
        </div>
        <div className="workspace-header-actions">
          <select
            className="toolbar-input"
            aria-label="按项目筛选代码源"
            value={projectId || ''}
            onChange={(event) => {
              const next = new URLSearchParams(searchParams)
              if (event.target.value) next.set('project_id', event.target.value)
              else next.delete('project_id')
              setSearchParams(next)
            }}
          >
            <option value="">全部项目</option>
            {projects.map((project) => <option value={project.id} key={project.id}>{project.name}</option>)}
          </select>
          {canWrite && <button className="button button-primary" type="button" onClick={() => { setForm({ ...emptyForm, project_id: projectId ? String(projectId) : '' }); setShowCreate(true) }}>
            <Plus size={17} />
            添加代码源
          </button>}
        </div>
      </header>

      {(loadError || actionError) && <div className="inline-error" role="alert">{loadError || actionError}</div>}

      {loadError ? null : sources.length === 0 ? (
        <section className="empty-state">
          <span className="empty-state-icon"><Braces size={23} /></span>
          <h2>连接第一个代码仓库</h2>
          <p>支持 GitHub；开发环境可扫描管理员配置的本地目录。GitLab 和 Bitbucket 暂未开放。</p>
          {canWrite && <button className="button button-primary" type="button" onClick={() => { setForm({ ...emptyForm, project_id: projectId ? String(projectId) : '' }); setShowCreate(true) }}>
            <Plus size={16} />
            添加代码源
          </button>}
        </section>
      ) : (
        <section className="resource-grid">
          {sources.map((source) => {
            const snapshot = snapshots[source.id]
            return (
              <article className="resource-card" key={source.id}>
                <div className="resource-card-header">
                  <span className="resource-icon"><Braces size={19} /></span>
                  <div>
                    <h2>{source.name}</h2>
                    <p>{source.provider} / {source.default_branch}</p>
                    {source.project_id && <small>{projects.find((project) => project.id === source.project_id)?.name || `Project #${source.project_id}`}</small>}
                  </div>
                  <StatusBadge status={['github', 'local'].includes(source.provider) ? source.scan_status : 'unsupported'} />
                </div>

                <div className="resource-meta">
                  {source.provider === 'local' ? (
                    <code>{source.repo_url}</code>
                  ) : (
                    <a href={source.repo_url} target="_blank" rel="noreferrer">
                      {source.repo_url.replace(/^https?:\/\//, '')} <ExternalLink size={11} />
                    </a>
                  )}
                </div>

                <div className="resource-summary">
                  <span>文件<strong>{snapshot?.total_files ?? '-'}</strong></span>
                  <span>代码行<strong>{snapshot?.total_lines ?? '-'}</strong></span>
                  <span>Commit<strong>{snapshot?.commit_sha?.slice(0, 7) || '-'}</strong></span>
                </div>

                {snapshot?.language_breakdown && (
                  <div className="tag-list">
                    {Object.entries(snapshot.language_breakdown).slice(0, 5).map(([language, bytes]) => (
                      <span className="tag" key={language}>{language} · {(Number(bytes) / 1024).toFixed(0)}KB</span>
                    ))}
                  </div>
                )}

                {canWrite && <div className="row-actions">
                  <button className="button button-primary button-small" type="button" onClick={() => handleScan(source.id)} disabled={scanningId === source.id || !['github', 'local'].includes(source.provider)}>
                    <RefreshCw className={scanningId === source.id ? 'spin' : ''} size={14} />
                    {scanningId === source.id ? '扫描中' : '扫描仓库'}
                  </button>
                  <button className="button button-danger button-small" type="button" onClick={() => handleDelete(source.id)}>
                    <Trash2 size={14} />
                    删除
                  </button>
                </div>}
              </article>
            )
          })}
        </section>
      )}

      {canWrite && showCreate && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setShowCreate(false)}>
          <div className="workspace-modal" role="dialog" aria-modal="true" aria-labelledby="create-source-title" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2 id="create-source-title">添加代码源</h2>
                <p>连接仓库后，ScopePilot 会读取结构与语言信息用于影响分析。</p>
              </div>
              <button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={() => setShowCreate(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <div className="form-grid">
                <label className="form-field is-wide">
                  <span>所属项目</span>
                  <select value={form.project_id} onChange={(event) => setForm({ ...form, project_id: event.target.value })} required>
                    <option value="">选择项目</option>
                    {projects.map((project) => <option value={project.id} key={project.id}>{project.name}</option>)}
                  </select>
                </label>
                <label className="form-field">
                  <span>名称</span>
                  <input type="text" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Backend Repository" />
                </label>
                <label className="form-field">
                  <span>提供商</span>
                  <select value={form.provider} onChange={(event) => setForm({ ...form, provider: event.target.value, repo_url: '', access_token: '' })}>
                    <option value="github">GitHub</option>
                    <option value="gitlab" disabled>GitLab（暂不支持）</option>
                    <option value="bitbucket" disabled>Bitbucket（暂不支持）</option>
                    <option value="local">Local（仅限开发环境允许目录）</option>
                  </select>
                </label>
                <label className="form-field is-wide">
                  <span>{form.provider === 'local' ? '本地仓库路径' : '仓库 URL'}</span>
                  <span className="field-help">{form.provider === 'local' ? '路径必须位于服务端配置的允许目录内' : '仅支持 GitHub 仓库根 URL'}</span>
                  <input type={form.provider === 'local' ? 'text' : 'url'} value={form.repo_url} onChange={(event) => setForm({ ...form, repo_url: event.target.value })} placeholder={form.provider === 'local' ? 'C:\\repos\\my-project' : 'https://github.com/owner/repo'} />
                </label>
                <label className="form-field">
                  <span>默认分支</span>
                  <span className="field-help">用于创建仓库快照</span>
                  <input type="text" value={form.default_branch} onChange={(event) => setForm({ ...form, default_branch: event.target.value })} placeholder="main" />
                </label>
                {form.provider !== 'local' && <label className="form-field">
                  <span>Access Token</span>
                  <span className="field-help">私有仓库需要只读权限</span>
                  <input type="password" value={form.access_token} onChange={(event) => setForm({ ...form, access_token: event.target.value })} placeholder="可选" />
                </label>}
              </div>
              <div className="modal-actions">
                <button className="button" type="button" onClick={() => setShowCreate(false)}>取消</button>
                <button className="button button-primary" type="button" onClick={handleCreate} disabled={creating || !form.project_id || !form.name || !form.repo_url}>
                  {creating ? <LoaderCircle className="spin" size={15} /> : <Plus size={15} />}
                  {creating ? '创建中' : '创建代码源'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const className = status === 'done'
    ? 'is-success'
    : status === 'failed'
      ? 'is-danger'
      : status === 'scanning'
        ? 'is-info'
        : status === 'unsupported'
          ? 'is-warning'
        : 'is-warning'

  return <span className={`status-badge ${className}`}>{statusLabel(status)}</span>
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: '待扫描',
    scanning: '扫描中',
    done: '已扫描',
    failed: '扫描失败',
    unsupported: '暂不支持',
  }
  return labels[status] || status
}
