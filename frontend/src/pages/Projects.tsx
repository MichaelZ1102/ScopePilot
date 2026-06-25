import { useState, useEffect, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  listProjects,
  createProject,
  deleteProject,
  importSprint,
  type Project,
} from '../lib/api'

const styles = {
  page: { maxWidth: 1000, margin: '0 auto' },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '1.5rem',
  },
  title: { fontSize: '1.5rem', fontWeight: 700, color: '#1a1a2e' },
  btn: {
    padding: '0.5rem 1.2rem',
    border: 'none',
    borderRadius: 6,
    cursor: 'pointer',
    fontSize: '0.9rem',
    fontWeight: 600,
    color: '#fff',
  },
  btnPrimary: { background: '#4fc3f7' },
  btnDark: { background: '#1a1a2e' },
  btnDanger: { background: '#e74c3c' },
  btnSmall: { padding: '0.35rem 0.8rem', fontSize: '0.8rem' },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
    gap: '1rem',
  },
  card: {
    background: '#fff',
    borderRadius: 10,
    padding: '1.25rem',
    boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
    border: '1px solid #eee',
  },
  cardTitle: { fontSize: '1.1rem', fontWeight: 600, color: '#1a1a2e', marginBottom: '0.4rem' },
  cardText: { fontSize: '0.85rem', color: '#888', marginBottom: '0.2rem' },
  cardActions: {
    display: 'flex',
    gap: '0.5rem',
    marginTop: '0.75rem',
    flexWrap: 'wrap' as const,
  },
  empty: {
    textAlign: 'center' as const,
    color: '#888',
    padding: '3rem',
    background: '#fff',
    borderRadius: 10,
  },
  // Modal / Form
  modalOverlay: {
    position: 'fixed' as const,
    inset: 0,
    background: 'rgba(0,0,0,0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 100,
  },
  modal: {
    background: '#fff',
    borderRadius: 12,
    padding: '2rem',
    width: '100%',
    maxWidth: 500,
    boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
    maxHeight: '90vh',
    overflow: 'auto',
  },
  modalTitle: { fontSize: '1.2rem', fontWeight: 600, marginBottom: '0.5rem', color: '#1a1a2e' },
  modalSub: { fontSize: '0.85rem', color: '#888', marginBottom: '1.25rem' },
  label: {
    display: 'block',
    color: '#555',
    fontSize: '0.85rem',
    fontWeight: 500,
    marginBottom: '0.3rem',
  },
  input: {
    width: '100%',
    padding: '0.6rem 0.8rem',
    borderRadius: 6,
    border: '1px solid #ddd',
    fontSize: '0.9rem',
    marginBottom: '1rem',
    boxSizing: 'border-box' as const,
  },
  modalActions: { display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' as const, marginTop: '1rem' },
}

