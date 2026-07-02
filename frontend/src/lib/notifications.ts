import api from './client'
import type { Notification, WebhookSubscription } from './types'

export async function listNotifications() {
  const response = await api.get('/notifications/')
  return response.data as Notification[]
}

export async function markNotificationRead(id: number) {
  const response = await api.patch(`/notifications/${id}/read`)
  return response.data as Notification
}

export async function listWebhooks() {
  const response = await api.get('/notifications/webhooks')
  return response.data as WebhookSubscription[]
}

export async function createWebhook(data: { name: string; provider: string; url: string; events: string[]; secret?: string }) {
  const response = await api.post('/notifications/webhooks', data)
  return response.data as WebhookSubscription
}

export async function deleteWebhook(id: number) {
  await api.delete(`/notifications/webhooks/${id}`)
}
