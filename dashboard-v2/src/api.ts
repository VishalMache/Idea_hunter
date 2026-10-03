import type { Opportunity, OpportunityDossier, Run, Signal, Source } from './types'

const baseUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(body.detail ?? `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export const api = {
  opportunities: () => request<{ items: Opportunity[] }>('/opportunities?limit=100'),
  opportunity: (id: number) => request<OpportunityDossier>(`/opportunities/${id}`),
  signals: () => request<{ items: Signal[] }>('/signals?limit=100'),
  runs: () => request<Run[]>('/runs'),
  sources: () => request<{ items: Source[] }>('/sources'),
  createRun: () => request<Run>('/runs', { method: 'POST', body: JSON.stringify({ kind: 'full' }) }),
  retryStep: (runId: number, stepKey: string) => request<Run>(`/runs/${runId}/steps/${stepKey}/retry`, { method: 'POST' }),
  decide: (opportunityId: number, decision: string, reason = '') => request<{ id: number }>('/decisions', { method: 'POST', body: JSON.stringify({ opportunity_id: opportunityId, decision, reason }) }),
}
