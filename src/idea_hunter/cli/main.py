import typer
import asyncio
import sys
from rich.console import Console
from rich.progress import track
from sqlalchemy import select, func
from idea_hunter.collectors.hackernews import HackerNewsCollector
from idea_hunter.collectors.reddit import RedditCollector
from idea_hunter.collectors.github import GitHubCollector
from idea_hunter.collectors.reviews import PlayStoreReviewsCollector
from idea_hunter.collectors.discovery import get_collector
from idea_hunter.collectors.source_catalog import SOURCES, get_source
from idea_hunter.collectors.manual_import import iter_manual_observations
from idea_hunter.db.session import session_scope
from idea_hunter.db.models import Source, Observation, Problem, ProblemEvidence, Opportunity, OpportunityScore, ExistingSolution, ResearchRun, CostLog, ProblemResearch, Trend, HardProblem, TechShift
from idea_hunter.application.services.ingestion import get_or_create_source_query, mark_source_query_success, normalized_content_hash
from idea_hunter.application.services.triage import TRIAGE_TYPES, heuristic_triage
from idea_hunter.config import settings
from idea_hunter.processing.extractor import ProblemExtractor
from idea_hunter.processing.cleaner import TextCleaner
from idea_hunter.processing.prefilter import prefilter
from idea_hunter.processing.embedder import Embedder
from idea_hunter.analysis.clusterer import ProblemClusterer
from idea_hunter.analysis.scorer import EvidenceScorer
from idea_hunter.output.report_generator import MarkdownReportGenerator
from idea_hunter.processing.verifier import ProblemVerifier
from idea_hunter.processing.researcher import research_problem, research_priority
from idea_hunter.llm.router import model_router
from sqlalchemy.dialects.postgresql import insert

# HN/Reddit/review text can contain characters outside the Windows legacy
# console code page. Keep Rich output from aborting an otherwise valid run.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(help="Idea Hunter: Local Opportunity Intelligence Engine")
collect_app = typer.Typer(help="Collect data from sources")
process_app = typer.Typer(help="Process collected data")
analyze_app = typer.Typer(help="Analyze and score opportunities")
output_app = typer.Typer(help="Generate outputs and reports")

app.add_typer(collect_app, name="collect")
app.add_typer(process_app, name="process")
app.add_typer(analyze_app, name="analyze")
app.add_typer(output_app, name="output")

console = Console()

def run_async(coro):
    return asyncio.run(coro)

@collect_app.command("hackernews")
def collect_hn(
    query: str = typer.Option(..., help="Search query to collect"), 
    limit: int = typer.Option(100, help="Number of items to collect")
):
    """Collect problem observations from HackerNews."""
    console.print(f"Collecting up to {limit} items from HackerNews for query: '{query}'...")
    collector = HackerNewsCollector()
    
    async def _run():
        count = 0
        async with session_scope() as session:
            # Ensure Source exists
            stmt = select(Source).where(Source.source_type == "hackernews")
            result = await session.execute(stmt)
            source = result.scalar_one_or_none()
            if not source:
                source = Source(name="HackerNews", source_type="hackernews", base_url="https://news.ycombinator.com")
                session.add(source)
                await session.flush()
                
            run = ResearchRun(source_type="hackernews", query=query)
            session.add(run)
            await session.flush()
                
            source_query = await get_or_create_source_query(session, source_id=source.id, query=query)
            async for obs in collector.collect(query=query, limit=limit, since_cursor=source_query.last_seen_cursor):
                clean_text = TextCleaner.process(obs.raw_text)
                if not clean_text:
                    continue
                    
                # Run pre-filter (zero LLM cost)
                pf_result = prefilter(clean_text, engagement=obs.engagement or 0)
                
                if pf_result.passed:
                    console.print(f"[green]Passed ({pf_result.score}):[/green] {clean_text[:80]}...")
                else:
                    console.print(f"[dim]Filtered ({pf_result.reason}):[/dim] {clean_text[:80]}...")
                
                # Use PostgreSQL ON CONFLICT DO NOTHING for deduplication
                stmt = insert(Observation).values(
                    raw_text=clean_text,
                    content_hash=normalized_content_hash(clean_text),
                    normalized_text=clean_text,
                    source_id=source.id,
                    source_url=obs.source_url,
                    published_at=obs.published_at,
                    author=obs.author,
                    engagement=obs.engagement,
                    topic=obs.topic,
                    passed_prefilter=pf_result.passed
                ).on_conflict_do_nothing(index_elements=['content_hash'])
                
                await session.execute(stmt)
                
                if obs.cursor_value:
                    mark_source_query_success(source_query, obs.cursor_value)
                    
                count += 1
                
            run.items_collected = count
            run.status = "completed"
            run.completed_at = func.now()
                
        console.print(f"\n[bold]Saved {count} observations to database.[/bold]")
        
    run_async(_run())

