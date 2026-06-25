import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getSprint, type SprintDetail, type TicketDetail } from '../lib/api'

const styles = {
  page: { maxWidth: 1100, margin: '0 auto' },
  backLink: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.3rem',
    color: '#4fc3f7',
    cursor: 'pointer',
    fontSize: '0.9rem',
    marginBottom: '1rem',
    textDecoration: 'none',
  } as React.CSSProperties,
  header: {
    background: '#fff',
    borderRadius: 12,
    padding: '1.5rem 2rem',
    marginBottom: '1.5rem',
    boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
  } as React.CSSProperties,
  sprintName: { fontSize: '1.5rem', fontWeight: 700, color: '#1a1a2e', marginBottom: '0.5rem' },
  metaRow: {
    display: 'flex',
    gap: '2rem',
    flexWrap: 'wrap' as const,
    fontSize: '0.9rem',
    color: '#666',
  },
  metaItem: { display: 'flex', alignItems: 'center', gap: '0.4rem' },
  badge: (state: string): React.CSSProperties => {
    const colors: Record<string, string> = { active: '#81c784', closed: '#90a4ae', future: '#4fc3f7' }
    return {
      background: colors[state] || '#eee',
      color: '#fff',
      padding: '0.2rem 0.6rem',
      borderRadius: 10,
      fontSize: '0.8rem',
      fontWeight: 500,
    }
  },
  tableWrapper: {
    background: '#fff',
    borderRadius: 12,
    overflow: 'hidden',
    boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
  } as React.CSSProperties,
  table: { width: '100%', borderCollapse: 'collapse' as const },
  th: {
    padding: '0.85rem 1rem',
    textAlign: 'left' as const,
    fontSize: '0.8rem',
    fontWeight: 600,
    color: '#888',
    borderBottom: '2px solid #eee',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },
  td: {
    padding: '0.75rem 1rem',
    fontSize: '0.88rem',
    color: '#333',
    borderBottom: '1px solid #f0f0f0',
    verticalAlign: 'top' as const,
  },
  tr: { cursor: 'pointer', transition: 'background 0.15s' },
  trExpanded: { background: '#f8faff' },
  priorityBadge: (p?: string): React.CSSProperties => {
    const colors: Record<string, string> = {
      Highest: '#e74c3c',
      High: '#e67e22',
      Medium: '#f1c40f',
      Low: '#3498db',
      Lowest: '#95a5a6',
    }
    return {
      background: (p && colors[p]) || '#eee',
      color: (p && colors[p]) ? '#fff' : '#333',
      padding: '0.15rem 0.5rem',
      borderRadius: 10,
      fontSize: '0.75rem',
    }
  },
  expandedRow: { background: '#f8faff' },
  detailPanel: {
    padding: '1rem 2rem 1.5rem',
    background: '#f8faff',
    borderBottom: '1px solid #e8ecf4',
  } as React.CSSProperties,
  detailLabel: { fontSize: '0.8rem', fontWeight: 600, color: '#666', marginBottom: '0.25rem', marginTop: '0.75rem' },
  detailText: { fontSize: '0.88rem', color: '#333', lineHeight: 1.5, whiteSpace: 'pre-wrap' as const },
  tag: {
    display: 'inline-block',
    padding: '0.15rem 0.5rem',
    borderRadius: 4,
    background: '#e8ecf4',
    color: '#555',
    fontSize: '0.78rem',
    marginRight: '0.3rem',
    marginBottom: '0.3rem',
  } as React.CSSProperties,
  loading: { textAlign: 'center' as const, padding: '3rem', color: '#888' },
  empty: { textAlign: 'center' as const, padding: '2rem', color: '#888' },
}

