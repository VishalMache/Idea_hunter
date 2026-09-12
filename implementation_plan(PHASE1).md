# Idea Hunter — Phase 1: Research Core

Build the foundational data pipeline that can reliably discover and extract real problems from public data sources.

## User Review Required

> [!CAUTION]
> **Hardware Reality Check: 8GB RAM + Integrated Graphics**
> 
> Your hardware is significantly constrained for local LLM inference. Here's the honest assessment:
> 
> | Model Size | RAM Required | Feasibility on Your Hardware |
> |-----------|-------------|----------------------------|
> | 1-3B (Q4) | ~2-3 GB | ✅ Runs, but slow (~2-5 tok/s) |
> | 7-9B (Q4) | ~5-6 GB | ⚠️ Barely fits, leaves no headroom for DB/app |
> | 7-9B (Q8) | ~8-10 GB | ❌ Won't fit |
> | 13B+ | 10+ GB | ❌ Impossible |
> 
> **My recommendation for Phase 1:**
> - Use **Ollama** with `phi3:mini` (3.8B Q4, ~2.3GB) or `qwen2.5:3b` for all LLM tasks
> - Use `nomic-embed-text` (137M params, ~275MB) for embeddings — runs well on CPU
> - Accept that the 3B model will need **very** strong prompts + structured output to compensate
> - Reserve the option to add a cloud API fallback (e.g., Gemini Flash free tier) for complex reasoning tasks like Devil's Advocate — entirely optional and only when local quality is insufficient
> 
> The architecture is designed so you can swap in larger models later when you upgrade hardware. Nothing is locked to a specific model size.

> [!IMPORTANT]
> **Scope Decision: No Frontend for Phase 1**
> 
> Per your preference, Phase 1 is backend/CLI only. The "Opportunity Radar" dashboard moves to Phase 2+. Instead, we build:
> - Rich CLI interface using `rich` library for tables, progress bars, formatted output
> - JSON/CSV export for all reports
> - FastAPI endpoints ready for frontend consumption later

## Open Questions

> [!IMPORTANT]
> **PostgreSQL Setup — How are you running it?**
> - Do you already have PostgreSQL installed locally?
> - Would you prefer Docker (cleaner isolation) or native Windows install?
> - Given 8GB RAM, Docker adds ~200-400MB overhead — worth considering

> [!IMPORTANT]
> **Ollama — Is it installed?**
> - Do you already have Ollama running on your machine?
> - If not, we'll add installation steps to the setup process

> [!IMPORTANT]
> **Cloud API Fallback — Your Stance**
> - The architecture doc says "no cloud LLM dependency" 
> - With 8GB RAM, a 3B model is your ceiling for reliable local inference
> - Do you want a **completely offline** system (accepting lower quality on complex analysis), or are you open to an optional cloud API fallback for the hardest reasoning tasks only?

---

## Proposed Changes

### 1. Project Foundation

#### [NEW] Project root structure

