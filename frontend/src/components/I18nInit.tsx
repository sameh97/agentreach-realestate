'use client'

import { useEffect } from 'react'
import { useI18n } from '@/lib/i18n'

/** Applies the saved (or browser) language once on load. Renders nothing. */
export function I18nInit() {
  const init = useI18n(s => s.init)
  useEffect(() => { init() }, [init])
  return null
}
