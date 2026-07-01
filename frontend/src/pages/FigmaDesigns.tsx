import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  Frame,
  Layers3,
  LoaderCircle,
  PenTool,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'

import {
  analyzeFigmaDesign,
  deleteFigmaAnalysis,
  listFigmaAnalyses,
  type FigmaAnalysis,
} from '../lib/api'
import { getApiErrorMessage } from '../lib/client'

export default function FigmaDesigns() {
  const [analyses, setAnalyses] = useState<FigmaAnalysis[]>([])
  const [loading, setLoading] = useState(true)
  const [showAnalyze, setShowAnalyze] = useState(false)
  const [form, setForm] = useState({ figma_url: '', figma_token: '', ticket_summary: '' })
  const [analyzing, setAnalyzing] = useState(false)
  const [viewResult, setViewResult] = useState<FigmaAnalysis | null>(null)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    try {
      setAnalyses(await listFigmaAnalyses())
    } catch {
      setAnalyses([])
    } finally {
      setLoading(false)
    }
  }

  async function handleAnalyze() {
    setAnalyzing(true)
    try {
      const result = await analyzeFigmaDesign(form.figma_url, form.figma_token, form.ticket_summary)
      setShowAnalyze(false)
      setForm({ figma_url: '', figma_token: '', ticket_summary: '' })
      await loadData()
      setViewResult(result)
    } catch (error: unknown) {
      alert(getApiErrorMessage(error, 'Analysis failed'))
    } finally {
      setAnalyzing(false)
    }
  }

  async function handleDelete(id: number) {
    if (!confirm('确定删除该分析结果吗？')) return
    try {
      await deleteFigmaAnalysis(id)
      setViewResult(null)
      await loadData()
    } catch {
      alert('删除失败')
    }
  }

  if (loading) {
    return (
      <div className="loading-state">
        <span className="loading-state-icon"><LoaderCircle className="spin" size={22} /></span>
        <p>正在加载设计分析...</p>
      </div>
    )
  }

  return (
    <div className="workspace-page">
      <header className="workspace-header">
        <div>
          <span className="workspace-kicker">Design Impact Workspace</span>
          <h1>Figma 设计分析</h1>
          <p>读取 Figma 页面、组件和设计 Token，并评估 Ticket 对前后端实现的影响。</p>
        </div>
        <div className="workspace-header-actions">
          <button className="button button-primary" type="button" onClick={() => setShowAnalyze(true)}>
            <Sparkles size={17} />
            分析 Figma 设计
          </button>
        </div>
      </header>

      {viewResult ? (
        <AnalysisDetail analysis={viewResult} onBack={() => setViewResult(null)} onDelete={handleDelete} />
      ) : analyses.length === 0 ? (
        <section className="empty-state">
          <span className="empty-state-icon"><PenTool size={23} /></span>
          <h2>开始第一次设计影响分析</h2>
          <p>提供 Figma 文件链接和只读 Token，ScopePilot 会提取设计结构并生成实现影响项。</p>
          <button className="button button-primary" type="button" onClick={() => setShowAnalyze(true)}>
            <Sparkles size={16} />
            分析 Figma 设计
          </button>
        </section>
      ) : (
        <section className="resource-grid">
          {analyses.map((analysis) => (
            <article className="resource-card" key={analysis.id}>
              <div className="resource-card-header">
                <span className="resource-icon"><PenTool size={19} /></span>
                <div>
                  <h2>{analysis.file_name}</h2>
                  <p>{analysis.ai_used ? 'AI 辅助分析' : '规则分析'}</p>
                </div>
                <span className="status-badge is-success">已完成</span>
              </div>
              <div className="resource-summary">
                <span>页面/框架<strong>{analysis.frame_count}</strong></span>
                <span>文本节点<strong>{analysis.text_node_count}</strong></span>
                <span>影响项<strong>{analysis.implications.length}</strong></span>
              </div>
              <div className="tag-list">
                {analysis.implications.slice(0, 4).map((implication, index) => (
                  <span className={`tag is-${implication.priority}`} key={`${implication.type}-${index}`}>
                    {priorityLabel(implication.priority)}
                  </span>
                ))}
              </div>
              <div className="row-actions">
                <button className="button button-primary button-small" type="button" onClick={() => setViewResult(analysis)}>查看分析</button>
                <button className="button button-danger button-small" type="button" onClick={() => handleDelete(analysis.id)}>
                  <Trash2 size={14} />
                  删除
                </button>
              </div>
            </article>
          ))}
        </section>
      )}

      {showAnalyze && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setShowAnalyze(false)}>
          <div className="workspace-modal" role="dialog" aria-modal="true" aria-labelledby="analyze-figma-title" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2 id="analyze-figma-title">分析 Figma 设计</h2>
                <p>读取文件结构、设计 Token 和可见文本，形成实现影响清单。</p>
              </div>
              <button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={() => setShowAnalyze(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <div className="form-grid">
                <label className="form-field is-wide">
                  <span>Figma 设计链接</span>
                  <input type="url" value={form.figma_url} onChange={(event) => setForm({ ...form, figma_url: event.target.value })} placeholder="https://www.figma.com/design/..." />
                </label>
                <label className="form-field is-wide">
                  <span>Figma Personal Access Token</span>
                  <span className="field-help">需要 file:read 权限，Token 仅用于本次服务端请求。</span>
                  <input type="password" value={form.figma_token} onChange={(event) => setForm({ ...form, figma_token: event.target.value })} placeholder="figd_..." />
                </label>
                <label className="form-field is-wide">
                  <span>关联 Ticket 摘要</span>
                  <input type="text" value={form.ticket_summary} onChange={(event) => setForm({ ...form, ticket_summary: event.target.value })} placeholder="可选，例如：新增用户资料编辑页面" />
                </label>
              </div>
              <div className="modal-actions">
                <button className="button" type="button" onClick={() => setShowAnalyze(false)}>取消</button>
                <button className="button button-primary" type="button" onClick={handleAnalyze} disabled={analyzing || !form.figma_url || !form.figma_token}>
                  {analyzing ? <LoaderCircle className="spin" size={15} /> : <Sparkles size={15} />}
                  {analyzing ? '分析中' : '开始分析'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function AnalysisDetail({ analysis, onBack, onDelete }: {
  analysis: FigmaAnalysis
  onBack: () => void
  onDelete: (id: number) => void
}) {
  return (
    <section>
      <div className="detail-header">
        <div className="detail-heading">
          <button className="icon-button" type="button" title="返回" aria-label="返回" onClick={onBack}>
            <ArrowLeft size={18} />
          </button>
          <div>
            <h2>{analysis.file_name}</h2>
            <p>{analysis.ai_used ? 'AI 辅助设计影响分析' : '规则设计影响分析'}</p>
          </div>
        </div>
        <div className="detail-actions">
          <button className="button button-danger button-small" type="button" onClick={() => onDelete(analysis.id)}>
            <Trash2 size={14} />
            删除分析
          </button>
        </div>
      </div>

      <div className="metric-strip">
        <div className="metric-item"><span>页面/框架</span><strong>{analysis.frame_count}</strong></div>
        <div className="metric-item"><span>文本节点</span><strong>{analysis.text_node_count}</strong></div>
        <div className="metric-item"><span>实现影响项</span><strong>{analysis.implications.length}</strong></div>
      </div>

      <section className="workspace-panel">
        <div className="panel-header">
          <div>
            <h2>实现影响分析</h2>
            <p>按优先级核对接口、数据、业务规则和组件实现。</p>
          </div>
        </div>
        <div className="detail-stack" style={{ padding: 12 }}>
          {analysis.implications.map((implication, index) => (
            <article className="detail-card" key={`${implication.type}-${index}`}>
              <div className="detail-card-head">
                <div className="tag-list" style={{ marginTop: 0 }}>
                  <span className={`tag is-${implication.priority}`}>{priorityLabel(implication.priority)}</span>
                  <span className="tag">{implication.type}</span>
                </div>
              </div>
              <h3>{implication.title}</h3>
              <p>{implication.description}</p>
              {implication.detail && Object.keys(implication.detail).length > 0 && (
                <pre className="code-block">{JSON.stringify(implication.detail, null, 2)}</pre>
              )}
            </article>
          ))}
        </div>
      </section>

      {analysis.design_tokens && (
        <section className="workspace-panel" style={{ marginTop: 16 }}>
          <div className="panel-header">
            <div>
              <h2>设计系统 Token</h2>
              <p>从 Figma 文件中提取的颜色与间距值。</p>
            </div>
          </div>
          <div className="settings-section">
            {analysis.design_tokens.colors && Object.keys(analysis.design_tokens.colors).length > 0 && (
              <>
                <div className="detail-heading">
                  <span className="resource-icon"><Layers3 size={17} /></span>
                  <div><h2>颜色</h2><p>{Object.keys(analysis.design_tokens.colors).length} 个颜色 Token</p></div>
                </div>
                <div className="tag-list">
                  {Object.entries(analysis.design_tokens.colors).slice(0, 20).map(([name, color]) => (
                    <span className="tag" key={name}>
                      <span style={{ width: 10, height: 10, borderRadius: 2, background: String(color), border: '1px solid rgba(0,0,0,.08)' }} />
                      {name}
                    </span>
                  ))}
                </div>
              </>
            )}
            {analysis.design_tokens.spacing && analysis.design_tokens.spacing.length > 0 && (
              <div style={{ marginTop: 18 }}>
                <div className="detail-heading">
                  <span className="resource-icon"><Frame size={17} /></span>
                  <div><h2>间距</h2><p>{analysis.design_tokens.spacing.length} 个间距 Token</p></div>
                </div>
                <div className="tag-list">
                  {analysis.design_tokens.spacing.map((spacing: number, index: number) => (
                    <span className="tag" key={`${spacing}-${index}`}>{spacing}px</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>
      )}
    </section>
  )
}

function priorityLabel(priority: string) {
  const labels: Record<string, string> = {
    high: '高优先级',
    medium: '中优先级',
    low: '低优先级',
  }
  return labels[priority] || priority
}
