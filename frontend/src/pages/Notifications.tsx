import { useEffect, useState } from 'react'
import { Bell, Check, LoaderCircle } from 'lucide-react'

import { listNotifications, markNotificationRead, type Notification } from '../lib/api'
import { getApiErrorMessage } from '../lib/client'

export default function Notifications() {
  const [items, setItems] = useState<Notification[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load() {
    setError('')
    try {
      setItems(await listNotifications())
    } catch (requestError: unknown) {
      setItems([])
      setError(getApiErrorMessage(requestError, '通知加载失败，请稍后重试。'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function markRead(item: Notification) {
    if (item.is_read) return
    try {
      const updated = await markNotificationRead(item.id)
      setItems((current) => current.map((value) => value.id === item.id ? updated : value))
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, '通知状态更新失败。'))
    }
  }

  if (loading) return <div className="loading-state"><span className="loading-state-icon"><LoaderCircle className="spin" size={22} /></span><p>正在加载通知...</p></div>
  return (
    <div className="workspace-page">
      <header className="workspace-header"><div><span className="workspace-kicker">Activity Inbox</span><h1>通知</h1><p>分析、审核、同步和报告发布事件会汇总在这里。</p></div></header>
      {error && <div className="inline-error" role="alert">{error}</div>}
      {error && items.length === 0 ? null : items.length === 0 ? (
        <section className="empty-state"><span className="empty-state-icon"><Bell size={23} /></span><h2>暂无通知</h2><p>系统关键事件发生后会在这里提醒你。</p></section>
      ) : (
        <section className="workspace-panel">
          <div className="data-list">
            {items.map((item) => (
              <button className={`data-row notification-row${item.is_read ? ' is-read' : ''}`} type="button" key={item.id} onClick={() => markRead(item)}>
                <span className="resource-icon"><Bell size={17} /></span>
                <div><h3>{item.title}</h3><p>{item.message}</p><small>{new Date(item.created_at).toLocaleString('zh-CN')}</small></div>
                {item.is_read ? <Check size={16} /> : <span className="status-badge is-info">未读</span>}
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
