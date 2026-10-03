# =============================================================================
# run.ps1 -- Idea Hunter: One-Click Full Pipeline
# =============================================================================
# Usage:
#   .\run.ps1                                      (uses default queries)
#   .\run.ps1 -Queries "SaaS tools","remote work"  (custom queries)
#   .\run.ps1 -SkipCollect                          (skip data collection, use existing data)
#   .\run.ps1 -SkipDashboard                        (pipeline only, no browser UI)
# =============================================================================

param(
    [string[]]$Queries = @("I hate", "why is there no", "I wish there was", "annoying problem", "nobody solves"),
    [switch]$SkipCollect,
    [switch]$SkipDashboard
)

$ErrorActionPreference = "Continue"
$Python = ".venv\Scripts\python"

function Step($msg) {
    Write-Host ""
    Write-Host "--------------------------------------------------" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "--------------------------------------------------" -ForegroundColor Cyan
}

function Run([string[]]$cmdArgs) {
    $display = $cmdArgs -join ' '
    Write-Host "> $display" -ForegroundColor DarkGray
    & $cmdArgs[0] $cmdArgs[1..($cmdArgs.Length - 1)]
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        Write-Host "[WARN] Command exited with code $LASTEXITCODE -- continuing..." -ForegroundColor Yellow
    }
}

function Test-LocalPort([int]$Port) {
    return $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1)
}

function Start-DashboardServices {
    if (Test-LocalPort 8000) {
        Write-Host "  -> FastAPI backend already running on http://localhost:8000" -ForegroundColor DarkGray
    } else {
        Write-Host "  -> Starting FastAPI backend on http://localhost:8000" -ForegroundColor DarkGray
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$PWD`"; .venv\Scripts\python -m uvicorn idea_hunter.api.main:app --reload --port 8000" -WindowStyle Normal
        Start-Sleep -Seconds 2
    }

    if (Test-LocalPort 5173) {
        Write-Host "  -> Dashboard already running on http://localhost:5173" -ForegroundColor DarkGray
    } else {
        Write-Host "  -> Starting Dashboard on http://localhost:5173" -ForegroundColor DarkGray
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$PWD\dashboard-v2`"; npm run dev" -WindowStyle Normal
        Start-Sleep -Seconds 3
    }

    Start-Process "http://localhost:5173"
}

Write-Host ""
Write-Host "IDEA HUNTER -- Full Pipeline Starting" -ForegroundColor Green
Write-Host "    $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray

if (-not $SkipDashboard) {
    Write-Host ""
    Write-Host "Launching live pipeline dashboard..." -ForegroundColor Magenta
    Start-DashboardServices
}

# Keep the live database schema aligned with the checked-in SQLAlchemy models
# before any collector or pipeline stage queries Source/Observation records.
Step "SCHEMA PREFLIGHT -- Applying database migrations"
Run @(".venv\Scripts\alembic", "upgrade", "heads")

# -- STEP 1: Collect ----------------------------------------------------------
if (-not $SkipCollect) {
    Step "STEP 1/8 -- Collecting Data from HackerNews"
    foreach ($q in $Queries) {
        Write-Host "  Querying: '$q'" -ForegroundColor White
        Run @($Python, "-m", "idea_hunter.cli.main", "collect", "hackernews", "--query", $q, "--limit", "100")
    }

    Step "STEP 1B -- Collecting Data from Enabled Public/API Sources"
    Write-Host "  Collecting DEV.to articles..." -ForegroundColor White
    Run @($Python, "-m", "idea_hunter.cli.main", "collect", "source", "--source", "devto", "--query", "saas", "--limit", "50")

    $envFile = if (Test-Path ".env") { Get-Content ".env" -Raw } else { "" }
    $redditConfigured = $envFile -match '(?m)^REDDIT_CLIENT_ID=.+\S' -and $envFile -match '(?m)^REDDIT_CLIENT_SECRET=.+\S'
    if ($redditConfigured) {
        Write-Host "  Collecting Reddit community signals..." -ForegroundColor White
        foreach ($q in $Queries) {
            Run @($Python, "-m", "idea_hunter.cli.main", "collect", "reddit", "--query", "$q | SaaS,startups,Entrepreneur", "--limit", "25")
        }
    } else {
        Write-Host "  [SKIP] Reddit collector disabled: credentials are not configured." -ForegroundColor Yellow
    }

    $productHuntConfigured = $envFile -match '(?m)^PRODUCT_HUNT_TOKEN=.+\S'
    if ($productHuntConfigured) {
        Write-Host "  Collecting Product Hunt product signals..." -ForegroundColor White
        Run @($Python, "-m", "idea_hunter.cli.main", "collect", "source", "--source", "producthunt", "--query", "startup products", "--limit", "25")
    } else {
        Write-Host "  [SKIP] Product Hunt collector disabled: PRODUCT_HUNT_TOKEN is not configured." -ForegroundColor Yellow
    }
} else {
    Write-Host "[SKIP] Data collection skipped (using existing observations)" -ForegroundColor Yellow
}

# -- STEP 2: Embed ------------------------------------------------------------
Step "STEP 2/8 -- Triage Signals (pain/workaround/WTP/contradiction/noise)"
Run @($Python, "-m", "idea_hunter.cli.main", "process", "triage")

# -- STEP 3: Embed ------------------------------------------------------------
Step "STEP 3/8 -- Embed Accepted Observations"
Run @($Python, "-m", "idea_hunter.cli.main", "process", "embed")

# -- STEP 4: Cluster ----------------------------------------------------------
Step "STEP 4/8 -- Clustering Similar Problems"
Run @($Python, "-m", "idea_hunter.cli.main", "process", "cluster")

# -- STEP 5: Extract ----------------------------------------------------------
Step "STEP 5/8 -- Extracting Structured Problems from Eligible Clusters"
Run @($Python, "-m", "idea_hunter.cli.main", "process", "extract", "--limit", "2")

# -- STEP 6: Research ---------------------------------------------------------
Step "STEP 6/8 -- Verify + Deep Research (Bull/Bear/Market Intelligence)"
Run @($Python, "-m", "idea_hunter.cli.main", "process", "verify")
Run @($Python, "-m", "idea_hunter.cli.main", "analyze", "research", "--limit", "1")
Run @($Python, "-m", "idea_hunter.cli.main", "analyze", "path-b")

# -- STEP 7: Score ------------------------------------------------------------
Step "STEP 7/8 -- Potential, Confidence, Freshness, and Next Step"
Run @($Python, "-m", "idea_hunter.cli.main", "analyze", "score")

# -- STEP 8: Report -----------------------------------------------------------
Step "STEP 8/8 -- Generating Opportunity Report"
Run @($Python, "-m", "idea_hunter.cli.main", "output", "report")

Write-Host ""
Write-Host "[DONE] Pipeline complete! Report saved to: opportunity_report.md" -ForegroundColor Green

if (-not $SkipDashboard) {
    Write-Host "    Dashboard  -> http://localhost:5173" -ForegroundColor White
    Write-Host "    API Docs   -> http://localhost:8000/docs" -ForegroundColor White
}
