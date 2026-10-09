'use client'

import type { Lead } from '@/types/lead'
import { useT } from '@/lib/i18n'

interface Props { leads: Lead[] }

export function LeadFooter({ leads }: Props) {
  const t = useT()
  const high = leads.filter(l => l.score >= 70).length
  const mid  = leads.filter(l => l.score >= 40 && l.score < 70).length
  const low  = leads.filter(l => l.score < 40).length
  const verified  = leads.filter(l => l.email_verified).length
  const catchall  = leads.filter(l => l.email_catchall).length

  return (
    <div className="flex items-center gap-6 px-5 py-3 border-t border-[var(--border)] bg-[var(--panel)] text-[12px] text-[var(--muted)] flex-wrap">
      <StatDot color="#00e676" count={high}     label={t('footer.high')} />
      <StatDot color="#ffb300" count={mid}      label={t('footer.medium')} />
      <StatDot color="#ff5252" count={low}      label={t('footer.low')} />
      <div className="w-px h-4 bg-[var(--border)] mx-1" />
      <StatDot color="#00d4ff" count={verified}  label={t('footer.verified')} />
      <StatDot color="#ffb300" count={catchall}  label={t('footer.catchall')} />
      <div className="ms-auto font-mono text-[11px]">
        {t('footer.total', { n: leads.length })}
      </div>
    </div>
  )
}

function StatDot({ color, count, label }: { color: string; count: number; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
      <span className="font-bold font-mono" style={{ color: 'var(--text)' }}>{count}</span>
      <span>{label}</span>
    </div>
  )
}