@collect_app.command("reviews")
def collect_reviews(
    query: str = typer.Option(..., help="App category or search query (e.g., 'productivity', 'finance')"), 
    limit: int = typer.Option(100, help="Number of items to collect")
):
    """Collect problem observations from Play Store reviews."""
    console.print(f"Collecting up to {limit} reviews for apps matching: '{query}'...")
    collector = PlayStoreReviewsCollector()
    
    async def _run():
        count = 0
        async with session_scope() as session:
            stmt = select(Source).where(Source.source_type == "playstore_reviews")
            result = await session.execute(stmt)
            source = result.scalar_one_or_none()
            if not source:
                source = Source(name="Play Store Reviews", source_type="playstore_reviews", base_url="https://play.google.com/store")
                session.add(source)
                await session.flush()
                
            run = ResearchRun(source_type="playstore_reviews", query=query)
            session.add(run)
            await session.flush()
                
            source_query = await get_or_create_source_query(session, source_id=source.id, query=query)
            async for obs in collector.collect(query=query, limit=limit, since_cursor=source_query.last_seen_cursor):
                clean_text = TextCleaner.process(obs.raw_text)
                if not clean_text:
                    continue
                    
                pf_result = prefilter(clean_text, engagement=obs.engagement or 0)
                
                if pf_result.passed:
                    console.print(f"[green]Passed ({pf_result.score}):[/green] {clean_text[:80]}...")
                else:
                    console.print(f"[dim]Filtered ({pf_result.reason}):[/dim] {clean_text[:80]}...")
                
                stmt_insert = insert(Observation).values(
                    raw_text=clean_text,
                    content_hash=normalized_content_hash(clean_text),
                    normalized_text=clean_text,
                    source_id=source.id,
                    source_url=obs.source_url,
                    published_at=obs.published_at,
                    author=obs.author,
                    engagement=obs.engagement,
                    topic=obs.topic,
                    passed_prefilter=pf_result.passed
                ).on_conflict_do_nothing(index_elements=['content_hash'])
                
                await session.execute(stmt_insert)
                
                if obs.cursor_value:
                    mark_source_query_success(source_query, obs.cursor_value)
                    
                count += 1
                
            run.items_collected = count
            run.status = "completed"
            run.completed_at = func.now()
                
        console.print(f"\n[bold]Saved {count} observations to database.[/bold]")
        
    run_async(_run())

@collect_app.command("reddit")
def collect_reddit(
    query: str = typer.Option(..., help="Search query (format: 'query | sub1,sub2')"), 
    limit: int = typer.Option(100, help="Number of items to collect")
):
    """Collect problem observations from Reddit."""
    console.print(f"Collecting up to {limit} items from Reddit for query: '{query}'...")
    collector = RedditCollector()
    
    async def _run():
        count = 0
        async with session_scope() as session:
            # Ensure Source exists
            stmt = select(Source).where(Source.source_type == "reddit")
            result = await session.execute(stmt)
            source = result.scalar_one_or_none()
            if not source:
                source = Source(name="Reddit", source_type="reddit", base_url="https://reddit.com")
                session.add(source)
                await session.flush()
                
            run = ResearchRun(source_type="reddit", query=query)
            session.add(run)
            await session.flush()
            source_query = await get_or_create_source_query(session, source_id=source.id, query=query)
            async for obs in collector.collect(query=query, limit=limit):
                clean_text = TextCleaner.process(obs.raw_text)
                if not clean_text:
                    continue
                    
                # Run pre-filter (zero LLM cost)
                pf_result = prefilter(clean_text, engagement=obs.engagement or 0)
                
                if pf_result.passed:
                    console.print(f"[green]Passed ({pf_result.score}):[/green] {clean_text[:80]}...")
                else:
                    console.print(f"[dim]Filtered ({pf_result.reason}):[/dim] {clean_text[:80]}...")
                
                # Use PostgreSQL ON CONFLICT DO NOTHING for deduplication
                stmt_insert = insert(Observation).values(
                    raw_text=clean_text,
                    normalized_text=clean_text,
                    content_hash=normalized_content_hash(clean_text),
                    source_id=source.id,
                    source_url=obs.source_url,
                    published_at=obs.published_at,
                    author=obs.author,
                    engagement=obs.engagement,
                    topic=obs.topic,
                    passed_prefilter=pf_result.passed
                ).on_conflict_do_nothing(index_elements=['content_hash'])
                
                await session.execute(stmt_insert)
                
                count += 1
            mark_source_query_success(source_query)
                
            run.items_collected = count
            run.status = "completed"
            run.completed_at = func.now()
                
        console.print(f"\n[bold]Saved {count} observations to database.[/bold]")
        
    run_async(_run())