```
idea_hunter/
├── pyproject.toml              # uv/pip project config
├── .env.template               # Environment variable template
├── .env                        # Local config (gitignored)
├── .gitignore
├── README.md
├── alembic.ini                 # DB migration config
├── alembic/                    # DB migrations
│   ├── env.py
│   └── versions/
├── src/
│   └── idea_hunter/
│       ├── __init__.py
│       ├── config.py           # Settings via pydantic-settings
│       ├── main.py             # CLI entrypoint
│       │
│       ├── db/                 # Database layer
│       │   ├── __init__.py
│       │   ├── engine.py       # SQLAlchemy async engine
│       │   ├── models.py       # ORM models
│       │   └── session.py      # Session management
│       │
│       ├── collectors/         # Data source collectors
│       │   ├── __init__.py
│       │   ├── base.py         # Abstract collector
│       │   ├── reddit.py       # Reddit via PRAW/async-praw
│       │   ├── github.py       # GitHub Issues API
│       │   ├── hackernews.py   # HN Algolia API (no key needed)
│       │   ├── reviews.py      # App/product reviews
│       │   └── trends.py       # Google Trends via pytrends
│       │
│       ├── processing/         # Data processing pipeline
│       │   ├── __init__.py
│       │   ├── cleaner.py      # Text cleaning, normalization
│       │   ├── deduplicator.py # Near-duplicate detection
│       │   ├── embedder.py     # Local embedding generation
│       │   └── extractor.py    # Problem extraction via LLM
│       │
│       ├── analysis/           # Analysis engines
│       │   ├── __init__.py
│       │   ├── clusterer.py    # Problem clustering
│       │   ├── scorer.py       # Deterministic opportunity scoring
│       │   └── confidence.py   # Evidence confidence calculator
│       │
│       ├── llm/                # LLM abstraction layer
│       │   ├── __init__.py
│       │   ├── client.py       # Ollama/OpenAI-compatible client
│       │   ├── router.py       # Model routing (small vs medium)
│       │   ├── prompts.py      # Prompt templates
│       │   └── schemas.py      # Pydantic output schemas
│       │
│       └── cli/                # CLI interface
│           ├── __init__.py
│           ├── collect.py      # Collection commands
│           ├── analyze.py      # Analysis commands
│           └── report.py       # Report generation
│
├── tests/
│   ├── conftest.py
│   ├── test_collectors/
│   ├── test_processing/
│   └── test_analysis/
│
└── research_eval/              # Evaluation data (your section 20)
    ├── good_cases/
    ├── bad_cases/
    ├── hallucinations/
    ├── missed_opportunities/
    └── false_opportunities/
```

---

### 2. Dependencies & Configuration

#### [NEW] [pyproject.toml](file:///d:/VMsProject/Creations/idea_hunter/pyproject.toml)

Core dependencies (minimal, no bloat):

| Category | Packages | Why |
|----------|----------|-----|
| **Framework** | `fastapi`, `uvicorn` | API layer (ready for Phase 2+ frontend) |
| **Database** | `sqlalchemy[asyncio]`, `asyncpg`, `alembic` | Async PostgreSQL ORM + migrations |
| **LLM** | `ollama`, `pydantic` | Local model client + structured output |
| **Embeddings** | `sentence-transformers` | Local embedding generation (CPU-friendly) |
| **Collectors** | `asyncpraw`, `httpx`, `pytrends`, `beautifulsoup4` | Source-specific data collection |
| **Processing** | `scikit-learn`, `numpy` | Clustering, dedup, similarity |
| **CLI** | `typer`, `rich` | Beautiful CLI interface |
| **Config** | `pydantic-settings`, `python-dotenv` | Type-safe configuration |
| **Testing** | `pytest`, `pytest-asyncio` | Test framework |

#### [NEW] [.env.template](file:///d:/VMsProject/Creations/idea_hunter/.env.template)

```env
# Database
DATABASE_URL=postgresql+asyncpg://ideahunter:ideahunter@localhost:5432/ideahunter

# LLM (Ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_SMALL=qwen2.5:3b
OLLAMA_MODEL_MEDIUM=phi3:mini
OLLAMA_EMBED_MODEL=nomic-embed-text

# Optional Cloud Fallback (leave empty to disable)
# CLOUD_API_KEY=
# CLOUD_API_MODEL=

# Collectors (add as needed)
# REDDIT_CLIENT_ID=
# REDDIT_CLIENT_SECRET=
# GITHUB_TOKEN=
```

---

### 3. PostgreSQL Schema

#### [NEW] [src/idea_hunter/db/models.py](file:///d:/VMsProject/Creations/idea_hunter/src/idea_hunter/db/models.py)

13 core tables implementing the schema from your architecture doc:

```mermaid
erDiagram
    sources ||--o{ observations : "collected_from"
    observations ||--o{ problem_evidence : "supports"
    problems ||--o{ problem_evidence : "evidenced_by"
    problems ||--o{ workarounds : "worked_around_by"
    problems }o--|| markets : "affects"
    companies ||--o{ products : "owns"
    products }o--|| markets : "operates_in"
    opportunities ||--o{ opportunity_scores : "scored_as"
    opportunities }o--|| problems : "addresses"
    research_runs ||--o{ observations : "produced"
```

