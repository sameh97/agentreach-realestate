'use client'

import clsx from 'clsx'
import { LOCALES, useI18n, useT, type Locale } from '@/lib/i18n'

export function LanguageSwitcher({ className }: { className?: string }) {
  const { locale, setLocale } = useI18n()
  const t = useT()

  return (
    <div role="group" aria-label={t('lang.label')} className={clsx('lang-switch', className)}>
      {(Object.keys(LOCALES) as Locale[]).map(l => (
        <button
          key={l}
          type="button"
          lang={l}
          title={LOCALES[l].name}
          aria-pressed={l === locale}
          className={clsx('lang-btn', l === locale && 'active')}
          onClick={() => setLocale(l)}
        >
          {LOCALES[l].short}
        </button>
      ))}
    </div>
  )
}
