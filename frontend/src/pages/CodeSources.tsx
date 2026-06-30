import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  listCodeSources, createCodeSource, deleteCodeSource, scanRepository, getLatestSnapshot,
  type CodeSource, type RepoSnapshot,
} from '../lib/api'

const styles: any = {
  page: { maxWidth: 1000, margin: '0 auto' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' },
  title: { fontSize: '1.5rem', fontWeight: 700, color: '#1a1a2e' },
  btn: { padding: '0.5rem 1.2rem', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600, color: '#fff' },
  btnPrimary: { background: '#4fc3f7' },
  btnDark: { background: '#1a1a2e' },
  btnDanger: { background: '#e74c3c' },
  btnSmall: { padding: '0.35rem 0.8rem', fontSize: '0.8rem' },
  btnSuccess: { background: '#81c784' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '1rem' },
  card: { background: '#fff', borderRadius: 10, padding: '1.25rem', boxShadow: '0 1px 4px rgba(0,0,0,0.06)', border: '1px solid #eee' },
  cardTitle: { fontSize: '1.1rem', fontWeight: 600, color: '#1a1a2e', marginBottom: '0.4rem' },
  cardText: { fontSize: '0.85rem', color: '#888', marginBottom: '0.2rem' },
  cardActions: { display: 'flex', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap' as const },
  empty: { textAlign: 'center' as const, color: '#888', padding: '3rem', background: '#fff', borderRadius: 10 },
  modalOverlay: { position: 'fixed' as const, inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 },
  modal: { background: '#fff', borderRadius: 12, padding: '2rem', width: '100%', maxWidth: 500, boxShadow: '0 8px 32px rgba(0,0,0,0.2)', maxHeight: '90vh', overflow: 'auto' },
  modalTitle: { fontSize: '1.2rem', fontWeight: 600, marginBottom: '0.5rem', color: '#1a1a2e' },
  modalSub: { fontSize: '0.85rem', color: '#888', marginBottom: '1.25rem' },
  label: { display: 'block', color: '#555', fontSize: '0.85rem', fontWeight: 500, marginBottom: '0.3rem' },
  input: { width: '100%', padding: '0.6rem 0.8rem', borderRadius: 6, border: '1px solid #ddd', fontSize: '0.9rem', marginBottom: '1rem', boxSizing: 'border-box' as const },
  select: { width: '100%', padding: '0.6rem 0.8rem', borderRadius: 6, border: '1px solid #ddd', fontSize: '0.9rem', marginBottom: '1rem', boxSizing: 'border-box' as const, background: '#fff' },
  modalActions: { display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' as const, marginTop: '1rem' },
  badge: (status: string) => {
    const colors: Record<string, string> = { pending: '#ffb74d', scanning: '#4fc3f7', done: '#81c784', failed: '#e74c3c' }
    return { background: colors[status] || '#eee', color: '#fff', padding: '0.15rem 0.5rem', borderRadius: 10, fontSize: '0.75rem', display: 'inline-block' }
  },
  snapshotBox: { background: '#f8faff', borderRadius: 8, padding: '0.75rem 1rem', marginTop: '0.5rem', fontSize: '0.8rem', color: '#555', border: '1px solid #e8ecf4' },
  langTag: { display: 'inline-block', padding: '0.15rem 0.4rem', borderRadius: 4, background: '#e8ecf4', color: '#555', fontSize: '0.75rem', marginRight: '0.25rem', marginBottom: '0.25rem' },
}

export default function CodeSources() {
  const { t } = useTranslation()
  const [sources, setSources] = useState<CodeSource[]>([])
  const [snapshots, setSnapshots] = useState<Record<number, RepoSnapshot | null>>({})
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', provider: 'github', repo_url: '', default_branch: 'main', access_token: '' })
  const [creating, setCreating] = useState(false)

  useEffect(() => { loadSources() }, [])

  async function loadSources() {
    try {
      const srcs = await listCodeSources()
      setSources(srcs)
      // Load latest snapshots
      const sm: Record<number, RepoSnapshot | null> = {}
      for (const s of srcs) {
        try { sm[s.id] = await getLatestSnapshot(s.id) } catch { sm[s.id] = null }
      }
      setSnapshots(sm)
    } catch { /* ignore */ } finally { setLoading(false) }
  }

  async function handleCreate() {
    setCreating(true)
    try {
      await createCodeSource(form)
      setShowCreate(false)
      setForm({ name: '', provider: 'github', repo_url: '', default_branch: 'main', access_token: '' })
      await loadSources()
    } catch { alert('创建失败') } finally { setCreating(false) }
  }

  async function handleDelete(id: number) {
    if (!confirm('确定要删除该代码源吗？')) return
    try { await deleteCodeSource(id); await loadSources() }
    catch { alert('删除失败') }
  }

  async function handleScan(id: number) {
    try {
      const snapshot = await scanRepository(id)
      setSnapshots((prev) => ({ ...prev, [id]: snapshot }))
      await loadSources()
    } catch (err: any) {
      alert(err?.response?.data?.detail || '扫描失败')
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: '3rem', color: '#888' }}>{t('dashboard.loading')}</div>

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <h2 style={styles.title}>📂 Codebase 源</h2>
        <button style={{ ...styles.btn, ...styles.btnPrimary }} onClick={() => setShowCreate(true)}>
          + 添加代码源
        </button>
      </div>

      {sources.length === 0 ? (
        <div style={styles.empty}>
          <p style={{ marginBottom: '0.75rem' }}>暂无代码源。添加 GitHub/GitLab 仓库开始分析。</p>
        </div>
      ) : (
        <div style={styles.grid}>
          {sources.map((s) => {
            const snap = snapshots[s.id]
            return (
              <div key={s.id} style={styles.card}>
                <div style={styles.cardTitle}>{s.name}</div>
                <div style={styles.cardText}>
                  提供商: <strong>{s.provider}</strong> | 分支: <strong>{s.default_branch}</strong>
                </div>
                <div style={styles.cardText}>
                  <a href={s.repo_url} target="_blank" rel="noreferrer" style={{ color: '#4fc3f7' }}>
                    {s.repo_url.replace(/^https?:\/\//, '')}
                  </a>
                </div>
                <div style={{ marginTop: '0.4rem' }}>
                  <span style={styles.badge(s.scan_status)}>{s.scan_status}</span>
                </div>

                {snap && (
                  <div style={styles.snapshotBox}>
                    <div>📁 {snap.total_files} 文件 | 📄 {snap.total_lines} 行</div>
                    <div style={{ marginTop: '0.25rem' }}>
                      {snap.language_breakdown && Object.entries(snap.language_breakdown).slice(0, 5).map(([lang, bytes]) => (
                        <span key={lang} style={styles.langTag}>{lang} ({(bytes as number / 1024).toFixed(0)}KB)</span>
                      ))}
                    </div>
                    {snap.commit_sha && <div style={{ marginTop: '0.25rem', fontFamily: 'monospace', fontSize: '0.75rem' }}>📌 {snap.commit_sha.slice(0, 7)}</div>}
                    <div style={{ marginTop: '0.25rem' }}>🕐 {new Date(snap.scanned_at).toLocaleString('zh-CN')}</div>
                  </div>
                )}

                <div style={styles.cardActions}>
                  <button style={{ ...styles.btn, ...styles.btnSuccess, ...styles.btnSmall }} onClick={() => handleScan(s.id)}>
                    🔄 扫描
                  </button>
                  <button style={{ ...styles.btn, ...styles.btnDanger, ...styles.btnSmall }} onClick={() => handleDelete(s.id)}>
                    删除
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Create Source Modal */}
      {showCreate && (
        <div style={styles.modalOverlay} onClick={() => setShowCreate(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalTitle}>添加代码源</div>
            <div style={styles.modalSub}>连接 GitHub/GitLab 仓库进行代码影响分析</div>
            <div>
              <label style={styles.label}>名称</label>
              <input style={styles.input} type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="My Backend Repo" required />

              <label style={styles.label}>提供商</label>
              <select style={styles.select} value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })}>
                <option value="github">GitHub</option>
                <option value="gitlab">GitLab</option>
                <option value="bitbucket">Bitbucket</option>
                <option value="local">Local</option>
              </select>

              <label style={styles.label}>仓库 URL</label>
              <input style={styles.input} type="url" value={form.repo_url} onChange={(e) => setForm({ ...form, repo_url: e.target.value })} placeholder="https://github.com/owner/repo" required />

              <label style={styles.label}>默认分支</label>
              <input style={styles.input} type="text" value={form.default_branch} onChange={(e) => setForm({ ...form, default_branch: e.target.value })} placeholder="main" />

              <label style={styles.label}>Access Token (可选)</label>
              <input style={styles.input} type="password" value={form.access_token} onChange={(e) => setForm({ ...form, access_token: e.target.value })} placeholder="ghp_..." />
              <div style={{ fontSize: '0.8rem', color: '#888', marginBottom: '1rem' }}>
                用于 GitHub API 认证。需要 repo 读取权限。留空使用公共 API 限流。
              </div>

              <div style={styles.modalActions}>
                <button type="button" style={{ ...styles.btn, background: '#ccc', color: '#333' }} onClick={() => setShowCreate(false)}>取消</button>
                <button type="button" style={{ ...styles.btn, ...styles.btnPrimary }} onClick={handleCreate} disabled={creating}>
                  {creating ? '创建中...' : '创建'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