**Key tables:**

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `sources` | Data source registry | `name`, `source_type`, `base_url`, `reliability_score` |
| `observations` | Raw evidence items | `raw_text`, `source_id`, `source_url`, `published_at`, `collected_at`, `engagement`, `topic`, `country`, `embedding` |
| `problems` | Extracted problems | `title`, `description`, `user_segment`, `industry`, `severity`, `frequency` |
| `problem_evidence` | Links problems ↔ observations | `problem_id`, `observation_id`, `evidence_strength`, `evidence_text` |
| `workarounds` | Manual workarounds people use | `problem_id`, `description`, `pain_level` |
| `companies` | Known companies/products | `name`, `website`, `industry` |
| `products` | Existing solutions | `company_id`, `name`, `category`, `strengths`, `weaknesses` |
| `markets` | Market definitions | `name`, `size_estimate`, `growth_rate` |
| `trends` | Trend signals | `keyword`, `direction`, `source`, `measured_at` |
| `opportunities` | Discovered opportunities | `problem_id`, `title`, `description`, `status` |
| `opportunity_scores` | Deterministic scores | `opportunity_id`, `pain_severity`, `frequency`, `growth`, `wtp`, `market_size`, `competition_gap`, `distribution`, `technical`, `final_score`, `evidence_confidence` |
| `research_runs` | Audit trail for collection runs | `source_type`, `query`, `started_at`, `completed_at`, `items_collected`, `status` |
| `experiments` | System evaluation tracking | `name`, `hypothesis`, `result`, `metrics_json` |

Every observation carries the **provenance record** you specified:
- `source`, `source_url`, `published_at`, `collected_at`, `author`, `raw_text`, `engagement`, `topic`, `country`

---

### 4. Data Collectors

#### [NEW] [src/idea_hunter/collectors/base.py](file:///d:/VMsProject/Creations/idea_hunter/src/idea_hunter/collectors/base.py)

Abstract base class that every collector implements:

```python
class BaseCollector(ABC):
    async def collect(self, query: str, limit: int) -> list[RawObservation]
    async def validate_credentials(self) -> bool
    def source_type(self) -> str
```

Every collector:
1. Creates a `research_run` record before starting
2. Yields `RawObservation` objects with full provenance
3. Deduplicates against existing observations (by URL hash)
4. Updates `research_run` with final counts on completion
5. Handles rate limiting and retries internally

#### [NEW] Collector implementations (build order):

| # | Collector | API / Method | Auth Required | Priority |
|---|-----------|-------------|---------------|----------|
| 1 | `hackernews.py` | HN Algolia API | ❌ No | 🔥 First (easiest, no auth) |
| 2 | `reddit.py` | Async PRAW | ✅ Yes | 🔥 High (richest complaint data) |
| 3 | `github.py` | GitHub REST API | ✅ Yes | 🔥 High (technical problems) |
| 4 | `trends.py` | pytrends | ❌ No | Medium |
| 5 | `reviews.py` | Web scraping | ❌ No | Medium |

---

### 5. Processing Pipeline

#### [NEW] [src/idea_hunter/processing/cleaner.py](file:///d:/VMsProject/Creations/idea_hunter/src/idea_hunter/processing/cleaner.py)

- Strip HTML, markdown artifacts, URLs
- Normalize whitespace, encoding
- Language detection (keep English only for Phase 1)
- Extract structured metadata (mentions of tools, companies, prices)

#### [NEW] [src/idea_hunter/processing/deduplicator.py](file:///d:/VMsProject/Creations/idea_hunter/src/idea_hunter/processing/deduplicator.py)

- URL-based exact dedup (fast, first pass)
- MinHash/LSH for near-duplicate detection on text content
- Configurable similarity threshold (default 0.85)

#### [NEW] [src/idea_hunter/processing/embedder.py](file:///d:/VMsProject/Creations/idea_hunter/src/idea_hunter/processing/embedder.py)

- Uses `nomic-embed-text` via Ollama (768-dim, CPU-friendly, ~275MB RAM)
- Batch embedding with progress tracking
- Stores embeddings in PostgreSQL `pgvector` column
- Fallback: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, ~90MB, even lighter)

