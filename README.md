# Idea Hunter

Idea Hunter is an evidence-first opportunity research engine. It collects
signals, preserves rejected and contradictory evidence, clusters recurring
problems, creates quote-verifiable claims, and separates opportunity
Potential, evidence Confidence, and Freshness.

## Local stack

```powershell
Copy-Item .env.template .env
docker compose up --build
```

The API is available at `http://localhost:8000`, with the redesigned API at
`/api/v1`. Run `alembic upgrade head` before using the CLI outside Docker.

The active frontend is `dashboard-v2/`:

```powershell
cd dashboard-v2
npm install
npm run dev
```

## Pipeline concepts

1. Collect with a cursor per source query.
2. Normalize and deduplicate using normalized-text hashes.
3. Triage signals as pain, workaround, willingness-to-pay, contradiction, or
   noise without deleting rejected records.
4. Embed and cluster with durable state.
5. Apply deterministic evidence gates before hosted-model spend.
6. Store claims with source quotes and quote verification.
7. Score Potential, Confidence, and Freshness separately and recommend one
   next action.
