# Local Opportunity Intelligence Engine — Revised Plan

**Goal:** An agentic market-research pipeline to surface startup ideas — either new needs created by a relevant shift, or practical, scalable solutions to old, neglected problems.

**Core principle:** Validation gates, not a linear build. You don't build stage N+1 until stage N proves it's worth building on top of. Every phase ends with a pass/fail check before the next one starts.

---

## 1. Data Sources & Ingestion

Start with 3 sources, not 10:

- **Reddit** (PRAW API) — best signal-to-noise for genuine complaints
- **Hacker News** (Algolia HN API — free, no auth)
- **App Store / Play Store reviews** for a few relevant app categories

Each collector is a small standalone script:
```
reddit_collector.py
hn_collector.py
reviews_collector.py
```

Every record stores: `source, source_url, published_at, collected_at, raw_text, engagement_score, content_hash`

**Efficiency — incremental crawling:** Store a `last_seen_cursor` per source per subreddit/query. Never re-pull the same window twice. Cuts API/scrape volume by 80%+ after the first run.

**Efficiency — pre-filter before anything expensive:** Run a cheap keyword/regex + basic sentiment heuristic pass first (no LLM, no embeddings) to drop obvious noise (spam, memes, off-topic). Only promote survivors to embedding/LLM stages.

Expand to GitHub Issues, job postings, Product Hunt, news, forums **only after Phase 1 proves the pipeline finds real problems** — not before.

---

## 2. Storage — Single Database, No Premature Graph DB

Drop Cognee and Qdrant for v1. Use **PostgreSQL + pgvector** for everything.

```
sources
observations (raw_text, embedding, content_hash, cluster_id)
problems (title, description, severity, frequency, status)
problem_evidence (problem_id, observation_id, evidence_strength)
existing_solutions (problem_id, name, url, gap_notes)
opportunity_scores (problem_id, score, confidence, breakdown_json)
research_runs (id, started_at, status, notes)
```

`content_hash` on observations does double duty: cross-source dedup **and** LLM-extraction caching (see §5).

If, after real use, you find yourself doing multi-hop relationship queries ("problems connected to a regulation that's connected to 3 competitors") that Postgres joins genuinely struggle with — *then* add a graph layer (Cognee). Don't pre-build it on spec.

---

## 3. Clustering — Deterministic, Not Agentic

```
observations → embeddings (local embedding model, cheap)
            → cosine similarity clustering (HDBSCAN or simple threshold clustering)
            → cluster centroids + representative samples
```

Pure math, no LLM calls — fast and free to re-run. Only cluster **labeling** needs a model call: one call per cluster, not per observation.

---

## 4. Extraction

Use a **hosted LLM API** (Claude/GPT) for the reasoning-heavy steps, not a local 1–3B/7–9B model. Reasoning quality here directly determines whether the system produces useful signal or plausible-sounding noise — this is the wrong place to cut cost. Local models are fine for the cheap pre-filter step (§1), not for problem/market analysis.

> If local-only inference is a hard requirement (cost at scale, privacy, or a separate learning goal), keep it — but that's months of prompt-engineering/routing effort traded for a weaker final signal. Decide this explicitly rather than defaulting into it.

Every extraction call returns a strict schema, no essays:

```json
{
  "problem": "",
  "target_user": "",
  "severity": 0,
  "frequency": 0,
  "workaround": "",
  "evidence_ids": [],
  "confidence": 0
}
```

**Efficiency — extraction cache:** Key by `content_hash`. Re-running the pipeline never re-extracts the same raw content — just re-links it.

**Efficiency — batching:** Batch cluster-labeling calls (5–10 clusters per request where supported) to cut round-trips and cost.

---

## 5. Agents — Three, Not Six, Run as a Plain Sequential Pipeline First

Skip LangGraph for v1. A plain Python function chain with a `research_runs` status column gives you the same "resume a failed step" benefit without orchestration overhead. Introduce LangGraph later only if you need parallel branching or human-in-the-loop pausing that a retry loop can't handle.

1. **Problem + Demand agent** — what's broken, how often, for whom (merges the original's Problem + Demand roles — they answer overlapping questions)
2. **Competition + Trend agent** — what exists, why it's inadequate, is this growing (merges Competition + Trend)
3. **Devil's Advocate** — why this could fail, what evidence contradicts it

**Verifier** stays deterministic, not another LLM persona — it confirms every claim in the output traces to an `evidence_id` in the database. A Python query, not a model call.

Add a standalone Economics agent and a separate Trend agent only if the merged agents prove to miss things in practice.

---

## 6. Scoring — Deterministic (kept from the original — this part was right)

```
Final Score = Raw Opportunity Score × Evidence Confidence × Source Diversity
```

Weights: pain severity, frequency, growth trend, market gap, feasibility given your own stack (Flutter / FastAPI / Firebase — you can actually build the winners). Plain Python, no LLM in the loop.

**Efficiency/quality — source reliability weighting:** Track which sources historically produced problems that later validated well (once you act on outputs), and up-weight those sources' evidence over time. The system gets smarter with use instead of staying static.

---

## 7. Output — Skip the Dashboard Until Phase 4

A markdown report per research run is enough for months:

```
## Problem: <title>
Score: 84 | Confidence: 91% | Evidence: 23 items across 3 sources
Who: ...
Why current solutions fail: ...
Devil's Advocate: ...
```

Build the Next.js "Opportunity Radar" dashboard only once enough runs exist that scrolling markdown files is the actual bottleneck — not before.

---

## 8. Roadmap With Hard Validation Gates

### Phase 1 (1–2 weeks): Signal → Problem
Build: 3 collectors, dedup, embeddings, clustering, one extraction call per cluster, markdown output.
**Gate:** Does this surface 2–3 problems you didn't already know about and would seriously consider? If no — fix source selection or extraction prompts before proceeding.

### Phase 2 (1 week): Scoring + Verifier
Add deterministic scoring, evidence confidence, verifier.
**Gate:** Does the ranking match your own gut sense of "this one's more promising"? If scores feel random, fix the weight formula or evidence signals before adding agents.

### Phase 3 (1–2 weeks): Devil's Advocate + Competition Analysis
Add the two extra agent roles.
**Gate:** Does Devil's Advocate actually kill ideas that deserved killing, based on runs you've manually reviewed?

### Phase 4 (ongoing, only if Phases 1–3 held up): Continuous Radar
Scheduled daily/weekly delta runs, trend-over-time tracking ("moved from #34 to #7"), dashboard, alerting.

### Deferred indefinitely, unless a specific pain point demands it
Cognee / knowledge graph, Qdrant, LangGraph, fine-tuning, speculative decoding, fully-local inference for reasoning steps.

---

## 9. Efficiency Additions Not in the Original

- **Cost/token tracking** per run from day one — you'll want this before it surprises you.
- **Kill switch / max-iteration cap** on any "investigate deeper" loop, so a single problem can't spiral into unlimited API spend.
- **Human-label feedback loop:** every manual accept/reject of a surfaced problem gets stored — free few-shot data to improve extraction prompts later.
- **Freshness decay:** evidence older than N months counts less unless reconfirmed by newer observations, so stale complaints don't outrank live ones.

---

## Bottom-Line v1 Stack

Python + PostgreSQL/pgvector + a hosted LLM API + plain sequential orchestration + (optional) FastAPI if you want an API surface.

Everything else in the original doc — Cognee, Qdrant, LangGraph, fully-local inference, fine-tuning, speculative decoding, the Next.js dashboard — is a legitimate *future* upgrade, not a v1 requirement. Add each piece only when a validation gate shows the simpler version is actually the bottleneck.
