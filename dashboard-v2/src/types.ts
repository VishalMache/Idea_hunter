export type Opportunity = {
  id: number
  problem_id: number
  title: string
  status: string
  potential: number | null
  confidence: number | null
  freshness_days: number | null
  next_step: string | null
  severity: number | null
  frequency: number | null
}

export type ClaimEvidence = {
  observation_id: number
  quote: string
  verified: boolean
  stance: string
  source: string
  source_url: string | null
  published_at: string | null
  author: string | null
  engagement: number | null
}

export type OpportunityDossier = Opportunity & {
  description: string
  score_breakdown: Record<string, unknown> | null
  research: Record<string, unknown> | null
  claims: Array<{ id: number; text: string; kind: string; support_state: string; confidence: number; evidence: ClaimEvidence[] }>
}

export type Signal = {
  id: number
  text: string
  source: string
  source_url: string | null
  signal_type: string | null
  triage_state: string
  embedding_state: string
  engagement: number | null
  published_at: string | null
}

export type Run = {
  id: number
  kind: string
  status: string
  budget_usd: number
  total_cost_usd: number
  error: string | null
  steps: Array<{ id: number; step_key: string; status: string; attempt_count: number; cost_usd: number; error: string | null }>
}

export type Source = {
  id: number
  name: string
  key: string
  health_status: string | null
  acquisition_method: string | null
  reliability: number
  queries: Array<{ id: number; key: string; text: string; cursor: string | null; last_success_at: string | null; last_error: string | null }>
}
