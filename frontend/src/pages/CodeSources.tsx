import { useEffect, useState } from 'react'
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
  scanRepository,
  type CodeSource,
  type RepoSnapshot,
} from '../lib/api'
import { getApiErrorMessage } from '../lib/client'

const emptyForm = {
  name: '',
  provider: 'github',
  repo_url: '',
  default_branch: 'main',
  access_token: '',
}

export default function CodeSources() {
  const [sources, setSources] = useState<CodeSource[]>([])
  const [snapshots, setSnapshots] = useState<Record<number, RepoSnapshot | null>>({})
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [creating, setCreating] = useState(false)
  const [scanningId, setScanningId] = useState<number | null>(null)

  useEffect(() => { loadSources() }, [])

  async function loadSources() {
    try {
      const loadedSources = await listCodeSources()
      setSources(loadedSources)
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
    } catch {
      setSources([])
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate() {
    setCreating(true)
    try {
      await createCodeSource(form)
      setShowCreate(false)
      setForm(emptyForm)
      await loadSources()
    } catch {
      alert('创建失败')
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(id: number) {
    if (!confirm('确定要删除该代码源吗？')) return
    try {
      await deleteCodeSource(id)
      await loadSources()
    } catch {
      alert('删除失败')
    }
  }

  async function handleScan(id: number) {
    setScanningId(id)
    try {
      const snapshot = await scanRepository(id)
      setSnapshots((current) => ({ ...current, [id]: snapshot }))
      await loadSources()
    } catch (error: unknown) {
      alert(getApiErrorMessage(error, 'Scan failed'))
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

  return (
    <div className="workspace-page">
      <header className="workspace-header">
        <div>
          <span className="workspace-kicker">Code Impact Sources</span>
          <h1>Codebase</h1>
          <p>连接代码仓库并生成快照，为 Ticket 分析提供文件、语言和提交证据。</p>
        </div>
        <div className="workspace-header-actions">
          <button className="button button-primary" type="button" onClick={() => setShowCreate(true)}>
            <Plus size={17} />
            添加代码源
          </button>
        </div>
      </header>

      {sources.length === 0 ? (
        <section className="empty-state">
          <span className="empty-state-icon"><Braces size={23} /></span>
          <h2>连接第一个代码仓库</h2>
          <p>支持 GitHub、GitLab、Bitbucket 和本地仓库。扫描后可将文件结构关联到单个 Ticket。</p>
          <button className="button button-primary" type="button" onClick={() => setShowCreate(true)}>
            <Plus size={16} />
            添加代码源
          </button>
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
                  </div>
                  <StatusBadge status={source.scan_status} />
                </div>

                <div className="resource-meta">
                  <a href={source.repo_url} target="_blank" rel="noreferrer">
                    {source.repo_url.replace(/^https?:\/\//, '')} <ExternalLink size={11} />
                  </a>
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

                <div className="row-actions">
                  <button className="button button-primary button-small" type="button" onClick={() => handleScan(source.id)} disabled={scanningId === source.id}>
                    <RefreshCw className={scanningId === source.id ? 'spin' : ''} size={14} />
                    {scanningId === source.id ? '扫描中' : '扫描仓库'}
                  </button>
                  <button className="button button-danger button-small" type="button" onClick={() => handleDelete(source.id)}>
                    <Trash2 size={14} />
                    删除
                  </button>
                </div>
              </article>
            )
          })}
        </section>
      )}

      {showCreate && (
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
                <label className="form-field">
                  <span>名称</span>
                  <input type="text" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Backend Repository" />
                </label>
                <label className="form-field">
                  <span>提供商</span>
                  <select value={form.provider} onChange={(event) => setForm({ ...form, provider: event.target.value })}>
                    <option value="github">GitHub</option>
                    <option value="gitlab">GitLab</option>
                    <option value="bitbucket">Bitbucket</option>
                    <option value="local">Local</option>
                  </select>
                </label>
                <label className="form-field is-wide">
                  <span>仓库 URL</span>
                  <input type="url" value={form.repo_url} onChange={(event) => setForm({ ...form, repo_url: event.target.value })} placeholder="https://github.com/owner/repo" />
                </label>
                <label className="form-field">
                  <span>默认分支</span>
                  <span className="field-help">用于创建仓库快照</span>
                  <input type="text" value={form.default_branch} onChange={(event) => setForm({ ...form, default_branch: event.target.value })} placeholder="main" />
                </label>
                <label className="form-field">
                  <span>Access Token</span>
                  <span className="field-help">私有仓库需要只读权限</span>
                  <input type="password" value={form.access_token} onChange={(event) => setForm({ ...form, access_token: event.target.value })} placeholder="可选" />
                </label>
              </div>
              <div className="modal-actions">
                <button className="button" type="button" onClick={() => setShowCreate(false)}>取消</button>
                <button className="button button-primary" type="button" onClick={handleCreate} disabled={creating || !form.name || !form.repo_url}>
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
        : 'is-warning'

  return <span className={`status-badge ${className}`}>{statusLabel(status)}</span>
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: '待扫描',
    scanning: '扫描中',
    done: '已扫描',
    failed: '扫描失败',
  }
  return labels[status] || status
}
