'use client'

import { useT } from '@/lib/i18n'

export function HeroSection() {
  const t = useT()
  const stats = [1, 2, 3].map(i => ({
    val:   t(`hero.stat${i}` as 'hero.stat1'),
    label: t(`hero.stat${i}Label` as 'hero.stat1Label'),
  }))
  const tags = t('hero.ticker').split('|')

  return (
    <section className="hero">
      {/* Eyebrow */}
      <div className="hero-eyebrow">
        <span className="eyebrow-dot" />
        {t('hero.eyebrow')}
      </div>

      {/* Headline */}
      <h1>
        {t('hero.title1')}<br />
        <span className="hero-gradient">{t('hero.title2')}</span>
      </h1>

      {/* Sub-headline */}
      <p className="hero-sub">
        {t('hero.sub')}
      </p>

      {/* CTA row */}
      <div className="hero-cta-row">
        <a href="#search" className="btn-hero-primary">
          {t('hero.cta')}
        </a>
        <span className="hero-cta-note">{t('hero.ctaNote')}</span>
      </div>

      {/* Stats Section */}
      <div className="hero-stats">
        {stats.map(s => (
          <div className="hero-stat" key={s.label}>
            <strong>{s.val}</strong>
            <span>{s.label}</span>
          </div>
        ))}
      </div>

      {/* Concept Update: Infinite Marquee Ticker */}
      <div className="hero-ticker-wrap">
        <div className="hero-ticker-label">{t('hero.tickerLabel')}</div>
        <div className="marquee-container">
          <div className="marquee-content">
            {/* We double the array to ensure seamless looping */}
            {[...tags, ...tags].map((l, i) => (
              <div key={i} className="ticker-item">
                <span className="ticker-bullet">•</span>
                {l}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}