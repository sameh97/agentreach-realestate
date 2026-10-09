import type { Metadata } from 'next'
import './globals.css'
import { LOCALE_STORAGE_KEY } from '@/lib/i18n/storageKey'
import { I18nInit } from '@/components/I18nInit'

export const metadata: Metadata = {
  title: 'AgentReach — Verified Real Estate Agent & Brokerage Leads',
  description: 'Find real estate agents and brokerages by city, verified and scored for B2B outreach. Powered by LangGraph.',
  icons: { icon: '/favicon.ico' },
}

// Runs before first paint so a saved Hebrew/Arabic choice doesn't flash an
// LTR layout first. The i18n store takes over (and handles first visits) on mount.
const setDirection = `try{var l=localStorage.getItem('${LOCALE_STORAGE_KEY}');if(l==='he'||l==='ar'){document.documentElement.lang=l;document.documentElement.dir='rtl'}}catch(e){}`

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: setDirection }} />
      </head>
      <body>
        <I18nInit />
        {children}
      </body>
    </html>
  )
}
