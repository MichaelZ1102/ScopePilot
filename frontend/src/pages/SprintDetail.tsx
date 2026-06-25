import { useParams } from 'react-router-dom'

export default function SprintDetail() {
  const { id } = useParams()

  return (
    <div>
      <h2>Sprint Detail: {id}</h2>
      <p style={{ color: '#666' }}>Sprint analysis report will be displayed here.</p>
    </div>
  )
}