@process_app.command("triage")
def triage_observations(
    limit: int = typer.Option(500, help="Maximum untriaged observations to label"),
    use_local_model: bool = typer.Option(True, help="Use Ollama first; fall back to deterministic triage on failure"),
):
    """Label signals without discarding them: pain, workaround, WTP, contradiction, or noise."""
    console.print(f"Triaging up to {limit} observations...")

    async def _run():
        async with session_scope() as session:
            observations = (await session.execute(
                select(Observation).where(Observation.triage_state == "pending").limit(limit)
            )).scalars().all()
            for observation in observations:
                text = observation.normalized_text or observation.raw_text
                result = heuristic_triage(text)
                if use_local_model:
                    try:
                        model_result = await model_router.triage_signal(text)
                        if model_result.signal_type in TRIAGE_TYPES:
                            result = type(result)(model_result.signal_type, model_result.confidence, model_result.rationale)
                    except Exception as error:
                        console.print(f"[dim]Local triage fallback: {error}[/dim]")
                observation.signal_type = result.signal_type
                observation.triage_state = "rejected" if result.signal_type == "noise" else "accepted"
                # Existing embedding queries use passed_prefilter. Preserve the
                # storage column while changing its meaning from keyword gate
                # to an explicit triage outcome.
                observation.passed_prefilter = result.signal_type != "noise"
            console.print(f"[bold green]Triaged {len(observations)} observations.[/bold green]")

    run_async(_run())

@process_app.command("embed")
def embed_observations(limit: int = typer.Option(500, help="Number of observations to embed")):
    """Run local Ollama embeddings on un-embedded observations that passed the pre-filter."""
    console.print(f"Starting embedding pipeline for up to {limit} observations...")
    embedder = Embedder()
    
    async def _run():
        async with session_scope() as session:
            stmt = select(Observation).where(Observation.passed_prefilter == True, Observation.embedding.is_(None)).limit(limit)
            result = await session.execute(stmt)
            observations = result.scalars().all()
            
            if not observations:
                console.print("No new observations to embed.")
                return
                
            console.print(f"Embedding {len(observations)} observations in chunks...")
            chunk_size = 10
            embedded_count = 0
            
            for i in range(0, len(observations), chunk_size):
                chunk_obs = observations[i:i + chunk_size]
                texts = [obs.raw_text for obs in chunk_obs]
                
                # Process this chunk
                embeddings = await embedder.embed_batch(texts)
                
                for obs, emb in zip(chunk_obs, embeddings):
                    obs.embedding_attempts = (obs.embedding_attempts or 0) + 1
                    if emb:
                        obs.embedding = emb
                        obs.embedding_model = settings.ollama_embed_model
                        obs.embedding_dimension = len(emb)
                        obs.embedding_state = "completed"
                    else:
                        obs.embedding_state = "failed"
                    
                await session.flush()
                embedded_count += sum(1 for embedding in embeddings if embedding)
                console.print(f"Embedded {embedded_count}/{len(observations)}...")
                
            console.print(f"[bold green]Successfully embedded {embedded_count} items.[/bold green]")
            
    run_async(_run())

