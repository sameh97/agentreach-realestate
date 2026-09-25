'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import { startJob, getSearch, subscribeToJob, PipelineEvent } from '@/lib/api'
import type { Lead } from '@/types/lead'

export type JobStatus = 'idle' | 'queued' | 'running' | 'done' | 'failed'

export interface NodeState {
  id:     string
  label:  string
  icon:   string
  status: 'idle' | 'active' | 'done' | 'error'
  detail: string
}

const INITIAL_NODES: NodeState[] = [
  { id: 'parse_query',      label: 'Query Parser',    icon: '🧠', status: 'idle', detail: 'Waiting…' },
  { id: 'scrape_maps',      label: 'Maps Scraper',    icon: '🗺️',  status: 'idle', detail: 'Waiting…' },
  { id: 'enrich_websites',  label: 'Email Enricher',  icon: '📧', status: 'idle', detail: 'Waiting…' },
  { id: 'enrich_re_signals', label: 'Realtor Signals', icon: '🏷️', status: 'idle', detail: 'Waiting…' },
  { id: 'verify_emails',    label: 'Verifier',        icon: '✅', status: 'idle', detail: 'Waiting…' },
  { id: 'score_leads',      label: 'Lead Scorer',     icon: '⭐', status: 'idle', detail: 'Waiting…' },
  { id: 'deliver',          label: 'File Delivery',   icon: '📥', status: 'idle', detail: 'Waiting…' },
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

  const advanceNode = useCallback((nodeId: string, detail: string, s: NodeState['status'] = 'done') => {
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
        advanceNode('parse_query', `${ev.business_type} · ${ev.location}`)
        break

      case 'scrape_maps':
        advanceNode('scrape_maps', `${ev.count ?? 0} businesses`)
        break

      case 'enrich_websites':
        advanceNode('enrich_websites', `${ev.count ?? 0} with email`)
        break

      case 'enrich_re_signals':
        advanceNode('enrich_re_signals', `${ev.brokerages ?? 0} brokerages found`)
        break

      case 'verify_emails':
        advanceNode('verify_emails', `${ev.verified ?? 0}/${ev.total ?? 0} valid`)
        break

      case 'score_leads':
        advanceNode('score_leads', `${ev.high_quality ?? 0} high-quality`)
        if (ev.preview?.length) setLeads(ev.preview as Lead[])
        break

      case 'deliver':
        advanceNode('deliver', 'Files ready')
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
          if (active) { active.status = 'error'; active.detail = 'Failed' }
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
      setError(err instanceof Error ? err.message : 'Could not start the search')
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
      setError(err instanceof Error ? err.message : 'Could not load this search')
    }
  }, [reset, follow, handleEvent])

  const clear = useCallback(() => reset(null), [reset])

  return {
    status, nodes, events, leads, leadCount,
    searchId, query, createdAt, error,
    run, load, clear,
  }
}
