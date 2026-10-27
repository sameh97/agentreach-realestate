'use client'

import type { Lead } from '@/types/lead'
import clsx from 'clsx'
import { useT, type TKey } from '@/lib/i18n'

interface Props {
  leads: Lead[]
}

function ScorePill({ score }: { score: number }) {
  return (
    <span className={clsx(
      'inline-flex items-center justify-center font-mono text-[12px] font-bold px-2 py-[3px] rounded-md min-w-[42px]',
      score >= 70 && 'bg-[rgba(0,230,118,0.12)] text-[#00e676]',
      score >= 40 && score < 70 && 'bg-[rgba(255,179,0,0.12)] text-[#ffb300]',
      score < 40  && 'bg-[rgba(255,82,82,0.12)]  text-[#ff5252]',
    )}>
      {score}
    </span>
  )
}

// Collapses the verifier's statuses into what the user acts on. Catch-all servers
// accept any address (mail doesn't bounce), so they count as valid; anything
// undeliverable was already removed by the backend.
function isValidEmail(lead: Lead) {
  return lead.email_verified || lead.email_catchall || lead.email_status === 'valid'
}

function EmailCell({ lead }: { lead: Lead }) {
  const t = useT()
  if (!lead.primary_email) return <span className="text-[11px] text-[var(--muted)]">—</span>
  const valid = isValidEmail(lead)
  return (
    <div className="min-w-0">
      <a
        href={`mailto:${lead.primary_email}`}
        className="font-mono text-[12px] text-[var(--accent)] truncate block max-w-[220px] hover:underline"
        dir="ltr"
      >
        {lead.primary_email}
      </a>
      <span className={clsx(
        'inline-flex mt-[3px] text-[10px] font-bold font-mono px-2 py-[1px] rounded',
        valid ? 'bg-[rgba(0,230,118,0.1)] text-[#00e676]' : 'bg-[rgba(107,124,143,0.15)] text-[#6b7c8f]',
      )}>
        {t(valid ? 'verify.valid' : 'verify.unverified')}
      </span>
    </div>
  )
}

const TEAM_COLORS: Record<string, string> = {
  brokerage:   'bg-[rgba(179,136,255,0.12)] text-[#b388ff]',
  large_team:  'bg-[rgba(0,212,255,0.12)]  text-[var(--accent)]',
  small_team:  'bg-[rgba(0,230,118,0.10)]  text-[#00e676]',
  solo:        'bg-[rgba(107,124,143,0.15)] text-[#6b7c8f]',
}

function TeamBadge({ lead }: { lead: Lead }) {
  const t = useT()
  const key = lead.team_size
  if (!key || !(key in TEAM_COLORS) || key === 'unknown') {
    return <span className="text-[11px] text-[var(--muted)]">—</span>
  }
  return (
    <span className={clsx('inline-flex items-center text-[10px] font-bold font-mono px-2 py-[2px] rounded', TEAM_COLORS[key])}>
      {t(`team.${key}` as TKey)}
    </span>
  )
}

function SpecializationTags({ specializations }: { specializations: string[] }) {
  const t = useT()
  if (!specializations || specializations.length === 0) {
    return <span className="text-[11px] text-[var(--muted)]">—</span>
  }
  return (
    <div className="flex flex-wrap gap-1 max-w-[180px]">
      {specializations.slice(0, 2).map(tag => (
        <span key={tag} className="text-[10px] font-mono px-[6px] py-[1px] rounded bg-[rgba(0,212,255,0.08)] text-[var(--accent)] border border-[rgba(0,212,255,0.15)] whitespace-nowrap">
          {SPEC_KEYS.has(tag) ? t(`spec.${tag}` as TKey) : tag.replace(/_/g, ' ')}
        </span>
      ))}
      {specializations.length > 2 && (
        <span className="text-[10px] text-[var(--muted)]">+{specializations.length - 2}</span>
      )}
    </div>
  )
}

