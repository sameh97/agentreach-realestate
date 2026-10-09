import type { Lead } from '@/types/lead'
import { t, translateServerError } from './i18n'

export type { Lead }

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || ''

// ── Types ────────────────────────────────────────────────────────────────────

export interface User {
  id:         string
  email:      string
  name:       string
  created_at: string
}

export interface AuthResponse {
  token: string
  user:  User
}

export interface JobCreated {
  job_id:     string
  stream_url: string
  status_url: string
}

export type SearchStatus = 'queued' | 'running' | 'done' | 'failed'

export interface SearchSummary {
  id:                 string
  query:              string
  status:             SearchStatus
  location:           string
  lead_count:         number
  high_quality_count: number
  verified_count:     number
  error:              string
  created_at:         string
  finished_at:        string | null
  csv_url:            string | null
  xlsx_url:           string | null
}

export interface SearchDetail extends SearchSummary {
  events: PipelineEvent[]
  leads:  Lead[]
}

export interface PipelineEvent {
  node:           string
  ts:             string
  message?:       string
  count?:         number
  verified?:      number
  total?:         number
  high_quality?:  number
  business_type?: string
  location?:      string
  radius_km?:     number
  brokerages?:    number
  csv_url?:       string
  xlsx_url?:      string
  lead_count?:    number
  preview?:       Lead[]
  status?:        string
}

// ── Token storage ────────────────────────────────────────────────────────────

const TOKEN_KEY = 'agentreach_token'
export const LOGOUT_EVENT = 'agentreach:logout'

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch { /* storage unavailable — session lasts until reload */ }
}

// ── Fetch wrapper ────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') return translateServerError(body.detail)
    if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      return translateServerError(String(body.detail[0].msg).replace(/^Value error, /, ''))
    }
  } catch { /* not JSON */ }
  return t('err.requestFailed', { n: res.status })
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')

  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  } catch {
    // Network error — e.g. the free backend is still waking up
    throw new ApiError(0, t('err.network'))
  }
  if (res.ok) return res

  // Expired / invalid session anywhere except the login form itself
  if (res.status === 401 && token && !path.startsWith('/api/auth/login')) {
    setToken(null)
    window.dispatchEvent(new Event(LOGOUT_EVENT))
  }
  throw new ApiError(res.status, await errorMessage(res))
}

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(path, init)
  return res.status === 204 ? (undefined as T) : res.json()
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export function login(email: string, password: string) {
  return apiJson<AuthResponse>('/api/auth/login', {
    method: 'POST', body: JSON.stringify({ email, password }),
  })
}

export function register(name: string, email: string, password: string) {
  return apiJson<AuthResponse>('/api/auth/register', {
    method: 'POST', body: JSON.stringify({ name, email, password }),
  })
}

export function getMe() {
  return apiJson<User>('/api/auth/me')
}

// ── Searches ─────────────────────────────────────────────────────────────────

export function listSearches() {
  return apiJson<SearchSummary[]>('/api/searches')
}

export function getSearch(id: string) {
  return apiJson<SearchDetail>(`/api/searches/${id}`)
}

export function deleteSearch(id: string) {
  return apiJson<void>(`/api/searches/${id}`, { method: 'DELETE' })
}

// ── Jobs ─────────────────────────────────────────────────────────────────────

export function startJob(query: string, maxResults = 100) {
  return apiJson<JobCreated>('/api/leads/generate', {
    method: 'POST',
    body:   JSON.stringify({ query, max_results: maxResults, max_retries: 3 }),
  })
}

/** Downloads a search's leads with the auth header, then saves the file. */
export async function downloadSearch(id: string, format: 'csv' | 'xlsx') {
  const res  = await apiFetch(`/api/leads/download/${id}?format=${format}`)
  const blob = await res.blob()
  const name = res.headers.get('Content-Disposition')?.match(/filename="?([^"]+)"?/)?.[1]
    ?? `agentreach_leads.${format}`

  const url = URL.createObjectURL(blob)
  const a   = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Live pipeline progress over SSE. Uses fetch (not EventSource) so the JWT
 * travels in the Authorization header instead of the URL.
 * `onDone` fires once when the stream ends, for whatever reason.
 */
export function subscribeToJob(
  jobId:   string,
  onEvent: (ev: PipelineEvent) => void,
  onDone?: () => void,
): () => void {
  const ctrl = new AbortController()

  ;(async () => {
    try {
      const res    = await apiFetch(`/api/leads/stream/${jobId}`, { signal: ctrl.signal })
      const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader()
      let buf = ''

      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buf += value

        let sep: number
        while ((sep = buf.indexOf('\n\n')) !== -1) {
          const block = buf.slice(0, sep)
          buf = buf.slice(sep + 2)
          const data = block.split('\n')
            .filter(l => l.startsWith('data:'))
            .map(l => l.slice(5).trim())
            .join('\n')
          if (!data) continue   // keep-alive comment

          const event: PipelineEvent = JSON.parse(data)
          if (event.node === 'end') return
          onEvent(event)
        }
      }
    } catch (err) {
      if (ctrl.signal.aborted) return
      console.error('Stream error:', err)
    } finally {
      if (!ctrl.signal.aborted) onDone?.()
    }
  })()

  return () => ctrl.abort()
}
