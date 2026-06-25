import { useState, useEffect } from 'react'

interface Sprint {
  id: number
  name: string
  state: string
  total_tickets: number
}

export default function Dashboard() {
  const [sprints, setSprints] = useState<Sprint[]>([])

  useEffect(() => {
    // TODO: fetch from API
    setSprints([
      { id: 3060, name: 'LPRO Sprint 0707', state: 'active', total_tickets: 43 },
    ])
  }, [])

  return (
    <div>
      <h2 style={{ marginBottom: '1.5rem' }}>📊 Dashboard</h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
        <StatCard label="Active Sprints" value="1" color="#4fc3f7" />
        <StatCard label="Total Tickets" value="43" color="#81c784" />
        <StatCard label="Pending Analysis" value="--" color="#ffb74d" />
      </div>

      <h3 style={{ marginBottom: '0.75rem' }}>Recent Sprints</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: 8 }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #eee', textAlign: 'left' }}>
            <th style={{ padding: '0.75rem 1rem' }}>Sprint</th>
            <th style={{ padding: '0.75rem 1rem' }}>State</th>
            <th style={{ padding: '0.75rem 1rem' }}>Tickets</th>
            <th style={{ padding: '0.75rem 1rem' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sprints.map(s => (
            <tr key={s.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
              <td style={{ padding: '0.75rem 1rem' }}>{s.name}</td>
              <td style={{ padding: '0.75rem 1rem' }}><Badge state={s.state} /></td>
              <td style={{ padding: '0.75rem 1rem' }}>{s.total_tickets}</td>
              <td style={{ padding: '0.75rem 1rem' }}>
                <button style={btnStyle}>View Report</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ background: '#fff', borderRadius: 8, padding: '1.25rem', borderLeft: `4px solid ${color}` }}>
      <div style={{ color: '#666', fontSize: '0.85rem', marginBottom: '0.25rem' }}>{label}</div>
      <div style={{ fontSize: '1.75rem', fontWeight: 700 }}>{value}</div>
    </div>
  )
}

function Badge({ state }: { state: string }) {
  const colors: Record<string, string> = { active: '#81c784', closed: '#90a4ae', future: '#4fc3f7' }
  return (
    <span style={{
      background: colors[state] || '#eee',
      color: '#fff',
      padding: '0.2rem 0.6rem',
      borderRadius: 12,
      fontSize: '0.8rem',
    }}>
      {state}
    </span>
  )
}

const btnStyle: React.CSSProperties = {
  padding: '0.4rem 0.8rem',
  background: '#1a1a2e',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  cursor: 'pointer',
  fontSize: '0.85rem',
}