@process_app.command("cluster")
def cluster_observations():
    """Cluster all embedded observations that haven't been clustered yet."""
    console.print("Starting HDBSCAN clustering on un-clustered observations...")
    clusterer = ProblemClusterer(min_cluster_size=2)
    
    async def _run():
        async with session_scope() as session:
            stmt = select(Observation).where(Observation.embedding.is_not(None), Observation.cluster_id.is_(None))
            result = await session.execute(stmt)
            observations = result.scalars().all()
            
            if not observations:
                console.print("No new observations to cluster.")
                return
                
            console.print(f"Checking {len(observations)} observations against existing clusters...")
            
            # Step 1: PGVector merging
            merged_count = 0
            unmerged_observations = []
            existing_stmt = select(Observation.cluster_id, Observation.embedding).where(
                Observation.cluster_id.is_not(None)
            )
            existing_clusters = (await session.execute(existing_stmt)).all()
            
            for obs in observations:
                # Compare in Python so this works with both legacy JSON and
                # pgvector-backed embedding columns.
                nn_row = min(
                    existing_clusters,
                    key=lambda candidate: clusterer.cosine_distance(obs.embedding, candidate.embedding),
                    default=None,
                )
                distance = (
                    clusterer.cosine_distance(obs.embedding, nn_row.embedding)
                    if nn_row else None
                )
                
                if nn_row and distance < 0.2: # 0.2 is the cosine distance threshold (higher similarity)
                    obs.cluster_id = nn_row.cluster_id
                    merged_count += 1
                    
                    # Log trend velocity if we merge
                    trend = Trend(
                        keyword=f"Cluster {nn_row.cluster_id}",
                        direction="Growing",
                        source="vector_merge"
                    )
                    session.add(trend)
                else:
                    unmerged_observations.append(obs)
            
            console.print(f"Merged {merged_count} observations into existing clusters.")
            
            if not unmerged_observations:
                await session.flush()
                return

            console.print(f"Running HDBSCAN on remaining {len(unmerged_observations)} observations...")
            embeddings = [obs.embedding for obs in unmerged_observations]
            
            result = clusterer.cluster(embeddings)
            labels = result["labels"]
            
            # Find the max cluster ID currently in the DB so we don't overlap
            max_cluster_stmt = select(func.max(Observation.cluster_id))
            max_res = await session.execute(max_cluster_stmt)
            max_id = max_res.scalar_one_or_none() or 0
            
            clustered_count = 0
            singleton_count = 0
            
            # Find the max label from valid clusters
            valid_labels = [l for l in labels if l != -1]
            max_assigned_label = max(valid_labels) if valid_labels else -1
            
            # We will use this to assign singletons their own cluster ID
            current_cluster_offset = max_id + max_assigned_label + 1
            
            for obs, label in zip(unmerged_observations, labels):
                if label != -1: # -1 is noise in HDBSCAN
                    obs.cluster_id = max_id + label + 1
                    clustered_count += 1
                else:
                    # Treat noise as a singleton cluster
                    current_cluster_offset += 1
                    obs.cluster_id = current_cluster_offset
                    singleton_count += 1
                    
            console.print(f"[bold green]Successfully grouped {clustered_count} items into new clusters, kept {singleton_count} singletons.[/bold green]")
            
    run_async(_run())

@process_app.command("extract")
def extract_problems(limit: int = typer.Option(None, help="Number of clusters to process")):
    """Run LLM problem extraction on un-extracted clusters."""
    limit = limit or settings.extraction_clusters_per_run
    console.print(f"Starting extraction pipeline for up to {limit} clusters...")
    
    extractor = ProblemExtractor()
    
    async def _run():
        async with session_scope() as session:
            # Find cluster_ids that have no ProblemEvidence yet (and aren't noise: > 0)
            subq = select(Observation.cluster_id).join(ProblemEvidence, Observation.id == ProblemEvidence.observation_id)
            stmt = select(Observation.cluster_id).where(Observation.cluster_id > 0).where(Observation.cluster_id.notin_(subq)).distinct().limit(limit)
            result = await session.execute(stmt)
            cluster_ids = result.scalars().all()
            
            if not cluster_ids:
                console.print("No new clusters to process.")
                return
                
            # Check budget
            cost_stmt = select(func.sum(CostLog.cost_usd))
            total_cost_res = await session.execute(cost_stmt)
            total_cost = total_cost_res.scalar_one_or_none() or 0.0
            
            if total_cost >= settings.max_cost_per_run_usd:
                console.print(f"[red]Budget exceeded![/red] Total cost: ${total_cost:.4f} >= ${settings.max_cost_per_run_usd:.2f}")
                return
                
            run = ResearchRun(source_type="extract", query=f"Processing {len(cluster_ids)} clusters")
            session.add(run)
            await session.commit()
            run_id = run.id
                
            console.print(f"Processing {len(cluster_ids)} clusters...")
            extracted_count = 0
            
            for cid in track(cluster_ids, description="Extracting problems..."):
                try:
                    obs_stmt = select(Observation).where(Observation.cluster_id == cid)
                    obs_res = await session.execute(obs_stmt)
                    cluster_obs = obs_res.scalars().all()
                    
                    texts = [obs.raw_text for obs in cluster_obs]
                    
                    # LLM magic across the whole cluster!
                    result, competition = await extractor.process_cluster(texts, run_id=run_id)
                    
                    if result:
                        console.print(f"\n[bold green]Found Problem![/bold green] {result.problem} (Severity: {result.severity}/10)")
                        console.print(f"  Target: {result.target_user} | Workaround: {result.workaround}")
                        
                        is_singleton = len(cluster_obs) == 1
                        problem = Problem(
                            title=result.problem,
                            description=result.context,
                            user_segment=result.target_user,
                            severity=result.severity,
                            frequency=result.frequency,
                            workaround=result.workaround,
                            devils_advocate_notes=result.devils_advocate_notes,
                            signal_type="singleton" if is_singleton else "cluster"
                        )
                        session.add(problem)
                        await session.flush()
                        
                        for obs in cluster_obs:
                            evidence = ProblemEvidence(
                                problem_id=problem.id,
                                observation_id=obs.id,
                                evidence_strength=0.3 if is_singleton else result.confidence,
                                evidence_text=obs.raw_text[:500]
                            )
                            session.add(evidence)
                            
                        if competition:
                            for competitor in competition.competitors:
                                sol = ExistingSolution(
                                    problem_id=problem.id,
                                    name=competitor.name,
                                    url=competitor.url,
                                    gap_notes=(
                                        f"Gap: {competition.market_gap}\n"
                                        f"Why they fail: {competition.why_they_fail}\n"
                                        f"Pricing: {competitor.pricing_tier}\n"
                                        f"Customers: {competitor.estimated_customers}\n"
                                        f"Weaknesses: {competitor.weaknesses}"
                                    )
                                )
                                session.add(sol)
                        else:
                            for sol_name in result.existing_solutions:
                                sol = ExistingSolution(
                                    problem_id=problem.id,
                                    name=sol_name
                                )
                                session.add(sol)
                            
                        extracted_count += 1
                except Exception as e:
                    console.print(f"[red]Error extracting from cluster {cid}: {e}[/red]")
                    
            run.items_collected = extracted_count
            run.status = "completed"
            run.completed_at = func.now()
            
            rc_stmt = select(func.sum(CostLog.cost_usd)).where(CostLog.run_id == run_id)
            rc_res = await session.execute(rc_stmt)
            run.total_cost_usd = rc_res.scalar_one_or_none() or 0.0
                    
        console.print(f"\n[bold]Extraction complete. Found {extracted_count} problems.[/bold]")
        
    run_async(_run())

