'use client'

import { useState, useRef, useCallback } from 'react'
import { startJob, subscribeToJob, PipelineEvent } from '@/lib/api'
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

export function useLeadJob() {
  const [status, setStatus]     = useState<JobStatus>('idle')
  const [nodes, setNodes]       = useState<NodeState[]>(INITIAL_NODES.map(n => ({ ...n })))
  const [events, setEvents]     = useState<PipelineEvent[]>([])
  const [leads, setLeads]       = useState<Lead[]>([])
  const [leadCount, setLeadCount] = useState(0)
  const [csvUrl, setCsvUrl]     = useState('')
  const [xlsxUrl, setXlsxUrl]   = useState('')

  const unsub = useRef<(() => void) | null>(null)

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
        if (ev.csv_url)  setCsvUrl(ev.csv_url)
        if (ev.xlsx_url) setXlsxUrl(ev.xlsx_url)
        break

      case 'done':
        setStatus('done')
        setLeadCount(ev.lead_count ?? 0)
        if (ev.lead_count) setLeadCount(ev.lead_count)
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

  const run = useCallback(async (query: string) => {
    if (!query.trim()) return
    unsub.current?.()

    // Reset all state
    setStatus('queued')
    setNodes(INITIAL_NODES.map(n => ({ ...n })))
    setEvents([])
    setLeads([])
    setLeadCount(0)
    setCsvUrl('')
    setXlsxUrl('')

    try {
      const job = await startJob(query)
      unsub.current = subscribeToJob(
        job.job_id,
        handleEvent,
        (finalStatus) => setStatus(finalStatus === 'done' ? 'done' : 'failed'),
      )
    } catch (err) {
      console.error('Job start failed:', err)
      // Fall through to demo mode
      runDemo(handleEvent, setStatus, setLeads, setLeadCount)
    }
  }, [handleEvent])

  return { status, nodes, events, leads, leadCount, csvUrl, xlsxUrl, run }
}

// ── Demo mode when backend is not reachable ─────────────────────────────────

