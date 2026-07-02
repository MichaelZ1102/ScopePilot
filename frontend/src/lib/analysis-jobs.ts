import api from './client'
import type { AnalysisJob } from './types'

export async function listAnalysisJobs() {
  const response = await api.get('/analysis/jobs')
  return response.data as AnalysisJob[]
}

export async function cancelAnalysisJob(jobId: number) {
  const response = await api.post(`/analysis/jobs/${jobId}/cancel`)
  return response.data as AnalysisJob
}

export async function retryAnalysisJob(jobId: number) {
  const response = await api.post(`/analysis/jobs/${jobId}/retry`)
  return response.data as AnalysisJob
}
