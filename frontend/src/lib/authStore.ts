// lib/authStore.ts — current user + JWT session, with Zustand
import { create } from 'zustand'
import * as api from './api'
import type { User } from './api'

type AuthStatus = 'loading' | 'authed' | 'anon'

interface AuthStore {
  user:     User | null
  status:   AuthStatus
  init:     () => Promise<void>
  login:    (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  logout:   () => void
}

export const useAuth = create<AuthStore>((set, get) => ({
  user:   null,
  status: 'loading',

  // Restores the session from the stored token (runs once per page load)
  init: async () => {
    if (get().status !== 'loading') return
    if (!api.getToken()) return set({ status: 'anon' })
    try {
      set({ user: await api.getMe(), status: 'authed' })
    } catch {
      api.setToken(null)
      set({ user: null, status: 'anon' })
    }
  },

  login: async (email, password) => {
    const { token, user } = await api.login(email, password)
    api.setToken(token)
    set({ user, status: 'authed' })
  },

  register: async (name, email, password) => {
    const { token, user } = await api.register(name, email, password)
    api.setToken(token)
    set({ user, status: 'authed' })
  },

  logout: () => {
    api.setToken(null)
    set({ user: null, status: 'anon' })
  },
}))

// A 401 from any API call means the session is gone
if (typeof window !== 'undefined') {
  window.addEventListener(api.LOGOUT_EVENT, () => {
    useAuth.setState({ user: null, status: 'anon' })
  })
}
