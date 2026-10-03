"""Typed v1 API for the evidence-first redesign."""

from datetime import datetime
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from idea_hunter.application.services.runs import cancel_run, create_run, retry_step
from idea_hunter.config import settings
from idea_hunter.db.engine import get_db_session
from idea_hunter.db.models import (
    Claim,
    ClaimEvidence,
    Cluster,
    Decision,
    Observation,
    Opportunity,
    OpportunityScore,
    PipelineRun,
    Problem,
    ProblemResearch,
    RunStep,
    Source,
    SourceQuery,
)


router = APIRouter(prefix="/api/v1", tags=["v1"])


class PageMeta(BaseModel):
    next_cursor: Optional[int] = None


class OpportunityListItem(BaseModel):
    id: int
    problem_id: int
    title: str
    status: str
    potential: Optional[float] = None
    confidence: Optional[float] = None
    freshness_days: Optional[int] = None
    next_step: Optional[str] = None
    severity: Optional[int] = None
    frequency: Optional[int] = None


class OpportunityListResponse(BaseModel):
    items: list[OpportunityListItem]
    meta: PageMeta


class SignalItem(BaseModel):
    id: int
    text: str
    source: str
    source_url: Optional[str] = None
    signal_type: Optional[str] = None
    triage_state: str
    embedding_state: str
    engagement: Optional[int] = None
    published_at: Optional[datetime] = None


class SignalListResponse(BaseModel):
    items: list[SignalItem]
    meta: PageMeta


class EvidenceItem(BaseModel):
    observation_id: int
    quote: str
    verified: bool
    stance: str
    source: str
    source_url: Optional[str] = None
    published_at: Optional[datetime] = None
    author: Optional[str] = None
    engagement: Optional[int] = None


class ClaimItem(BaseModel):
    id: int
    text: str
    kind: str
    support_state: str
    confidence: float
    evidence: list[EvidenceItem]


class OpportunityDossier(BaseModel):
    id: int
    problem_id: int
    title: str
    description: str
    status: str
    potential: Optional[float] = None
    confidence: Optional[float] = None
    freshness_days: Optional[int] = None
    next_step: Optional[str] = None
    score_breakdown: Optional[dict] = None
    research: Optional[dict] = None
    claims: list[ClaimItem]


class RunStepResponse(BaseModel):
    id: int
    step_key: str
    status: str
    attempt_count: int
    cost_usd: float
    error: Optional[str] = None
    output: Optional[dict] = None


class RunResponse(BaseModel):
    id: int
    kind: str
    status: str
    budget_usd: float
    total_cost_usd: float
    error: Optional[str] = None
    steps: list[RunStepResponse] = []


class CreateRunRequest(BaseModel):
    kind: str = "full"
    idempotency_key: Optional[str] = None
    budget_usd: float = Field(default_factory=lambda: settings.max_cost_per_run_usd, gt=0)
    config: dict = Field(default_factory=dict)


class DecisionRequest(BaseModel):
    problem_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    actor: str = "local-user"
    decision: Literal["accept", "reject", "investigate", "interview", "test_pricing", "prototype"]
    reason: str = ""


def _score_for(scores: list[OpportunityScore]) -> Optional[OpportunityScore]:
    return next((score for score in scores if score.scoring_version == "v2"), scores[0] if scores else None)


def _run_response(run: PipelineRun) -> RunResponse:
    return RunResponse(
        id=run.id,
        kind=run.kind,
        status=run.status,
        budget_usd=run.budget_usd,
        total_cost_usd=run.total_cost_usd,
        error=run.error,
        steps=[
            RunStepResponse(
                id=step.id,
                step_key=step.step_key,
                status=step.status,
                attempt_count=step.attempt_count,
                cost_usd=step.cost_usd,
                error=step.error,
                output=step.output_json,
            )
            for step in run.steps
        ],
    )


