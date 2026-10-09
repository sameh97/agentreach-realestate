'use client'

import { useCallback } from 'react'
import { create } from 'zustand'
import { en, type Dict, type TKey } from './en'
import { he } from './he'
import { ar } from './ar'
import { LOCALE_STORAGE_KEY } from './storageKey'

export type { TKey }

// Adding a language = a dictionary file + one entry here.
export const LOCALES = {
  en: { short: 'EN', name: 'English', dir: 'ltr', intl: 'en-US' },
  he: { short: 'עב', name: 'עברית',   dir: 'rtl', intl: 'he-IL' },
  ar: { short: 'عر', name: 'العربية', dir: 'rtl', intl: 'ar-u-nu-latn' }, // Latin digits
} as const

export type Locale = keyof typeof LOCALES
type Vars = Record<string, string | number>

const DICTS: Record<Locale, Dict> = { en, he, ar }

function isLocale(v: unknown): v is Locale {
  return typeof v === 'string' && v in LOCALES
}

function translate(locale: Locale, key: TKey, vars?: Vars): string {
  const dict = DICTS[locale]
  const one  = vars?.n === 1 ? (dict as Record<string, string>)[`${key}_one`] : undefined
  const s    = one ?? dict[key] ?? en[key] ?? key
  return vars ? s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m)) : s
}

function applyToDocument(locale: Locale) {
  const html = document.documentElement
  html.lang = locale
  html.dir  = LOCALES[locale].dir
}

interface I18nState {
  locale:    Locale
  init:      () => void
  setLocale: (l: Locale) => void
}

// Starts as 'en' on the server and the first client render (no hydration
// mismatch); init() then switches to the saved or browser language.
export const useI18n = create<I18nState>((set) => ({
  locale: 'en',

  init: () => {
    let locale: Locale = 'en'
    try {
      const saved = localStorage.getItem(LOCALE_STORAGE_KEY)
      if (isLocale(saved)) locale = saved
      else {
        // 'iw' is the legacy code some browsers still report for Hebrew
        const browser = (navigator.languages ?? [navigator.language])
          .map(l => l.slice(0, 2).toLowerCase().replace('iw', 'he'))
        locale = browser.find(isLocale) ?? 'en'
      }
    } catch { /* storage blocked — keep English */ }
    applyToDocument(locale)
    set({ locale })
  },

  setLocale: (locale) => {
    try { localStorage.setItem(LOCALE_STORAGE_KEY, locale) } catch { /* ignore */ }
    applyToDocument(locale)
    set({ locale })
  },
}))

/** Translator bound to the current language; re-renders on language change. */
export function useT() {
  const locale = useI18n(s => s.locale)
  return useCallback((key: TKey, vars?: Vars) => translate(locale, key, vars), [locale])
}

export function useLocaleInfo() {
  const locale = useI18n(s => s.locale)
  return { locale, ...LOCALES[locale] }
}

/** For non-React code (api.ts). Uses the language at call time. */
export function t(key: TKey, vars?: Vars): string {
  return translate(useI18n.getState().locale, key, vars)
}

// The backend speaks English; map its known messages onto dictionary keys.
const SERVER_ERRORS: [RegExp, TKey][] = [
  [/^Incorrect email or password/i,           'err.badLogin'],
  [/^An account with this email already exists/i, 'err.emailExists'],
  [/^You already have a search running/i,     'err.searchRunning'],
  [/^Daily limit reached \((\d+)/i,           'err.dailyLimit'],
  [/^Enter a valid email address/i,           'err.invalidEmail'],
  [/^Password must be at least/i,             'err.passwordShort'],
  [/^Password must be at most/i,              'err.passwordLong'],
  [/^Query cannot be empty/i,                 'err.queryEmpty'],
  [/^(Session expired|Invalid token|Not authenticated|User no longer exists)/i, 'err.sessionExpired'],
  [/^Search not found/i,                      'err.searchNotFound'],
]

export function translateServerError(message: string): string {
  for (const [re, key] of SERVER_ERRORS) {
    const m = message.match(re)
    if (m) return t(key, m[1] ? { n: m[1] } : undefined)
  }
  return message
}
