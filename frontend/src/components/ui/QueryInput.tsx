'use client'

import { useT } from '@/lib/i18n'

interface Props {
  value:    string
  onChange: (v: string) => void
  onSubmit: () => void
  loading:  boolean
}

export function QueryInput({ value, onChange, onSubmit, loading }: Props) {
  const t = useT()
  return (
    <div id="search" className="query-card">
      <div className="query-label">{t('query.label')}</div>
      <div className="query-row">
        <input
          type="text"
          className="query-input"
          dir="auto"
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !loading && onSubmit()}
          placeholder={t('query.placeholder')}
        />
        <button
          className="btn-generate"
          onClick={onSubmit}
          disabled={loading || !value.trim()}
        >
          {loading ? t('query.finding') : t('query.find')}
        </button>
      </div>
      <div className="example-chips">
        <span className="example-chip-label">{t('query.try')}</span>
        {t('query.examples').split('|').map(ex => (
          <button key={ex} className="example-chip" onClick={() => onChange(ex)}>
            {ex}
          </button>
        ))}
      </div>
    </div>
  )
}