function runDemo(
  handleEvent: (ev: PipelineEvent) => void,
  setStatus: (s: JobStatus) => void,
  setLeads: (l: Lead[]) => void,
  setLeadCount: (n: number) => void,
) {
  const DEMO: Lead[] = [
    { name: 'The Sunrise Realty Group',   primary_email: 'team@sunriserealty.com',        email_verified: true,  email_catchall: false, email_status: 'valid',     rating: 4.9, review_count: 214, score: 100, phone: '+1-512-555-0101', address: '2201 S Lamar Blvd, Austin, TX', website: 'sunriserealty.com',      owner_name: '', owner_position: '', category: 'Real estate agency', source: 'demo', team_size: 'brokerage',  specializations: ['luxury', 'relocation'],       years_in_business: 18, license_detected: true,  idx_detected: true,  testimonial_count: 12, service_area_count: 6 },
    { name: 'Capital City Realtors',      primary_email: 'leads@capitalcityrealtors.com', email_verified: true,  email_catchall: false, email_status: 'valid',     rating: 4.6, review_count: 178, score: 100, phone: '+1-737-555-0034', address: '6301 W Parmer Ln, Austin, TX',   website: 'capitalcityrealtors.com', owner_name: '', owner_position: '', category: 'Real estate agency', source: 'demo', team_size: 'brokerage',  specializations: ['commercial', 'luxury'],       years_in_business: 22, license_detected: true,  idx_detected: true,  testimonial_count: 15, service_area_count: 8 },
    { name: 'Metro Home Advisors',        primary_email: 'info@metrohomeadvisors.com',    email_verified: true,  email_catchall: false, email_status: 'valid',     rating: 4.6, review_count: 98,  score: 88,  phone: '+1-512-555-0142', address: '4518 N Lamar Blvd, Austin, TX',  website: 'metrohomeadvisors.com', owner_name: '', owner_position: '', category: 'Real estate agency', source: 'demo', team_size: 'large_team', specializations: ['new_construction'],           years_in_business: 9,  license_detected: true,  idx_detected: true,  testimonial_count: 7,  service_area_count: 4 },
    { name: 'Valley Estates & Land',      primary_email: 'info@valleyestatesland.com',    email_verified: true,  email_catchall: false, email_status: 'valid',     rating: 4.7, review_count: 156, score: 84,  phone: '+1-737-555-0089', address: '2814 Exposition Blvd, Austin, TX', website: 'valleyestatesland.com', owner_name: '', owner_position: '', category: 'Real estate agency', source: 'demo', team_size: 'small_team', specializations: ['land', 'waterfront'],         years_in_business: 14, license_detected: true,  idx_detected: true,  testimonial_count: 9,  service_area_count: 5 },
    { name: 'James Patel Real Estate',    primary_email: 'james@jamespatelre.com',        email_verified: true,  email_catchall: false, email_status: 'valid',     rating: 4.9, review_count: 312, score: 80,  phone: '+1-512-555-0278', address: '8802 Research Blvd, Austin, TX', website: 'jamespatelre.com',       owner_name: '', owner_position: '', category: 'Real estate agent',  source: 'demo', team_size: 'solo',        specializations: ['luxury'],                     years_in_business: 11, license_detected: true,  idx_detected: true,  testimonial_count: 20, service_area_count: 3 },
    { name: 'Downtown Living Group',      primary_email: 'hello@downtownliving.com',      email_verified: false, email_catchall: true,  email_status: 'catch-all', rating: 4.1, review_count: 42,  score: 56,  phone: '+1-512-555-0189', address: '1902 E Cesar Chavez, Austin, TX', website: 'downtownliving.com',   owner_name: '', owner_position: '', category: 'Real estate agency', source: 'demo', team_size: 'small_team', specializations: ['new_construction'],           years_in_business: 3,  license_detected: false, idx_detected: true,  testimonial_count: 2,  service_area_count: 2 },
    { name: 'Maria Chen Realtor',         primary_email: 'maria@mariachenhomes.com',      email_verified: true,  email_catchall: false, email_status: 'valid',     rating: 4.8, review_count: 67,  score: 46,  phone: '+1-512-555-0312', address: '5201 Airport Blvd, Austin, TX',   website: 'mariachenhomes.com',   owner_name: '', owner_position: '', category: 'Real estate agent',  source: 'demo', team_size: 'solo',        specializations: ['first_time_buyer'],           years_in_business: 4,  license_detected: false, idx_detected: false, testimonial_count: 3,  service_area_count: 2 },
    { name: 'Sunset Ridge Realtors',      primary_email: 'info@sunsetridgerealtors.com',  email_verified: false, email_catchall: false, email_status: 'unknown',   rating: 4.0, review_count: 22,  score: 22,  phone: '',                address: '3344 Oak Springs Dr, Austin, TX', website: 'sunsetridgerealtors.com', owner_name: '', owner_position: '', category: 'Real estate agent', source: 'demo', team_size: 'solo',        specializations: [],                             years_in_business: 2,  license_detected: false, idx_detected: false, testimonial_count: 0,  service_area_count: 1 },
  ]

  const steps: PipelineEvent[] = [
    { node: 'start',            ts: now(), message: '[DEMO MODE] Simulating pipeline — connect backend for live data' },
    { node: 'parse_query',      ts: now(), business_type: 'real estate agent & brokerage', location: 'Austin, TX', radius_km: 25, message: 'Query parsed' },
    { node: 'scrape_maps',      ts: now(), count: 48, message: 'Scraped 48 agents & brokerages' },
    { node: 'enrich_websites',  ts: now(), count: 31, message: 'Found emails for 31 businesses' },
    { node: 'enrich_re_signals', ts: now(), count: 31, brokerages: 2, message: 'Scanned sites — 2 brokerages detected' },
    { node: 'verify_emails',    ts: now(), verified: 28, total: 31, message: '28/31 emails verified' },
    { node: 'score_leads',      ts: now(), high_quality: 5, preview: DEMO, message: 'Leads scored' },
    { node: 'deliver',          ts: now(), csv_url: '#', xlsx_url: '#', message: 'Files ready' },
    { node: 'done',             ts: now(), lead_count: DEMO.length, message: `${DEMO.length} verified leads ready!` },
  ]

  const delays = [300, 900, 2200, 3600, 4800, 6000, 6800, 7200, 7600]
  steps.forEach((ev, i) => {
    setTimeout(() => {
      handleEvent(ev)
      if (ev.node === 'done') {
        setLeads(DEMO)
        setLeadCount(DEMO.length)
        setStatus('done')
      }
    }, delays[i])
  })
}

function now() { return new Date().toISOString() }