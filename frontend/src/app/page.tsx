'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Header }        from '@/components/ui/Header'
import { HeroSection }   from '@/components/ui/HeroSection'
import { QueryInput }    from '@/components/ui/QueryInput'
import { PipelinePanel } from '@/components/pipeline/PipelinePanel'
import { ResultsPanel }  from '@/components/leads/ResultsPanel'
import { FeaturesRow }   from '@/components/ui/FeaturesRow'
import { SearchHistory } from '@/components/searches/SearchHistory'
import { useLeadJob }    from '@/hooks/useLeadJob'
import { useSearches }   from '@/hooks/useSearches'
import { useAuth }       from '@/lib/authStore'
import { downloadSearch } from '@/lib/api'

// Keeps the open search in the URL (?s=<id>) so a refresh reopens it
function setUrlSearch(id: string | null) {
  window.history.replaceState(null, '', id ? `/?s=${id}` : '/')
}

export default function HomePage() {
  const router = useRouter()
  const { status: authStatus, init } = useAuth()

  useEffect(() => { init() }, [init])
  useEffect(() => { if (authStatus === 'anon') router.replace('/login') }, [authStatus, router])

  if (authStatus !== 'authed') {
    return <div className="auth-wrap"><div className="history-empty">Loading…</div></div>
  }
  return <Dashboard />
}

function Dashboard() {
  const [query, setQuery] = useState('')
  const { searches, loaded, refresh, remove } = useSearches()
  const job = useLeadJob(refresh)
  const hasJob = job.status !== 'idle'

  // Reopen the search from the URL on first load
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('s')
    if (id) job.load(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { setUrlSearch(job.searchId) }, [job.searchId])

  const openSearch = useCallback((id: string) => {
    job.load(id)
    // Stacked layout (history above results): jump to the results, not the page top
    if (window.matchMedia('(max-width: 1024px)').matches) {
      setTimeout(() => document.querySelector('.main-grid')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 150)
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }, [job])

  const newSearch = useCallback(() => {
    job.clear()
    setQuery('')
    document.querySelector<HTMLInputElement>('.query-input')?.focus()
  }, [job])

  const removeSearch = useCallback((id: string) => {
    if (id === job.searchId) job.clear()
    remove(id)
  }, [job, remove])

  return (
    <>
      <Header />
      <div className="dash-wrap">
        <SearchHistory
          searches={searches}
          loaded={loaded}
          activeId={job.searchId}
          onSelect={openSearch}
          onDelete={removeSearch}
          onNew={newSearch}
        />

        <main className="min-w-0">
          {loaded && searches.length === 0 && !hasJob && <HeroSection />}

          <QueryInput
            value={query}
            onChange={setQuery}
            onSubmit={() => job.run(query)}
            loading={job.status === 'running' || job.status === 'queued'}
          />
          {job.error && <div className="auth-error mb-5">{job.error}</div>}

          {hasJob && (
            <div className={`main-grid ${job.status === 'done' ? 'results-first' : ''}`}>
              <PipelinePanel nodes={job.nodes} events={job.events} />
              <ResultsPanel
                status={job.status}
                leads={job.leads}
                leadCount={job.leadCount}
                query={job.query}
                createdAt={job.createdAt}
                onDownload={fmt => downloadSearch(job.searchId!, fmt)}
              />
            </div>
          )}
          {!hasJob && <FeaturesRow />}
        </main>
      </div>
    </>
  )
}
