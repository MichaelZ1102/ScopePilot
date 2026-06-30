import { type ReactNode } from 'react'

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
      <div style={{ padding: 24, textAlign: 'center', color: '#888' }}>
        加载中...
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: '#c00' }}>
        <p>加载失败: {error.message}</p>
      </div>
    )
  }

  if (empty) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: '#888' }}>
        {emptyText}
      </div>
    )
  }

  return <>{children}</>
}
