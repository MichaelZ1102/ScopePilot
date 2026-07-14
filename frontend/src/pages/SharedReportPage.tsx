import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { FileText, LoaderCircle, LockKeyhole, ScanSearch } from 'lucide-react'

import { accessSharedReport } from '../lib/team'
import { getApiErrorMessage } from '../lib/client'
import type { SharedReportAccess } from '../lib/types'

function renderInline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>
    }
    return part
  })
}

function renderMarkdown(content: string): ReactNode[] {
  const nodes: ReactNode[] = []
  let listItems: string[] = []
  let inCode = false
  let codeLines: string[] = []

  const flushList = () => {
    if (!listItems.length) return
    nodes.push(
      <ul key={`list-${nodes.length}`}>
        {listItems.map((item, index) => <li key={index}>{renderInline(item)}</li>)}
      </ul>,
    )
    listItems = []
  }

  const flushCode = () => {
    if (!codeLines.length) return
    nodes.push(<code className="code-block" key={`code-${nodes.length}`}>{codeLines.join('\n')}</code>)
    codeLines = []
  }

  content.split(/\r?\n/).forEach((line) => {
    if (line.trim().startsWith('```')) {
      if (inCode) flushCode()
      else flushList()
      inCode = !inCode
      return
    }

    if (inCode) {
      codeLines.push(line)
      return
    }

    const trimmed = line.trim()
    if (!trimmed) {
      flushList()
      return
    }

    const bullet = trimmed.match(/^[-*]\s+(.+)$/)
    if (bullet) {
      listItems.push(bullet[1])
      return
    }

    flushList()
    const heading = trimmed.match(/^(#{1,3})\s+(.+)$/)
    if (heading) {
      const Tag = heading[1].length === 1 ? 'h2' : heading[1].length === 2 ? 'h3' : 'h4'
      nodes.push(<Tag key={`heading-${nodes.length}`}>{renderInline(heading[2])}</Tag>)
      return
    }

    nodes.push(<p key={`paragraph-${nodes.length}`}>{renderInline(trimmed)}</p>)
  })

  if (inCode) flushCode()
  flushList()
  return nodes
}

export default function SharedReportPage() {
  const { token = '' } = useParams()
  const [report, setReport] = useState<SharedReportAccess | null>(null)
  const [password, setPassword] = useState('')
  const [needsPassword, setNeedsPassword] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function loadReport(nextPassword = '') {
    setLoading(true)
    setError('')
    try {
      const data = await accessSharedReport(token, nextPassword)
      setReport(data)
      setNeedsPassword(false)
    } catch (requestError: unknown) {
      const detail = getApiErrorMessage(requestError, 'Unable to load shared report.')
      const status = typeof requestError === 'object' && requestError !== null && 'response' in requestError
        ? (requestError as { response?: { status?: number } }).response?.status
        : undefined
      if (status === 403) setNeedsPassword(true)
      setError(detail)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (token) loadReport()
  }, [token])

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    loadReport(password)
  }

  return (
    <main className="shared-report-page">
      <div className="shared-report-shell">
        <div className="shared-report-brand"><ScanSearch size={18} /> ScopePilot</div>
        <article className="shared-report-card">
          <header className="shared-report-header">
            <span className="workspace-kicker">Shared Sprint Analysis</span>
            <h1>{report?.title || '共享分析报告'}</h1>
            {report && (
              <p>Sprint #{report.sprint_id} · 分享人 {report.shared_by || 'ScopePilot'} · 已查看 {report.view_count} 次</p>
            )}
          </header>

          {loading && (
            <div className="loading-state" role="status" aria-live="polite" style={{ border: 0, borderRadius: 0 }}>
              <span className="loading-state-icon"><LoaderCircle className="spin" size={22} /></span>
              <p>正在加载报告...</p>
            </div>
          )}

          {needsPassword && !loading && (
            <form className="shared-report-access" onSubmit={handleSubmit}>
              <span className="resource-icon"><LockKeyhole size={18} /></span>
              <input className="toolbar-input" aria-label="报告访问密码" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="输入报告访问密码" autoFocus />
              <button className="button button-primary" type="submit">打开报告</button>
            </form>
          )}

          {error && !loading && <div className="inline-error" role="alert" style={{ margin: 24 }}>{error}</div>}
          {report?.content_error && <div className="inline-error" role="alert" style={{ margin: 24 }}>{report.content_error}</div>}

          {report?.content && (
            <section className="shared-report-content">
              <div className="detail-heading">
                <span className="resource-icon"><FileText size={18} /></span>
                <div><h2>分析内容</h2><p>由 ScopePilot 根据 Sprint Ticket 生成</p></div>
              </div>
              {renderMarkdown(report.content)}
            </section>
          )}
        </article>
      </div>
    </main>
  )
}
