import { useEffect, useState } from 'react'
import { Code2, FileCode2, LoaderCircle, RefreshCw, X } from 'lucide-react'

import {
  analyzeCodeImpact,
  getTicketCodeImpact,
  listCodeSources,
  type CodeImpact,
  type CodeSource,
} from '../lib/api'

interface Props {
  ticketId: number
  sprintId: number
  summary: string
  description?: string
  readOnly?: boolean
}

export default function CodeImpactPanel({ ticketId, sprintId, summary, description, readOnly = false }: Props) {
  const [sources, setSources] = useState<CodeSource[]>([])
  const [impact, setImpact] = useState<CodeImpact | null>(null)
  const [loading, setLoading] = useState(false)
  const [showSources, setShowSources] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setImpact(null)
    setError('')
    getTicketCodeImpact(ticketId)
      .then(setImpact)
      .catch(() => undefined)
  }, [ticketId])

  async function handleAnalyze(sourceId: number) {
    setLoading(true)
    setShowSources(false)
    setError('')
    try {
      const result = await analyzeCodeImpact(
        sourceId,
        ticketId,
        sprintId,
        summary,
        description,
      )
      setImpact(result)
    } catch {
      setError('代码影响分析失败，请检查代码源是否已完成扫描。')
    } finally {
      setLoading(false)
    }
  }

  async function openSourcePicker() {
    setError('')
    try {
      setSources(await listCodeSources())
      setShowSources(true)
    } catch {
      setError('代码源加载失败。')
    }
  }

  return (
    <section className="analysis-section code-impact-panel">
      <div className="analysis-section-heading">
        <span className="analysis-section-icon"><Code2 size={20} /></span>
        <div>
          <h3>代码影响</h3>
          <p>根据 Ticket 内容定位可能需要修改的文件和模块。</p>
        </div>
        {!readOnly && (
          <button className="button button-secondary section-action" type="button" onClick={openSourcePicker} disabled={loading}>
            {loading ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={16} />}
            {impact ? '重新分析' : '选择代码源分析'}
          </button>
        )}
      </div>

      {error && <div className="inline-error">{error}</div>}

      {impact ? (
        <div className="impact-content">
          <p className="impact-summary">{impact.summary}</p>
          <div className="impact-file-list">
            {(impact.affected_files || []).map((file) => (
              <div className="impact-file-row" key={`${file.path}-${file.change_type}`}>
                <FileCode2 size={17} />
                <code>{file.path}</code>
                <span className="change-badge">{file.change_type}</span>
                <span className="confidence">{Math.round(file.confidence * 100)}%</span>
                {file.reasons?.length ? <small>{file.reasons.join('；')}</small> : null}
              </div>
            ))}
            {(impact.affected_files || []).length === 0 && (
              <div className="analysis-empty-inline">暂未识别到受影响文件。</div>
            )}
          </div>
        </div>
      ) : (
        <div className="analysis-empty">
          <Code2 size={28} />
          <strong>尚未生成代码影响分析</strong>
          <span>先在 Codebase 页面添加并扫描代码源，然后从这里开始分析。</span>
          {!readOnly && <button className="button button-primary" type="button" onClick={openSourcePicker} disabled={loading}>选择代码源</button>}
        </div>
      )}

      {showSources && (
        <div className="workspace-modal-backdrop" role="presentation" onMouseDown={() => setShowSources(false)}>
          <div className="workspace-modal" role="dialog" aria-modal="true" aria-labelledby="source-dialog-title" onMouseDown={(event) => event.stopPropagation()}>
            <div className="workspace-modal-header">
              <div>
                <h3 id="source-dialog-title">选择代码源</h3>
                <p>使用已扫描的代码仓库分析当前 Ticket。</p>
              </div>
              <button className="icon-button" type="button" aria-label="关闭" title="关闭" onClick={() => setShowSources(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="source-list">
              {sources.map((source) => (
                <button className="source-option" type="button" key={source.id} onClick={() => handleAnalyze(source.id)}>
                  <Code2 size={18} />
                  <span>
                    <strong>{source.name}</strong>
                    <small>{source.provider} · {source.default_branch}</small>
                  </span>
                  <span className={`source-status is-${source.scan_status}`}>{source.scan_status}</span>
                </button>
              ))}
              {sources.length === 0 && (
                <div className="analysis-empty-inline">尚未配置代码源，请先前往 Codebase 页面添加。</div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
