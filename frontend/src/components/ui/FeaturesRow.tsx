'use client'

import { useT } from '@/lib/i18n'

const ICONS = ['⚡', '✅', '🏢', '🏷️', '📊', '📥']

export function FeaturesRow() {
  const t = useT()
  return (
    <div className="features-grid">
      {ICONS.map((icon, i) => (
        <div key={i} className="feat-card">
          <div className="feat-icon">{icon}</div>
          <div className="feat-title">{t(`feat.${i + 1}.title` as 'feat.1.title')}</div>
          <div className="feat-desc">{t(`feat.${i + 1}.desc` as 'feat.1.desc')}</div>
        </div>
      ))}
    </div>
  )
}