#### [NEW] [src/idea_hunter/processing/extractor.py](file:///d:/VMsProject/Creations/idea_hunter/src/idea_hunter/processing/extractor.py)

The core problem extraction engine. Uses the 3B model with structured output:

```python
class ExtractedProblem(BaseModel):
    problem: str
    target_user: str
    context: str
    severity: int  # 1-10
    frequency: int  # 1-10
    workaround: str
    existing_solutions: list[str]
    evidence_ids: list[str]
    confidence: float  # 0-1
```

Key techniques to make the 3B model work:
1. **Few-shot examples** baked into every prompt
2. **Strict JSON output** via Ollama's JSON mode
3. **Single-task prompts** — one observation at a time, never batch analysis
4. **Classification before extraction** — small model classifies "is this a complaint?" before expensive extraction runs

---

### 6. LLM Abstraction Layer

#### [NEW] [src/idea_hunter/llm/client.py](file:///d:/VMsProject/Creations/idea_hunter/src/idea_hunter/llm/client.py)

Unified client wrapping Ollama's Python SDK:

```python
class LLMClient:
    async def generate(self, prompt: str, model: str = None, 
                       schema: Type[BaseModel] = None) -> str | BaseModel
    async def embed(self, texts: list[str]) -> list[list[float]]
    async def classify(self, text: str, labels: list[str]) -> str
```

#### [NEW] [src/idea_hunter/llm/router.py](file:///d:/VMsProject/Creations/idea_hunter/src/idea_hunter/llm/router.py)

Model router that selects model based on task complexity:

| Task | Model | Why |
|------|-------|-----|
| Classification (complaint? yes/no) | `qwen2.5:3b` | Simple binary task |
| Language detection | `qwen2.5:3b` | Pattern matching |
| Problem extraction | `phi3:mini` or `qwen2.5:3b` | Needs structured reasoning |
| Summarization | `qwen2.5:3b` | Can handle with good prompts |
| Query expansion | `qwen2.5:3b` | Simple rewriting |

On 8GB RAM, both models are in the 3B class so the "routing" is mainly about prompt complexity rather than model switching. When you upgrade hardware, the router becomes the swap point for 7B+ models.

---

### 7. Analysis Engines

#### [NEW] [src/idea_hunter/analysis/clusterer.py](file:///d:/VMsProject/Creations/idea_hunter/src/idea_hunter/analysis/clusterer.py)

Problem clustering using your exact approach:
1. Load all observation embeddings from PostgreSQL
2. Run HDBSCAN clustering (handles variable-density clusters better than K-means)
3. Select representative samples per cluster
4. Feed representatives to LLM for cluster labeling
5. Store labeled problem clusters back to `problems` table

This is **deterministic + LLM hybrid** — the clustering math is Python, only the labeling uses the model.

#### [NEW] [src/idea_hunter/analysis/scorer.py](file:///d:/VMsProject/Creations/idea_hunter/src/idea_hunter/analysis/scorer.py)

Your exact deterministic scoring formula:

```python
# Component weights (your Section 10)
WEIGHTS = {
    "pain_severity": 0.20,
    "problem_frequency": 0.15,
    "growth_trend": 0.15,
    "willingness_to_pay": 0.15,
    "market_size": 0.10,
    "competition_gap": 0.10,
    "distribution_feasibility": 0.10,
    "technical_feasibility": 0.05,
}

final_score = raw_opportunity_score * evidence_confidence * source_quality
```

**No LLM decides the final score.** Python does it.

#### [NEW] [src/idea_hunter/analysis/confidence.py](file:///d:/VMsProject/Creations/idea_hunter/src/idea_hunter/analysis/confidence.py)

Evidence confidence engine (your Section 11):

```python
class EvidenceConfidence:
    evidence_count: int
    source_diversity: float    # unique source types / total
    source_quality: float      # weighted by source reliability
    recency: float             # decay function on age
    independent_confirmation: int  # distinct independent sources
    contradictory_evidence: int
```

---

### 8. CLI Interface

#### [NEW] [src/idea_hunter/cli/](file:///d:/VMsProject/Creations/idea_hunter/src/idea_hunter/cli/)

