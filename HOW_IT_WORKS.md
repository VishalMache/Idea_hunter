# IDEA HUNTER — System Documentation

> A local, privacy-first **Opportunity Intelligence Engine** that automatically harvests user complaints from the internet, clusters them by theme, extracts structured problems using AI, scores them for startup viability, and surfaces them through a web dashboard.

---

## How the Pipeline Works (End-to-End)

Below is the full flow from raw internet data to a scored startup opportunity, in exact execution order.

```
Internet Data Sources
        │
        ▼
   [1] COLLECTORS
  (hackernews, playstore, github)
        │
        ▼
   [2] PRE-FILTER
  (keyword + noise check)
        │
        ▼
   [3] DEDUPLICATE
  (SHA-256 content hash → Postgres ON CONFLICT)
        │
        ▼
   [4] EMBED
  (Ollama nomic-embed-text → 768-dim vector)
        │
        ▼
   [5] CLUSTER
  (HDBSCAN on embeddings → thematic groups)
        │
        ▼
   [6] EXTRACT + COMPETITION AGENT
  (OpenRouter GPT-4o-mini → structured problem + competitor analysis)
        │
        ▼
   [7] VERIFY
  (Deterministic quality gate → flags weak problems)
        │
        ▼
   [8] SCORE
  (Weighted formula + source diversity + engagement bonus)
        │
        ▼
   [9] DASHBOARD + REPORT
  (React Web UI + Markdown file)
```

---

## Stage-by-Stage Breakdown

### Stage 1 — Collectors

**Where:** `src/idea_hunter/collectors/`

Collectors are responsible for pulling raw text data from the internet. All collectors inherit from `BaseCollector` and yield `RawObservation` objects.

| Collector | File | Status | Requires Auth? | Notes |
|---|---|---|---|---|
| HackerNews | `hackernews.py` | ✅ Working | No | Uses Algolia free API. Searches HN comments by keyword. Paginated. |
| Google Play Store | `reviews.py` | ✅ Working | No | Scrapes 1–3 star reviews for apps matching a search query. |
| GitHub Issues | `github.py` | ⚠️ Built, Untested | Optional (`github_token`) | Searches GitHub Issues for bug reports & feature requests. |
| Reddit | `reddit.py` | ⚠️ Built, No Credentials | Yes (`reddit_client_id/secret`) | Built using `asyncpraw`. Deferred until Reddit API credentials are available. |

Each `RawObservation` carries: `source_type`, `source_url`, `raw_text`, `author`, `published_at`, `engagement` (upvotes/comments), `topic`, `cursor_value`.

---

### Stage 2 — Pre-Filter

**Where:** `src/idea_hunter/processing/prefilter.py`

A cheap, zero-cost gate that runs **before** any embedding or LLM call. It drops obvious noise to save money.

**How it works:**
1. **Length check** — drops anything under 30 characters.
2. **Noise patterns** — drops `[deleted]`, posts that are just URLs, quoted/forwarded text, pure laughing reactions.
3. **Engagement gate** — optionally drops low-engagement posts (configurable `min_engagement`).
4. **Pain keyword matching** — checks for keywords like: `"frustrated"`, `"hate"`, `"no tool"`, `"would pay"`, `"manual"`, `"missing feature"`, `"spent hours"`, etc. Requires at least 1 match to pass. 3+ matches = max signal score.

Returns a `PrefilterResult(passed, reason, score)`.

---

### Stage 3 — Deduplication

**Where:** `src/idea_hunter/processing/deduplicator.py`

Computes a **SHA-256 hash** of the cleaned text. When inserting into PostgreSQL, uses `ON CONFLICT DO NOTHING` on the unique `content_hash` column. This means the same complaint can never be stored twice even across multiple collection runs.

---

### Stage 4 — Embedding

**Where:** `src/idea_hunter/processing/embedder.py`

Converts each cleaned observation into a **768-dimensional vector** using **Ollama running locally** with the `nomic-embed-text` model. This runs entirely on your machine — no API cost.

The embedding is stored as JSON in the `observations.embedding` column (for now; a native `pgvector` column can replace this later).

---