@process_app.command("verify")
def verify_problems(
    retry_flagged: bool = typer.Option(False, help="Re-evaluate problems flagged by the previous verifier."),
):
    """Verify extracted problems before they are scored."""
    console.print("Running verification checks on extracted problems...")
    
    async def _run():
        async with session_scope() as session:
            statuses = ["new", "needs_evidence"] + (["flagged"] if retry_flagged else [])
            stmt = select(Problem).where(Problem.verified == False, Problem.status.in_(statuses))
            result = await session.execute(stmt)
            problems = result.scalars().all()
            
            if not problems:
                console.print("No unverified problems found.")
                return
                
            verified_count = 0
            needs_evidence_count = 0
            rejected_count = 0
            
            for prob in problems:
                result = await ProblemVerifier.verify(session, prob.id)
                prob.verification_attempts = (prob.verification_attempts or 0) + 1
                prob.verification_reason = result.reason
                prob.verification_details = result.details
                if result.verified:
                    prob.verified = True
                    prob.status = "verified"
                    verified_count += 1
                elif result.reason in {"missing_problem"}:
                    prob.status = "rejected"
                    rejected_count += 1
                else:
                    prob.status = "needs_evidence"
                    needs_evidence_count += 1
                    
            await session.flush()
            console.print(f"Verified {verified_count} problems. Needs evidence: {needs_evidence_count}. Rejected: {rejected_count}.")
            
    run_async(_run())

