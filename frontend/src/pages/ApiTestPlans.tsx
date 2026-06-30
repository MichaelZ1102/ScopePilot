import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  listSpecs, importSpecFromUrl, importSpecFromContent, deleteSpec,
  generateTestPlan, listTestPlans, getTestPlan,
  exportPlanMarkdown, exportPlanPostman,
  type ApiSpec, type TestPlan,
} from '../lib/api'
import { getApiErrorMessage } from '../lib/client'

const styles: any = {
  page: { maxWidth: 1100, margin: '0 auto' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' },
  title: { fontSize: '1.5rem', fontWeight: 700, color: '#1a1a2e' },
  btn: { padding: '0.5rem 1.2rem', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600, color: '#fff' },
  btnPrimary: { background: '#4fc3f7' },
  btnDark: { background: '#1a1a2e' },
  btnDanger: { background: '#e74c3c' },
  btnSuccess: { background: '#81c784' },
  btnSmall: { padding: '0.35rem 0.8rem', fontSize: '0.8rem' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1rem' },
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
  textarea: { width: '100%', padding: '0.6rem 0.8rem', borderRadius: 6, border: '1px solid #ddd', fontSize: '0.9rem', marginBottom: '1rem', boxSizing: 'border-box' as const, minHeight: 120, fontFamily: 'monospace' },
  modalActions: { display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' as const, marginTop: '1rem' },
  tag: { display: 'inline-block', padding: '0.15rem 0.5rem', borderRadius: 4, background: '#e8ecf4', color: '#555', fontSize: '0.78rem', marginRight: '0.3rem', marginBottom: '0.3rem' },
  tabBar: { display: 'flex', gap: '0.5rem', marginBottom: '1rem' },
  tab: (active: boolean) => ({ padding: '0.5rem 1.2rem', borderRadius: 6, cursor: 'pointer', fontSize: '0.85rem', fontWeight: 500, border: 'none', background: active ? '#1a1a2e' : '#eee', color: active ? '#fff' : '#333' }),
  testTypeTag: (type: string) => {
    const colors: Record<string, string> = { positive: '#81c784', negative: '#e74c3c', edge: '#ffb74d', security: '#ba68c8' }
    return { display: 'inline-block', padding: '0.1rem 0.4rem', borderRadius: 4, background: colors[type] || '#eee', color: '#fff', fontSize: '0.75rem', fontWeight: 500 }
  },
  detailSection: { background: '#f8faff', borderRadius: 8, padding: '1rem', marginTop: '0.75rem', border: '1px solid #e8ecf4', fontSize: '0.88rem', lineHeight: 1.5 },
  methodBadge: (method: string) => {
    const colors: Record<string, string> = { GET: '#81c784', POST: '#4fc3f7', PUT: '#ffb74d', PATCH: '#ba68c8', DELETE: '#e74c3c' }
    return { display: 'inline-block', padding: '0.1rem 0.4rem', borderRadius: 4, background: colors[method] || '#888', color: '#fff', fontSize: '0.72rem', fontWeight: 700, fontFamily: 'monospace', marginRight: '0.4rem' }
  },
}

export default function ApiTestPlans() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<'specs' | 'plans'>('specs')
  const [specs, setSpecs] = useState<ApiSpec[]>([])
  const [plans, setPlans] = useState<TestPlan[]>([])
  const [loading, setLoading] = useState(true)

  // Import modal
  const [showImport, setShowImport] = useState(false)
  const [importMode, setImportMode] = useState<'url' | 'content'>('url')
  const [importForm, setImportForm] = useState({ url: '', name: '', content: '' })
  const [importing, setImporting] = useState(false)

  // Plan detail
  const [viewPlan, setViewPlan] = useState<TestPlan | null>(null)
  const [planFilter] = useState<string>('all')

  useEffect(() => { loadData() }, [])

  async function loadData() {
    try {
      const [s, p] = await Promise.all([listSpecs(), listTestPlans()])
      setSpecs(s)
      setPlans(p)
    } catch { /* ignore */ } finally { setLoading(false) }
  }

  async function handleImport() {
    setImporting(true)
    try {
      if (importMode === 'url') {
        await importSpecFromUrl(importForm.url, importForm.name)
      } else {
        await importSpecFromContent(importForm.content, importForm.name)
      }
      setShowImport(false)
      setImportForm({ url: '', name: '', content: '' })
      await loadData()
    } catch (err: unknown) {
      alert(getApiErrorMessage(err, 'Import failed'))
    } finally { setImporting(false) }
  }

  async function handleDeleteSpec(id: number) {
    if (!confirm('确定删除该 API Spec 吗？关联的测试计划也会被删除。')) return
    try { await deleteSpec(id); await loadData() } catch { alert('删除失败') }
  }

  async function handleGenerate(specId: number) {
    try {
      const plan = await generateTestPlan(specId)
      setPlans(await listTestPlans())
      setViewPlan(plan)
      setTab('plans')
    } catch (err: unknown) {
      alert(getApiErrorMessage(err, 'Generate failed'))
    }
  }

  async function handleViewPlan(planId: number) {
    try {
      const plan = await getTestPlan(planId)
      setViewPlan(plan)
    } catch { alert('获取计划失败') }
  }

  async function handleExportMd(planId: number) {
    try {
      const { markdown } = await exportPlanMarkdown(planId)
      const blob = new Blob([markdown], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `test-plan-${planId}.md`
      a.click(); URL.revokeObjectURL(url)
    } catch { alert('导出失败') }
  }

  async function handleExportPostman(planId: number) {
    try {
      const { collection } = await exportPlanPostman(planId)
      const blob = new Blob([JSON.stringify(collection, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `test-plan-${planId}.postman_collection.json`
      a.click(); URL.revokeObjectURL(url)
    } catch { alert('导出失败') }
  }

  // Unused planFilter kept for future filtering UI
  if (false) void planFilter;

  if (loading) return <div style={{ textAlign: 'center', padding: '3rem', color: '#888' }}>{t('dashboard.loading')}</div>

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <h2 style={styles.title}>🧪 API 测试计划</h2>
        <button style={{ ...styles.btn, ...styles.btnPrimary }} onClick={() => setShowImport(true)}>
          + 导入 OpenAPI Spec
        </button>
      </div>

      <div style={styles.tabBar}>
        <button style={styles.tab(tab === 'specs')} onClick={() => setTab('specs')}>
          📋 API Specs ({specs.length})
        </button>
        <button style={styles.tab(tab === 'plans')} onClick={() => setTab('plans')}>
          📝 测试计划 ({plans.length})
        </button>
      </div>

      {tab === 'specs' && (
        specs.length === 0 ? (
          <div style={styles.empty}>
            <p style={{ marginBottom: '0.75rem' }}>暂无 API Spec，点击上方按钮导入。</p>
          </div>
        ) : (
          <div style={styles.grid}>
            {specs.map((s) => (
              <div key={s.id} style={styles.card}>
                <div style={styles.cardTitle}>{s.name}</div>
                <div style={styles.cardText}>{s.title} v{s.version}</div>
                <div style={styles.cardText}>📡 {s.endpoint_count} 个端点</div>
                <div style={styles.cardText}>📎 {s.source.slice(0, 60)}</div>
                <div style={{ marginTop: '0.4rem', fontSize: '0.78rem', color: '#aaa' }}>
                  {new Date(s.created_at).toLocaleString('zh-CN')}
                </div>
                <div style={styles.cardActions}>
                  <button style={{ ...styles.btn, ...styles.btnSuccess, ...styles.btnSmall }} onClick={() => handleGenerate(s.id)}>
                    🚀 生成测试计划
                  </button>
                  <button style={{ ...styles.btn, ...styles.btnDanger, ...styles.btnSmall }} onClick={() => handleDeleteSpec(s.id)}>
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {tab === 'plans' && (
        <>
          {plans.length === 0 ? (
            <div style={styles.empty}>
              <p>暂无测试计划。先在 Specs 标签页导入 API 定义并生成计划。</p>
            </div>
          ) : viewPlan ? (
            <PlanDetail
              plan={viewPlan}
              onBack={() => setViewPlan(null)}
              onExportMd={handleExportMd}
              onExportPostman={handleExportPostman}
            />
          ) : (
            <div style={styles.grid}>
              {plans.map((p) => {
                const cov = p.coverage_summary
                return (
                  <div key={p.id} onClick={() => handleViewPlan(p.id)} style={{ ...styles.card, cursor: 'pointer' }}>
                    <div style={styles.cardTitle}>{p.title}</div>
                    <div style={styles.cardText}>📡 {p.endpoints_analyzed} 端点 | 🧪 {p.scenario_count} 场景</div>
                    <div style={{ marginTop: '0.3rem', display: 'flex', gap: '0.5rem', fontSize: '0.78rem' }}>
                      <span>✅ {cov.positive_scenarios} 正向</span>
                      <span>❌ {cov.negative_scenarios} 负向</span>
                      <span>⚠️ {cov.edge_scenarios} 边界</span>
                    </div>
                    <div style={{ marginTop: '0.3rem', fontSize: '0.78rem', color: '#aaa' }}>
                      {cov.ai_generated ? '🤖 AI 生成' : '📐 规则生成'} · {new Date(p.created_at).toLocaleString('zh-CN')}
                    </div>
                    <div style={styles.cardActions}>
                      <button style={{ ...styles.btn, ...styles.btnSmall, background: '#90a4ae' }} onClick={(e) => { e.stopPropagation(); handleExportMd(p.id) }}>
                        📄 Markdown
                      </button>
                      <button style={{ ...styles.btn, ...styles.btnSmall, background: '#ff6b6b' }} onClick={(e) => { e.stopPropagation(); handleExportPostman(p.id) }}>
                        🚀 Postman
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}

      {/* Import Modal */}
      {showImport && (
        <div style={styles.modalOverlay} onClick={() => setShowImport(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalTitle}>导入 OpenAPI Spec</div>
            <div style={styles.modalSub}>从 URL 或粘贴内容导入 API 定义</div>

            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
              <button style={styles.tab(importMode === 'url')} onClick={() => setImportMode('url')}>🔗 URL</button>
              <button style={styles.tab(importMode === 'content')} onClick={() => setImportMode('content')}>📝 粘贴内容</button>
            </div>

            <label style={styles.label}>名称</label>
            <input style={styles.input} type="text" value={importForm.name}
              onChange={(e) => setImportForm({ ...importForm, name: e.target.value })}
              placeholder="My API" required />

            {importMode === 'url' ? (
              <>
                <label style={styles.label}>OpenAPI URL</label>
                <input style={styles.input} type="url" value={importForm.url}
                  onChange={(e) => setImportForm({ ...importForm, url: e.target.value })}
                  placeholder="https://raw.githubusercontent.com/.../openapi.json" required />
              </>
            ) : (
              <>
                <label style={styles.label}>OpenAPI JSON/YAML 内容</label>
                <textarea style={styles.textarea} value={importForm.content}
                  onChange={(e) => setImportForm({ ...importForm, content: e.target.value })}
                  placeholder='{"openapi": "3.0.0", "info": {...}, "paths": {...}}' />
              </>
            )}

            <div style={styles.modalActions}>
              <button style={{ ...styles.btn, background: '#ccc', color: '#333' }} onClick={() => setShowImport(false)}>取消</button>
              <button style={{ ...styles.btn, ...styles.btnPrimary }} onClick={handleImport} disabled={importing}>
                {importing ? '导入中...' : '导入'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function PlanDetail({ plan, onBack, onExportMd, onExportPostman }: {
  plan: TestPlan; onBack: () => void; onExportMd: (id: number) => void; onExportPostman: (id: number) => void
}) {
  const cov = plan.coverage_summary
  const [filterType, setFilterType] = useState<string>('all')

  const scenarios = (plan.scenarios || []).filter(s => filterType === 'all' || s.test_type === filterType)
  const typeCounts: Record<string, number> = {}
  ;(plan.scenarios || []).forEach(s => { typeCounts[s.test_type] = (typeCounts[s.test_type] || 0) + 1 })

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div>
          <button onClick={onBack} style={{ background: 'none', border: 'none', color: '#4fc3f7', cursor: 'pointer', fontSize: '0.9rem', marginRight: '0.75rem' }}>← 返回</button>
          <span style={{ fontSize: '1.1rem', fontWeight: 600, color: '#1a1a2e' }}>{plan.title}</span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button style={{ ...styles.btn, ...styles.btnSmall, background: '#90a4ae' }} onClick={() => onExportMd(plan.id)}>📄 Markdown</button>
          <button style={{ ...styles.btn, ...styles.btnSmall, background: '#ff6b6b' }} onClick={() => onExportPostman(plan.id)}>🚀 Postman</button>
        </div>
      </div>

      <div style={{ ...styles.detailSection, marginBottom: '1rem' }}>
        <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
          <div><strong>端点数:</strong> {plan.endpoints_analyzed}</div>
          <div><strong>场景数:</strong> {plan.scenario_count}</div>
          <div><strong>Base URL:</strong> {plan.base_url || '—'}</div>
          <div><strong>生成方式:</strong> {cov.ai_generated ? '🤖 AI' : '📐 规则'}</div>
        </div>
        <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
          <span>✅ 正向: {cov.positive_scenarios}</span>
          <span>❌ 负向: {cov.negative_scenarios}</span>
          <span>⚠️ 边界/安全: {cov.edge_scenarios}</span>
        </div>
      </div>

      {/* Filter */}
      <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
        <button style={styles.tab(filterType === 'all')} onClick={() => setFilterType('all')}>全部 ({plan.scenario_count || 0})</button>
        {Object.entries(typeCounts).map(([type, count]) => (
          <button key={type} style={styles.tab(filterType === type)} onClick={() => setFilterType(type)}>
            {type} ({count})
          </button>
        ))}
      </div>

      {/* Scenarios */}
      {scenarios.map((s, i) => (
        <div key={i} style={{
          background: '#fff', borderRadius: 8, padding: '0.75rem 1rem', marginBottom: '0.5rem',
          border: '1px solid #eee', boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.3rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={styles.testTypeTag(s.test_type)}>{s.test_type}</span>
              <span style={styles.methodBadge(s.method)}>{s.method}</span>
              <code style={{ fontSize: '0.85rem', color: '#1a1a2e' }}>{s.endpoint}</code>
            </div>
            <span style={{ fontSize: '0.78rem', color: '#888' }}>期望: {s.expected_status}</span>
          </div>
          <div style={{ fontSize: '0.95rem', fontWeight: 500, color: '#1a1a2e', marginBottom: '0.2rem' }}>{s.scenario_name}</div>
          <div style={{ fontSize: '0.85rem', color: '#666' }}>{s.description}</div>
          <div style={{ fontSize: '0.82rem', color: '#888', marginTop: '0.2rem' }}>{s.expected_behavior}</div>
          {s.test_input && Object.keys(s.test_input).length > 0 && (
            <pre style={{ fontSize: '0.75rem', background: '#f5f5f5', padding: '0.4rem 0.6rem', borderRadius: 4, marginTop: '0.3rem', overflow: 'auto', maxHeight: 100 }}>
              {JSON.stringify(s.test_input, null, 2)}
            </pre>
          )}
        </div>
      ))}

      {scenarios.length === 0 && (
        <div style={styles.empty}>该分类暂无测试场景</div>
      )}
    </div>
  )
}
