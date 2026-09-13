import asyncio
import math
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from rich.console import Console
from idea_hunter.db.models import Problem, ProblemEvidence, Observation, ProblemResearch
from idea_hunter.llm.router import model_router

console = Console()


def research_priority(problem: Problem) -> float:
    """Rank candidates by signal strength without pretending weak evidence is proof."""
    details = problem.verification_details or {}
    severity = (problem.severity or 5) / 10
    frequency = (problem.frequency or 5) / 10
    evidence_count = min(1.0, details.get("evidence_count", 0) / 3)
    source_count = min(1.0, details.get("source_count", 0) / 2)
    engagement = min(1.0, math.log1p(details.get("max_engagement", 0)) / math.log(26))
    return round(
        0.45 * ((severity + frequency) / 2)
        + 0.25 * evidence_count
        + 0.20 * source_count
        + 0.10 * engagement,
        4,
    )

async def research_problem(session: AsyncSession, problem: Problem, run_id: int = None) -> ProblemResearch:
    """Runs the multi-agent research pipeline on a single problem and saves it to ProblemResearch."""
    
    # 1. Fetch evidence
    result = await session.execute(
        select(Observation.raw_text)
        .join(ProblemEvidence, ProblemEvidence.observation_id == Observation.id)
        .where(ProblemEvidence.problem_id == problem.id)
    )
    # Bound the context so a very large cluster does not make research slower,
    # more expensive, or less focused.  The raw evidence remains in the DB.
    evidence_texts = [row[0][:1_500] for row in result.all()[:8]]
    
    if not evidence_texts:
        console.print(f"[yellow]Skipping Problem {problem.id}: No evidence found.[/yellow]")
        return None

    console.print(f"[cyan]Starting Phase 2 Agents for Problem {problem.id}: '{problem.title}'[/cyan]")

    # 2. Run independent agents in parallel
    try:
        customer, market, tech, dist, why_now = await asyncio.gather(
            model_router.analyze_customer(problem.title, problem.description, evidence_texts, run_id),
            model_router.analyze_market(problem.title, problem.description, evidence_texts, run_id),
            model_router.analyze_technical(problem.title, problem.description, evidence_texts, run_id),
            model_router.analyze_distribution(problem.title, problem.description, evidence_texts, run_id),
            model_router.analyze_why_now(problem.title, problem.description, evidence_texts, run_id)
        )
    except Exception as e:
        console.print(f"[red]Error during parallel research for problem {problem.id}: {e}[/red]")
        return None

    console.print(f"[cyan]Parallel research complete. Starting Bull/Bear Debate...[/cyan]")

    # 3. Run Debate Agent using the outputs
    try:
        debate = await model_router.run_bull_bear_debate(
            problem.title, problem.description,
            customer, market, tech, dist, why_now, run_id
        )
    except Exception as e:
        console.print(f"[red]Error during debate for problem {problem.id}: {e}[/red]")
        return None

    # 4. Save to Database
    research = ProblemResearch(
        problem_id=problem.id,
        customer_analysis=customer.model_dump(),
        market_research=market.model_dump(),
        technical_feasibility=tech.model_dump(),
        distribution_difficulty=dist.model_dump(),
        why_now=why_now.model_dump(),
        bull_case=debate.bull_case,
        bear_case=debate.bear_case,
        debate_verdict=debate.verdict
    )
    
    session.add(research)
    await session.commit()
    
    console.print(f"[bold green]Successfully researched and saved intelligence for Problem {problem.id}[/bold green]")
    return research
