import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { accessSharedReport } from '../lib/team'
import { getApiErrorMessage } from '../lib/client'
import type { SharedReportAccess } from '../lib/types'

const styles = {
  page: {
    minHeight: '100vh',
    background: '#f5f5f5',
    padding: '2rem',
    boxSizing: 'border-box' as const,
  },
  shell: {
    maxWidth: 900,
    margin: '0 auto',
    background: '#fff',
    borderRadius: 8,
    padding: '1.5rem',
    boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
  },
  title: {
    margin: 0,
    color: '#1a1a2e',
    fontSize: '1.4rem',
    lineHeight: 1.3,
  },
  meta: {
    marginTop: '0.5rem',
    color: '#777',
    fontSize: '0.85rem',
  },
  report: {
    marginTop: '1.5rem',
    padding: '1rem',
    border: '1px solid #eee',
    borderRadius: 6,
    background: '#fafafa',
    color: '#222',
    overflowX: 'auto' as const,
    lineHeight: 1.6,
    fontSize: '0.9rem',
  },
  reportHeading: {
    margin: '1rem 0 0.4rem',
    color: '#1a1a2e',
    lineHeight: 1.35,
  },
  reportParagraph: {
    margin: '0.45rem 0',
  },
  reportList: {
    margin: '0.35rem 0 0.75rem',
    paddingLeft: '1.25rem',
  },
  reportCode: {
    display: 'block',
    margin: '0.75rem 0',
    padding: '0.75rem',
    borderRadius: 6,
    background: '#f0f0f0',
    whiteSpace: 'pre-wrap' as const,
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
  },
  form: {
    marginTop: '1.5rem',
    display: 'flex',
    gap: '0.75rem',
    flexWrap: 'wrap' as const,
  },
  input: {
    flex: '1 1 240px',
    padding: '0.6rem 0.75rem',
    borderRadius: 6,
    border: '1px solid #ddd',
    fontSize: '0.9rem',
  },
  button: {
    padding: '0.6rem 1rem',
    border: 'none',
    borderRadius: 6,
    background: '#1a1a2e',
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 600,
  },
  message: {
    marginTop: '1rem',
    color: '#c0392b',
    fontSize: '0.9rem',
  },
}

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
      <ul key={`list-${nodes.length}`} style={styles.reportList}>
        {listItems.map((item, index) => <li key={index}>{renderInline(item)}</li>)}
      </ul>,
    )
    listItems = []
  }

  const flushCode = () => {
    if (!codeLines.length) return
    nodes.push(<code key={`code-${nodes.length}`} style={styles.reportCode}>{codeLines.join('\n')}</code>)
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
      const level = heading[1].length
      const fontSize = level === 1 ? '1.2rem' : level === 2 ? '1rem' : '0.92rem'
      const Tag = level === 1 ? 'h2' : level === 2 ? 'h3' : 'h4'
      nodes.push(
        <Tag key={`heading-${nodes.length}`} style={{ ...styles.reportHeading, fontSize }}>
          {renderInline(heading[2])}
        </Tag>,
      )
      return
    }

    nodes.push(
      <p key={`paragraph-${nodes.length}`} style={styles.reportParagraph}>
        {renderInline(trimmed)}
      </p>,
    )
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
    } catch (err: unknown) {
      const detail = getApiErrorMessage(err, 'Unable to load shared report.')
      const status = typeof err === 'object' && err !== null && 'response' in err
        ? (err as { response?: { status?: number } }).response?.status
        : undefined
      if (status === 403) {
        setNeedsPassword(true)
      }
      setError(detail)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (token) {
      loadReport()
    }
  }, [token])

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    loadReport(password)
  }

  return (
    <div style={styles.page}>
      <div style={styles.shell}>
        <h1 style={styles.title}>{report?.title || 'Shared report'}</h1>
        {report && (
          <div style={styles.meta}>
            Sprint #{report.sprint_id} - Shared by {report.shared_by || 'ScopePilot'} - Views {report.view_count}
          </div>
        )}

        {loading && <div style={styles.message}>Loading report...</div>}

        {needsPassword && (
          <form style={styles.form} onSubmit={handleSubmit}>
            <input
              style={styles.input}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Report password"
              autoFocus
            />
            <button style={styles.button} type="submit">Open report</button>
          </form>
        )}

        {error && !loading && <div style={styles.message}>{error}</div>}

        {report?.content_error && (
          <div style={styles.message}>{report.content_error}</div>
        )}

        {report?.content && (
          <div style={styles.report}>{renderMarkdown(report.content)}</div>
        )}
      </div>
    </div>
  )
}
