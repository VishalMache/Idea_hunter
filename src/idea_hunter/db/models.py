from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, JSON, func, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

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

class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (UniqueConstraint("content_hash", name="uq_observation_content_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_text: Mapped[str] = mapped_column(Text)
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
    embedding = mapped_column(Vector(768))
    passed_prefilter: Mapped[Optional[bool]] = mapped_column(default=None)

    source: Mapped["Source"] = relationship()

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
    signal_type: Mapped[str] = mapped_column(String(50), default="cluster")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

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

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="discovered")

    problem: Mapped["Problem"] = relationship()

class OpportunityScore(Base):
    __tablename__ = "opportunity_scores"

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
    source_diversity: Mapped[float] = mapped_column(Float, default=1.0)
    breakdown_json: Mapped[Optional[dict]] = mapped_column(JSON)

    opportunity: Mapped["Opportunity"] = relationship()

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
