import { useState } from 'react'
import { listCodeSources, analyzeCodeImpact, type CodeSource, type CodeImpact } from '../lib/api'

const styles: any = {
  container: { marginTop: '0.75rem' },
  btn: { padding: '0.35rem 0.8rem', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: '0.8rem', fontWeight: 500, color: '#fff', background: '#1a1a2e' },
  btnSmall: { padding: '0.25rem 0.6rem', fontSize: '0.75rem' },
  impactBox: { background: '#fff', borderRadius: 8, padding: '0.75rem 1rem', marginTop: '0.5rem', border: '1px solid #e8ecf4' },
  summary: { fontSize: '0.85rem', color: '#333', lineHeight: 1.5, marginBottom: '0.5rem' },
  fileRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.3rem 0', borderBottom: '1px solid #f0f0f0', fontSize: '0.8rem' },
  filePath: { fontFamily: 'monospace', fontSize: '0.78rem', color: '#1a1a2e' },
  changeTag: (type: string) => {
    const colors: Record<string, string> = { modify: '#4fc3f7', create: '#81c784', test: '#ffb74d', config: '#ba68c8' }
    return { background: colors[type] || '#eee', color: '#fff', padding: '0.1rem 0.4rem', borderRadius: 4, fontSize: '0.7rem' }
  },
  confBar: (conf: number) => ({
    width: `${conf * 100}%`,
    height: 4,
    background: conf > 0.7 ? '#81c784' : conf > 0.4 ? '#ffb74d' : '#e74c3c',
    borderRadius: 2,
    marginLeft: '0.5rem',
  }),
  noData: { fontSize: '0.8rem', color: '#888', padding: '0.5rem 0' },
}

interface Props {
  ticketId: number
  sprintId: number
  summary: string
  description?: string
}

export default function CodeImpactPanel({ ticketId, sprintId, summary, description }: Props) {
  const [sources, setSources] = useState<CodeSource[]>([])
  const [impact, setImpact] = useState<CodeImpact | null>(null)
  const [loading, setLoading] = useState(false)
  const [showSources, setShowSources] = useState(false)

  async function handleAnalyze(sourceId: number) {
    setLoading(true)
    setShowSources(false)
    try {
      const result = await analyzeCodeImpact(sourceId, ticketId, sprintId, summary, description)
      setImpact(result)
    } catch {
      alert('分析失败')
    } finally {
      setLoading(false)
    }
  }

  async function loadSources() {
    try {
      const srcs = await listCodeSources()
      setSources(srcs)
      setShowSources(true)
    } catch {
      alert('加载代码源失败')
    }
  }

  return (
    <div style={styles.container}>
      {impact ? (
        <div style={styles.impactBox}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <strong style={{ fontSize: '0.85rem', color: '#1a1a2e' }}>🔍 Code Impact</strong>
            <button style={{ ...styles.btn, ...styles.btnSmall }} onClick={loadSources}>重新分析</button>
          </div>
          <div style={styles.summary}>{impact.summary}</div>
          {impact.affected_files && impact.affected_files.length > 0 && (
            <div>
              <div style={{ fontSize: '0.75rem', color: '#888', marginBottom: '0.25rem' }}>受影响文件 ({impact.affected_files.length})</div>
              {impact.affected_files.slice(0, 10).map((f, i) => (
                <div key={i} style={styles.fileRow}>
                  <span style={styles.filePath}>{f.path}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <span style={styles.changeTag(f.change_type)}>{f.change_type}</span>
                    <span style={{ fontSize: '0.7rem', color: '#888' }}>{Math.round(f.confidence * 100)}%</span>
                  </div>
                </div>
              ))}
              {impact.affected_files.length > 10 && (
                <div style={{ fontSize: '0.75rem', color: '#888', marginTop: '0.25rem' }}>
                  ... 还有 {impact.affected_files.length - 10} 个文件
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div>
          {loading ? (
            <div style={styles.noData}>分析中...</div>
          ) : (
            <button style={styles.btn} onClick={loadSources}>
              🔍 分析 Code Impact
            </button>
          )}
        </div>
      )}

      {/* Source picker dialog */}
      {showSources && (
        <div style={{
          position: 'fixed' as const, inset: 0, background: 'rgba(0,0,0,0.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200,
        }} onClick={() => setShowSources(false)}>
          <div style={{
            background: '#fff', borderRadius: 12, padding: '1.5rem', width: '100%', maxWidth: 400,
            boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
          }} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', color: '#1a1a2e' }}>
              选择代码源进行分析
            </div>
            {sources.length === 0 ? (
              <div style={{ fontSize: '0.85rem', color: '#888' }}>
                暂未配置代码源，请先在 Codebase 页面添加。
              </div>
            ) : (
              <div>
                {sources.map((s) => (
                  <div key={s.id} style={{
                    padding: '0.6rem 0.8rem', cursor: 'pointer', borderRadius: 6, marginBottom: '0.3rem',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    background: '#f8faff', border: '1px solid #e8ecf4',
                  }} onClick={() => handleAnalyze(s.id)}>
                    <span style={{ fontWeight: 500, fontSize: '0.9rem' }}>{s.name}</span>
                    <span style={{ fontSize: '0.75rem', color: '#888' }}>{s.provider}</span>
                  </div>
                ))}
              </div>
            )}
            <div style={{ marginTop: '1rem', textAlign: 'right' as const }}>
              <button style={{ ...styles.btn, background: '#ccc', color: '#333' }} onClick={() => setShowSources(false)}>
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
