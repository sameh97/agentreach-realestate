'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/authStore'

interface Props {
  mode: 'login' | 'register'
}

const COPY = {
  login: {
    title:    'Welcome back',
    sub:      'Log in to run searches and see your saved leads.',
    submit:   'Log in',
    busy:     'Logging in…',
    switch:   "Don't have an account?",
    switchTo: 'Create one',
    href:     '/register',
  },
  register: {
    title:    'Create your account',
    sub:      'Every search you run is saved to your account — come back to it any time.',
    submit:   'Create account',
    busy:     'Creating account…',
    switch:   'Already have an account?',
    switchTo: 'Log in',
    href:     '/login',
  },
}

export function AuthForm({ mode }: Props) {
  const router = useRouter()
  const { status, init, login, register } = useAuth()
  const copy = COPY[mode]

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
      setError(err instanceof Error ? err.message : 'Something went wrong')
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <Link href="/" className="logo auth-logo">
        <div className="logo-icon">⚡</div>
        <span>Agent<span className="logo-accent">Reach</span></span>
      </Link>

      <form className="auth-card" onSubmit={onSubmit}>
        <h1 className="auth-title">{copy.title}</h1>
        <p className="auth-sub">{copy.sub}</p>

        {mode === 'register' && (
          <label className="auth-field">
            <span>Name</span>
            <input className="auth-input" value={name} onChange={e => setName(e.target.value)}
                   placeholder="Jane Smith" autoComplete="name" />
          </label>
        )}

        <label className="auth-field">
          <span>Email</span>
          <input className="auth-input" type="email" required value={email}
                 onChange={e => setEmail(e.target.value)}
                 placeholder="you@company.com" autoComplete="email" />
        </label>

        <label className="auth-field">
          <span>Password</span>
          <input className="auth-input" type="password" required minLength={mode === 'register' ? 8 : undefined}
                 value={password} onChange={e => setPassword(e.target.value)}
                 placeholder={mode === 'register' ? 'At least 8 characters' : '••••••••'}
                 autoComplete={mode === 'register' ? 'new-password' : 'current-password'} />
        </label>

        {error && <div className="auth-error">{error}</div>}

        <button type="submit" className="btn-generate auth-submit" disabled={busy}>
          {busy ? copy.busy : copy.submit}
        </button>

        <div className="auth-switch">
          {copy.switch} <Link href={copy.href}>{copy.switchTo}</Link>
        </div>
      </form>
    </div>
  )
}
