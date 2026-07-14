import { useEffect, useState } from 'react'
import { Ban, CheckCircle2, Clock3, LoaderCircle, RefreshCw, RotateCcw, XCircle } from 'lucide-react'

import { cancelAnalysisJob, listAnalysisJobs, retryAnalysisJob, type AnalysisJob } from '../lib/api'
import { getApiErrorMessage } from '../lib/client'

export default function AnalysisJobs() {
  const [jobs, setJobs] = useState<AnalysisJob[]>([])
  const [loading, setLoading] = useState(true)
  const [workingId, setWorkingId] = useState<number | null>(null)
  const [error, setError] = useState('')

  async function load() {
    try {
      setJobs(await listAnalysisJobs())
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '分析任务加载失败。'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const timer = window.setInterval(load, 3000)
    return () => window.clearInterval(timer)
  }, [])

  async function handleCancel(jobId: number) {
    setWorkingId(jobId)
    try {
      await cancelAnalysisJob(jobId)
      await load()
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '取消任务失败。'))
    } finally {
      setWorkingId(null)
    }
  }

  async function handleRetry(jobId: number) {
    setWorkingId(jobId)
    try {
      await retryAnalysisJob(jobId)
      await load()
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, '重试任务失败。'))
    } finally {
      setWorkingId(null)
    }
  }

  if (loading) return <div className="loading-state"><span className="loading-state-icon"><LoaderCircle className="spin" size={22} /></span><p>正在加载分析任务...</p></div>

  return (
    <div className="workspace-page">
      <header className="workspace-header">
        <div><span className="workspace-kicker">Analysis Operations</span><h1>分析任务</h1><p>查看分析进度、失败原因，并取消或重试任务。</p></div>
        <button className="button" type="button" onClick={load}><RefreshCw size={16} /> 刷新</button>
      </header>
      {error && <div className="inline-error">{error}</div>}
      {jobs.length === 0 ? (
        <section className="empty-state"><span className="empty-state-icon"><Clock3 size={23} /></span><h2>暂无分析任务</h2><p>从 Sprint 工作台启动分析后，任务会显示在这里。</p></section>
      ) : (
        <section className="workspace-panel">
          <div className="detail-stack" style={{ padding: 12 }}>
            {jobs.map((job) => {
              const progress = job.progress_total ? Math.round(job.progress_current / job.progress_total * 100) : 0
              return (
                <article className="detail-card" key={job.id}>
                  <div className="detail-card-head">
                    <div><JobIcon status={job.status} /><strong>任务 #{job.id} · Sprint #{job.sprint_id}</strong></div>
                    <span className={`status-badge ${job.status === 'done' ? 'is-success' : job.status === 'failed' ? 'is-high' : 'is-info'}`}>{job.status}</span>
                  </div>
                  <div className="job-progress"><span style={{ width: `${progress}%` }} /></div>
                  <p>{job.progress_current} / {job.progress_total} Ticket · {progress}%</p>
                  <div className="metadata-grid">
                    <div><span>创建时间</span><strong>{formatTime(job.created_at)}</strong></div>
                    <div><span>开始时间</span><strong>{formatTime(job.started_at)}</strong></div>
                    <div><span>结束时间</span><strong>{formatTime(job.finished_at)}</strong></div>
                    <div><span>运行耗时</span><strong>{formatDuration(job.started_at, job.finished_at)}</strong></div>
                  </div>
                  {job.error_message && <div className="inline-error">{job.error_message}</div>}
                  <div className="row-actions">
                    {['queued', 'running', 'cancel_requested'].includes(job.status) && <button className="button button-danger button-small" type="button" onClick={() => handleCancel(job.id)} disabled={workingId === job.id}><Ban size={14} /> 取消</button>}
                    {['failed', 'cancelled'].includes(job.status) && <button className="button button-primary button-small" type="button" onClick={() => handleRetry(job.id)} disabled={workingId === job.id}><RotateCcw size={14} /> 重试</button>}
                  </div>
                </article>
              )
            })}
          </div>
        </section>
      )}
    </div>
  )
}

function JobIcon({ status }: { status: AnalysisJob['status'] }) {
  if (status === 'done') return <CheckCircle2 size={16} />
  if (status === 'failed' || status === 'cancelled') return <XCircle size={16} />
  return <LoaderCircle className={status === 'running' ? 'spin' : ''} size={16} />
}

function formatTime(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

function formatDuration(start?: string | null, end?: string | null) {
  if (!start) return '尚未开始'
  const startTime = new Date(start).getTime()
  const endTime = end ? new Date(end).getTime() : Date.now()
  if (!Number.isFinite(startTime) || !Number.isFinite(endTime) || endTime < startTime) return '—'
  const seconds = Math.round((endTime - startTime) / 1000)
  if (seconds < 60) return `${seconds} 秒`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  if (minutes < 60) return `${minutes} 分 ${remainingSeconds} 秒`
  const hours = Math.floor(minutes / 60)
  return `${hours} 小时 ${minutes % 60} 分`
}