export default function SprintDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [sprint, setSprint] = useState<SprintDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedTicket, setExpandedTicket] = useState<number | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    getSprint(Number(id))
      .then(setSprint)
      .catch(() => {
        alert('获取 Sprint 详情失败')
        navigate('/')
      })
      .finally(() => setLoading(false))
  }, [id, navigate])

  if (loading) {
    return <div style={styles.loading}>加载中...</div>
  }

  if (!sprint) {
    return <div style={styles.empty}>Sprint 未找到</div>
  }

  const tickets = sprint.tickets || []

  return (
    <div style={styles.page}>
      <div style={styles.backLink} onClick={() => navigate('/')}>
        ← 返回仪表盘
      </div>

      <div style={styles.header}>
        <div style={styles.sprintName}>{sprint.name}</div>
        <div style={styles.metaRow}>
          <div style={styles.metaItem}>
            <span>状态:</span>
            <span style={styles.badge(sprint.state)}>{sprint.state}</span>
          </div>
          <div style={styles.metaItem}>
            <span>工单数:</span>
            <span>{sprint.total_tickets}</span>
          </div>
          <div style={styles.metaItem}>
            <span>分析状态:</span>
            <span>{sprint.analysis_status || '-'}</span>
          </div>
          {sprint.started_at && (
            <div style={styles.metaItem}>
              <span>开始:</span>
              <span>{sprint.started_at.slice(0, 10)}</span>
            </div>
          )}
          {sprint.ended_at && (
            <div style={styles.metaItem}>
              <span>结束:</span>
              <span>{sprint.ended_at.slice(0, 10)}</span>
            </div>
          )}
        </div>
      </div>

      {tickets.length === 0 ? (
        <div style={styles.empty}>该 Sprint 暂无工单数据</div>
      ) : (
        <div style={styles.tableWrapper}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Key</th>
                <th style={{ ...styles.th, minWidth: 250 }}>摘要</th>
                <th style={styles.th}>状态</th>
                <th style={styles.th}>优先级</th>
                <th style={styles.th}>经办人</th>
                <th style={styles.th}>故事点</th>
              </tr>
            </thead>
            <tbody>
              {tickets.map((t) => (
                <TicketRow
                  key={t.id}
                  ticket={t}
                  isExpanded={expandedTicket === t.id}
                  onToggle={() =>
                    setExpandedTicket(expandedTicket === t.id ? null : t.id)
                  }
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function TicketRow({
  ticket,
  isExpanded,
  onToggle,
}: {
  ticket: TicketDetail
  isExpanded: boolean
  onToggle: () => void
}) {
  return (
    <>
      <tr
        style={{
          ...styles.tr,
          ...(isExpanded ? styles.trExpanded : {}),
        }}
        onClick={onToggle}
      >
        <td style={styles.td}>
          <span style={{ fontWeight: 600, color: '#1a1a2e' }}>{ticket.key}</span>
        </td>
        <td style={styles.td}>{ticket.summary}</td>
        <td style={styles.td}>{ticket.status || '-'}</td>
        <td style={styles.td}>
          <span style={styles.priorityBadge(ticket.priority)}>
            {ticket.priority || '-'}
          </span>
        </td>
        <td style={styles.td}>{ticket.assignee || '-'}</td>
        <td style={styles.td}>
          {ticket.story_points != null ? ticket.story_points : '-'}
        </td>
      </tr>
      {isExpanded && (
        <tr style={styles.expandedRow}>
          <td colSpan={6} style={{ padding: 0 }}>
            <div style={styles.detailPanel}>
              {ticket.description && (
                <>
                  <div style={styles.detailLabel}>描述</div>
                  <div style={styles.detailText}>{ticket.description}</div>
                </>
              )}

              {ticket.acceptance_criteria && ticket.acceptance_criteria.length > 0 && (
                <>
                  <div style={styles.detailLabel}>验收标准</div>
                  <ul style={{ margin: '0.25rem 0', paddingLeft: '1.25rem' }}>
                    {ticket.acceptance_criteria.map((c, i) => (
                      <li key={i} style={{ fontSize: '0.88rem', color: '#333', marginBottom: '0.2rem' }}>
                        {c}
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {ticket.labels && ticket.labels.length > 0 && (
                <>
                  <div style={styles.detailLabel}>标签</div>
                  <div>
                    {ticket.labels.map((l) => (
                      <span key={l} style={styles.tag}>{l}</span>
                    ))}
                  </div>
                </>
              )}

              {ticket.issue_type && (
                <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: '#666' }}>
                  类型: {ticket.issue_type}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