@analyze_app.command("research")
def research_problems(
    limit: int = typer.Option(None, help="Number of highest-priority candidates to research"),
    include_needs_evidence: bool = typer.Option(True, help="Research promising candidates that still need corroboration."),
):
    """Research the strongest evidence-backed candidates, not only fully verified ones."""
    limit = limit or settings.research_problems_per_run
    console.print(f"Starting Phase 2 Research Pipeline for up to {limit} problems...")
    
    async def _run():
        async with session_scope() as session:
            # Check budget first
            cost_stmt = select(func.sum(CostLog.cost_usd))
            total_cost_res = await session.execute(cost_stmt)
            total_cost = total_cost_res.scalar_one_or_none() or 0.0
            
            if total_cost >= settings.max_cost_per_run_usd:
                console.print(f"[red]Budget exceeded![/red] Total cost: ${total_cost:.4f} >= ${settings.max_cost_per_run_usd:.2f}")
                return
            
            # A candidate can be worth researching before it is fully proven.
            # Research creates a validation brief; verification still controls
            # how much confidence users should place in the result.
            eligible_statuses = ["verified"]
            if include_needs_evidence:
                eligible_statuses.append("needs_evidence")
            stmt = (
                select(Problem)
                .outerjoin(ProblemResearch)
                .where(ProblemResearch.id == None, Problem.status.in_(eligible_statuses))
            )
            result = await session.execute(stmt)
            problems = sorted(result.scalars().all(), key=research_priority, reverse=True)[:limit]
            
            if not problems:
                console.print("No eligible un-researched candidates found.")
                return
                
            run = ResearchRun(source_type="research", query=f"Researching {len(problems)} problems")
            session.add(run)
            await session.commit()
            run_id = run.id
                
            console.print(f"Researching {len(problems)} problems...")
            researched_count = 0
            
            for prob in track(problems, description="Researching..."):
                try:
                    console.print(f"[dim]Priority {research_priority(prob):.2f} | status: {prob.status}[/dim]")
                    res = await research_problem(session, prob, run_id=run_id)
                    if res:
                        researched_count += 1
                except Exception as e:
                    console.print(f"[red]Error researching problem {prob.id}: {e}[/red]")
                    
            run.items_collected = researched_count
            run.status = "completed"
            run.completed_at = func.now()
            
            rc_stmt = select(func.sum(CostLog.cost_usd)).where(CostLog.run_id == run_id)
            rc_res = await session.execute(rc_stmt)
            run.total_cost_usd = rc_res.scalar_one_or_none() or 0.0
                    
        console.print(f"\n[bold]Research complete. Generated {researched_count} intel reports.[/bold]")
        
    run_async(_run())

@analyze_app.command("path-b")
def path_b_discovery():
    """Run Path B discovery: Old Problems + New Tech Shifts."""
    console.print("Starting Path B Discovery Pipeline...")
    
    async def _run():
        async with session_scope() as session:
            hp_stmt = select(HardProblem)
            hp_res = await session.execute(hp_stmt)
            hard_problems = hp_res.scalars().all()
            
            ts_stmt = select(TechShift)
            ts_res = await session.execute(ts_stmt)
            tech_shifts = ts_res.scalars().all()
            
            if not hard_problems or not tech_shifts:
                console.print("[yellow]Skipping Path B: Need at least one HardProblem and one TechShift in DB.[/yellow]")
                return
                
            shift_names = [ts.name for ts in tech_shifts]
            
            run = ResearchRun(source_type="path_b", query=f"Evaluating {len(hard_problems)} hard problems")
            session.add(run)
            await session.commit()
            run_id = run.id
            
            console.print(f"Evaluating {len(hard_problems)} hard problems against {len(shift_names)} tech shifts...")
            found_count = 0
            
            for hp in track(hard_problems, description="Evaluating..."):
                try:
                    res = await model_router.analyze_path_b(hp.title, hp.description, shift_names, run_id=run_id)
                    
                    if res.opportunity_found and res.confidence_score > 0.6:
                        console.print(f"\n[bold green]Path B Opportunity Found![/bold green] {res.synthesis_title}")
                        console.print(f"  Why Now: {res.why_now}")
                        
                        # Create synthetic Problem and ProblemResearch
                        problem = Problem(
                            title=res.synthesis_title,
                            description=res.synthesis_description,
                            industry=hp.industry,
                            severity=8, # Hard problems are painful by definition
                            frequency=5,
                            verified=True,
                            signal_type="path_b"
                        )
                        session.add(problem)
                        await session.flush()
                        
                        pr = ProblemResearch(
                            problem_id=problem.id,
                            why_now={"triggers": shift_names, "explanation": res.why_now, "score": res.confidence_score},
                            bull_case=f"Solves {hp.title} which has been unsolved for years due to technological limitations.",
                            debate_verdict="BUILD"
                        )
                        session.add(pr)
                        found_count += 1
                        
                except Exception as e:
                    console.print(f"[red]Error evaluating hard problem {hp.id}: {e}[/red]")
                    
            run.items_collected = found_count
            run.status = "completed"
            run.completed_at = func.now()
            
            rc_stmt = select(func.sum(CostLog.cost_usd)).where(CostLog.run_id == run_id)
            rc_res = await session.execute(rc_stmt)
            run.total_cost_usd = rc_res.scalar_one_or_none() or 0.0
            
            console.print(f"\n[bold]Path B complete. Generated {found_count} compound opportunities.[/bold]")
            
    run_async(_run())