export default function Projects() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)

  // Create project form
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({
    name: '',
    jira_url: '',
    jira_email: '',
    jira_api_token: '',
    jira_project_key: '',
  })
  const [creating, setCreating] = useState(false)

  // Import dialog
  const [importProject, setImportProject] = useState<Project | null>(null)
  const [sprintName, setSprintName] = useState('')
  const [importing, setImporting] = useState(false)

  useEffect(() => {
    loadProjects()
  }, [])

  async function loadProjects() {
    try {
      const data = await listProjects()
      setProjects(data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    setCreating(true)
    try {
      await createProject(form)
      setShowCreate(false)
      setForm({ name: '', jira_url: '', jira_email: '', jira_api_token: '', jira_project_key: '' })
      await loadProjects()
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? ((err as { response: { data: { detail: string } } }).response?.data?.detail ?? '创建失败')
          : '创建失败'
      alert(msg)
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(id: number) {
    if (!confirm('确定要删除该项目吗？')) return
    try {
      await deleteProject(id)
      setProjects((prev) => prev.filter((p) => p.id !== id))
    } catch {
      alert('删除失败')
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
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? ((err as { response: { data: { detail: string } } }).response?.data?.detail ?? '导入失败')
          : '导入失败'
      alert(msg)
    } finally {
      setImporting(false)
    }
  }

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '3rem', color: '#888' }}>加载中...</div>
  }

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <h2 style={styles.title}>📁 项目管理</h2>
        <button
          style={{ ...styles.btn, ...styles.btnPrimary }}
          onClick={() => setShowCreate(true)}
        >
          + 新建项目
        </button>
      </div>

      {projects.length === 0 ? (
        <div style={styles.empty}>
          <p style={{ marginBottom: '0.75rem' }}>暂无项目，点击上方按钮创建你的第一个项目</p>
        </div>
      ) : (
        <div style={styles.grid}>
          {projects.map((p) => (
            <div key={p.id} style={styles.card}>
              <div style={styles.cardTitle}>{p.name}</div>
              <div style={styles.cardText}>Jira: {p.jira_url}</div>
              <div style={styles.cardText}>项目密钥: {p.jira_project_key}</div>
              <div style={styles.cardText}>创建时间: {p.created_at?.slice(0, 10) || '-'}</div>
              <div style={styles.cardActions}>
                <button
                  style={{ ...styles.btn, ...styles.btnDark, ...styles.btnSmall }}
                  onClick={() => {
                    setImportProject(p)
                    setSprintName('')
                  }}
                >
                  导入 Sprint
                </button>
                <button
                  style={{ ...styles.btn, ...styles.btnDanger, ...styles.btnSmall }}
                  onClick={() => handleDelete(p.id)}
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Project Modal */}
      {showCreate && (
        <div style={styles.modalOverlay} onClick={() => setShowCreate(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalTitle}>新建项目</div>
            <div style={styles.modalSub}>配置 Jira 连接信息以导入 Sprint</div>
            <form onSubmit={handleCreate}>
              <label style={styles.label}>项目名称</label>
              <input
                style={styles.input}
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="My Project"
                required
              />

              <label style={styles.label}>Jira URL</label>
              <input
                style={styles.input}
                type="url"
                value={form.jira_url}
                onChange={(e) => setForm({ ...form, jira_url: e.target.value })}
                placeholder="https://your-domain.atlassian.net"
                required
              />

              <label style={styles.label}>Jira 邮箱</label>
              <input
                style={styles.input}
                type="email"
                value={form.jira_email}
                onChange={(e) => setForm({ ...form, jira_email: e.target.value })}
                placeholder="you@example.com"
                required
              />

              <label style={styles.label}>Jira API Token</label>
              <input
                style={styles.input}
                type="password"
                value={form.jira_api_token}
                onChange={(e) => setForm({ ...form, jira_api_token: e.target.value })}
                placeholder="Your Jira API token"
                required
              />

              <label style={styles.label}>Jira 项目密钥</label>
              <input
                style={styles.input}
                type="text"
                value={form.jira_project_key}
                onChange={(e) => setForm({ ...form, jira_project_key: e.target.value })}
                placeholder="e.g. LPRO, SCRUM"
                required
              />

              <div style={styles.modalActions}>
                <button
                  type="button"
                  style={{ ...styles.btn, background: '#ccc', color: '#333' }}
                  onClick={() => setShowCreate(false)}
                >
                  取消
                </button>
                <button
                  type="submit"
                  style={{ ...styles.btn, ...styles.btnPrimary }}
                  disabled={creating}
                >
                  {creating ? '创建中...' : '创建'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Import Sprint Dialog */}
      {importProject && (
        <div style={styles.modalOverlay} onClick={() => setImportProject(null)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalTitle}>导入 Sprint</div>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
              项目: {importProject.name}
            </p>
            <label style={styles.label}>Sprint 名称</label>
            <input
              style={styles.input}
              type="text"
              placeholder="如: LPRO Sprint 0707"
              value={sprintName}
              onChange={(e) => setSprintName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleImport()}
              autoFocus
            />
            <div style={styles.modalActions}>
              <button
                style={{ ...styles.btn, background: '#ccc', color: '#333' }}
                onClick={() => setImportProject(null)}
              >
                取消
              </button>
              <button
                style={{ ...styles.btn, ...styles.btnPrimary }}
                onClick={handleImport}
                disabled={importing || !sprintName.trim()}
              >
                {importing ? '导入中...' : '导入'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
