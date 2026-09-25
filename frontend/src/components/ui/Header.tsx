'use client'

import { useAuth } from '@/lib/authStore'

export function Header() {
  const { user, logout } = useAuth()

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-[rgba(8,12,16,0.92)] backdrop-blur-xl">
      <div className="flex items-center justify-between py-[14px] px-6 max-w-[1440px] mx-auto">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--accent)] to-[var(--accent2)] flex items-center justify-center text-black font-bold text-sm">
            ⚡
          </div>
          <span className="text-[20px] font-bold tracking-tight">
            Agent<span className="text-[var(--accent)]">Reach</span>
          </span>
          <span className="text-[11px] font-semibold tracking-wide px-2 py-[3px] rounded bg-[rgba(0,212,255,0.08)] text-[var(--accent)] border border-[rgba(0,212,255,0.2)]">
            BETA
          </span>
        </div>

        {/* Account */}
        {user && (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-[var(--panel)] border border-[var(--border2)] flex items-center justify-center text-[13px] font-bold text-[var(--accent)]">
                {(user.name || user.email).charAt(0).toUpperCase()}
              </div>
              <div className="hidden sm:block leading-tight">
                {user.name && <div className="text-[13px] font-semibold">{user.name}</div>}
                <div className="text-[11px] font-mono text-[var(--muted)]">{user.email}</div>
              </div>
            </div>
            <button
              onClick={logout}
              className="text-[12px] font-semibold px-3 py-[6px] rounded-lg border border-[var(--border2)] text-[var(--muted)] hover:text-[var(--text)] hover:border-[var(--muted)] transition-colors"
            >
              Log out
            </button>
          </div>
        )}
      </div>
    </header>
  )
}