@router.get("/opportunities", response_model=OpportunityListResponse)
async def list_opportunities(
    next_step: Optional[str] = None,
    min_confidence: Optional[float] = Query(default=None, ge=0, le=1),
    cursor: Optional[int] = Query(default=None, gt=0),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(Opportunity).options(selectinload(Opportunity.problem), selectinload(Opportunity.scores)).order_by(Opportunity.id.desc())
    if cursor:
        stmt = stmt.where(Opportunity.id < cursor)
    rows = (await db.execute(stmt.limit(limit + 1))).scalars().unique().all()
    items = []
    for opportunity in rows[:limit]:
        score = _score_for(opportunity.scores)
        if next_step and (not score or score.next_step != next_step):
            continue
        if min_confidence is not None and (not score or (score.confidence if score.confidence is not None else score.evidence_confidence) < min_confidence):
            continue
        items.append(OpportunityListItem(
            id=opportunity.id,
            problem_id=opportunity.problem_id,
            title=opportunity.title,
            status=opportunity.status,
            potential=score.potential if score else None,
            confidence=(score.confidence if score and score.confidence is not None else score.evidence_confidence if score else None),
            freshness_days=score.freshness_days if score else None,
            next_step=score.next_step if score else None,
            severity=opportunity.problem.severity if opportunity.problem else None,
            frequency=opportunity.problem.frequency if opportunity.problem else None,
        ))
    return OpportunityListResponse(items=items, meta=PageMeta(next_cursor=rows[limit].id if len(rows) > limit else None))


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDossier)
async def get_opportunity(opportunity_id: int, db: AsyncSession = Depends(get_db_session)):
    opportunity = await db.scalar(
        select(Opportunity)
        .where(Opportunity.id == opportunity_id)
        .options(selectinload(Opportunity.problem), selectinload(Opportunity.scores))
    )
    if not opportunity or not opportunity.problem:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    score = _score_for(opportunity.scores)
    research = await db.scalar(select(ProblemResearch).where(ProblemResearch.problem_id == opportunity.problem_id))
    claims = (await db.execute(select(Claim).where(Claim.problem_id == opportunity.problem_id))).scalars().all()
    claim_items = []
    for claim in claims:
        rows = (await db.execute(
            select(ClaimEvidence, Observation, Source)
            .join(Observation, ClaimEvidence.observation_id == Observation.id)
            .join(Source, Observation.source_id == Source.id)
            .where(ClaimEvidence.claim_id == claim.id)
        )).all()
        claim_items.append(ClaimItem(
            id=claim.id,
            text=claim.text,
            kind=claim.kind,
            support_state=claim.support_state,
            confidence=claim.confidence,
            evidence=[EvidenceItem(
                observation_id=evidence.observation_id,
                quote=evidence.quote,
                verified=evidence.verified,
                stance=evidence.stance,
                source=source.source_type,
                source_url=observation.source_url,
                published_at=observation.published_at,
                author=observation.author,
                engagement=observation.engagement,
            ) for evidence, observation, source in rows],
        ))
    research_payload = None
    if research:
        research_payload = {
            "customer": research.customer_analysis,
            "market": research.market_research,
            "technical": research.technical_feasibility,
            "distribution": research.distribution_difficulty,
            "why_now": research.why_now,
            "bull_case": research.bull_case,
            "bear_case": research.bear_case,
            "verdict": research.debate_verdict,
        }
    return OpportunityDossier(
        id=opportunity.id,
        problem_id=opportunity.problem_id,
        title=opportunity.title,
        description=opportunity.description,
        status=opportunity.status,
        potential=score.potential if score else None,
        confidence=(score.confidence if score and score.confidence is not None else score.evidence_confidence if score else None),
        freshness_days=score.freshness_days if score else None,
        next_step=score.next_step if score else None,
        score_breakdown=score.breakdown_json if score else None,
        research=research_payload,
        claims=claim_items,
    )


