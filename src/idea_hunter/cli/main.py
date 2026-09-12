import typer
import asyncio
from rich.console import Console
from rich.progress import track
from sqlalchemy import select, func
from idea_hunter.collectors.hackernews import HackerNewsCollector
from idea_hunter.collectors.reddit import RedditCollector
from idea_hunter.collectors.github import GitHubCollector
from idea_hunter.collectors.reviews import PlayStoreReviewsCollector
from idea_hunter.db.session import session_scope
from idea_hunter.db.models import Source, Observation, Problem, ProblemEvidence, Opportunity, OpportunityScore, ExistingSolution, ResearchRun, CostLog, ProblemResearch, Trend, HardProblem, TechShift
from idea_hunter.config import settings
from idea_hunter.processing.extractor import ProblemExtractor
from idea_hunter.processing.cleaner import TextCleaner
from idea_hunter.processing.prefilter import prefilter
from idea_hunter.processing.embedder import Embedder
from idea_hunter.analysis.clusterer import ProblemClusterer
from idea_hunter.analysis.scorer import EvidenceScorer
from idea_hunter.output.report_generator import MarkdownReportGenerator
from idea_hunter.processing.verifier import ProblemVerifier
from idea_hunter.processing.researcher import research_problem
from idea_hunter.llm.router import model_router
from sqlalchemy.dialects.postgresql import insert

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
                
            async for obs in collector.collect(query=query, limit=limit, since_cursor=source.last_seen_cursor):
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
                    content_hash=obs.content_hash,
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
                    source.last_seen_cursor = obs.cursor_value
                    
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
                
            async for obs in collector.collect(query=query, limit=limit, since_cursor=source.last_seen_cursor):
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
                    content_hash=obs.content_hash,
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
                    source.last_seen_cursor = obs.cursor_value
                    
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
                    content_hash=obs.content_hash,
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
                
            run.items_collected = count
            run.status = "completed"
            run.completed_at = func.now()
                
        console.print(f"\n[bold]Saved {count} observations to database.[/bold]")
        
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
                
            console.print(f"Embedding {len(observations)} observations...")
            texts = [obs.raw_text for obs in observations]
            
            # This uses local Ollama via nomic-embed-text
            embeddings = await embedder.embed_batch(texts)
            
            for obs, emb in zip(observations, embeddings):
                obs.embedding = emb
                
            console.print(f"[bold green]Successfully embedded {len(observations)} items.[/bold green]")
            
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
            
            for obs in observations:
                # Find nearest clustered observation
                nn_stmt = (
                    select(Observation.cluster_id, Observation.embedding.cosine_distance(obs.embedding).label("dist"))
                    .where(Observation.cluster_id.is_not(None))
                    .order_by("dist")
                    .limit(1)
                )
                nn_res = await session.execute(nn_stmt)
                nn_row = nn_res.first()
                
                if nn_row and nn_row.dist < 0.2: # 0.2 is the cosine distance threshold (higher similarity)
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
def extract_problems(limit: int = typer.Option(10, help="Number of clusters to process")):
    """Run LLM problem extraction on un-extracted clusters."""
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
                            for sol_name in competition.competitors:
                                sol = ExistingSolution(
                                    problem_id=problem.id,
                                    name=sol_name,
                                    gap_notes=f"Gap: {competition.market_gap}\nWhy they fail: {competition.why_they_fail}"
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
def verify_problems():
    """Verify extracted problems before they are scored."""
    console.print("Running verification checks on extracted problems...")
    
    async def _run():
        async with session_scope() as session:
            stmt = select(Problem).where(Problem.verified == False, Problem.status != "flagged")
            result = await session.execute(stmt)
            problems = result.scalars().all()
            
            if not problems:
                console.print("No unverified problems found.")
                return
                
            verified_count = 0
            flagged_count = 0
            
            for prob in problems:
                is_valid = await ProblemVerifier.verify(session, prob.id)
                if is_valid:
                    prob.verified = True
                    verified_count += 1
                else:
                    prob.status = "flagged"
                    flagged_count += 1
                    
            await session.flush()
            console.print(f"Verified {verified_count} problems. Flagged {flagged_count} problems.")
            
    run_async(_run())

@analyze_app.command("research")
def research_problems(limit: int = typer.Option(5, help="Number of verified problems to research")):
    """Run the multi-agent research pipeline on verified problems."""
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
            
            # Find verified problems that don't have ProblemResearch yet
            stmt = select(Problem).outerjoin(ProblemResearch).where(ProblemResearch.id == None).where(Problem.verified == True).limit(limit)
            result = await session.execute(stmt)
            problems = result.scalars().all()
            
            if not problems:
                console.print("No un-researched problems found.")
                return
                
            run = ResearchRun(source_type="research", query=f"Researching {len(problems)} problems")
            session.add(run)
            await session.commit()
            run_id = run.id
                
            console.print(f"Researching {len(problems)} problems...")
            researched_count = 0
            
            for prob in track(problems, description="Researching..."):
                try:
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
            # Find problems that haven't been scored yet and are verified
            stmt = select(Problem).outerjoin(Opportunity).where(Opportunity.id == None).where(Problem.verified == True)
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
                    select(Observation)
                    .join(ProblemEvidence, Observation.id == ProblemEvidence.observation_id)
                    .where(ProblemEvidence.problem_id == prob.id)
                )
                obs_result = await session.execute(obs_stmt)
                obs_list = obs_result.scalars().all()
                
                # Fetch existing solutions count
                sol_stmt = select(func.count(ExistingSolution.id)).where(ExistingSolution.problem_id == prob.id)
                sol_result = await session.execute(sol_stmt)
                sol_count = sol_result.scalar_one_or_none() or 0
                
                # 3. Score
                score_dict = EvidenceScorer.score(prob, research, obs_list, sol_count)
                
                opp = Opportunity(
                    problem_id=prob.id,
                    title=f"Opportunity: {prob.title}",
                    description=prob.description,
                    status="scored"
                )
                session.add(opp)
                await session.flush()
                
                score = OpportunityScore(
                    opportunity_id=opp.id,
                    pain_severity=score_dict["dimensions"]["pain"]["score"],
                    frequency=prob.frequency / 10.0 if prob.frequency else 0.5,
                    growth=score_dict["dimensions"]["market"]["score"],
                    wtp=score_dict["dimensions"]["wtp"]["score"],
                    market_size=score_dict["dimensions"]["market"]["score"],
                    competition_gap=score_dict["dimensions"]["competition"]["score"],
                    distribution=score_dict["dimensions"]["distribution"]["score"],
                    technical=score_dict["dimensions"]["technical"]["score"],
                    final_score=score_dict["final_score"],
                    evidence_confidence=score_dict["confidence"],
                    breakdown_json=score_dict
                )
                session.add(score)
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
