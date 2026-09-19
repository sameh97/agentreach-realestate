import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'AgentReach — Verified Real Estate Agent & Brokerage Leads',
  description: 'Find real estate agents and brokerages by city, verified and scored for B2B outreach. Powered by LangGraph.',
  icons: { icon: '/favicon.ico' },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}