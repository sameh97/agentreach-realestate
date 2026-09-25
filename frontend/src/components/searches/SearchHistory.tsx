'use client'

import { useMemo, useState } from 'react'
import clsx from 'clsx'
import type { SearchSummary } from '@/lib/api'

interface Props {
  searches: SearchSummary[]
  loaded:   boolean
  activeId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onNew:    () => void
}

// ── Date helpers ─────────────────────────────────────────────────────────────

function startOfDay(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
}

function groupLabel(iso: string): string {
  const days = Math.round((startOfDay(new Date()) - startOfDay(new Date(iso))) / 86_400_000)
  if (days <= 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7)  return 'This week'
  if (days < 30) return 'This month'
  return 'Older'
}

function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60)     return 'just now'
  if (s < 3600)   return `${Math.floor(s / 60)}m ago`
  if (s < 86400)  return `${Math.floor(s / 3600)}h ago`
  if (s < 604800) return `${Math.floor(s / 86400)}d ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

// ── Component ────────────────────────────────────────────────────────────────

export function SearchHistory({ searches, loaded, activeId, onSelect, onDelete, onNew }: Props) {
  const [filter, setFilter] = useState('')

  const groups = useMemo(() => {
    const f = filter.trim().toLowerCase()
    const visible = f
      ? searches.filter(s => s.query.toLowerCase().includes(f) || s.location.toLowerCase().includes(f))
      : searches

    const out: { label: string; items: SearchSummary[] }[] = []
    for (const s of visible) {
      const label = groupLabel(s.created_at)
      const last  = out[out.length - 1]
      if (last?.label === label) last.items.push(s)
      else out.push({ label, items: [s] })
    }
    return out
  }, [searches, filter])

  const totalLeads = searches.reduce((n, s) => n + (s.lead_count || 0), 0)

  return (
    <aside className="history-card">
      <div className="history-head">
        <div>
          <div className="card-label !mb-1">Your searches</div>
          <div className="history-stats">
            {searches.length} searches · {totalLeads.toLocaleString()} leads
          </div>
        </div>
        <button className="history-new" onClick={onNew} title="Start a new search">+ New</button>
      </div>

      {searches.length > 5 && (
        <input
          className="history-filter"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filter searches…"
        />
      )}

      <div className="history-list">
        {!loaded && <div className="history-empty">Loading…</div>}

        {loaded && searches.length === 0 && (
          <div className="history-empty">
            <div className="text-[28px] opacity-30 mb-2">🗂️</div>
            No searches yet.<br />Run one and it will be saved here.
          </div>
        )}

        {loaded && searches.length > 0 && groups.length === 0 && (
          <div className="history-empty">No searches match “{filter}”.</div>
        )}

        {groups.map(g => (
          <div key={g.label}>
            <div className="history-group">{g.label}</div>
            {g.items.map(s => (
              <HistoryItem
                key={s.id}
                search={s}
                active={s.id === activeId}
                onSelect={() => onSelect(s.id)}
                onDelete={() => {
                  if (confirm(`Delete the search “${s.query}”? This can't be undone.`)) onDelete(s.id)
                }}
              />
            ))}
          </div>
        ))}
      </div>
    </aside>
  )
}

function HistoryItem({ search: s, active, onSelect, onDelete }: {
  search:   SearchSummary
  active:   boolean
  onSelect: () => void
  onDelete: () => void
}) {
  const running = s.status === 'queued' || s.status === 'running'

  return (
    <div
      role="button"
      tabIndex={0}
      className={clsx('history-item', active && 'active')}
      onClick={onSelect}
      onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onSelect()}
    >
      <div className="history-item-top">
        <span className={clsx('history-dot', s.status)} />
        <span className="history-query">{s.query}</span>
        <button
          className="history-delete"
          title="Delete search"
          aria-label="Delete search"
          onClick={e => { e.stopPropagation(); onDelete() }}
        >
          ✕
        </button>
      </div>

      <div className="history-meta">
        {s.location && <span className="truncate">📍 {s.location}</span>}
        <span className="ml-auto shrink-0">{timeAgo(s.created_at)}</span>
      </div>

      <div className="history-badges">
        {running && <span className="history-badge running">Running…</span>}
        {s.status === 'failed' && <span className="history-badge failed">Failed</span>}
        {s.status === 'done' && (
          <>
            <span className="history-badge">{s.lead_count} leads</span>
            {s.high_quality_count > 0 && (
              <span className="history-badge high">{s.high_quality_count} high-quality</span>
            )}
          </>
        )}
      </div>
    </div>
  )
}
