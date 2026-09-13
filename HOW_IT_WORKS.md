# Idea Hunter — How It Works

> **A local AI-powered pipeline that crawls the internet for pain points, clusters them into validated problems, researches them with a multi-agent LLM system, and scores them as startup opportunities.**

---

## Table of Contents

1. [The Big Picture](#1-the-big-picture)
2. [Architecture Overview](#2-architecture-overview)
3. [The 7-Step Pipeline](#3-the-7-step-pipeline)
   - [Step 1: Collect](#step-1-collect)
   - [Step 2: Embed](#step-2-embed)
   - [Step 3: Cluster](#step-3-cluster)
   - [Step 4: Extract](#step-4-extract)
   - [Step 5: Research (Multi-Agent)](#step-5-research-multi-agent)
   - [Step 6: Score](#step-6-score)
   - [Step 7: Report](#step-7-report)
4. [Path B — Compound Discovery](#4-path-b--compound-discovery)
5. [The LLM Stack](#5-the-llm-stack)
6. [The Database Schema](#6-the-database-schema)
7. [The API & Dashboard](#7-the-api--dashboard)
8. [Cost Control System](#8-cost-control-system)
9. [Configuration Reference](#9-configuration-reference)
10. [Running the Pipeline](#10-running-the-pipeline)

---

## 1. The Big Picture

Idea Hunter is an **automated opportunity intelligence engine** for founders. It answers one question:

> *"What real problems are people complaining about online that nobody has built a great solution for yet?"*

Instead of manual research, gut-feel, or expensive market research firms, Idea Hunter:

1. **Scrapes** pain signals from HackerNews, Reddit, GitHub Issues, and Play Store reviews.
2. **Filters** noise at zero LLM cost using keyword heuristics.
3. **Clusters** similar complaints together using vector embeddings + HDBSCAN.
4. **Extracts** a structured problem from each cluster using an LLM.
5. **Researches** each problem with 5 parallel AI agents (Customer, Market, Technical, Distribution, Why Now).
6. **Debates** the idea with a Bull/Bear Judge agent.
7. **Scores** and **ranks** opportunities using an evidence-backed scoring model.
8. **Reports** the top opportunities as a ranked markdown file.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         SOURCES                                 │
│   HackerNews   Reddit   GitHub Issues   Play Store Reviews      │
└───────────────────────────┬─────────────────────────────────────┘
                            │  collect
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  PRE-FILTER  (Zero LLM cost — keyword + regex + engagement)     │
│  Pain keywords: "frustrated", "workaround", "would pay", etc.   │
│  Noise patterns: "[deleted]", "lol", bare URLs dropped          │
└───────────────────────────┬─────────────────────────────────────┘
                            │  pass
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  OBSERVATIONS TABLE  (PostgreSQL + pgvector)                    │
│  raw_text, content_hash, source_id, engagement, passed_prefilter│
└───────────────────────────┬─────────────────────────────────────┘
                            │  embed
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  LOCAL OLLAMA  —  nomic-embed-text  (768-dim vectors)           │
│  Embeddings stored in pgvector column on observations table     │
└───────────────────────────┬─────────────────────────────────────┘
                            │  cluster
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  HDBSCAN  →  cluster_id assigned to each observation            │
│  New observations merged into existing clusters via cosine dist  │
└───────────────────────────┬─────────────────────────────────────┘
                            │  extract (per cluster)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  HOSTED LLM  (OpenRouter / OpenAI / Anthropic)                  │
│  → ExtractedProblem  (title, severity, frequency, workaround)   │
│  → CompetitionAnalysis  (competitors, gap, why they fail)       │
│  Saved as Problems + ProblemEvidence + ExistingSolutions        │
└───────────────────────────┬─────────────────────────────────────┘
                            │  verify
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  VERIFIER  (rule-based quality gates)                           │
│  severity×frequency >= 25, min 2 evidence observations,         │
│  at least 1 engaged source or multi-platform signal             │
└───────────────────────────┬─────────────────────────────────────┘
                            │  research (5 agents in parallel)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  MULTI-AGENT RESEARCH PIPELINE                                  │
│  ┌──────────┐ ┌────────┐ ┌────────────┐ ┌──────────┐ ┌───────┐│
│  │ Customer │ │ Market │ │ Technical  │ │Distribut.│ │WhyNow ││
│  │  Agent   │ │ Agent  │ │   Agent    │ │  Agent   │ │ Agent ││
│  └────┬─────┘ └───┬────┘ └─────┬──────┘ └────┬─────┘ └──┬────┘│
│       └───────────┴────────────┴─────────────┴──────────┘     │
│                                │ combine                        │
│                                ▼                                │
│                    BULL/BEAR JUDGE AGENT                        │
│                    → verdict: BUILD / VALIDATE / KILL           │
└───────────────────────────┬─────────────────────────────────────┘
                            │  score
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  EVIDENCE-BACKED SCORER                                         │
│  Weighted dimensions → final_score (0.0–1.0)                   │
│  Multiplied by evidence_confidence                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │  report
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  opportunity_report.md  +  FastAPI REST  +  React Dashboard     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. The 7-Step Pipeline

### Step 1: Collect

**Command:** `process collect hackernews --query "I hate" --limit 100`

**Sources:**

| Collector | What it scrapes | Key signal |
|---|---|---|
| `HackerNewsCollector` | Ask HN, Show HN, comment threads | Upvote count as engagement |
| `RedditCollector` | Posts/comments from target subreddits | Upvotes + comment count |
| `GitHubCollector` | Open issues with pain keywords | Reactions count |
| `PlayStoreReviewsCollector` | 1–3 star app reviews | Star rating as negative signal |

**What happens:**
1. Each collector fetches raw posts/comments.
2. Text is cleaned by `TextCleaner` (strips HTML, extra whitespace, etc.).
3. The **Pre-Filter** runs instantly on every piece of text — zero LLM cost:
   - Checks for pain keywords: `"frustrated"`, `"workaround"`, `"would pay"`, `"nobody solves"`, `"wish there was"`, etc.
   - Drops noise patterns: `[deleted]`, `[removed]`, bare URLs, `lol`/`haha` reactions.
   - Requires minimum text length (30 chars).
4. Each observation is stored with a **SHA-256 content hash** for deduplication. PostgreSQL `ON CONFLICT DO NOTHING` ensures the same post is never stored twice even across multiple runs.
5. A `last_seen_cursor` is stored per source to enable **incremental crawling** — next run picks up from where it left off.

**Key field saved:** `passed_prefilter` (boolean) — only `True` records move forward.

---

### Step 2: Embed

**Command:** `process embed`

**What happens:**
1. Queries all observations where `passed_prefilter = true AND embedding IS NULL`.
2. Sends text to **local Ollama** running `nomic-embed-text` (768 dimensions).
3. Embeddings are processed in chunks of 10 and flushed to PostgreSQL after each chunk (so progress is preserved if interrupted).
4. Stores the vector in the `embedding` column (pgvector type).

**Why nomic-embed-text?** It's a fast, high-quality embedding model that runs fully locally — no API cost, no data leaving your machine.

---

### Step 3: Cluster

**Command:** `process cluster`

**What happens:**
1. Loads all observations with embeddings and no `cluster_id` yet.
2. **Merge phase (pgvector):** For each new observation, computes cosine distance to the nearest already-clustered observation. If distance < 0.2 (high similarity), merges it into that cluster. Also logs a `Trend` entry to track growing clusters.
3. **HDBSCAN phase:** Any observation that didn't merge runs through HDBSCAN (`min_cluster_size=2`, `min_samples=2`). This creates new clusters from fresh data.
4. Noise points (HDBSCAN label `-1`) become singleton clusters — they still get processed in extraction.
5. Each observation gets a `cluster_id` written back.

**Why HDBSCAN?** It's density-based — no need to pre-specify the number of clusters. It naturally finds groups of semantically similar complaints and handles outliers gracefully.

---

### Step 4: Extract

**Command:** `process extract --limit 10`

**What happens per cluster:**
1. Finds all cluster IDs that don't yet have a `ProblemEvidence` record (i.e., unprocessed clusters).
2. For each cluster, fetches all raw texts in it.
3. Sends them to the **hosted LLM** (OpenRouter/OpenAI/Anthropic) with two parallel prompts:

**Prompt A — Problem Extraction:**
> *"You are an expert product researcher. Extract the core problem this cluster of complaints all share: title, who experiences it, severity (1-10), frequency (1-10), workaround, and a Devil's Advocate view on why this is a bad startup idea."*

**Prompt B — Competition Analysis:**
> *"Analyze the competitive landscape: who are the existing solutions, why are they failing, and what is the exact market gap?"*

4. If a valid problem is found, it's saved as:
   - A `Problem` row (title, description, severity, frequency, user_segment, workaround, signal_type)
   - `ProblemEvidence` rows linking each observation to the problem
   - `ExistingSolution` rows for each named competitor

**Budget guard:** Checks total cost before each cluster — stops if `max_cost_per_run_usd` (default: $2.00) is exceeded.

---

### Step 5: Research (Multi-Agent)

**Command:** `analyze research`

This is the most powerful step. For each verified problem, **5 specialist agents run in parallel** using `asyncio.gather`:

| Agent | What it analyzes | Output |
|---|---|---|
| **Customer Agent** | B2C vs B2B, who holds the budget, economic value, pain frequency | `CustomerAnalysis` |
| **Market Agent** | TAM sizing from signals, growth trajectory, adjacent spend | `MarketResearch` |
| **Technical Agent** | Core tech required, complexity score, regulatory blockers, MVP cost estimate | `TechnicalAssessment` |
| **Distribution Agent** | Where users hang out, acquisition channel, how hard to break in (1-10) | `DistributionAssessment` |
| **Why Now Agent** | What technology/regulatory/behaviour shift makes this solvable TODAY | `WhyNowAssessment` |

After all 5 agents complete, the **Bull/Bear Judge Agent** receives all 5 reports and produces:
- **Bull Case** — strongest argument for why this is a billion-dollar company
- **Bear Case** — strongest structural argument for why it will fail
- **Verdict** — `BUILD`, `VALIDATE`, or `KILL`

All results are saved to `problem_research` as JSON columns.

---

### Step 6: Score

**Command:** `analyze score`

**The scoring model** combines 7 weighted dimensions into a final `0.0–1.0` score:

| Dimension | Weight | Source |
|---|---|---|
| Pain Severity | 20% | `problem.severity / 10` |
| Market Size | 15% | Market Agent `score` |
| Willingness to Pay | 15% | Pricing signals in raw text + Customer Agent |
| Why Now | 15% | Why Now Agent `score` |
| Competition Gap | 15% | Named competitors count |
| Distribution | 10% | Distribution Agent `score` |
| Technical Feasibility | 10% | Technical Agent `score` |

**Evidence Confidence Multiplier:**
```
confidence = 0.4 + (0.1 × platforms_covered) + (0.05 × min(10, independent_sources))
final_score = raw_score × confidence
```

This means a problem with lots of cross-platform evidence scores higher than one seen only once on a single source — the system rewards signal diversity.

**Evidence Ledger** (saved per opportunity):
- User complaints count
- Independent sources (cross-referenced)
- Platforms covered
- Named competitors found
- Pricing evidence signals (mentions of "$")
- Recent signals (last 30 days)

---

### Step 7: Report

**Command:** `output report`

Generates `opportunity_report.md` with all opportunities ranked by final score. Each entry shows:
- Final score and confidence percentage
- Star ratings (★★★★☆) for each dimension with evidence snippet
- Full evidence ledger
- Bull Case, Bear Case, and BUILD/VALIDATE/KILL verdict

---

## 4. Path B — Compound Discovery

**Command:** `analyze path-b`

This is a second discovery mode that finds **"Old Problem + New Tech = New Opportunity"**.

You seed the database with:
- `HardProblem` rows — problems that have been painful for decades but were previously unsolvable (e.g., "Real-time language translation for video calls", "Automated medical coding")
- `TechShift` rows — recent technological or regulatory shifts (e.g., "LLMs can now follow complex instructions", "EU AI Act came into force", "Inference cost dropped 100x")

The **Compound Opportunity Agent** then asks:
> *"Does any recent tech shift suddenly make this hard old problem solvable in a way it wasn't before?"*

If `confidence_score > 0.6`, a new `Problem` + `ProblemResearch` is created with `signal_type = "path_b"` and immediately marked verified, skipping the normal collection pipeline.

---

## 5. The LLM Stack

Idea Hunter uses a **two-tier LLM architecture** to minimize cost:

### Local (Free — via Ollama)

| Model | Used For |
|---|---|
| `nomic-embed-text` | Semantic embeddings for all observations |
| `granite3.1-dense:2b` | Quick complaint classification (pre-LLM gate) |

### Hosted (Paid — via API)

| Provider | Default Model | Used For |
|---|---|---|
| OpenRouter | `openai/gpt-4o-mini` | Problem extraction, research agents, debate |
| OpenAI | `gpt-4o-mini` | Alternative provider |
| Anthropic | `claude-3-5-haiku-20241022` | Alternative provider |

Switch provider by setting `LLM_PROVIDER=openai` (or `anthropic`, `openrouter`) in `.env`.

### How `ModelRouter` works

`ModelRouter` in [`llm/router.py`](src/idea_hunter/llm/router.py) dispatches tasks:
- **Cheap/local tasks** → `local_client.generate_structured()` using Ollama
- **Expensive/reasoning tasks** → `hosted_client.generate_structured()` using the hosted API

All LLM calls produce **structured Pydantic output** — no regex parsing of free text.

---

## 6. The Database Schema

```
sources            ← One row per data source (hackernews, reddit, etc.)
  └── observations ← Raw scraped text + embedding vector + cluster_id
        └── problem_evidence ← Links observations → problems
              └── problems   ← Extracted structured problems
                    ├── existing_solutions  ← Named competitor list
                    ├── problem_research    ← Multi-agent JSON reports
                    └── opportunities       ← Scored opportunities
                          └── opportunity_scores ← Dimension breakdown

research_runs   ← Audit log of every pipeline execution
cost_logs       ← Token-level cost tracking per run
user_feedback   ← Human accept/reject verdicts on opportunities
trends          ← Velocity signals when observations merge into clusters
hard_problems   ← Seed data for Path B discovery
tech_shifts     ← Seed data for Path B discovery
```

**Key design decisions:**
- **pgvector** for the `embedding` column enables cosine similarity search directly in SQL — no separate vector DB needed.
- **Content hash deduplication** (SHA-256) prevents the same complaint from being processed twice across multiple runs.
- **Incremental crawl cursor** (`last_seen_cursor` on `sources`) means each new run only fetches posts newer than the last run.
- **`signal_type`** on problems tracks where they came from: `"cluster"` (from HDBSCAN), `"singleton"` (single observation), or `"path_b"` (compound discovery).

---

## 7. The API & Dashboard

### FastAPI Backend (`src/idea_hunter/api/main.py`)

Running at `http://localhost:8000`:

| Endpoint | Description |
|---|---|
| `GET /opportunities` | List all scored opportunities sorted by score |
| `GET /opportunities/{id}` | Full details for one opportunity |
| `GET /problems` | List all extracted problems |
| `POST /feedback/{problem_id}` | Submit BUILD/KILL verdict |
| `GET /stats` | Database stats summary |
| `GET /docs` | Auto-generated Swagger UI |

### React Dashboard (`dashboard-v2/`)

Running at `http://localhost:5173`:
- Opportunity cards ranked by score with star ratings
- Evidence ledger display per opportunity
- Bull/Bear debate viewer
- One-click BUILD/KILL feedback buttons

---

## 8. Cost Control System

Every hosted LLM call is tracked in the `cost_logs` table with:
- `model` — which model was used
- `provider` — openrouter / openai / anthropic
- `input_tokens`, `output_tokens`, `cost_usd`
- `run_id` — links back to the research run

**Budget guards** in the pipeline:
- Before each cluster extraction: checks if total cost >= `max_cost_per_run_usd` (default: $2.00)
- Before each research run: same check

**Typical costs:**
| Stage | Cost |
|---|---|
| Embedding 500 observations | $0.00 (local Ollama) |
| Extract 10 clusters | ~$0.05–$0.15 (GPT-4o-mini) |
| Research 5 problems (5 agents + debate) | ~$0.10–$0.30 |
| **Total per full run** | **~$0.15–$0.50** |

---

## 9. Configuration Reference

All settings are in `.env` (read by `src/idea_hunter/config.py`):

```dotenv
# Database
DATABASE_URL=postgresql+asyncpg://ideahunter:ideahunter@localhost:5432/ideahunter

# Local Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_SMALL=granite3.1-dense:2b
OLLAMA_EMBED_MODEL=nomic-embed-text

# Hosted LLM
LLM_PROVIDER=openrouter           # openrouter | openai | anthropic | ollama
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-4o-mini

# Cost Limits
MAX_COST_PER_RUN_USD=2.0
MAX_AGENT_ITERATIONS=3

# Data Sources (optional)
GITHUB_TOKEN=ghp_...
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
```

---

## 10. Running the Pipeline

### One-click full pipeline

```powershell
.\run.ps1
```

### With options

```powershell
# Custom queries
.\run.ps1 -Queries "I hate", "why is there no", "annoying problem"

# Skip data collection (use existing observations)
.\run.ps1 -SkipCollect

# Pipeline only, no dashboard launch
.\run.ps1 -SkipDashboard
```

### Step-by-step manual run

```powershell
# 1. Collect from HackerNews
python -m idea_hunter.cli.main collect hackernews --query "I hate" --limit 100

# 2. Embed observations (local Ollama)
python -m idea_hunter.cli.main process embed

# 3. Cluster similar problems
python -m idea_hunter.cli.main process cluster

# 4. Extract problems from clusters (LLM)
python -m idea_hunter.cli.main process extract --limit 10

# 5. Verify problems (rule-based gates)
python -m idea_hunter.cli.main process verify

# 6. Run multi-agent research (LLM)
python -m idea_hunter.cli.main analyze research

# 7. Path B discovery (optional)
python -m idea_hunter.cli.main analyze path-b

# 8. Score all problems
python -m idea_hunter.cli.main analyze score

# 9. Generate report
python -m idea_hunter.cli.main output report
```

### Launch services separately

```powershell
# FastAPI backend
python -m uvicorn idea_hunter.api.main:app --reload --port 8000

# React dashboard
cd dashboard-v2
npm run dev
```

---

*Built with: Python, SQLAlchemy (async), PostgreSQL, pgvector, Ollama, HDBSCAN, FastAPI, React*