@analyze_app.command("score")
def score_opportunities():
    """Score extracted problems and create opportunities."""
    console.print("Scoring extracted problems...")
    
    async def _run():
        async with session_scope() as session:
            # Scores are versioned and recalculated in place. This keeps a
            # rerun idempotent instead of creating another opportunity row.
            stmt = select(Problem).join(ProblemResearch)
            result = await session.execute(stmt)
            problems = result.scalars().all()
            
            if not problems:
                console.print("No un-scored problems found.")
                return
                
            console.print(f"Scoring {len(problems)} new problems...")
            
            scored_count = 0
            for prob in problems:
                # 1. Fetch ProblemResearch
                pr_stmt = select(ProblemResearch).where(ProblemResearch.problem_id == prob.id)
                pr_res = await session.execute(pr_stmt)
                research = pr_res.scalar_one_or_none()
                
                # 2. Fetch all related observations
                obs_stmt = (
                    select(Observation, Source.source_type)
                    .join(ProblemEvidence, Observation.id == ProblemEvidence.observation_id)
                    .join(Source, Observation.source_id == Source.id)
                    .where(ProblemEvidence.problem_id == prob.id)
                )
                obs_result = await session.execute(obs_stmt)
                obs_list = []
                for observation, source_type in obs_result.all():
                    # Avoid async lazy-loading Observation.source inside the
                    # synchronous scoring function.
                    observation._source_type = source_type
                    obs_list.append(observation)
                
                # Fetch existing solutions count
                sol_stmt = select(func.count(ExistingSolution.id)).where(ExistingSolution.problem_id == prob.id)
                sol_result = await session.execute(sol_stmt)
                sol_count = sol_result.scalar_one_or_none() or 0
                
                # 3. Score
                score_dict = EvidenceScorer.score(prob, research, obs_list, sol_count)
                
                opp = await session.scalar(select(Opportunity).where(Opportunity.problem_id == prob.id))
                if not opp:
                    opp = Opportunity(
                        problem_id=prob.id,
                        title=f"Opportunity: {prob.title}",
                        description=prob.description,
                    )
                    session.add(opp)
                    await session.flush()
                opp.status = "scored" if prob.verified else "validation_needed"

                score = await session.scalar(
                    select(OpportunityScore).where(
                        OpportunityScore.opportunity_id == opp.id,
                        OpportunityScore.scoring_version == "v2",
                    )
                )
                values = {
                    "pain_severity": score_dict["dimensions"]["pain"]["score"],
                    "frequency": prob.frequency / 10.0 if prob.frequency else 0.5,
                    "growth": score_dict["dimensions"]["market"]["score"],
                    "wtp": score_dict["dimensions"]["wtp"]["score"],
                    "market_size": score_dict["dimensions"]["market"]["score"],
                    "competition_gap": score_dict["dimensions"]["competition"]["score"],
                    "distribution": score_dict["dimensions"]["distribution"]["score"],
                    "technical": score_dict["dimensions"]["technical"]["score"],
                    "final_score": score_dict["final_score"],
                    "evidence_confidence": score_dict["confidence"],
                    "potential": score_dict["potential_score"],
                    "confidence": score_dict["confidence"],
                    "freshness_days": score_dict["freshness_days"],
                    "next_step": score_dict["next_step"],
                    "source_diversity": score_dict["ledger"]["platforms_covered"],
                    "breakdown_json": score_dict,
                }
                if score:
                    for field, value in values.items():
                        setattr(score, field, value)
                else:
                    session.add(OpportunityScore(opportunity_id=opp.id, scoring_version="v2", **values))
                scored_count += 1
                
        console.print(f"\n[bold]Successfully scored {scored_count} opportunities.[/bold]")
        
    run_async(_run())

@output_app.command("report")
def generate_report(output_file: str = typer.Option("opportunity_report.md", help="Output file path")):
    """Generate a markdown report of scored opportunities."""
    console.print(f"Generating report at {output_file}...")
    
    async def _run():
        generator = MarkdownReportGenerator()
        path = await generator.generate(output_file)
        if path:
            console.print(f"[bold green]Report generated successfully at:[/bold green] {path}")
        else:
            console.print("[yellow]No scored opportunities found. Run 'analyze score' first.[/yellow]")
            
    run_async(_run())

@app.command("status")
def system_status():
    """Show system status."""
    console.print("[bold green]Idea Hunter System Status[/bold green]")
    console.print("PostgreSQL: [yellow]Checking...[/yellow]")
    console.print("Ollama: [yellow]Checking...[/yellow]")

if __name__ == "__main__":
    app()

@collect_app.command("sources")
def list_sources():
    """List the registered discovery sources and their safe acquisition mode."""
    for source in SOURCES:
        console.print(f"{source.key:18} {source.acquisition:14} {source.signal_kind:24} {source.name}")

