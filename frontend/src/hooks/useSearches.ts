'use client'

import { useCallback, useEffect, useState } from 'react'
import { listSearches, deleteSearch, SearchSummary } from '@/lib/api'

/** The logged-in user's saved searches, newest first. */
export function useSearches() {
  const [searches, setSearches] = useState<SearchSummary[]>([])
  const [loaded, setLoaded]     = useState(false)

  const refresh = useCallback(async () => {
    try {
      setSearches(await listSearches())
    } catch (err) {
      console.error('Could not load searches:', err)
    } finally {
      setLoaded(true)
    }
  }, [])

  const remove = useCallback(async (id: string) => {
    setSearches(prev => prev.filter(s => s.id !== id))   // optimistic
    try {
      await deleteSearch(id)
    } catch (err) {
      console.error('Delete failed:', err)
      refresh()
    }
  }, [refresh])

  useEffect(() => { refresh() }, [refresh])

  // While anything is running, keep its status and counts fresh
  const anyRunning = searches.some(s => s.status === 'queued' || s.status === 'running')
  useEffect(() => {
    if (!anyRunning) return
    const t = setInterval(refresh, 4000)
    return () => clearInterval(t)
  }, [anyRunning, refresh])

  return { searches, loaded, refresh, remove }
}
