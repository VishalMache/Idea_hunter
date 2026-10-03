from datetime import datetime
from typing import List, Optional
from sqlalchemy import Boolean, String, Integer, Float, DateTime, ForeignKey, Text, JSON, func, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector


class CompatibleVector(Vector):
    """Accept vector values returned by asyncpg's native codec or as text."""

    cache_ok = True

    def result_processor(self, dialect, coltype):
        parent_processor = super().result_processor(dialect, coltype)

        def process(value):
            if value is None or isinstance(value, list):
                return value
            return parent_processor(value)

        return process


class Base(DeclarativeBase):
    pass

class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(50))
    base_url: Mapped[Optional[str]] = mapped_column(String(1024))
    reliability_score: Mapped[float] = mapped_column(Float, default=1.0)
    last_seen_cursor: Mapped[Optional[str]] = mapped_column(String(512))  # for incremental crawl
    categories: Mapped[Optional[list]] = mapped_column(JSON)
    signal_kind: Mapped[Optional[str]] = mapped_column(String(50))
    acquisition_method: Mapped[Optional[str]] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(default=False)
    health_status: Mapped[Optional[str]] = mapped_column(String(50))
    health_note: Mapped[Optional[str]] = mapped_column(Text)

    queries: Mapped[List["SourceQuery"]] = relationship(back_populates="source", cascade="all, delete-orphan")

class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (UniqueConstraint("content_hash", name="uq_observation_content_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[Optional[str]] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)  # SHA-256, used for dedup + cache
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    author: Mapped[Optional[str]] = mapped_column(String(255))
    engagement: Mapped[Optional[int]] = mapped_column(Integer)
    topic: Mapped[Optional[str]] = mapped_column(String(255))
    country: Mapped[Optional[str]] = mapped_column(String(2))
    cluster_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    cluster_ref_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clusters.id", ondelete="SET NULL"), index=True)
    embedding = mapped_column(CompatibleVector(768))
    embedding_model: Mapped[Optional[str]] = mapped_column(String(255))
    embedding_dimension: Mapped[Optional[int]] = mapped_column(Integer)
    embedding_state: Mapped[str] = mapped_column(String(30), default="pending")
    embedding_attempts: Mapped[int] = mapped_column(Integer, default=0)
    passed_prefilter: Mapped[Optional[bool]] = mapped_column(default=None)
    signal_type: Mapped[Optional[str]] = mapped_column(String(50))
    triage_state: Mapped[str] = mapped_column(String(30), default="pending")
    raw_payload_ref: Mapped[Optional[str]] = mapped_column(String(1024))
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)

    source: Mapped["Source"] = relationship()
    cluster: Mapped[Optional["Cluster"]] = relationship(back_populates="observations")

class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    user_segment: Mapped[Optional[str]] = mapped_column(String(255))
    industry: Mapped[Optional[str]] = mapped_column(String(255))
    severity: Mapped[Optional[int]] = mapped_column(Integer)   # 1-10
    frequency: Mapped[Optional[int]] = mapped_column(Integer)  # 1-10
    workaround: Mapped[Optional[str]] = mapped_column(Text)
    devils_advocate_notes: Mapped[Optional[str]] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(50), default="new")
    verification_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    verification_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    verification_attempts: Mapped[int] = mapped_column(Integer, default=0)
    signal_type: Mapped[str] = mapped_column(String(50), default="cluster")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    claims: Mapped[List["Claim"]] = relationship(back_populates="problem", cascade="all, delete-orphan")

class ProblemResearch(Base):
    __tablename__ = "problem_research"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), unique=True)
    
    customer_analysis: Mapped[Optional[dict]] = mapped_column(JSON)
    market_research: Mapped[Optional[dict]] = mapped_column(JSON)
    technical_feasibility: Mapped[Optional[dict]] = mapped_column(JSON)
    distribution_difficulty: Mapped[Optional[dict]] = mapped_column(JSON)
    why_now: Mapped[Optional[dict]] = mapped_column(JSON)
    
    bull_case: Mapped[Optional[str]] = mapped_column(Text)
    bear_case: Mapped[Optional[str]] = mapped_column(Text)
    debate_verdict: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    problem: Mapped["Problem"] = relationship()

class ProblemEvidence(Base):
    __tablename__ = "problem_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"))
    observation_id: Mapped[int] = mapped_column(ForeignKey("observations.id"))
    evidence_strength: Mapped[float] = mapped_column(Float)
    evidence_text: Mapped[Optional[str]] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    problem: Mapped["Problem"] = relationship()
    observation: Mapped["Observation"] = relationship()

class ExistingSolution(Base):
    __tablename__ = "existing_solutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"))
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[Optional[str]] = mapped_column(String(1024))
    gap_notes: Mapped[Optional[str]] = mapped_column(Text)

    problem: Mapped["Problem"] = relationship()

