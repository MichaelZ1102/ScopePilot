import { useState, useEffect } from 'react'
import {
  analyzeFigmaDesign, listFigmaAnalyses, deleteFigmaAnalysis,
  type FigmaAnalysis,
} from '../lib/api'
import { getApiErrorMessage } from '../lib/client'

const styles: any = {
  page: { maxWidth: 1100, margin: '0 auto' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' },
  title: { fontSize: '1.5rem', fontWeight: 700, color: '#1a1a2e' },
  subtitle: { fontSize: '0.9rem', color: '#888', marginBottom: '1.5rem' },
  btn: { padding: '0.5rem 1.2rem', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600, color: '#fff' },
  btnPrimary: { background: '#4fc3f7' },
  btnDark: { background: '#1a1a2e' },
  btnDanger: { background: '#e74c3c' },
  btnSmall: { padding: '0.35rem 0.8rem', fontSize: '0.8rem' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '1rem' },
  card: { background: '#fff', borderRadius: 10, padding: '1.25rem', boxShadow: '0 1px 4px rgba(0,0,0,0.06)', border: '1px solid #eee' },
  cardTitle: { fontSize: '1.1rem', fontWeight: 600, color: '#1a1a2e', marginBottom: '0.4rem' },
  cardText: { fontSize: '0.85rem', color: '#888', marginBottom: '0.2rem' },
  cardActions: { display: 'flex', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap' as const },
  empty: { textAlign: 'center' as const, color: '#888', padding: '3rem', background: '#fff', borderRadius: 10 },
  modalOverlay: { position: 'fixed' as const, inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 },
  modal: { background: '#fff', borderRadius: 12, padding: '2rem', width: '100%', maxWidth: 500, boxShadow: '0 8px 32px rgba(0,0,0,0.2)' },
  modalTitle: { fontSize: '1.2rem', fontWeight: 600, marginBottom: '0.5rem', color: '#1a1a2e' },
  modalSub: { fontSize: '0.85rem', color: '#888', marginBottom: '1.25rem' },
  label: { display: 'block', color: '#555', fontSize: '0.85rem', fontWeight: 500, marginBottom: '0.3rem' },
  input: { width: '100%', padding: '0.6rem 0.8rem', borderRadius: 6, border: '1px solid #ddd', fontSize: '0.9rem', marginBottom: '1rem', boxSizing: 'border-box' as const },
  modalActions: { display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' as const, marginTop: '1rem' },
  priorityTag: (p: string) => {
    const colors: Record<string, string> = { high: '#e74c3c', medium: '#ffb74d', low: '#90a4ae' }
    return { display: 'inline-block', padding: '0.1rem 0.4rem', borderRadius: 4, background: colors[p] || '#eee', color: '#fff', fontSize: '0.72rem', fontWeight: 500, marginRight: '0.3rem' }
  },
  detailSection: { background: '#f8faff', borderRadius: 8, padding: '1rem', marginTop: '0.75rem', border: '1px solid #e8ecf4', fontSize: '0.88rem', lineHeight: 1.5 },
  tokenChip: { display: 'inline-block', padding: '0.15rem 0.4rem', borderRadius: 4, background: '#e8ecf4', color: '#555', fontSize: '0.75rem', marginRight: '0.25rem', marginBottom: '0.25rem' },
}

export default function FigmaDesigns() {
  const [analyses, setAnalyses] = useState<FigmaAnalysis[]>([])
  const [loading, setLoading] = useState(true)
  const [showAnalyze, setShowAnalyze] = useState(false)
  const [form, setForm] = useState({ figma_url: '', figma_token: '', ticket_summary: '' })
  const [analyzing, setAnalyzing] = useState(false)
  const [viewResult, setViewResult] = useState<FigmaAnalysis | null>(null)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    try { setAnalyses(await listFigmaAnalyses()) }
    catch { /* ignore */ } finally { setLoading(false) }
  }

  async function handleAnalyze() {
    setAnalyzing(true)
    try {
      const result = await analyzeFigmaDesign(form.figma_url, form.figma_token, form.ticket_summary)
      setShowAnalyze(false)
      setForm({ figma_url: '', figma_token: '', ticket_summary: '' })
      await loadData()
      setViewResult(result)
    } catch (err: unknown) {
      alert(getApiErrorMessage(err, 'Analysis failed'))
    } finally { setAnalyzing(false) }
  }

  async function handleDelete(id: number) {
    if (!confirm('确定删除该分析结果吗？')) return
    try { await deleteFigmaAnalysis(id); await loadData() }
    catch { alert('删除失败') }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: '3rem', color: '#888' }}>加载中...</div>

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <h2 style={styles.title}>🎨 Figma 设计分析</h2>
        <button style={{ ...styles.btn, ...styles.btnPrimary }} onClick={() => setShowAnalyze(true)}>
          + 分析 Figma 设计
        </button>
      </div>
      <p style={styles.subtitle}>
        导入 Figma 设计链接，自动提取设计字段、组件结构，并生成后端实现影响分析。
      </p>

      {viewResult ? (
        <AnalysisDetail analysis={viewResult} onBack={() => setViewResult(null)} onDelete={handleDelete} />
      ) : analyses.length === 0 ? (
        <div style={styles.empty}>
          <p style={{ marginBottom: '0.75rem' }}>暂无设计分析。点击上方按钮导入 Figma 链接。</p>
        </div>
      ) : (
        <div style={styles.grid}>
          {analyses.map((a) => (
            <div key={a.id} style={{ ...styles.card, cursor: 'pointer' }} onClick={() => setViewResult(a)}>
              <div style={styles.cardTitle}>{a.file_name}</div>
              <div style={styles.cardText}>🖼️ {a.frame_count} 个框架 | 📝 {a.text_node_count} 个文本</div>
              <div style={{ marginTop: '0.3rem', display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
                {a.implications.slice(0, 3).map((imp, i) => (
                  <span key={i} style={styles.priorityTag(imp.priority)}>
                    {imp.priority}
                  </span>
                ))}
              </div>
              <div style={{ marginTop: '0.3rem', fontSize: '0.78rem', color: '#aaa' }}>
                {a.ai_used ? '🤖 AI 辅助' : '📐 规则分析'} · {new Date(a.created_at).toLocaleString('zh-CN')}
              </div>
              <div style={styles.cardActions}>
                <button style={{ ...styles.btn, ...styles.btnDanger, ...styles.btnSmall }} onClick={(e) => { e.stopPropagation(); handleDelete(a.id) }}>
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Analyze Modal */}
      {showAnalyze && (
        <div style={styles.modalOverlay} onClick={() => setShowAnalyze(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalTitle}>分析 Figma 设计</div>
            <div style={styles.modalSub}>输入 Figma 链接和 Token，自动提取设计字段并生成后端影响分析</div>

            <label style={styles.label}>Figma 设计链接</label>
            <input style={styles.input} type="url" value={form.figma_url}
              onChange={(e) => setForm({ ...form, figma_url: e.target.value })}
              placeholder="https://www.figma.com/design/xxx/..." required />

            <label style={styles.label}>Figma Personal Access Token</label>
            <input style={styles.input} type="password" value={form.figma_token}
              onChange={(e) => setForm({ ...form, figma_token: e.target.value })}
              placeholder="figd_..." required />
            <div style={{ fontSize: '0.8rem', color: '#888', marginBottom: '1rem' }}>
              在 Figma &gt; Settings &gt; Personal Access Tokens 创建。需要 file:read 权限。
            </div>

            <label style={styles.label}>关联 Ticket 摘要 (可选)</label>
            <input style={styles.input} type="text" value={form.ticket_summary}
              onChange={(e) => setForm({ ...form, ticket_summary: e.target.value })}
              placeholder="如: 新增用户资料编辑页面" />

            <div style={styles.modalActions}>
              <button style={{ ...styles.btn, background: '#ccc', color: '#333' }} onClick={() => setShowAnalyze(false)}>取消</button>
              <button style={{ ...styles.btn, ...styles.btnPrimary }} onClick={handleAnalyze} disabled={analyzing || !form.figma_url || !form.figma_token}>
                {analyzing ? '分析中...' : '开始分析'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function AnalysisDetail({ analysis, onBack, onDelete }: { analysis: FigmaAnalysis; onBack: () => void; onDelete: (id: number) => void }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div>
          <button onClick={onBack} style={{ background: 'none', border: 'none', color: '#4fc3f7', cursor: 'pointer', fontSize: '0.9rem', marginRight: '0.75rem' }}>← 返回</button>
          <span style={{ fontSize: '1.1rem', fontWeight: 600, color: '#1a1a2e' }}>{analysis.file_name}</span>
        </div>
        <span style={{ fontSize: '0.78rem', color: '#aaa' }}>
          {analysis.ai_used ? '🤖 AI 辅助分析' : '📐 规则分析'}
        </span>
      </div>

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <div style={{ background: '#fff', borderRadius: 8, padding: '0.75rem 1rem', border: '1px solid #eee', flex: 1, minWidth: 120 }}>
          <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{analysis.frame_count}</div>
          <div style={{ fontSize: '0.8rem', color: '#888' }}>框架/页面</div>
        </div>
        <div style={{ background: '#fff', borderRadius: 8, padding: '0.75rem 1rem', border: '1px solid #eee', flex: 1, minWidth: 120 }}>
          <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{analysis.text_node_count}</div>
          <div style={{ fontSize: '0.8rem', color: '#888' }}>文本节点</div>
        </div>
        <div style={{ background: '#fff', borderRadius: 8, padding: '0.75rem 1rem', border: '1px solid #eee', flex: 1, minWidth: 120 }}>
          <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{analysis.implications.length}</div>
          <div style={{ fontSize: '0.8rem', color: '#888' }}>影响项</div>
        </div>
      </div>

      {/* Implications */}
      <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#1a1a2e', marginBottom: '0.75rem' }}>后端影响分析</h3>
      {analysis.implications.map((imp, i) => (
        <div key={i} style={{
          background: '#fff', borderRadius: 8, padding: '0.75rem 1rem', marginBottom: '0.5rem',
          border: '1px solid #eee', borderLeft: `4px solid ${
            imp.priority === 'high' ? '#e74c3c' : imp.priority === 'medium' ? '#ffb74d' : '#90a4ae'
          }`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.3rem' }}>
            <span style={styles.priorityTag(imp.priority)}>{imp.priority}</span>
            <span style={{ fontSize: '0.72rem', color: '#888' }}>{imp.type}</span>
          </div>
          <div style={{ fontSize: '0.95rem', fontWeight: 500, color: '#1a1a2e' }}>{imp.title}</div>
          <div style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.2rem' }}>{imp.description}</div>
          {imp.detail && Object.keys(imp.detail).length > 0 && (
            <pre style={{ fontSize: '0.75rem', background: '#f5f5f5', padding: '0.4rem 0.6rem', borderRadius: 4, marginTop: '0.3rem', overflow: 'auto', maxHeight: 120 }}>
              {JSON.stringify(imp.detail, null, 2)}
            </pre>
          )}
        </div>
      ))}

      {/* Design Tokens */}
      {analysis.design_tokens && (
        <details style={{ marginTop: '1rem' }}>
          <summary style={{ cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600, color: '#1a1a2e' }}>
            设计系统 Token ({Object.keys(analysis.design_tokens.colors || {}).length} 颜色, {analysis.design_tokens.spacing?.length || 0} 间距)
          </summary>
          <div style={styles.detailSection}>
            {analysis.design_tokens.colors && Object.keys(analysis.design_tokens.colors).length > 0 && (
              <div style={{ marginBottom: '0.5rem' }}>
                <strong>Colors:</strong>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', marginTop: '0.3rem' }}>
                  {Object.entries(analysis.design_tokens.colors).slice(0, 20).map(([name, color]) => (
                    <div key={name} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', background: '#fff', padding: '0.2rem 0.5rem', borderRadius: 4, border: '1px solid #eee' }}>
                      <span style={{ width: 12, height: 12, borderRadius: 2, background: color as string, display: 'inline-block' }} />
                      <span style={{ fontSize: '0.72rem' }}>{name}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {analysis.design_tokens.spacing && analysis.design_tokens.spacing.length > 0 && (
              <div>
                <strong>Spacing:</strong>
                <div style={{ marginTop: '0.2rem' }}>
                  {analysis.design_tokens.spacing.map((s: number, i: number) => (
                    <span key={i} style={styles.tokenChip}>{s}px</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </details>
      )}

      <div style={{ marginTop: '1rem' }}>
        <button style={{ ...styles.btn, ...styles.btnDanger, ...styles.btnSmall }} onClick={() => onDelete(analysis.id)}>
          删除此分析
        </button>
      </div>
    </div>
  )
}
