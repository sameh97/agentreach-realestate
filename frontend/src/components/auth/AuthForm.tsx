'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/authStore'
import { useT } from '@/lib/i18n'
import { LanguageSwitcher } from '@/components/ui/LanguageSwitcher'

interface Props {
  mode: 'login' | 'register'
}

const SWITCH_HREF = { login: '/register', register: '/login' } as const

export function AuthForm({ mode }: Props) {
  const router = useRouter()
  const { status, init, login, register } = useAuth()
  const t = useT()
  const k = `auth.${mode}` as const

  const [name, setName]         = useState('')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [busy, setBusy]         = useState(false)

  useEffect(() => { init() }, [init])
  useEffect(() => { if (status === 'authed') router.replace('/') }, [status, router])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (mode === 'login') await login(email, password)
      else await register(name, email, password)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('err.generic'))
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <LanguageSwitcher className="auth-lang" />
      <Link href="/" className="logo auth-logo">
        <div className="logo-icon">⚡</div>
        <span>Agent<span className="logo-accent">Reach</span></span>
      </Link>

      <form className="auth-card" onSubmit={onSubmit}>
        <h1 className="auth-title">{t(`${k}.title`)}</h1>
        <p className="auth-sub">{t(`${k}.sub`)}</p>

        {mode === 'register' && (
          <label className="auth-field">
            <span>{t('auth.name')}</span>
            <input className="auth-input" value={name} onChange={e => setName(e.target.value)}
                   placeholder={t('auth.namePlaceholder')} autoComplete="name" />
          </label>
        )}

        <label className="auth-field">
          <span>{t('auth.email')}</span>
          <input className="auth-input" type="email" dir="ltr" required value={email}
                 onChange={e => setEmail(e.target.value)}
                 placeholder="you@company.com" autoComplete="email" />
        </label>

        <label className="auth-field">
          <span>{t('auth.password')}</span>
          <input className="auth-input" type="password" dir="ltr" required minLength={mode === 'register' ? 8 : undefined}
                 value={password} onChange={e => setPassword(e.target.value)}
                 placeholder={mode === 'register' ? t('auth.passwordHint') : '••••••••'}
                 autoComplete={mode === 'register' ? 'new-password' : 'current-password'} />
        </label>

        {error && <div className="auth-error">{error}</div>}

        <button type="submit" className="btn-generate auth-submit" disabled={busy}>
          {busy ? t(`${k}.busy`) : t(`${k}.submit`)}
        </button>

        <div className="auth-switch">
          {t(`${k}.switch`)} <Link href={SWITCH_HREF[mode]}>{t(`${k}.switchTo`)}</Link>
        </div>
      </form>
    </div>
  )
}
