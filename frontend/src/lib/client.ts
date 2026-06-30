import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,  // Send HttpOnly cookies
})

// Note: No manual Bearer token injection — the HttpOnly cookie
// is auto-sent by the browser on every request.
// Authorization header is still supported for external API clients.

api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      window.dispatchEvent(new CustomEvent('auth:logout'))
    }
    return Promise.reject(error)
  }
)

export function getApiErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail) && detail.length > 0) return 'Invalid request data.'
    if (error.message) return error.message
  }
  return fallback
}

export default api