Built with `typer` + `rich` for a professional terminal experience:

```bash
# Collect data
idea-hunter collect hackernews --query "frustrated with" --limit 500
idea-hunter collect reddit --subreddits "SaaS,startups,smallbusiness" --limit 1000
idea-hunter collect github --query "bug report" --repos "popular"

# Process collected data
idea-hunter process embed        # Generate embeddings for new observations
idea-hunter process extract      # Run problem extraction
idea-hunter process cluster      # Cluster problems
idea-hunter process dedup        # Remove near-duplicates

# Analyze
idea-hunter analyze score        # Score all opportunities
idea-hunter analyze top --limit 20  # Show top opportunities

# Reports
idea-hunter report problems      # List discovered problems
idea-hunter report opportunity <id>  # Deep dive on one opportunity  
idea-hunter report export --format json  # Export all data

# System
idea-hunter status               # Show DB stats, model status
idea-hunter run full             # Run full pipeline: collect → embed → extract → cluster → score
```

---

### 9. FastAPI Endpoints (Ready for Phase 2 Frontend)

#### [NEW] [src/idea_hunter/api/](file:///d:/VMsProject/Creations/idea_hunter/src/idea_hunter/api/)

Even though frontend is deferred, we build the API endpoints now so Phase 2 is just plugging in the dashboard:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/problems` | GET | List problems with filters |
| `/api/problems/{id}` | GET | Problem detail with evidence |
| `/api/opportunities` | GET | Ranked opportunity list |
| `/api/opportunities/{id}` | GET | Full opportunity dossier |
| `/api/research-runs` | GET | Collection history |
| `/api/stats` | GET | System statistics |
| `/api/collect` | POST | Trigger a collection run |
| `/api/analyze` | POST | Trigger analysis pipeline |

---

## Verification Plan

### Automated Tests

```bash
# Unit tests for each component
pytest tests/ -v

# Integration test: full pipeline on HN data
pytest tests/test_integration/ -v --timeout=120

# DB schema validation
alembic check
```

### Manual Verification

1. **Collector test**: Run HN collector with query "frustrated with invoicing", verify ≥10 observations stored with full provenance
2. **Embedding test**: Embed 100 observations, verify `pgvector` similarity search returns semantically relevant results
3. **Extraction test**: Feed 20 complaint observations through extractor, verify structured output matches schema
4. **Clustering test**: Cluster 500+ observations, verify clusters are semantically coherent
5. **Scoring test**: Score a known-good opportunity (e.g., "invoice reconciliation"), verify score components are reasonable
6. **Confidence test**: Verify that an opportunity backed by 30 sources from 4 independent source types scores higher confidence than one backed by 5 sources from 1 type

### Success Criteria for Phase 1

The system passes Phase 1 when you can:
1. ✅ Collect data from at least 2 sources
2. ✅ Generate embeddings and store them
3. ✅ Extract structured problems from raw observations
4. ✅ Cluster related observations into problem groups
5. ✅ Score opportunities deterministically
6. ✅ Answer: "Why did the system think this was a problem?" with evidence chain
7. ✅ Export results as JSON/CSV

---

## Build Order

| Step | Component | Est. Effort | Dependencies |
|------|-----------|-------------|--------------|
| 1 | Project skeleton + config | Small | None |
| 2 | Database schema + migrations | Small | PostgreSQL running |
| 3 | LLM client + model pull | Small | Ollama running |
| 4 | HN collector (no auth needed) | Small | Step 1-2 |
| 5 | Text cleaner + deduplicator | Small | Step 4 |
| 6 | Embedding pipeline | Medium | Step 3, pgvector |
| 7 | Problem extractor | Medium | Step 3, Step 6 |
| 8 | Reddit collector | Small | API keys |
| 9 | GitHub collector | Small | API token |
| 10 | Problem clusterer | Medium | Step 6 |
| 11 | Deterministic scorer | Small | Step 10 |
| 12 | Evidence confidence | Small | Step 11 |
| 13 | CLI interface | Medium | All above |
| 14 | FastAPI endpoints | Small | All above |
| 15 | Integration tests | Medium | All above |
