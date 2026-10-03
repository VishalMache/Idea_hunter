import { useEffect, useMemo, useState } from 'react'
import { Activity, Database, Gauge, Inbox, Radar, RefreshCw, Target } from 'lucide-react'
import { api } from './api'
import type { Opportunity, OpportunityDossier, Run, Signal, Source } from './types'
import './App.css'

type Tab = 'overview' | 'opportunities' | 'signals' | 'pipeline' | 'sources'
const tabs: Array<[Tab, string, typeof Gauge]> = [
  ['overview', 'Overview', Gauge], ['opportunities', 'Opportunities', Target],
  ['signals', 'Signals', Inbox], ['pipeline', 'Pipeline', Activity], ['sources', 'Sources', Database],
]
const percent = (value: number | null) => value == null ? '—' : `${Math.round(value * 100)}%`
const label = (value: string | null) => value ? value.replaceAll('_', ' ') : 'awaiting evidence'

export default function App() {
  const [tab, setTab] = useState<Tab>('overview')
  const [opportunities, setOpportunities] = useState<Opportunity[]>([])
  const [signals, setSignals] = useState<Signal[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [sources, setSources] = useState<Source[]>([])
  const [selected, setSelected] = useState<OpportunityDossier | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')

  const load = async () => {
    setLoading(true); setError('')
    try {
      const [opportunityData, signalData, runData, sourceData] = await Promise.all([api.opportunities(), api.signals(), api.runs(), api.sources()])
      setOpportunities(opportunityData.items); setSignals(signalData.items); setRuns(runData); setSources(sourceData.items)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load research data.') }
    finally { setLoading(false) }
  }
  useEffect(() => { void load() }, [])
  const filtered = useMemo(() => opportunities.filter(item => item.title.toLowerCase().includes(query.toLowerCase())), [opportunities, query])
  const openDossier = async (id: number) => { try { setSelected(await api.opportunity(id)) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load dossier.') } }
  const queueRun = async () => { try { await api.createRun(); await load(); setTab('pipeline') } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to queue run.') } }

  return <div className="app-layout">
    <aside className="sidebar"><div className="brand"><span className="brand-mark"><Radar size={18}/></span><b>IDEA HUNTER</b><small>OS</small></div>
      <div className="workspace-switcher"><span className="workspace-avatar">IH</span><span><small>WORKSPACE</small><b>Signal Lab</b></span></div>
      <nav className="nav"><small className="nav-label">RESEARCH</small>{tabs.map(([id, title, Icon]) => <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}><Icon size={17}/><span>{title}</span></button>)}</nav>
      <div className="sidebar-bottom"><div className="agent-status"><i className="pulse-dot"/><span><b>Evidence-first pipeline</b><small>Manual refresh; no fake live state</small></span></div></div>
    </aside>
    <div className="app-main"><header className="topbar"><div className="breadcrumb"><span>Signal Lab</span><b>{tabs.find(item => item[0] === tab)?.[1]}</b></div><div className="top-actions"><div className="global-search"><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search opportunities..."/></div><button className="btn" onClick={() => void load()}><RefreshCw size={14}/> Refresh</button></div></header>
      <main className="main-content"><div className="page-heading"><div><p className="eyebrow"><i className="live-dot"/> EVIDENCE-FIRST RESEARCH</p><h1>{tab === 'overview' ? 'What deserves your next hour?' : tabs.find(item => item[0] === tab)?.[1]}</h1><p className="page-subtitle">Potential, confidence and freshness remain separate. Scores recommend an action; they are not predictions.</p></div><button className="btn btn-primary" onClick={() => void queueRun()}>Queue analysis</button></div>
        {error && <div className="error-state">{error}</div>}
        {loading ? <div className="loading-state">Loading research workspace…</div> : <Views tab={tab} opportunities={filtered} signals={signals} runs={runs} sources={sources} openDossier={openDossier} retry={async (runId, step) => { await api.retryStep(runId, step); await load() }} />}
      </main>
    </div>
    {selected && <Dossier dossier={selected} close={() => setSelected(null)} refresh={load}/>} 
  </div>
}

function Views({ tab, opportunities, signals, runs, sources, openDossier, retry }: { tab: Tab; opportunities: Opportunity[]; signals: Signal[]; runs: Run[]; sources: Source[]; openDossier: (id: number) => Promise<void>; retry: (run: number, step: string) => Promise<void> }) {
  if (tab === 'overview') return <><section className="metric-grid"><Metric label="Opportunities" value={String(opportunities.length)} note="ranked for action"/><Metric label="Strong evidence" value={String(opportunities.filter(item => (item.confidence ?? 0) >= .65).length)} note="confidence ≥ 65%"/><Metric label="Pending runs" value={String(runs.filter(run => ['pending', 'running'].includes(run.status)).length)} note="resumable jobs"/></section><section className="content-panel"><Toolbar title="Recommended next actions" sub="The highest-potential opportunities, with confidence visible."/><OpportunityTable items={opportunities.slice(0, 8)} open={openDossier}/></section></>
  if (tab === 'opportunities') return <section className="content-panel"><Toolbar title="Opportunity radar" sub="Potential is attractiveness; confidence is evidence support; freshness is the latest strong signal."/><OpportunityTable items={opportunities} open={openDossier}/></section>
  if (tab === 'signals') return <section className="content-panel"><Toolbar title="Signal inbox" sub="Rejected, duplicate, and triaged items remain visible for recall review."/>{signals.map(signal => <article className="observation-card" key={signal.id}><em>“{signal.text}”</em><div className="observation-meta"><span>{signal.source} · {signal.signal_type ?? 'untriaged'} · {signal.triage_state}</span><span>↑ {signal.engagement ?? 0}</span></div></article>)}</section>
  if (tab === 'pipeline') return <section className="content-panel"><Toolbar title="Resumable runs" sub="Each stage is persisted and can be retried independently."/>{runs.map(run => <article className="run-card" key={run.id}><div><b>Run #{run.id}</b><span className="status-pill pending">{run.status}</span><small>${run.total_cost_usd.toFixed(2)} / ${run.budget_usd.toFixed(2)}</small></div>{run.error && <p className="run-error">{run.error}</p>}<div className="step-list">{run.steps.map(step => <div key={step.id}><span>{step.step_key.replaceAll('_', ' ')}</span><b>{step.status}</b><small>attempt {step.attempt_count}</small>{['failed', 'blocked'].includes(step.status) && <button className="text-btn" onClick={() => void retry(run.id, step.step_key)}>Retry</button>}</div>)}</div></article>)}</section>
  return <section className="content-panel"><Toolbar title="Source health" sub="Cursors are stored per source query, not globally per source."/>{sources.map(source => <article className="source-card" key={source.id}><b>{source.name}</b><span>{source.health_status ?? 'not configured'} · reliability {Math.round(source.reliability * 100)}%</span><small>{source.acquisition_method ?? 'unknown acquisition'}</small>{source.queries.map(query => <p key={query.id}>{query.text} — {query.last_success_at ? 'last successful run recorded' : 'not run yet'}</p>)}</article>)}</section>
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) { return <div className="metric-card"><span>{label}</span><strong>{value}</strong><small>{note}</small></div> }
function Toolbar({ title, sub }: { title: string; sub: string }) { return <div className="panel-toolbar"><div><h2>{title}</h2><p>{sub}</p></div></div> }
function OpportunityTable({ items, open }: { items: Opportunity[]; open: (id: number) => Promise<void> }) { return <div className="opportunity-table">{items.map(item => <button key={item.id} onClick={() => void open(item.id)}><span><b>{item.title}</b><small>{label(item.next_step)}</small></span><GaugeValue title="Potential" value={item.potential}/><GaugeValue title="Confidence" value={item.confidence}/><GaugeValue title="Freshness" value={item.freshness_days == null ? null : Math.max(0, 1 - item.freshness_days / 30)} suffix={item.freshness_days == null ? '—' : `${item.freshness_days}d`}/></button>)}</div> }
function GaugeValue({ title, value, suffix }: { title: string; value: number | null; suffix?: string }) { return <span className="gauge"><small>{title}</small><b>{suffix ?? percent(value)}</b></span> }
function Dossier({ dossier, close, refresh }: { dossier: OpportunityDossier; close: () => void; refresh: () => Promise<void> }) { const decide = async (decision: string) => { await api.decide(dossier.id, decision); await refresh(); close() }; return <div className="modal-overlay" onClick={close}><section className="modal-content dossier" onClick={event => event.stopPropagation()}><header className="modal-header"><div><p className="modal-kicker">OPPORTUNITY DOSSIER</p><h2>{dossier.title}</h2><div className="axis-row"><GaugeValue title="Potential" value={dossier.potential}/><GaugeValue title="Confidence" value={dossier.confidence}/><GaugeValue title="Freshness" value={null} suffix={dossier.freshness_days == null ? '—' : `${dossier.freshness_days} days`}/></div></div><button className="close-btn" onClick={close}>×</button></header><div className="modal-body"><section className="modal-section"><h3>Recommended next step</h3><div className="info-box"><b>{label(dossier.next_step)}</b><p>{dossier.description}</p></div></section><section className="modal-section"><h3>Evidence ledger</h3>{dossier.claims.length ? dossier.claims.map(claim => <article className="claim-card" key={claim.id}><b>{claim.kind} · {claim.support_state}</b><p>{claim.text}</p>{claim.evidence.map(evidence => <div className="evidence-item" key={`${claim.id}-${evidence.observation_id}-${evidence.quote}`}><em>“{evidence.quote}”</em><small>{evidence.verified ? 'verified quote' : 'unverified quote'} · {evidence.stance} · {evidence.source}</small></div>)}</article>) : <p className="text-secondary">No citation-backed claims have been extracted yet.</p>}</section></div><footer className="modal-footer"><button className="btn" onClick={close}>Close</button><div className="footer-actions"><button className="btn btn-reject" onClick={() => void decide('reject')}>Reject</button><button className="btn" onClick={() => void decide('interview')}>Interview users</button><button className="btn btn-primary" onClick={() => void decide('prototype')}>Prototype</button></div></footer></section></div> }