@router.get("/signals", response_model=SignalListResponse)
async def list_signals(
    source: Optional[str] = None,
    signal_type: Optional[str] = None,
    state: Optional[str] = None,
    cursor: Optional[int] = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(Observation, Source).join(Source, Observation.source_id == Source.id).order_by(Observation.id.desc())
    if source:
        stmt = stmt.where(Source.source_type == source)
    if signal_type:
        stmt = stmt.where(Observation.signal_type == signal_type)
    if state:
        stmt = stmt.where(Observation.triage_state == state)
    if cursor:
        stmt = stmt.where(Observation.id < cursor)
    rows = (await db.execute(stmt.limit(limit + 1))).all()
    return SignalListResponse(
        items=[SignalItem(
            id=observation.id,
            text=observation.normalized_text or observation.raw_text,
            source=source_row.source_type,
            source_url=observation.source_url,
            signal_type=observation.signal_type,
            triage_state=observation.triage_state,
            embedding_state=observation.embedding_state,
            engagement=observation.engagement,
            published_at=observation.published_at,
        ) for observation, source_row in rows[:limit]],
        meta=PageMeta(next_cursor=rows[limit][0].id if len(rows) > limit else None),
    )


@router.get("/clusters")
async def list_clusters(state: Optional[str] = None, db: AsyncSession = Depends(get_db_session)):
    stmt = select(Cluster).order_by(Cluster.last_seen_at.desc())
    if state:
        stmt = stmt.where(Cluster.state == state)
    clusters = (await db.execute(stmt)).scalars().all()
    return {"items": [{"id": row.id, "label": row.label, "state": row.state, "observation_count": row.observation_count, "first_seen_at": row.first_seen_at, "last_seen_at": row.last_seen_at} for row in clusters]}


@router.post("/runs", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_run(request: CreateRunRequest, db: AsyncSession = Depends(get_db_session)):
    run = await create_run(
        db,
        idempotency_key=request.idempotency_key or str(uuid4()),
        kind=request.kind,
        config=request.config,
        budget_usd=request.budget_usd,
    )
    await db.commit()
    await db.refresh(run, attribute_names=["steps"])
    return _run_response(run)


@router.get("/runs", response_model=list[RunResponse])
async def list_runs(limit: int = Query(default=30, ge=1, le=100), db: AsyncSession = Depends(get_db_session)):
    runs = (await db.execute(select(PipelineRun).options(selectinload(PipelineRun.steps)).order_by(PipelineRun.id.desc()).limit(limit))).scalars().unique().all()
    return [_run_response(run) for run in runs]


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: int, db: AsyncSession = Depends(get_db_session)):
    run = await db.scalar(select(PipelineRun).where(PipelineRun.id == run_id).options(selectinload(PipelineRun.steps)))
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _run_response(run)


@router.post("/runs/{run_id}/cancel", response_model=RunResponse)
async def cancel_run_endpoint(run_id: int, db: AsyncSession = Depends(get_db_session)):
    run = await db.scalar(select(PipelineRun).where(PipelineRun.id == run_id).options(selectinload(PipelineRun.steps)))
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    await cancel_run(db, run)
    await db.commit()
    return _run_response(run)


@router.post("/runs/{run_id}/steps/{step_key}/retry", response_model=RunResponse)
async def retry_run_step(run_id: int, step_key: str, db: AsyncSession = Depends(get_db_session)):
    run = await db.scalar(select(PipelineRun).where(PipelineRun.id == run_id).options(selectinload(PipelineRun.steps)))
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    step = next((item for item in run.steps if item.step_key == step_key), None)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found.")
    try:
        await retry_step(db, step)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    await db.commit()
    return _run_response(run)


@router.get("/sources")
async def list_sources(db: AsyncSession = Depends(get_db_session)):
    sources = (await db.execute(select(Source).options(selectinload(Source.queries)).order_by(Source.name))).scalars().unique().all()
    return {"items": [{
        "id": source.id,
        "name": source.name,
        "key": source.source_type,
        "health_status": source.health_status,
        "acquisition_method": source.acquisition_method,
        "reliability": source.reliability_score,
        "queries": [{"id": query.id, "key": query.query_key, "text": query.query_text, "cursor": query.last_seen_cursor, "last_success_at": query.last_success_at, "last_error": query.last_error} for query in source.queries],
    } for source in sources]}


@router.post("/decisions", status_code=status.HTTP_201_CREATED)
async def create_decision(request: DecisionRequest, db: AsyncSession = Depends(get_db_session)):
    if not request.problem_id and not request.opportunity_id:
        raise HTTPException(status_code=422, detail="Provide problem_id or opportunity_id.")
    if request.opportunity_id:
        opportunity = await db.scalar(select(Opportunity).where(Opportunity.id == request.opportunity_id))
        if not opportunity:
            raise HTTPException(status_code=404, detail="Opportunity not found.")
        if not request.problem_id:
            request.problem_id = opportunity.problem_id
        if request.decision in {"accept", "reject"}:
            opportunity.status = "accepted" if request.decision == "accept" else "rejected"
    decision = Decision(
        problem_id=request.problem_id,
        opportunity_id=request.opportunity_id,
        actor=request.actor,
        decision=request.decision,
        reason=request.reason or None,
    )
    db.add(decision)
    await db.commit()
    return {"id": decision.id, "status": "created"}


@router.get("/health/live")
async def liveness():
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db_session)):
    await db.execute(select(1))
    return {"status": "ready"}
