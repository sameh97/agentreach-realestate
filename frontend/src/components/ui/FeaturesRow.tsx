'use client'

const FEATURES = [
  {
    icon: '⚡',
    title: 'Results in under 2 minutes',
    desc:  'Type a city. We handle the research. Get a complete, ready-to-use agent & brokerage list faster than a Google search.',
  },
  {
    icon: '✅',
    title: 'Every email verified',
    desc:  'No bounced emails. No wasted outreach. Every contact is checked against live mail servers before it reaches you.',
  },
  {
    icon: '🏢',
    title: 'Team size & brokerage detected',
    desc:  'We classify each lead as solo agent, small team, large team, or brokerage — so you know exactly who you\'re pitching.',
  },
  {
    icon: '🏷️',
    title: 'Specialization tags',
    desc:  'Luxury, commercial, new construction, relocation, waterfront — we scan each site and tag what they actually focus on.',
  },
  {
    icon: '📊',
    title: 'Scored for B2B outreach',
    desc:  'Leads are ranked by team size, tenure, digital maturity, and email deliverability — the things that matter when you\'re selling TO agents.',
  },
  {
    icon: '📥',
    title: 'Download & use instantly',
    desc:  'Export to CSV or Excel. Import straight into your CRM, email tool, or outreach sequence. Zero friction.',
  },
]

export function FeaturesRow() {
  return (
    <div className="features-grid">
      {FEATURES.map(f => (
        <div key={f.title} className="feat-card">
          <div className="feat-icon">{f.icon}</div>
          <div className="feat-title">{f.title}</div>
          <div className="feat-desc">{f.desc}</div>
        </div>
      ))}
    </div>
  )
}