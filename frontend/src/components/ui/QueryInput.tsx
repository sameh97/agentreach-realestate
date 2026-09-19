'use client'

const EXAMPLES = [
  'Real estate agents in Austin TX',
  'Luxury realtors in Miami FL',
  'Brokerages in Denver CO',
  'Real estate teams in Scottsdale AZ',
  'Commercial agents in Chicago IL',
]

interface Props {
  value:    string
  onChange: (v: string) => void
  onSubmit: () => void
  loading:  boolean
}

export function QueryInput({ value, onChange, onSubmit, loading }: Props) {
  return (
    <div id="search" className="query-card">
      <div className="query-label">Where are you targeting? (Real estate agents &amp; brokerages)</div>
      <div className="query-row">
        <input
          type="text"
          className="query-input"
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !loading && onSubmit()}
          placeholder='e.g. "Luxury real estate agents in Miami FL"'
        />
        <button
          className="btn-generate"
          onClick={onSubmit}
          disabled={loading || !value.trim()}
        >
          {loading ? '⏳ Finding leads…' : '🔍 Find Leads'}
        </button>
      </div>
      <div className="example-chips">
        <span className="example-chip-label">Try:</span>
        {EXAMPLES.map(ex => (
          <button key={ex} className="example-chip" onClick={() => onChange(ex)}>
            {ex}
          </button>
        ))}
      </div>
    </div>
  )
}