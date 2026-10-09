'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import { startJob, getSearch, subscribeToJob, PipelineEvent } from '@/lib/api'
import type { Lead } from '@/types/lead'
import { t, type TKey } from '@/lib/i18n'

export type JobStatus = 'idle' | 'queued' | 'running' | 'done' | 'failed'

export interface NodeState {
  id:     string          // also the label's translation key: node.<id>
  icon:   string
  status: 'idle' | 'active' | 'done' | 'error'
  // Stored as a key + values, not text, so it re-renders when the language changes
  detail: { key: TKey; vars?: Record<string, string | number> }
}

const WAITING = { key: 'pipeline.waiting' } as const

const INITIAL_NODES: NodeState[] = [
  { id: 'parse_query',       icon: '🧠', status: 'idle', detail: WAITING },
  { id: 'scrape_maps',       icon: '🗺️', status: 'idle', detail: WAITING },
  { id: 'enrich_websites',   icon: '📧', status: 'idle', detail: WAITING },
  { id: 'enrich_re_signals', icon: '🏷️', status: 'idle', detail: WAITING },
  { id: 'verify_emails',     icon: '✅', status: 'idle', detail: WAITING },
  { id: 'score_leads',       icon: '⭐', status: 'idle', detail: WAITING },
  { id: 'deliver',           icon: '📥', status: 'idle', detail: WAITING },
]

/**
 * Drives the pipeline view for one search at a time — either a new run
 * (`run`) or a saved search from the user's history (`load`).
 * `onChange` fires whenever a search starts or finishes, so the history
 * list can refresh.
 */
export function useLeadJob(onChange?: () => void) {
  const [status, setStatus]       = useState<JobStatus>('idle')
  const [nodes, setNodes]         = useState<NodeState[]>(INITIAL_NODES.map(n => ({ ...n })))
  const [events, setEvents]       = useState<PipelineEvent[]>([])
  const [leads, setLeads]         = useState<Lead[]>([])
  const [leadCount, setLeadCount] = useState(0)
  const [searchId, setSearchId]   = useState<string | null>(null)
  const [query, setQuery]         = useState('')
  const [createdAt, setCreatedAt] = useState<string | null>(null)
  const [error, setError]         = useState('')

  const unsub      = useRef<(() => void) | null>(null)
  const currentId  = useRef<string | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  useEffect(() => () => unsub.current?.(), [])

  const advanceNode = useCallback((nodeId: string, detail: NodeState['detail'], s: NodeState['status'] = 'done') => {
    setNodes(prev => {
      const next = prev.map(n => ({ ...n }))
      const idx  = next.findIndex(n => n.id === nodeId)
      if (idx !== -1) {
        next[idx].status = s
        next[idx].detail = detail
        if (s === 'done' && idx + 1 < next.length) {
          next[idx + 1].status = 'active'
        }
      }
      return next
    })
  }, [])

  const handleEvent = useCallback((ev: PipelineEvent) => {
    setEvents(prev => [...prev, ev])

    switch (ev.node) {
      case 'start':
        setStatus('running')
        setNodes(prev => {
          const n = prev.map(p => ({ ...p }))
          n[0].status = 'active'
          return n
        })
        break

      case 'parse_query':
        advanceNode('parse_query', { key: 'detail.parsed', vars: { location: ev.location ?? '' } })
        break

      case 'scrape_maps':
        advanceNode('scrape_maps', { key: 'detail.businesses', vars: { n: ev.count ?? 0 } })
        break

      case 'enrich_websites':
        advanceNode('enrich_websites', { key: 'detail.withEmail', vars: { n: ev.count ?? 0 } })
        break

      case 'enrich_re_signals':
        advanceNode('enrich_re_signals', { key: 'detail.brokerages', vars: { n: ev.brokerages ?? 0 } })
        break

      case 'verify_emails':
        advanceNode('verify_emails', { key: 'detail.valid', vars: { v: ev.verified ?? 0, t: ev.total ?? 0 } })
        break

      case 'score_leads':
        advanceNode('score_leads', { key: 'detail.highQuality', vars: { n: ev.high_quality ?? 0 } })
        if (ev.preview?.length) setLeads(ev.preview as Lead[])
        break

      case 'deliver':
        advanceNode('deliver', { key: 'detail.filesReady' })
        break

      case 'done':
        setStatus('done')
        setLeadCount(ev.lead_count ?? 0)
        break

      case 'fail':
        setStatus('failed')
        setNodes(prev => {
          const n = prev.map(p => ({ ...p }))
          const active = n.find(x => x.status === 'active')
          if (active) { active.status = 'error'; active.detail = { key: 'detail.failed' } }
          return n
        })
        break
    }
  }, [advanceNode])

  const reset = useCallback((id: string | null) => {
    unsub.current?.()
    unsub.current = null
    currentId.current = id
    setSearchId(id)
    setStatus(id ? 'queued' : 'idle')
    setNodes(INITIAL_NODES.map(n => ({ ...n })))
    setEvents([])
    setLeads([])
    setLeadCount(0)
    setError('')
  }, [])

  // The live stream only carries a 5-lead preview — fetch the saved search
  // once it ends to get every lead and the authoritative final status.
  const finish = useCallback(async (id: string) => {
    try {
      const d = await getSearch(id)
      if (currentId.current !== id) return
      setLeads(d.leads)
      setLeadCount(d.lead_count)
      setStatus(d.status === 'done' ? 'done' : d.status === 'failed' ? 'failed' : 'running')
    } catch (err) {
      console.error('Could not load finished search:', err)
    }
    onChangeRef.current?.()
  }, [])

  const follow = useCallback((id: string) => {
    unsub.current = subscribeToJob(id, handleEvent, () => finish(id))
  }, [handleEvent, finish])

  const run = useCallback(async (q: string) => {
    if (!q.trim()) return
    reset(null)
    setStatus('queued')
    setQuery(q)
    setCreatedAt(new Date().toISOString())

    try {
      const job = await startJob(q)
      currentId.current = job.job_id
      setSearchId(job.job_id)
      onChangeRef.current?.()
      follow(job.job_id)
    } catch (err) {
      setStatus('idle')
      setError(err instanceof Error ? err.message : t('err.startFailed'))
    }
  }, [reset, follow])

  const load = useCallback(async (id: string) => {
    reset(id)
    try {
      const d = await getSearch(id)
      if (currentId.current !== id) return
      setQuery(d.query)
      setCreatedAt(d.created_at)

      if (d.status === 'queued' || d.status === 'running') {
        follow(id)   // the stream replays every event so far, then continues live
      } else {
        d.events.forEach(handleEvent)
        setLeads(d.leads)
        setLeadCount(d.lead_count)
        setStatus(d.status)
      }
    } catch (err) {
      if (currentId.current !== id) return
      setStatus('idle')
      setSearchId(null)
      setError(err instanceof Error ? err.message : t('err.loadFailed'))
    }
  }, [reset, follow, handleEvent])

  const clear = useCallback(() => reset(null), [reset])

  return {
    status, nodes, events, leads, leadCount,
    searchId, query, createdAt, error,
    run, load, clear,
  }
}
