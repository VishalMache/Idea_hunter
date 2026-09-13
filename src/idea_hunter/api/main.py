from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from idea_hunter.db.engine import get_db_session
from idea_hunter.db.models import Problem, Opportunity, OpportunityScore, Observation, ProblemEvidence, ExistingSolution, UserFeedback, ProblemResearch
from pydantic import BaseModel

class FeedbackRequest(BaseModel):
    verdict: str
    notes: str = ""

app = FastAPI(title="Idea Hunter API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db_session)):
    obs_count = await db.scalar(select(func.count(Observation.id)))
    prob_count = await db.scalar(select(func.count(Problem.id)))
    opp_count = await db.scalar(select(func.count(Opportunity.id)))
    
    return {"status": "running", "observations": obs_count, "problems": prob_count, "opportunities": opp_count}

@app.get("/api/pipeline")
async def get_pipeline_status(db: AsyncSession = Depends(get_db_session)):
    """Return live, database-backed progress for each pipeline stage."""
    async def count(statement):
        return await db.scalar(statement) or 0

    observations = await count(select(func.count(Observation.id)))
    passed = await count(select(func.count(Observation.id)).where(Observation.passed_prefilter.is_(True)))
    embedded = await count(select(func.count(Observation.id)).where(Observation.embedding.is_not(None)))
    clustered = await count(select(func.count(Observation.id)).where(Observation.cluster_id.is_not(None)))
    clusters = await count(
        select(func.count(func.distinct(Observation.cluster_id))).where(Observation.cluster_id.is_not(None))
    )
    extracted_clusters = await count(
        select(func.count(func.distinct(Observation.cluster_id)))
        .select_from(Observation)
        .join(ProblemEvidence, Observation.id == ProblemEvidence.observation_id)
        .where(Observation.cluster_id.is_not(None))
    )
    problems = await count(select(func.count(Problem.id)))
    verified = await count(select(func.count(Problem.id)).where(Problem.verified.is_(True)))
    researched = await count(select(func.count(ProblemResearch.id)))
    scored = await count(select(func.count(Opportunity.id)))

    def stage(stage_id, label, value, total, detail):
        state = "complete" if total and value >= total else "waiting"
        if value and value < total:
            state = "active"
        return {"id": stage_id, "label": label, "value": value, "total": total, "state": state, "detail": detail}

    return {
        "stages": [
            stage("collect", "Collect", observations, observations, f"{observations} observations saved"),
            stage("embed", "Embed", embedded, passed, f"{embedded} of {passed} signals embedded"),
            stage("cluster", "Cluster", clustered, embedded, f"{clustered} observations assigned to clusters"),
            stage("extract", "Extract", extracted_clusters, clusters, f"{problems} structured problems extracted"),
            stage("verify", "Verify", verified, problems, f"{verified} problems passed evidence checks"),
            stage("research", "Research", researched, verified, f"{researched} multi-agent research reports"),
            stage("score", "Score", scored, max(researched, scored), f"{scored} ranked opportunities"),
        ],
        "updated_at": "live",
    }

@app.get("/api/problems/recent")
async def list_recent_problems(limit: int = 12, db: AsyncSession = Depends(get_db_session)):
    stmt = select(Problem).order_by(Problem.created_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return {"problems": [{
        "id": problem.id,
        "title": problem.title,
        "severity": problem.severity,
        "frequency": problem.frequency,
        "verified": problem.verified,
        "status": problem.status,
        "signal_type": problem.signal_type,
        "created_at": problem.created_at,
    } for problem in rows]}

@app.get("/api/observations")
async def list_observations(limit: int = 100, db: AsyncSession = Depends(get_db_session)):
    stmt = select(Observation).order_by(Observation.collected_at.desc()).limit(limit)
    res = await db.execute(stmt)
    observations = res.scalars().all()
    
    data = []
    for obs in observations:
        data.append({
            "id": obs.id,
            "text": obs.raw_text,
            "source": obs.source_url or "unknown",
            "engagement": obs.engagement,
            "cluster_id": obs.cluster_id,
            "published_at": obs.published_at
        })
    return {"observations": data}

@app.get("/api/opportunities")
async def list_opportunities(db: AsyncSession = Depends(get_db_session)):
    stmt = (
        select(Problem, Opportunity, OpportunityScore, ProblemResearch)
        .outerjoin(Opportunity, Opportunity.problem_id == Problem.id)
        .outerjoin(OpportunityScore, Opportunity.id == OpportunityScore.opportunity_id)
        .outerjoin(ProblemResearch, ProblemResearch.problem_id == Problem.id)
        .order_by(OpportunityScore.final_score.desc().nullslast(), Problem.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    data = []
    for prob, opp, score, research in rows:
        unresearched_count = 0 if not score else sum(1 for v in [
            score.growth, score.wtp, score.market_size,
            score.competition_gap, score.distribution, score.technical
        ] if v is None)
        if score:
            stage_status = "Scored opportunity"
        elif research:
            stage_status = "Researched — awaiting score"
        elif prob.verified:
            stage_status = "Verified — awaiting research"
        else:
            stage_status = "Candidate — awaiting verification"
        
        data.append({
            "id": opp.id if opp else f"problem-{prob.id}",
            "problem_id": prob.id,
            "title": prob.title,
            "score": score.final_score if score else None,
            "severity": prob.severity,
            "frequency": prob.frequency,
            "unresearched_count": unresearched_count,
            "stage_status": stage_status,
            "description": prob.description,
            "target_user": prob.user_segment,
            "workaround": prob.workaround,
            "devils_advocate": prob.devils_advocate_notes
        })
    return {"opportunities": data}

@app.get("/api/problems/{problem_id}")
async def get_problem_details(problem_id: int, db: AsyncSession = Depends(get_db_session)):
    prob = await db.scalar(select(Problem).where(Problem.id == problem_id))
    if not prob:
        return {"error": "Problem not found"}
        
    sol_res = await db.execute(select(ExistingSolution).where(ExistingSolution.problem_id == problem_id))
    solutions = [{"name": s.name, "gap_notes": s.gap_notes} for s in sol_res.scalars().all()]
    
    ev_stmt = (
        select(Observation)
        .join(ProblemEvidence, Observation.id == ProblemEvidence.observation_id)
        .where(ProblemEvidence.problem_id == problem_id)
    )
    ev_res = await db.execute(ev_stmt)
    evidence = [{"text": o.raw_text, "source": o.source_url or "unknown", "engagement": o.engagement} for o in ev_res.scalars().all()]
    
    return {
        "problem": {
            "title": prob.title,
            "description": prob.description,
            "devils_advocate": prob.devils_advocate_notes
        },
        "solutions": solutions,
        "evidence": evidence
    }

@app.post("/api/feedback/{problem_id}")
async def submit_feedback(problem_id: int, request: FeedbackRequest, db: AsyncSession = Depends(get_db_session)):
    feedback = UserFeedback(
        problem_id=problem_id,
        verdict=request.verdict,
        notes=request.notes
    )
    db.add(feedback)
    
    # Also update opportunity status
    opp = await db.scalar(select(Opportunity).where(Opportunity.problem_id == problem_id))
    if opp:
        opp.status = "accepted" if request.verdict == "accept" else "rejected"
        
    await db.commit()
    return {"status": "success"}