### Stage 5 — Clustering

**Where:** `src/idea_hunter/analysis/clusterer.py`

Runs **HDBSCAN** (Hierarchical Density-Based Spatial Clustering) on the stored embeddings. Complaints about similar themes naturally cluster together. For example, "hate syncing calendar apps" and "my calendar doesn't work offline" would land in the same cluster.

**Key configuration:**
- `min_cluster_size = 2` (intentionally low for small datasets)
- `min_samples = 2`
- Noise points (cluster label `-1`) are discarded and never extracted

The cluster ID is written back into the `observations.cluster_id` column.

---

### Stage 6 — Extraction + Competition Agent

**Where:** `src/idea_hunter/processing/extractor.py`, `src/idea_hunter/llm/router.py`

For each cluster, the engine sends all raw texts to **OpenRouter (`gpt-4o-mini`)** via two chained LLM calls:

**Call 1 — Problem Extractor:**
Returns a structured `ExtractedProblem`:
- `problem` — concise title for the core pain
- `target_user` — who has this problem
- `context` — when/where it happens
- `severity` — 1–10 pain score
- `frequency` — 1–10 how often it occurs
- `workaround` — what users do today to cope
- `existing_solutions` — tools they mentioned
- `devils_advocate_notes` — a strict, falsifiable reason this might NOT be a good startup idea
- `confidence` — 0.0–1.0 confidence this is a real problem (below 0.3 = discarded)

**Call 2 — Competition Agent:**
Returns a `CompetitionAnalysis`:
- `competitors` — specific existing tools/products users are trying
- `why_they_fail` — the precise reason existing solutions are failing users
- `market_gap` — what a new entrant could do differently

Both results are saved to the `problems` and `existing_solutions` DB tables.

---

### Stage 7 — Verification Gate

**Where:** `src/idea_hunter/processing/verifier.py`

A deterministic, **zero-cost quality check** that runs before scoring. Sets `problem.verified = True` or `problem.status = "flagged"`.

**Rules to pass:**
1. `severity × frequency >= 25` (e.g., a 5×4 problem would fail, a 7×6 would pass)
2. At least 2 raw observations in the evidence chain
3. Either `max_engagement > 0` OR evidence spans more than 1 source

Problems that fail are marked `status = "flagged"` and are **not scored**.

---

### Stage 8 — Scoring

**Where:** `src/idea_hunter/analysis/scorer.py`

A deterministic weighted formula (no randomness, fully reproducible):

| Dimension | Weight |
|---|---|
| Pain Severity | 20% |
| Problem Frequency | 15% |
| Growth Trend | 15% |
| Willingness to Pay | 15% |
| Market Size | 10% |
| Competition Gap | 10% |
| Distribution Feasibility | 10% |
| Technical Feasibility | 5% |

**Bonuses applied after the base score:**
- **Evidence Confidence** multiplier (from LLM, 0.0–1.0)
- **Source Diversity**: up to +20% if the problem appears across multiple platforms
- **Engagement**: +10% if `max_engagement > 100`, +5% if `> 10`
- Final score is capped at 1.0

---

### Stage 9 — Output

**Two outputs are generated:**

#### A. Markdown Report (`opportunity_report.md`)
Generated by `src/idea_hunter/output/report_generator.py`. A static file you can read in any text editor. Contains all scored opportunities ranked by score.

#### B. Web Dashboard (`dashboard-v2/`)
A React app that talks to the **FastAPI backend** (`src/idea_hunter/api/main.py`).

**API endpoints available:**
| Method | Endpoint | What it does |
|---|---|---|
| `GET` | `/api/stats` | Overall pipeline health (counts) |
| `GET` | `/api/observations` | All raw collected observations |
| `GET` | `/api/opportunities` | All scored opportunities, ranked by score |
| `GET` | `/api/problems/{id}` | Full deep-dive: evidence chain, solutions, devil's advocate |
| `POST` | `/api/feedback/{id}` | Accept or reject an opportunity (saved to DB) |

**Dashboard views:**
- **Opportunity Radar** tab — scored cards you can click for deep-dives
- **Raw Observations** tab — all raw scraped text with source + engagement