const COLS = [
  { key: 'score',  w: '70px'  },
  { key: 'name',   w: 'auto'  },
  { key: 'email',  w: '230px' },
  { key: 'phone',  w: '140px' },
  { key: 'team',   w: '110px' },
  { key: 'specs',  w: '170px' },
  { key: 'rating', w: '90px'  },
] as const

function websiteLabel(url: string) {
  try { return new URL(url.startsWith('http') ? url : `https://${url}`).hostname.replace(/^www\./, '') }
  catch { return url }
}

const SPEC_KEYS = new Set(['luxury', 'commercial', 'new_construction', 'relocation', 'first_time_buyer',
                           'waterfront', 'land', 'vacation_rental', 'senior_55plus'])

export function LeadTable({ leads }: Props) {
  const t = useT()
  return (
    <div className="overflow-x-auto w-full animate-fade-in">
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr>
            {COLS.map(c => (
              <th
                key={c.key}
                style={{ width: c.w }}
                className="bg-[var(--panel)] px-4 py-[10px] text-start text-[10px] font-bold tracking-[1px] uppercase text-[var(--muted)] border-b border-[var(--border)] whitespace-nowrap"
              >
                {t(`table.${c.key}`)}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {leads.map((lead, i) => (
            <tr
              key={i}
              className="border-b border-[rgba(30,42,54,0.5)] hover:bg-[rgba(255,255,255,0.015)] transition-colors group"
            >
              {/* Score */}
              <td className="px-4 py-[11px]">
                <ScorePill score={lead.score} />
              </td>

              {/* Business name + address */}
              <td className="px-4 py-[11px]">
                <div className="font-semibold text-[var(--text)] leading-tight" dir="auto">
                  {lead.name}
                </div>
                <div className="text-[11px] text-[var(--muted)] mt-[2px] truncate max-w-[200px]">
                  {lead.address
                    ? lead.address.split(',').slice(-2).join(',').trim()
                    : '—'}
                </div>
                {lead.website && (
                  <a
                    href={lead.website.startsWith('http') ? lead.website : `https://${lead.website}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-[11px] text-[var(--accent)] mt-[2px] truncate max-w-[200px] hover:underline"
                    dir="ltr"
                  >
                    {websiteLabel(lead.website)} ↗
                  </a>
                )}
                {lead.owner_name && (
                  <div className="text-[10px] font-mono text-[#b388ff] mt-[2px]">
                    {lead.owner_name}
                    {lead.owner_position ? ` · ${lead.owner_position}` : ''}
                  </div>
                )}
              </td>

              {/* Email + validity */}
              <td className="px-4 py-[11px]">
                <EmailCell lead={lead} />
              </td>

              {/* Phone + WhatsApp */}
              <td className="px-4 py-[11px]">
                {lead.phone ? (
                  <a href={`tel:${lead.phone}`} className="font-mono text-[11px] text-[var(--text)] whitespace-nowrap hover:underline" dir="ltr">
                    {lead.phone}
                  </a>
                ) : (
                  <span className="text-[11px] text-[var(--muted)]">—</span>
                )}
                {lead.whatsapp && (
                  <a
                    href={`https://wa.me/${lead.whatsapp}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={t('table.whatsapp')}
                    className="block mt-[2px] text-[10px] font-semibold text-[#25d366] hover:underline"
                    dir="ltr"
                  >
                    WhatsApp ↗
                  </a>
                )}
              </td>

              {/* Team size */}
              <td className="px-4 py-[11px]">
                <TeamBadge lead={lead} />
              </td>

              {/* Specializations */}
              <td className="px-4 py-[11px]">
                <SpecializationTags specializations={lead.specializations} />
              </td>

              {/* Google rating */}
              <td className="px-4 py-[11px] whitespace-nowrap">
                {lead.rating ? (
                  <span className="text-[11px] font-mono text-[var(--text)]" dir="ltr">
                    <span className="text-[#ffb300]">★</span> {lead.rating.toFixed(1)}
                    <span className="text-[var(--muted)]"> ({lead.review_count})</span>
                  </span>
                ) : (
                  <span className="text-[11px] text-[var(--muted)]">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}