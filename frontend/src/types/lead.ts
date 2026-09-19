export interface Lead {
  name:           string
  primary_email:  string
  email_verified: boolean
  email_catchall: boolean
  email_status:   string
  owner_name:     string
  owner_position: string
  phone:          string
  website:        string
  address:        string
  rating:         number
  review_count:   number
  score:          number
  category:       string
  source:         string
  // Real-estate specific signals
  team_size:          'solo' | 'small_team' | 'large_team' | 'brokerage' | 'unknown'
  specializations:    string[]
  years_in_business:  number
  license_detected:   boolean
  idx_detected:       boolean
  testimonial_count:  number
  service_area_count: number
}