// Single place the UI talks to the backend.
// Set VITE_API_BASE at build time:  VITE_API_BASE=https://<appsail-url> npm run build
const BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

let currentUser = null
export const setUser = (u) => { currentUser = u }

async function call(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (currentUser) {
    headers['X-User-Email'] = currentUser.email
    headers['X-User-Role'] = currentUser.role
  }
  const res = await fetch(BASE + path, {
    method, headers, body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let msg = 'Request failed'
    try { msg = (await res.json()).detail || msg } catch {}
    throw new Error(msg)
  }
  return res.json()
}

export const api = {
  signup: (data) => call('/auth/signup', { method: 'POST', body: data }),
  login: (data) => call('/auth/login', { method: 'POST', body: data }),
  logout: () => call('/logout', { method: 'POST' }),
  newSession: (userId) => call(`/sessions/${userId}`, { method: 'POST' }),
  listSessions: (userId) => call(`/sessions/${userId}`),
  history: (sessionId) => call(`/history/${sessionId}`),
  chat: (sessionId, content) => call('/chat', { method: 'POST', body: { session_id: sessionId, content } }),
  audit: () => call('/audit'),
}
