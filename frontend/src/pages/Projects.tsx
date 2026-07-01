import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  ExternalLink,
  FolderKanban,
  Import,
  LoaderCircle,
  Plus,
  Trash2,
  X,
} from 'lucide-react'

import { createProject, deleteProject, importSprint, listProjects, type Project } from '../lib/api'
import { getApiErrorMessage } from '../lib/client'

const emptyForm = {
  name: '',
  jira_url: '',
  jira_email: '',
  jira_api_token: '',
  jira_project_key: '',
}

export default function Projects() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [creating, setCreating] = useState(false)
  const [importProject, setImportProject] = useState<Project | null>(null)
  const [sprintName, setSprintName] = useState('')
  const [importing, setImporting] = useState(false)

  useEffect(() => { loadProjects() }, [])

  async function loadProjects() {
    try {
      setProjects(await listProjects())
    } catch {
      setProjects([])
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    setCreating(true)
    try {
      await createProject(form)
      setShowCreate(false)
      setForm(emptyForm)
      await loadProjects()
    } catch (error: unknown) {
      alert(getApiErrorMessage(error, t('projects.create_failed')))
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(id: number) {
    if (!confirm(t('projects.delete_confirm'))) return
    try {
      await deleteProject(id)
      setProjects((current) => current.filter((project) => project.id !== id))
    } catch {
      alert(t('projects.delete_failed'))
    }
  }

  async function handleImport() {
    if (!importProject || !sprintName.trim()) return
    setImporting(true)
    try {
      const sprint = await importSprint(importProject.id, sprintName.trim())
      setImportProject(null)
      setSprintName('')
      navigate(`/sprint/${sprint.id}`)
    } catch (error: unknown) {
      alert(getApiErrorMessage(error, t('projects.import_failed')))
    } finally {
      setImporting(false)
    }
  }

  if (loading) {
    return (
      <div className="loading-state">
        <span className="loading-state-icon"><LoaderCircle className="spin" size={22} /></span>
        <p>{t('dashboard.loading')}</p>
      </div>
    )
  }

  return (
    <div className="workspace-page">
      <header className="workspace-header">
        <div>
          <span className="workspace-kicker">Jira Workspace</span>
          <h1>项目</h1>
          <p>连接 Jira 项目并导入 Sprint，建立 Ticket 分析的数据入口。</p>
        </div>
        <div className="workspace-header-actions">
          <button className="button button-primary" type="button" onClick={() => setShowCreate(true)}>
            <Plus size={17} />
            新建项目
          </button>
        </div>
      </header>

      {projects.length === 0 ? (
        <section className="empty-state">
          <span className="empty-state-icon"><FolderKanban size={23} /></span>
          <h2>连接第一个 Jira 项目</h2>
          <p>保存 Jira 地址、项目 Key 和访问凭据后，即可按 Sprint 同步 Ticket 并开始分析。</p>
          <button className="button button-primary" type="button" onClick={() => setShowCreate(true)}>
            <Plus size={16} />
            新建项目
          </button>
        </section>
      ) : (
        <section className="resource-grid">
          {projects.map((project) => (
            <article className="resource-card" key={project.id}>
              <div className="resource-card-header">
                <span className="resource-icon"><FolderKanban size={19} /></span>
                <div>
                  <h2>{project.name}</h2>
                  <p>{project.jira_project_key}</p>
                </div>
                <span className="status-badge is-success">已连接</span>
              </div>

              <div className="resource-summary">
                <span>Jira Key<strong>{project.jira_project_key}</strong></span>
                <span>创建日期<strong>{project.created_at?.slice(0, 10) || '-'}</strong></span>
                <span>数据源<strong>Jira Cloud</strong></span>
              </div>

              <div className="resource-meta">
                <a href={project.jira_url} target="_blank" rel="noreferrer">
                  {project.jira_url.replace(/^https?:\/\//, '')} <ExternalLink size={11} />
                </a>
              </div>

              <div className="row-actions">
                <button className="button button-primary button-small" type="button" onClick={() => { setImportProject(project); setSprintName('') }}>
                  <Import size={14} />
                  {t('projects.import_btn')}
                </button>
                <button className="button button-danger button-small" type="button" onClick={() => handleDelete(project.id)}>
                  <Trash2 size={14} />
                  {t('projects.delete_btn')}
                </button>
              </div>
            </article>
          ))}
        </section>
      )}

      {showCreate && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setShowCreate(false)}>
          <div className="workspace-modal" role="dialog" aria-modal="true" aria-labelledby="create-project-title" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2 id="create-project-title">{t('projects.create_title')}</h2>
                <p>{t('projects.create_subtitle')}</p>
              </div>
              <button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={() => setShowCreate(false)}>
                <X size={18} />
              </button>
            </div>
            <form className="modal-body" onSubmit={handleCreate}>
              <div className="form-grid">
                <label className="form-field is-wide">
                  <span>{t('projects.create_name')}</span>
                  <input type="text" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="My Project" required />
                </label>
                <label className="form-field is-wide">
                  <span>{t('projects.create_jira_url')}</span>
                  <input type="url" value={form.jira_url} onChange={(event) => setForm({ ...form, jira_url: event.target.value })} placeholder="https://your-domain.atlassian.net" required />
                </label>
                <label className="form-field">
                  <span>{t('projects.create_jira_email')}</span>
                  <input type="email" value={form.jira_email} onChange={(event) => setForm({ ...form, jira_email: event.target.value })} placeholder="you@example.com" required />
                </label>
                <label className="form-field">
                  <span>{t('projects.create_jira_key')}</span>
                  <input type="text" value={form.jira_project_key} onChange={(event) => setForm({ ...form, jira_project_key: event.target.value })} placeholder="LPRO" required />
                </label>
                <label className="form-field is-wide">
                  <span>{t('projects.create_jira_token')}</span>
                  <input type="password" value={form.jira_api_token} onChange={(event) => setForm({ ...form, jira_api_token: event.target.value })} placeholder="Jira API token" required />
                </label>
              </div>
              <div className="modal-actions">
                <button className="button" type="button" onClick={() => setShowCreate(false)}>{t('projects.cancel')}</button>
                <button className="button button-primary" type="submit" disabled={creating}>
                  {creating && <LoaderCircle className="spin" size={15} />}
                  {creating ? t('projects.creating') : t('projects.create_btn')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {importProject && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setImportProject(null)}>
          <div className="workspace-modal" role="dialog" aria-modal="true" aria-labelledby="import-project-title" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2 id="import-project-title">{t('projects.import_title')}</h2>
                <p>{t('projects.import_project_label')}: {importProject.name}</p>
              </div>
              <button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={() => setImportProject(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <label className="form-field">
                <span>{t('projects.import_label')}</span>
                <input type="text" placeholder={t('projects.import_placeholder')} value={sprintName} onChange={(event) => setSprintName(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && handleImport()} autoFocus />
              </label>
              <div className="modal-actions">
                <button className="button" type="button" onClick={() => setImportProject(null)}>{t('projects.import_cancel')}</button>
                <button className="button button-primary" type="button" onClick={handleImport} disabled={importing || !sprintName.trim()}>
                  {importing ? <LoaderCircle className="spin" size={15} /> : <Import size={15} />}
                  {importing ? t('projects.importing') : t('projects.import_confirm')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
