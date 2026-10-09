'use client'

import { useMemo, useState } from 'react'
import clsx from 'clsx'
import type { SearchSummary } from '@/lib/api'
import { useLocaleInfo, useT, type TKey } from '@/lib/i18n'

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

function groupKey(iso: string): TKey {
  const days = Math.round((startOfDay(new Date()) - startOfDay(new Date(iso))) / 86_400_000)
  if (days <= 0) return 'history.today'
  if (days === 1) return 'history.yesterday'
  if (days < 7)  return 'history.thisWeek'
  if (days < 30) return 'history.thisMonth'
  return 'history.older'
}

// Intl handles each language's grammar ("5m ago", "לפני 5 דק׳", "قبل 5 د")
function timeAgo(iso: string, intl: string, justNow: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  const rtf = new Intl.RelativeTimeFormat(intl, { style: 'narrow' })
  if (s < 60)     return justNow
  if (s < 3600)   return rtf.format(-Math.floor(s / 60), 'minute')
  if (s < 86400)  return rtf.format(-Math.floor(s / 3600), 'hour')
  if (s < 604800) return rtf.format(-Math.floor(s / 86400), 'day')
  return new Date(iso).toLocaleDateString(intl, { month: 'short', day: 'numeric' })
}

// ── Component ────────────────────────────────────────────────────────────────

export function SearchHistory({ searches, loaded, activeId, onSelect, onDelete, onNew }: Props) {
  const [filter, setFilter] = useState('')
  const t = useT()

  const groups = useMemo(() => {
    const f = filter.trim().toLowerCase()
    const visible = f
      ? searches.filter(s => s.query.toLowerCase().includes(f) || s.location.toLowerCase().includes(f))
      : searches

    const out: { label: TKey; items: SearchSummary[] }[] = []
    for (const s of visible) {
      const label = groupKey(s.created_at)
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
          <div className="card-label !mb-1">{t('history.title')}</div>
          <div className="history-stats">
            {t('history.stats', { n: searches.length, leads: totalLeads.toLocaleString() })}
          </div>
        </div>
        <button className="history-new" onClick={onNew} title={t('history.newTitle')}>{t('history.new')}</button>
      </div>

      {searches.length > 5 && (
        <input
          className="history-filter"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder={t('history.filter')}
          dir="auto"
        />
      )}

      <div className="history-list">
        {!loaded && <div className="history-empty">{t('common.loading')}</div>}

        {loaded && searches.length === 0 && (
          <div className="history-empty">
            <div className="text-[28px] opacity-30 mb-2">🗂️</div>
            {t('history.empty1')}<br />{t('history.empty2')}
          </div>
        )}

        {loaded && searches.length > 0 && groups.length === 0 && (
          <div className="history-empty">{t('history.noMatch', { q: filter })}</div>
        )}

        {groups.map(g => (
          <div key={g.label}>
            <div className="history-group">{t(g.label)}</div>
            {g.items.map(s => (
              <HistoryItem
                key={s.id}
                search={s}
                active={s.id === activeId}
                onSelect={() => onSelect(s.id)}
                onDelete={() => {
                  if (confirm(t('history.confirmDelete', { q: s.query }))) onDelete(s.id)
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
  const t = useT()
  const { intl } = useLocaleInfo()

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
        <span className="history-query" dir="auto">{s.query}</span>
        <button
          className="history-delete"
          title={t('history.delete')}
          aria-label={t('history.delete')}
          onClick={e => { e.stopPropagation(); onDelete() }}
        >
          ✕
        </button>
      </div>

      <div className="history-meta">
        {s.location && <span className="truncate">📍 {s.location}</span>}
        <span className="ms-auto shrink-0">{timeAgo(s.created_at, intl, t('history.justNow'))}</span>
      </div>

      <div className="history-badges">
        {running && <span className="history-badge running">{t('history.running')}</span>}
        {s.status === 'failed' && <span className="history-badge failed">{t('history.failed')}</span>}
        {s.status === 'done' && (
          <>
            <span className="history-badge">{t('history.leads', { n: s.lead_count })}</span>
            {s.high_quality_count > 0 && (
              <span className="history-badge high">{t('history.high', { n: s.high_quality_count })}</span>
            )}
          </>
        )}
      </div>
    </div>
  )
}