class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (UniqueConstraint("problem_id", name="uq_opportunity_problem_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="discovered")

    problem: Mapped["Problem"] = relationship()
    scores: Mapped[List["OpportunityScore"]] = relationship(back_populates="opportunity", cascade="all, delete-orphan")

class OpportunityScore(Base):
    __tablename__ = "opportunity_scores"
    __table_args__ = (UniqueConstraint("opportunity_id", "scoring_version", name="uq_opportunity_score_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"))
    pain_severity: Mapped[float] = mapped_column(Float)
    frequency: Mapped[float] = mapped_column(Float)
    growth: Mapped[float] = mapped_column(Float)
    wtp: Mapped[float] = mapped_column(Float)
    market_size: Mapped[float] = mapped_column(Float)
    competition_gap: Mapped[float] = mapped_column(Float)
    distribution: Mapped[float] = mapped_column(Float)
    technical: Mapped[float] = mapped_column(Float)
    final_score: Mapped[float] = mapped_column(Float)
    evidence_confidence: Mapped[float] = mapped_column(Float)
    potential: Mapped[Optional[float]] = mapped_column(Float)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    freshness_days: Mapped[Optional[int]] = mapped_column(Integer)
    next_step: Mapped[Optional[str]] = mapped_column(String(100))
    scoring_version: Mapped[str] = mapped_column(String(50), default="v2")
    source_diversity: Mapped[float] = mapped_column(Float, default=1.0)
    breakdown_json: Mapped[Optional[dict]] = mapped_column(JSON)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="scores")

class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50))
    query: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    items_collected: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="running")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

class CostLog(Base):
    __tablename__ = "cost_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("research_runs.id"))
    model: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"))
    verdict: Mapped[str] = mapped_column(String(20))  # "accept" | "reject"
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

class Trend(Base):
    __tablename__ = "trends"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str] = mapped_column(String(255))
    direction: Mapped[str] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(50))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

class HardProblem(Base):
    __tablename__ = "hard_problems"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    industry: Mapped[Optional[str]] = mapped_column(String(255))
    why_it_is_hard: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

class TechShift(Base):
    __tablename__ = "tech_shifts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100)) # e.g. AI, Regulatory, Cost
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class SourceQuery(Base):
    """A query-specific collection cursor and configuration for one source."""

    __tablename__ = "source_queries"
    __table_args__ = (UniqueConstraint("source_id", "query_key", name="uq_source_query_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    query_key: Mapped[str] = mapped_column(String(255))
    query_text: Mapped[str] = mapped_column(Text)
    config_json: Mapped[Optional[dict]] = mapped_column(JSON)
    last_seen_cursor: Mapped[Optional[str]] = mapped_column(String(512))
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    source: Mapped["Source"] = relationship(back_populates="queries")


class Cluster(Base):
    """Stable cluster identity, separated from legacy integer cluster_id values."""

    __tablename__ = "clusters"
    __table_args__ = (Index("ix_clusters_state_last_seen", "state", "last_seen_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[Optional[str]] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(30), default="new")
    centroid_metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    observation_count: Mapped[int] = mapped_column(Integer, default=0)

    observations: Mapped[List["Observation"]] = relationship(back_populates="cluster")


class PipelineRun(Base):
    """Resumable top-level pipeline execution with a per-run budget."""

    __tablename__ = "pipeline_runs"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_pipeline_run_idempotency_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(50), default="full")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(255))
    config_json: Mapped[Optional[dict]] = mapped_column(JSON)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    budget_usd: Mapped[float] = mapped_column(Float, default=2.0)
    error: Mapped[Optional[str]] = mapped_column(Text)

    steps: Mapped[List["RunStep"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class RunStep(Base):
    """A retryable, independently persisted pipeline or research operation."""

    __tablename__ = "run_steps"
    __table_args__ = (UniqueConstraint("run_id", "step_key", name="uq_run_step_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id", ondelete="CASCADE"), index=True)
    step_key: Mapped[str] = mapped_column(String(100))
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[Optional[str]] = mapped_column(Text)
    output_json: Mapped[Optional[dict]] = mapped_column(JSON)

    run: Mapped["PipelineRun"] = relationship(back_populates="steps")


class Claim(Base):
    """A statement about a problem, explicitly marked as evidence or hypothesis."""

    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(30), default="hypothesis")
    support_state: Mapped[str] = mapped_column(String(30), default="unverified")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    problem: Mapped["Problem"] = relationship(back_populates="claims")
    evidence: Mapped[List["ClaimEvidence"]] = relationship(back_populates="claim", cascade="all, delete-orphan")


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    __table_args__ = (UniqueConstraint("claim_id", "observation_id", "quote", name="uq_claim_evidence_quote"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    observation_id: Mapped[int] = mapped_column(ForeignKey("observations.id", ondelete="CASCADE"), index=True)
    quote: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    stance: Mapped[str] = mapped_column(String(30), default="support")

    claim: Mapped["Claim"] = relationship(back_populates="evidence")
    observation: Mapped["Observation"] = relationship()


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[Optional[int]] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    actor: Mapped[str] = mapped_column(String(255), default="local-user")
    decision: Mapped[str] = mapped_column(String(30))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class ModelRegistry(Base):
    __tablename__ = "model_registry"
    __table_args__ = (UniqueConstraint("provider", "model", name="uq_model_registry_provider_model"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(255))
    dimension: Mapped[Optional[int]] = mapped_column(Integer)
    input_cost_per_million: Mapped[float] = mapped_column(Float, default=0.0)
    output_cost_per_million: Mapped[float] = mapped_column(Float, default=0.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ModelCall(Base):
    __tablename__ = "model_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pipeline_runs.id", ondelete="SET NULL"), index=True)
    task: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(255))
    prompt_version: Mapped[Optional[str]] = mapped_column(String(100))
    schema_version: Mapped[Optional[str]] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
