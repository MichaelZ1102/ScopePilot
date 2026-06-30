import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { listProjects, listSprints, importSprint, type Project, type Sprint } from '../lib/api'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const styles: any = {
  page: { maxWidth: 1100, margin: '0 auto' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' },
  title: { fontSize: '1.5rem', fontWeight: 700, color: '#1a1a2e' },
  statsRow: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' },
  statCard: (color: string): React.CSSProperties => ({
    background: '#fff', borderRadius: 10, padding: '1.25rem',
    borderLeft: `4px solid ${color}`, boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
  }),
  statLabel: { color: '#666', fontSize: '0.85rem', marginBottom: '0.25rem' },
  statValue: { fontSize: '1.75rem', fontWeight: 700, color: '#1a1a2e' },
  sectionTitle: { fontSize: '1.1rem', fontWeight: 600, color: '#1a1a2e', marginBottom: '1rem' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' },
  card: { background: '#fff', borderRadius: 10, padding: '1.25rem', boxShadow: '0 1px 4px rgba(0,0,0,0.06)', border: '1px solid #eee' },
  cardTitle: { fontSize: '1.1rem', fontWeight: 600, color: '#1a1a2e', marginBottom: '0.5rem' },
  cardText: { fontSize: '0.85rem', color: '#888', marginBottom: '0.25rem' },
  cardActions: { display: 'flex', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap' as const },
  btn: { padding: '0.45rem 1rem', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: '0.85rem', fontWeight: 500, color: '#fff' },
  btnPrimary: { background: '#4fc3f7' },
  btnDark: { background: '#1a1a2e' },
  btnOutline: { background: 'transparent', border: '1px solid #1a1a2e', color: '#1a1a2e' },
  empty: { textAlign: 'center' as const, color: '#888', padding: '2rem', background: '#fff', borderRadius: 10 },
  sprintItem: { padding: '0.5rem 0', borderBottom: '1px solid #f0f0f0', fontSize: '0.85rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  modalOverlay: { position: 'fixed' as const, inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 },
  modal: { background: '#fff', borderRadius: 12, padding: '2rem', width: '100%', maxWidth: 440, boxShadow: '0 8px 32px rgba(0,0,0,0.2)' },
  modalTitle: { fontSize: '1.2rem', fontWeight: 600, marginBottom: '1rem', color: '#1a1a2e' },
  input: { width: '100%', padding: '0.65rem 0.85rem', borderRadius: 6, border: '1px solid #ddd', fontSize: '0.9rem', marginBottom: '1rem', boxSizing: 'border-box' as const },
  modalActions: { display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' as const },
  badge: (state: string): React.CSSProperties => {
    const colors: Record<string, string> = { active: '#81c784', closed: '#90a4ae', future: '#4fc3f7' }
    return { background: colors[state] || '#eee', color: '#fff', padding: '0.15rem 0.5rem', borderRadius: 10, fontSize: '0.75rem' }
  },
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [projects, setProjects] = useState<Project[]>([])
  const [sprintsMap, setSprintsMap] = useState<Record<number, Sprint[]>>({})
  const [loading, setLoading] = useState(true)
  const [importProject, setImportProject] = useState<Project | null>(null)
  const [sprintName, setSprintName] = useState('')
  const [importing, setImporting] = useState(false)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    try {
      const projs = await listProjects()
      setProjects(projs)
      const sm: Record<number, Sprint[]> = {}
      for (const p of projs) {
        try { sm[p.id] = await listSprints(p.id) } catch { sm[p.id] = [] }
      }
      setSprintsMap(sm)
    } catch {
      // not authenticated
    } finally {
      setLoading(false)
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
          ? ((err as { response: { data: { detail: string } } }).response?.data?.detail ?? t('dashboard.import_failed'))
          : t('dashboard.import_failed')
      alert(msg)
    } finally {
      setImporting(false)
    }
  }

  const totalSprints = Object.values(sprintsMap).reduce((sum, s) => sum + s.length, 0)
  const totalTickets = Object.values(sprintsMap).reduce((sum, s) => sum + s.reduce((t, sp) => t + sp.total_tickets, 0), 0)
  const activeSprints = Object.values(sprintsMap).reduce((sum, s) => sum + s.filter((sp) => sp.state === 'active').length, 0)

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '3rem', color: '#888' }}>{t('dashboard.loading')}</div>
  }

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <h2 style={styles.title}>{t('dashboard.title')}</h2>
      </div>

      <div style={styles.statsRow}>
        <div style={styles.statCard('#4fc3f7')}>
          <div style={styles.statLabel}>{t('dashboard.stats_active_sprints')}</div>
          <div style={styles.statValue}>{activeSprints}</div>
        </div>
        <div style={styles.statCard('#81c784')}>
          <div style={styles.statLabel}>{t('dashboard.stats_total_tickets')}</div>
          <div style={styles.statValue}>{totalTickets}</div>
        </div>
        <div style={styles.statCard('#ffb74d')}>
          <div style={styles.statLabel}>{t('dashboard.stats_projects')}</div>
          <div style={styles.statValue}>{projects.length}</div>
        </div>
        <div style={styles.statCard('#ba68c8')}>
          <div style={styles.statLabel}>{t('dashboard.stats_sprints')}</div>
          <div style={styles.statValue}>{totalSprints}</div>
        </div>
      </div>

      <h3 style={styles.sectionTitle}>{t('dashboard.section_overview')}</h3>

      {projects.length === 0 ? (
        <div style={styles.empty}>
          <p style={{ marginBottom: '0.5rem' }}>{t('dashboard.no_projects')}</p>
          <button style={{ ...styles.btn, ...styles.btnPrimary }} onClick={() => navigate('/projects')}>
            {t('dashboard.create_project_btn')}
          </button>
        </div>
      ) : (
        <div style={styles.grid}>
          {projects.map((p) => {
            const sprints = sprintsMap[p.id] || []
            return (
              <div key={p.id} style={styles.card}>
                <div style={styles.cardTitle}>{p.name}</div>
                <div style={styles.cardText}>{t('dashboard.label_key')}: {p.jira_project_key}</div>
                <div style={styles.cardText}>{t('dashboard.label_sprints')}: {sprints.length}</div>
                <div style={{ marginTop: '0.5rem' }}>
                  {sprints.slice(-3).map((sp) => (
                    <div key={sp.id} style={styles.sprintItem} onClick={() => navigate(`/sprint/${sp.id}`)}>
                      <span>{sp.name}</span>
                      <span style={styles.badge(sp.state)}>{sp.state}</span>
                    </div>
                  ))}
                </div>
                <div style={styles.cardActions}>
                  <button style={{ ...styles.btn, ...styles.btnDark }} onClick={() => navigate(`/sprint/${p.id}`)}>
                    {t('dashboard.view_sprints')}
                  </button>
                  <button style={{ ...styles.btn, ...styles.btnPrimary }} onClick={() => { setImportProject(p); setSprintName('') }}>
                    {t('dashboard.import_sprint')}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {importProject && (
        <div style={styles.modalOverlay} onClick={() => setImportProject(null)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalTitle}>{t('dashboard.import_title')}</div>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
              {t('dashboard.import_project_label')}: {importProject.name}
            </p>
            <input
              style={styles.input}
              type="text"
              placeholder={t('dashboard.import_placeholder')}
              value={sprintName}
              onChange={(e) => setSprintName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleImport()}
              autoFocus
            />
            <div style={styles.modalActions}>
              <button style={{ ...styles.btn, background: '#ccc', color: '#333' }} onClick={() => setImportProject(null)}>
                {t('dashboard.import_cancel')}
              </button>
              <button style={{ ...styles.btn, ...styles.btnPrimary }} onClick={handleImport} disabled={importing || !sprintName.trim()}>
                {importing ? t('dashboard.importing') : t('dashboard.import_confirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
