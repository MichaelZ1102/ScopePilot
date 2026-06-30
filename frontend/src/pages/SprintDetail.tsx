import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { getSprint, type SprintDetail, type TicketDetail } from '../lib/api'
import CodeImpactPanel from '../components/CodeImpactPanel'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const styles: any = {
  page: { maxWidth: 1100, margin: '0 auto' },
  backLink: { display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: '#4fc3f7', cursor: 'pointer', fontSize: '0.9rem', marginBottom: '1rem', textDecoration: 'none' },
  header: { background: '#fff', borderRadius: 12, padding: '1.5rem 2rem', marginBottom: '1.5rem', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' },
  sprintName: { fontSize: '1.5rem', fontWeight: 700, color: '#1a1a2e', marginBottom: '0.5rem' },
  metaRow: { display: 'flex', gap: '2rem', flexWrap: 'wrap' as const, fontSize: '0.9rem', color: '#666' },
  metaItem: { display: 'flex', alignItems: 'center', gap: '0.4rem' },
  badge: (state: string): React.CSSProperties => {
    const colors: Record<string, string> = { active: '#81c784', closed: '#90a4ae', future: '#4fc3f7' }
    return { background: colors[state] || '#eee', color: '#fff', padding: '0.2rem 0.6rem', borderRadius: 10, fontSize: '0.8rem', fontWeight: 500 }
  },
  tableWrapper: { background: '#fff', borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' },
  table: { width: '100%', borderCollapse: 'collapse' as const },
  th: { padding: '0.85rem 1rem', textAlign: 'left' as const, fontSize: '0.8rem', fontWeight: 600, color: '#888', borderBottom: '2px solid #eee', textTransform: 'uppercase' as const, letterSpacing: '0.5px' },
  td: { padding: '0.75rem 1rem', fontSize: '0.88rem', color: '#333', borderBottom: '1px solid #f0f0f0', verticalAlign: 'top' as const },
  tr: { cursor: 'pointer', transition: 'background 0.15s' },
  trExpanded: { background: '#f8faff' },
  priorityBadge: (p?: string): React.CSSProperties => {
    const colors: Record<string, string> = { Highest: '#e74c3c', High: '#e67e22', Medium: '#f1c40f', Low: '#3498db', Lowest: '#95a5a6' }
    return { background: (p && colors[p]) || '#eee', color: (p && colors[p]) ? '#fff' : '#333', padding: '0.15rem 0.5rem', borderRadius: 10, fontSize: '0.75rem' }
  },
  expandedRow: { background: '#f8faff' },
  detailPanel: { padding: '1rem 2rem 1.5rem', background: '#f8faff', borderBottom: '1px solid #e8ecf4' },
  detailLabel: { fontSize: '0.8rem', fontWeight: 600, color: '#666', marginBottom: '0.25rem', marginTop: '0.75rem' },
  detailText: { fontSize: '0.88rem', color: '#333', lineHeight: 1.5, whiteSpace: 'pre-wrap' as const },
  tag: { display: 'inline-block', padding: '0.15rem 0.5rem', borderRadius: 4, background: '#e8ecf4', color: '#555', fontSize: '0.78rem', marginRight: '0.3rem', marginBottom: '0.3rem' },
  loading: { textAlign: 'center' as const, padding: '3rem', color: '#888' },
  empty: { textAlign: 'center' as const, padding: '2rem', color: '#888' },
}

export default function SprintDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [sprint, setSprint] = useState<SprintDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedTicket, setExpandedTicket] = useState<number | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    getSprint(Number(id))
      .then(setSprint)
      .catch(() => { alert(t('sprint.load_failed')); navigate('/') })
      .finally(() => setLoading(false))
  }, [id, navigate, t])

  if (loading) return <div style={styles.loading}>{t('dashboard.loading')}</div>
  if (!sprint) return <div style={styles.empty}>{t('sprint.not_found')}</div>

  const tickets = sprint.tickets || []

  return (
    <div style={styles.page}>
      <div style={styles.backLink} onClick={() => navigate('/')}>{t('sprint.back')}</div>

      <div style={styles.header}>
        <div style={styles.sprintName}>{sprint.name}</div>
        <div style={styles.metaRow}>
          <div style={styles.metaItem}><span>{t('sprint.status')}:</span><span style={styles.badge(sprint.state)}>{sprint.state}</span></div>
          <div style={styles.metaItem}><span>{t('sprint.tickets')}:</span><span>{sprint.total_tickets}</span></div>
          <div style={styles.metaItem}><span>{t('sprint.analysis')}:</span><span>{sprint.analysis_status || '-'}</span></div>
          {sprint.started_at && <div style={styles.metaItem}><span>{t('sprint.start_date')}:</span><span>{sprint.started_at.slice(0, 10)}</span></div>}
          {sprint.ended_at && <div style={styles.metaItem}><span>{t('sprint.end_date')}:</span><span>{sprint.ended_at.slice(0, 10)}</span></div>}
        </div>
      </div>

      {tickets.length === 0 ? (
        <div style={styles.empty}>{t('sprint.no_tickets')}</div>
      ) : (
        <div style={styles.tableWrapper}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>{t('sprint.table_key')}</th>
                <th style={{ ...styles.th, minWidth: 250 }}>{t('sprint.table_summary')}</th>
                <th style={styles.th}>{t('sprint.table_status')}</th>
                <th style={styles.th}>{t('sprint.table_priority')}</th>
                <th style={styles.th}>{t('sprint.table_assignee')}</th>
                <th style={styles.th}>{t('sprint.table_story_points')}</th>
              </tr>
            </thead>
            <tbody>
              {tickets.map((ticket) => (
                <TicketRow key={ticket.id} ticket={ticket} isExpanded={expandedTicket === ticket.id} onToggle={() => setExpandedTicket(expandedTicket === ticket.id ? null : ticket.id)} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function TicketRow({ ticket, isExpanded, onToggle }: { ticket: TicketDetail; isExpanded: boolean; onToggle: () => void }) {
  const { t } = useTranslation()
  return (
    <>
      <tr style={{ ...styles.tr, ...(isExpanded ? styles.trExpanded : {}) }} onClick={onToggle}>
        <td style={styles.td}><span style={{ fontWeight: 600, color: '#1a1a2e' }}>{ticket.key}</span></td>
        <td style={styles.td}>{ticket.summary}</td>
        <td style={styles.td}>{ticket.status || '-'}</td>
        <td style={styles.td}><span style={styles.priorityBadge(ticket.priority)}>{ticket.priority || '-'}</span></td>
        <td style={styles.td}>{ticket.assignee || '-'}</td>
        <td style={styles.td}>{ticket.story_points != null ? ticket.story_points : '-'}</td>
      </tr>
      {isExpanded && (
        <tr style={styles.expandedRow}>
          <td colSpan={6} style={{ padding: 0 }}>
            <div style={styles.detailPanel}>
              {ticket.description && <><div style={styles.detailLabel}>{t('sprint.detail_description')}</div><div style={styles.detailText}>{ticket.description}</div></>}
              {ticket.acceptance_criteria && ticket.acceptance_criteria.length > 0 && (
                <><div style={styles.detailLabel}>{t('sprint.detail_ac')}</div>
                  <ul style={{ margin: '0.25rem 0', paddingLeft: '1.25rem' }}>
                    {ticket.acceptance_criteria.map((c, i) => <li key={i} style={{ fontSize: '0.88rem', color: '#333', marginBottom: '0.2rem' }}>{c}</li>)}
                  </ul>
                </>
              )}
              {ticket.labels && ticket.labels.length > 0 && (
                <><div style={styles.detailLabel}>{t('sprint.detail_labels')}</div>
                  <div>{ticket.labels.map((l) => <span key={l} style={styles.tag}>{l}</span>)}</div>
                </>
              )}
              {ticket.issue_type && <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: '#666' }}>{t('sprint.detail_type')}: {ticket.issue_type}</div>}
              <CodeImpactPanel
                ticketId={ticket.id}
                sprintId={ticket.sprint_id}
                summary={ticket.summary}
                description={ticket.description}
              />
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