@collect_app.command("source")
def collect_registered_source(
    source_key: str = typer.Option(..., "--source", help="Registered source key, e.g. devto or producthunt"),
    query: str = typer.Option("", help="Source-specific query/tag"),
    limit: int = typer.Option(100, min=1, max=100),
):
    """Collect from a registered source through the existing Observation pipeline."""
    definition = get_source(source_key)
    if definition.acquisition not in {"official_api", "public_api"}:
        raise typer.BadParameter(f"{definition.name} is {definition.acquisition}; use a permitted manual export/import rather than scraping it.")
    collector = get_collector(source_key)

    async def _run():
        async with session_scope() as session:
            source = (await session.execute(select(Source).where(Source.source_type == source_key))).scalar_one_or_none()
            if not source:
                source = Source(name=definition.name, source_type=definition.key, base_url=definition.base_url,
                                reliability_score=definition.reliability, categories=list(definition.categories),
                                signal_kind=definition.signal_kind, acquisition_method=definition.acquisition,
                                enabled=True, health_status="starting")
                session.add(source)
                await session.flush()
            run = ResearchRun(source_type=source_key, query=query)
            session.add(run)
            await session.flush()
            count = 0
            try:
                source_query = await get_or_create_source_query(session, source_id=source.id, query=query)
                async for obs in collector.collect(query=query, limit=limit, since_cursor=source_query.last_seen_cursor):
                    clean_text = TextCleaner.process(obs.raw_text)
                    if not clean_text:
                        continue
                    pf_result = prefilter(clean_text, engagement=obs.engagement or 0)
                    await session.execute(insert(Observation).values(
                        raw_text=clean_text, normalized_text=clean_text, content_hash=normalized_content_hash(clean_text), source_id=source.id,
                        source_url=obs.source_url, published_at=obs.published_at, author=obs.author,
                        engagement=obs.engagement, topic=obs.topic, country=obs.country,
                        passed_prefilter=pf_result.passed, metadata_json=obs.metadata,
                    ).on_conflict_do_nothing(index_elements=["content_hash"]))
                    if obs.cursor_value:
                        mark_source_query_success(source_query, obs.cursor_value)
                    count += 1
                source.health_status, source.health_note = "healthy", None
                run.status, run.items_collected = "completed", count
            except Exception as error:
                # A single source cannot abort other scheduled collection jobs.
                source.health_status, source.health_note = "unavailable", str(error)[:1000]
                run.status, run.notes = "failed", str(error)[:1000]
            finally:
                run.completed_at = func.now()
        console.print(f"{source_key}: completed with {count} items (check source health for failures).")
    run_async(_run())


@collect_app.command("import")
def import_source_export(
    source_key: str = typer.Option(..., "--source", help="Registered source key"),
    file: str = typer.Option(..., "--file", help="Licensed/user-provided .csv or .json export"),
    topic: str = typer.Option("", help="Optional research topic"),
):
    """Import a permitted export through the same Observation ingestion path."""
    definition = get_source(source_key)
    async def _run():
        async with session_scope() as session:
            source = (await session.execute(select(Source).where(Source.source_type == source_key))).scalar_one_or_none()
            if not source:
                source = Source(name=definition.name, source_type=definition.key, base_url=definition.base_url,
                    reliability_score=definition.reliability, categories=list(definition.categories), signal_kind=definition.signal_kind,
                    acquisition_method="manual_import", enabled=True, health_status="healthy")
                session.add(source); await session.flush()
            run = ResearchRun(source_type=source_key, query=topic or f"manual import: {file}")
            session.add(run); await session.flush(); count = 0
            try:
                for obs in iter_manual_observations(source_key, file, topic):
                    clean_text = TextCleaner.process(obs.raw_text)
                    if not clean_text: continue
                    result = prefilter(clean_text, engagement=obs.engagement or 0)
                    await session.execute(insert(Observation).values(raw_text=clean_text, normalized_text=clean_text, content_hash=normalized_content_hash(clean_text),
                        source_id=source.id, source_url=obs.source_url, published_at=obs.published_at, author=obs.author,
                        engagement=obs.engagement, topic=obs.topic, metadata_json=obs.metadata, passed_prefilter=result.passed
                    ).on_conflict_do_nothing(index_elements=["content_hash"]))
                    count += 1
                run.status, run.items_collected, source.health_status = "completed", count, "healthy"
            except Exception as error:
                run.status, run.notes, source.health_status, source.health_note = "failed", str(error)[:1000], "unavailable", str(error)[:1000]
            finally: run.completed_at = func.now()
    run_async(_run())
