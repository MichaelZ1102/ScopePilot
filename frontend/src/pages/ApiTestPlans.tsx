import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  Download,
  FileJson2,
  FlaskConical,
  LoaderCircle,
  Plus,
  Sparkles,
  Trash2,
  Upload,
  X,
} from 'lucide-react'

import {
  deleteSpec,
  exportPlanMarkdown,
  exportPlanPostman,
  generateTestPlan,
  getTestPlan,
  importSpecFromContent,
  importSpecFromUrl,
  listSpecs,
  listTestPlans,
  type ApiSpec,
  type TestPlan,
} from '../lib/api'
import { getApiErrorMessage } from '../lib/client'

export default function ApiTestPlans() {
  const [tab, setTab] = useState<'specs' | 'plans'>('specs')
  const [specs, setSpecs] = useState<ApiSpec[]>([])
  const [plans, setPlans] = useState<TestPlan[]>([])
  const [loading, setLoading] = useState(true)
  const [showImport, setShowImport] = useState(false)
  const [importMode, setImportMode] = useState<'url' | 'content'>('url')
  const [importForm, setImportForm] = useState({ url: '', name: '', content: '' })
  const [importing, setImporting] = useState(false)
  const [generatingId, setGeneratingId] = useState<number | null>(null)
  const [viewPlan, setViewPlan] = useState<TestPlan | null>(null)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    try {
      const [loadedSpecs, loadedPlans] = await Promise.all([listSpecs(), listTestPlans()])
      setSpecs(loadedSpecs)
      setPlans(loadedPlans)
    } catch {
      setSpecs([])
      setPlans([])
    } finally {
      setLoading(false)
    }
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
    } catch (error: unknown) {
      alert(getApiErrorMessage(error, 'Import failed'))
    } finally {
      setImporting(false)
    }
  }

  async function handleDeleteSpec(id: number) {
    if (!confirm('确定删除该 API Spec 吗？关联的测试计划也会被删除。')) return
    try {
      await deleteSpec(id)
      await loadData()
    } catch {
      alert('删除失败')
    }
  }

  async function handleGenerate(specId: number) {
    setGeneratingId(specId)
    try {
      const plan = await generateTestPlan(specId)
      setPlans(await listTestPlans())
      setViewPlan(plan)
      setTab('plans')
    } catch (error: unknown) {
      alert(getApiErrorMessage(error, 'Generate failed'))
    } finally {
      setGeneratingId(null)
    }
  }

  async function handleViewPlan(planId: number) {
    try {
      setViewPlan(await getTestPlan(planId))
    } catch {
      alert('获取计划失败')
    }
  }

  async function handleExportMarkdown(planId: number) {
    try {
      const { markdown } = await exportPlanMarkdown(planId)
      downloadFile(markdown, `test-plan-${planId}.md`, 'text/markdown')
    } catch {
      alert('导出失败')
    }
  }

  async function handleExportPostman(planId: number) {
    try {
      const { collection } = await exportPlanPostman(planId)
      downloadFile(JSON.stringify(collection, null, 2), `test-plan-${planId}.postman_collection.json`, 'application/json')
    } catch {
      alert('导出失败')
    }
  }

  if (loading) {
    return (
      <div className="loading-state">
        <span className="loading-state-icon"><LoaderCircle className="spin" size={22} /></span>
        <p>正在加载 API 数据...</p>
      </div>
    )
  }

  return (
    <div className="workspace-page">
      <header className="workspace-header">
        <div>
          <span className="workspace-kicker">API Quality Workspace</span>
          <h1>API 测试</h1>
          <p>导入 OpenAPI 定义，生成覆盖正向、异常、边界和安全场景的测试计划。</p>
        </div>
        <div className="workspace-header-actions">
          <button className="button button-primary" type="button" onClick={() => setShowImport(true)}>
            <Upload size={17} />
            导入 OpenAPI
          </button>
        </div>
      </header>

      <div className="workspace-tabs" role="tablist" aria-label="API workspace views">
        <button className={`workspace-tab${tab === 'specs' ? ' is-active' : ''}`} type="button" onClick={() => { setTab('specs'); setViewPlan(null) }}>
          <FileJson2 size={15} /> API Specs ({specs.length})
        </button>
        <button className={`workspace-tab${tab === 'plans' ? ' is-active' : ''}`} type="button" onClick={() => setTab('plans')}>
          <FlaskConical size={15} /> 测试计划 ({plans.length})
        </button>
      </div>

      {tab === 'specs' && (
        specs.length === 0 ? (
          <section className="empty-state">
            <span className="empty-state-icon"><FileJson2 size={23} /></span>
            <h2>导入第一份 OpenAPI 定义</h2>
            <p>支持从 URL 或 JSON/YAML 内容导入，导入后即可生成可导出的 API 测试计划。</p>
            <button className="button button-primary" type="button" onClick={() => setShowImport(true)}>
              <Upload size={16} />
              导入 OpenAPI
            </button>
          </section>
        ) : (
          <section className="resource-grid">
            {specs.map((spec) => (
              <article className="resource-card" key={spec.id}>
                <div className="resource-card-header">
                  <span className="resource-icon"><FileJson2 size={19} /></span>
                  <div>
                    <h2>{spec.name}</h2>
                    <p>{spec.title} · v{spec.version}</p>
                  </div>
                  <span className="status-badge is-info">已导入</span>
                </div>
                <div className="resource-summary">
                  <span>端点<strong>{spec.endpoint_count}</strong></span>
                  <span>版本<strong>{spec.version || '-'}</strong></span>
                  <span>导入日期<strong>{new Date(spec.created_at).toLocaleDateString('zh-CN')}</strong></span>
                </div>
                <p className="resource-meta">{spec.source.slice(0, 100)}</p>
                <div className="row-actions">
                  <button className="button button-primary button-small" type="button" onClick={() => handleGenerate(spec.id)} disabled={generatingId === spec.id}>
                    {generatingId === spec.id ? <LoaderCircle className="spin" size={14} /> : <Sparkles size={14} />}
                    {generatingId === spec.id ? '生成中' : '生成测试计划'}
                  </button>
                  <button className="button button-danger button-small" type="button" onClick={() => handleDeleteSpec(spec.id)}>
                    <Trash2 size={14} />
                    删除
                  </button>
                </div>
              </article>
            ))}
          </section>
        )
      )}

      {tab === 'plans' && (
        plans.length === 0 ? (
          <section className="empty-state">
            <span className="empty-state-icon"><FlaskConical size={23} /></span>
            <h2>暂无测试计划</h2>
            <p>先在 API Specs 中导入定义并生成计划，生成结果会在这里集中管理。</p>
            <button className="button" type="button" onClick={() => setTab('specs')}>查看 API Specs</button>
          </section>
        ) : viewPlan ? (
          <PlanDetail
            plan={viewPlan}
            onBack={() => setViewPlan(null)}
            onExportMarkdown={handleExportMarkdown}
            onExportPostman={handleExportPostman}
          />
        ) : (
          <section className="resource-grid">
            {plans.map((plan) => (
              <article className="resource-card" key={plan.id}>
                <div className="resource-card-header">
                  <span className="resource-icon"><FlaskConical size={19} /></span>
                  <div>
                    <h2>{plan.title}</h2>
                    <p>{plan.coverage_summary.ai_generated ? 'AI 生成' : '规则生成'}</p>
                  </div>
                  <span className="status-badge is-success">已生成</span>
                </div>
                <div className="resource-summary">
                  <span>端点<strong>{plan.endpoints_analyzed}</strong></span>
                  <span>场景<strong>{plan.scenario_count}</strong></span>
                  <span>正向场景<strong>{plan.coverage_summary.positive_scenarios}</strong></span>
                </div>
                <div className="tag-list">
                  <span className="tag is-success">正向 {plan.coverage_summary.positive_scenarios}</span>
                  <span className="tag is-high">负向 {plan.coverage_summary.negative_scenarios}</span>
                  <span className="tag is-medium">边界 {plan.coverage_summary.edge_scenarios}</span>
                </div>
                <div className="row-actions">
                  <button className="button button-primary button-small" type="button" onClick={() => handleViewPlan(plan.id)}>查看计划</button>
                  <button className="button button-small" type="button" onClick={() => handleExportMarkdown(plan.id)}>
                    <Download size={14} /> Markdown
                  </button>
                  <button className="button button-small" type="button" onClick={() => handleExportPostman(plan.id)}>
                    <Download size={14} /> Postman
                  </button>
                </div>
              </article>
            ))}
          </section>
        )
      )}

      {showImport && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setShowImport(false)}>
          <div className="workspace-modal is-wide" role="dialog" aria-modal="true" aria-labelledby="import-spec-title" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2 id="import-spec-title">导入 OpenAPI Spec</h2>
                <p>从公开 URL 或粘贴 JSON/YAML 内容导入 API 定义。</p>
              </div>
              <button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={() => setShowImport(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <div className="workspace-tabs">
                <button className={`workspace-tab${importMode === 'url' ? ' is-active' : ''}`} type="button" onClick={() => setImportMode('url')}>URL</button>
                <button className={`workspace-tab${importMode === 'content' ? ' is-active' : ''}`} type="button" onClick={() => setImportMode('content')}>粘贴内容</button>
              </div>
              <div className="form-grid">
                <label className="form-field is-wide">
                  <span>名称</span>
                  <input type="text" value={importForm.name} onChange={(event) => setImportForm({ ...importForm, name: event.target.value })} placeholder="Customer API" />
                </label>
                {importMode === 'url' ? (
                  <label className="form-field is-wide">
                    <span>OpenAPI URL</span>
                    <input type="url" value={importForm.url} onChange={(event) => setImportForm({ ...importForm, url: event.target.value })} placeholder="https://example.com/openapi.json" />
                  </label>
                ) : (
                  <label className="form-field is-wide">
                    <span>OpenAPI JSON/YAML 内容</span>
                    <textarea value={importForm.content} onChange={(event) => setImportForm({ ...importForm, content: event.target.value })} placeholder='{"openapi":"3.0.0","info":{},"paths":{}}' />
                  </label>
                )}
              </div>
              <div className="modal-actions">
                <button className="button" type="button" onClick={() => setShowImport(false)}>取消</button>
                <button
                  className="button button-primary"
                  type="button"
                  onClick={handleImport}
                  disabled={importing || !importForm.name || (importMode === 'url' ? !importForm.url : !importForm.content)}
                >
                  {importing ? <LoaderCircle className="spin" size={15} /> : <Plus size={15} />}
                  {importing ? '导入中' : '导入 Spec'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function PlanDetail({ plan, onBack, onExportMarkdown, onExportPostman }: {
  plan: TestPlan
  onBack: () => void
  onExportMarkdown: (id: number) => void
  onExportPostman: (id: number) => void
}) {
  const [filterType, setFilterType] = useState('all')
  const scenarios = (plan.scenarios || []).filter((scenario) => filterType === 'all' || scenario.test_type === filterType)
  const typeCounts: Record<string, number> = {}
  ;(plan.scenarios || []).forEach((scenario) => {
    typeCounts[scenario.test_type] = (typeCounts[scenario.test_type] || 0) + 1
  })

  return (
    <section>
      <div className="detail-header">
        <div className="detail-heading">
          <button className="icon-button" type="button" title="返回" aria-label="返回" onClick={onBack}>
            <ArrowLeft size={18} />
          </button>
          <div>
            <h2>{plan.title}</h2>
            <p>{plan.coverage_summary.ai_generated ? 'AI 生成测试计划' : '规则生成测试计划'}</p>
          </div>
        </div>
        <div className="detail-actions">
          <button className="button button-small" type="button" onClick={() => onExportMarkdown(plan.id)}>
            <Download size={14} /> Markdown
          </button>
          <button className="button button-primary button-small" type="button" onClick={() => onExportPostman(plan.id)}>
            <Download size={14} /> Postman
          </button>
        </div>
      </div>

      <div className="metric-strip">
        <div className="metric-item"><span>端点</span><strong>{plan.endpoints_analyzed}</strong></div>
        <div className="metric-item"><span>全部场景</span><strong>{plan.scenario_count}</strong></div>
        <div className="metric-item"><span>正向场景</span><strong>{plan.coverage_summary.positive_scenarios}</strong></div>
        <div className="metric-item"><span>异常与边界</span><strong>{plan.coverage_summary.negative_scenarios + plan.coverage_summary.edge_scenarios}</strong></div>
      </div>

      <div className="workspace-tabs">
        <button className={`workspace-tab${filterType === 'all' ? ' is-active' : ''}`} type="button" onClick={() => setFilterType('all')}>
          全部 ({plan.scenario_count || 0})
        </button>
        {Object.entries(typeCounts).map(([type, count]) => (
          <button className={`workspace-tab${filterType === type ? ' is-active' : ''}`} type="button" key={type} onClick={() => setFilterType(type)}>
            {testTypeLabel(type)} ({count})
          </button>
        ))}
      </div>

      <div className="detail-stack">
        {scenarios.map((scenario, index) => (
          <article className="detail-card" key={`${scenario.endpoint}-${index}`}>
            <div className="detail-card-head">
              <div className="tag-list" style={{ marginTop: 0 }}>
                <span className={`tag ${testTypeClass(scenario.test_type)}`}>{testTypeLabel(scenario.test_type)}</span>
                <span className="tag">{scenario.method}</span>
                <code>{scenario.endpoint}</code>
              </div>
              <span className="status-badge is-info">期望 {scenario.expected_status}</span>
            </div>
            <h3>{scenario.scenario_name}</h3>
            <p>{scenario.description}</p>
            <p>{scenario.expected_behavior}</p>
            {scenario.test_input && Object.keys(scenario.test_input).length > 0 && (
              <pre className="code-block">{JSON.stringify(scenario.test_input, null, 2)}</pre>
            )}
          </article>
        ))}
        {scenarios.length === 0 && <div className="empty-state"><p>该分类暂无测试场景。</p></div>}
      </div>
    </section>
  )
}

function testTypeLabel(type: string) {
  const labels: Record<string, string> = {
    positive: '正向',
    negative: '负向',
    edge: '边界',
    security: '安全',
  }
  return labels[type] || type
}

function testTypeClass(type: string) {
  if (type === 'positive') return 'is-success'
  if (type === 'negative' || type === 'security') return 'is-high'
  if (type === 'edge') return 'is-medium'
  return ''
}

function downloadFile(content: string, filename: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}
