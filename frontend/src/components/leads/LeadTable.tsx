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

// email_status values the verifier sends that have a translation
const VERIFY_STATUS_KEYS = new Set(['unknown', 'invalid', 'disposable', 'no_mx', 'bad_syntax', 'no_email', 'error', 'spam_trap', 'abuse'])

function VerifyBadge({ lead }: { lead: Lead }) {
  const t = useT()
  const cls = lead.email_verified
    ? 'bg-[rgba(0,230,118,0.1)] text-[#00e676]'
    : lead.email_catchall
    ? 'bg-[rgba(255,179,0,0.1)] text-[#ffb300]'
    : 'bg-[rgba(107,124,143,0.15)] text-[#6b7c8f]'

  const label = lead.email_verified
    ? t('verify.valid')
    : lead.email_catchall
    ? t('verify.catchall')
    : VERIFY_STATUS_KEYS.has(lead.email_status) ? t(`verify.${lead.email_status}` as TKey)
    : lead.email_status || t('verify.unknown')

  return (
    <span className={clsx('inline-flex items-center gap-1 text-[10px] font-bold font-mono px-2 py-[2px] rounded', cls)}>
      {label}
    </span>
  )
}

const TEAM_COLORS: Record<string, string> = {
  brokerage:   'bg-[rgba(179,136,255,0.12)] text-[#b388ff]',
  large_team:  'bg-[rgba(0,212,255,0.12)]  text-[var(--accent)]',
  small_team:  'bg-[rgba(0,230,118,0.10)]  text-[#00e676]',
  solo:        'bg-[rgba(107,124,143,0.15)] text-[#6b7c8f]',
  unknown:     'bg-[rgba(107,124,143,0.1)]  text-[var(--muted)]',
}

function TeamBadge({ lead }: { lead: Lead }) {
  const t = useT()
  const key = (lead.team_size in TEAM_COLORS ? lead.team_size : 'unknown') as string
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
  { key: 'email',  w: '210px' },
  { key: 'status', w: '100px' },
  { key: 'team',   w: '110px' },
  { key: 'specs',  w: '190px' },
  { key: 'years',  w: '70px'  },
  { key: 'phone',  w: '140px' },
] as const

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
                {lead.owner_name && (
                  <div className="text-[10px] font-mono text-[#b388ff] mt-[2px]">
                    {lead.owner_name}
                    {lead.owner_position ? ` · ${lead.owner_position}` : ''}
                  </div>
                )}
              </td>

              {/* Email */}
              <td className="px-4 py-[11px]">
                <span className="font-mono text-[12px] text-[var(--accent)] truncate block max-w-[200px]" dir="ltr">
                  {lead.primary_email || '—'}
                </span>
              </td>

              {/* Verification status */}
              <td className="px-4 py-[11px]">
                <VerifyBadge lead={lead} />
              </td>

              {/* Team size */}
              <td className="px-4 py-[11px]">
                <TeamBadge lead={lead} />
              </td>

              {/* Specializations */}
              <td className="px-4 py-[11px]">
                <SpecializationTags specializations={lead.specializations} />
              </td>

              {/* Years in business */}
              <td className="px-4 py-[11px]">
                <span className="text-[11px] font-mono text-[var(--muted)]">
                  {lead.years_in_business ? t('table.yearsShort', { n: lead.years_in_business }) : '—'}
                </span>
              </td>

              {/* Phone */}
              <td className="px-4 py-[11px]">
                <span className="font-mono text-[11px] text-[var(--muted)] whitespace-nowrap" dir="ltr">
                  {lead.phone || '—'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}