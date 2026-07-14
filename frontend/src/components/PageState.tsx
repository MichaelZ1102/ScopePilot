import { type ReactNode } from 'react'
import { AlertCircle, Inbox, LoaderCircle } from 'lucide-react'

interface Props {
  loading?: boolean
  error?: Error | null
  empty?: boolean
  emptyText?: string
  children: ReactNode
}

export function PageState({ loading, error, empty, emptyText = '暂无数据', children }: Props) {
  if (loading) {
    return (
      <div className="loading-state" role="status" aria-live="polite">
        <span className="loading-state-icon"><LoaderCircle className="spin" size={22} /></span>
        <p>正在加载...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="empty-state" role="alert">
        <span className="empty-state-icon"><AlertCircle size={22} /></span>
        <h2>加载失败</h2>
        <p>{error.message}</p>
      </div>
    )
  }

  if (empty) {
    return (
      <div className="empty-state">
        <span className="empty-state-icon"><Inbox size={22} /></span>
        <p>{emptyText}</p>
      </div>
    )
  }

  return <>{children}</>
}