---

## CLI Reference

All commands are run inside the `.venv` virtual environment.

```powershell
# COLLECT
idea-hunter collect hackernews --query "hate manually doing" --limit 100
idea-hunter collect playstore --query "productivity" --limit 100
idea-hunter collect github --query "feature request" --limit 50

# PROCESS
idea-hunter process embed           # Embed all un-embedded observations
idea-hunter process cluster         # Cluster embedded observations
idea-hunter process extract         # Run LLM extraction on all clusters
idea-hunter process verify          # Run quality gate on all problems

# ANALYZE
idea-hunter analyze score           # Score all verified problems

# OUTPUT
idea-hunter output report           # Generate opportunity_report.md
```

---

## Database Schema (PostgreSQL 17)

| Table | Purpose |
|---|---|
| `sources` | Metadata about each data source (HN, Play Store, etc.) |
| `observations` | Raw scraped text — the core data unit. Has `content_hash`, `embedding`, `cluster_id` |
| `problems` | LLM-extracted structured problem descriptions |
| `problem_evidence` | Join table linking `observations` → `problems` |
| `existing_solutions` | Competitors and gaps identified by the Competition Agent |
| `opportunities` | One-to-one with `problems`, holds the title and status |
| `opportunity_scores` | Full scoring breakdown for each opportunity |
| `user_feedback` | Stores your accept/reject verdicts from the dashboard |
| `research_runs` | Tracks collection runs (start/end time, items collected) |
| `cost_logs` | Tracks API token costs per run |
| `trends` | Placeholder for future trend detection |

---

## What's Still Pending (TODO)

### 🔴 Critical / Broken

- **`github.py` is untested** — The `github_token` config key doesn't exist in `settings` (the code references `settings.github_token` which doesn't exist in `config.py`). Will crash if you try to run `collect github`.
- **`pgvector` not used** — Embeddings are stored as JSON arrays, not proper PostgreSQL `vector` columns. This means semantic similarity search is not available and queries will be slow at scale.
- **Scoring inputs are hardcoded** — In `cli/main.py`, `growth_trend`, `willingness_to_pay`, `market_size`, `competition_gap`, `distribution_feasibility`, and `technical_feasibility` are all hardcoded to `0.5`. The LLM doesn't actually estimate these — only `severity` and `frequency` come from the extracted problem.

### 🟡 Incomplete / Stub

- **Reddit collector is built but not wired to CLI** — `reddit.py` exists and is fully coded, but there is no `collect reddit` CLI command. Also requires API credentials.
- **`trends` table is empty** — The `Trend` model exists but nothing writes to it. Trend detection was planned for a later phase.
- **`CostLog` table is never written to** — The table exists and the model is defined, but the LLM clients never actually log costs. The `max_cost_per_run_usd = $2.00` guardrail is not enforced.
- **`ResearchRun` table is never written to** — Run tracking is defined but not implemented in any CLI command.
- **`confidence.py` is unused** — `src/idea_hunter/analysis/confidence.py` exists but is never called in the pipeline.
- **Dashboard has no error states** — If the API is down, the React UI silently shows an empty state with no message.
- **No authentication on the API** — The FastAPI backend allows all origins (`*`) and has no auth. Fine for local use, but needs securing before any deployment.

### 🟢 Future / Phase 3

- **Reddit API credentials** — Wire up Reddit once you get API credentials from `reddit.com/prefs/apps`.
- **Native `pgvector` columns** — Replace JSON embeddings with proper `vector(768)` columns for fast approximate nearest-neighbor search.
- **Trend detection** — Populate the `trends` table by comparing cluster sizes over time.
- **Cost tracking** — Implement `CostLog` writes and enforce the `$2.00/run` guardrail.
- **`collect github` command** — Add the CLI command and fix the missing `github_token` config key.
- **Automatic pipeline scheduling** — Currently every step must be run manually. A scheduled background job would run the full pipeline nightly.
- **Better LLM scoring** — Replace the hardcoded `0.5` fallbacks for `willingness_to_pay`, `market_size`, etc. with actual LLM estimates from the extraction step.
