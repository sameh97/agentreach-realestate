'use client'

import { useState } from 'react'
import type { Lead } from '@/types/lead'
import type { JobStatus } from '@/hooks/useLeadJob'
import { LeadTable }  from './LeadTable'
import { LeadFooter } from './LeadFooter'
import { useLocaleInfo, useT } from '@/lib/i18n'

interface Props {
  status:    JobStatus
  leads:     Lead[]
  leadCount: number
  query:     string
  createdAt: string | null
  onDownload: (format: 'csv' | 'xlsx') => Promise<void>
}

export function ResultsPanel({ status, leads, leadCount, query, createdAt, onDownload }: Props) {
  const [downloading, setDownloading] = useState<'csv' | 'xlsx' | null>(null)
  const t = useT()
  const { intl } = useLocaleInfo()

  const isDone    = status === 'done'
  const isFailed  = status === 'failed'
  const isRunning = status === 'running' || status === 'queued'

  const title = isDone
    ? t('results.titleDone', { n: leadCount })
    : isFailed
    ? t('results.titleFailed')
    : t('results.titleRunning')

  const meta = isDone
    ? `"${query}" · ${new Date(createdAt ?? Date.now()).toLocaleString(intl, { dateStyle: 'medium', timeStyle: 'short' })}`
    : isFailed
    ? t('results.metaFailed')
    : t('results.metaRunning')

  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl overflow-hidden min-h-[400px] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)] bg-[var(--panel)]">
        <div>
          <div className={`text-[15px] font-semibold ${isFailed ? 'text-[var(--red)]' : ''}`}>
            {title}
          </div>
          <div className="text-[12px] font-mono text-[var(--muted)] mt-[2px]" dir="auto">{meta}</div>
        </div>

        {isDone && leadCount > 0 && (
          <div className="flex gap-2">
            {(['csv', 'xlsx'] as const).map(fmt => (
              <button
                key={fmt}
                disabled={downloading !== null}
                onClick={async () => {
                  setDownloading(fmt)
                  try { await onDownload(fmt) }
                  catch (err) { alert(err instanceof Error ? err.message : t('results.downloadFailed')) }
                  finally { setDownloading(null) }
                }}
                className={fmt === 'csv'
                  ? 'flex items-center gap-1.5 bg-[var(--panel)] border border-[var(--border2)] text-[var(--text)] rounded-lg px-3 py-[7px] text-[13px] font-semibold hover:border-[var(--accent)] hover:text-[var(--accent)] transition-all disabled:opacity-50'
                  : 'flex items-center gap-1.5 bg-[var(--panel)] border border-[rgba(0,230,118,0.3)] text-[var(--green)] rounded-lg px-3 py-[7px] text-[13px] font-semibold hover:border-[var(--green)] transition-all disabled:opacity-50'}
              >
                {downloading === fmt ? '⏳' : '⬇'} {fmt.toUpperCase()}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex-1">
        {leads.length > 0 ? (
          <LeadTable leads={leads} />
        ) : (
          <EmptyState status={status} />
        )}
      </div>

      {/* Footer */}
      {leads.length > 0 && <LeadFooter leads={leads} />}
    </div>
  )
}

function EmptyState({ status }: { status: JobStatus }) {
  const t = useT()
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-[var(--muted)] text-center px-8">
      <div className="text-[48px] opacity-20">
        {status === 'failed' ? '⚠️' : '🔍'}
      </div>
      <div className="text-[15px] font-semibold text-[var(--muted)]">
        {status === 'failed'
          ? t('results.emptyFailed')
          : status === 'running' || status === 'queued'
          ? t('results.emptyRunning')
          : t('results.emptyIdle')}
      </div>
      <div className="text-[13px]">
        {status === 'failed'
          ? t('results.emptyFailedSub')
          : t('results.emptyIdleSub')}
      </div>
    </div>
  )
}