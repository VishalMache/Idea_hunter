from pydantic import BaseModel, Field
from typing import List

class ExtractedProblem(BaseModel):
    problem: str = Field(..., description="A concise title for the core problem described across these texts.")
    target_user: str = Field(..., description="The main user segment experiencing this problem.")
    context: str = Field(..., description="The situation in which this problem occurs.")
    severity: int = Field(..., description="Score 1-10 on how painful this problem is.")
    frequency: int = Field(..., description="Score 1-10 on how often it happens.")
    workaround: str = Field(..., description="What users are currently doing to solve this.")
    existing_solutions: List[str] = Field(..., description="List of tools they mentioned using.")
    devils_advocate_notes: str = Field(..., description="Why might this NOT be a good startup idea? (e.g., too niche, already solved).")
    confidence: float = Field(..., description="Score 0.0 to 1.0 of how confident you are this is a real problem.")
    
class ClassificationResult(BaseModel):
    is_complaint: bool = Field(..., description="True if the text describes a genuine problem, frustration, or complaint.")
    category: str = Field(..., description="The category of the text (e.g. 'bug', 'missing feature', 'usability issue', 'pricing', 'other').")

class CompetitorDetail(BaseModel):
    name: str = Field(..., description="Name of the competitor")
    url: str = Field(..., description="Likely URL or domain")
    pricing_tier: str = Field(..., description="What they likely charge (e.g., 'Free', '$10/mo', 'Enterprise')")
    estimated_customers: str = Field(..., description="Scale of their user base if known")
    weaknesses: str = Field(..., description="What users hate about this specific competitor")

class CompetitionAnalysis(BaseModel):
    competitors: List[CompetitorDetail] = Field(..., description="Detailed breakdown of actual competitors")
    why_they_fail: str = Field(..., description="Why existing solutions as a whole fail these users")
    market_gap: str = Field(..., description="The precise gap in the market that a new solution could fill")

class CustomerAnalysis(BaseModel):
    customer_type: str = Field(..., description="Consumer (B2C), Prosumer, or Enterprise (B2B)?")
    economic_value: str = Field(..., description="What they currently pay (time/money) to cope")
    frequency: str = Field(..., description="How often they encounter this problem")
    decision_maker: str = Field(..., description="Who holds the budget to solve this?")
    concentration: str = Field(..., description="Is the pain concentrated in a small group or spread widely?")
    
class MarketResearch(BaseModel):
    estimated_size: str = Field(..., description="Estimated TAM based on signals")
    growth_trajectory: str = Field(..., description="Is this space growing, flat, or shrinking?")
    adjacent_spend: str = Field(..., description="What customers spend on adjacent solutions")
    score: float = Field(..., description="0.0 to 1.0 score for market attractiveness")

class TechnicalAssessment(BaseModel):
    required_tech: str = Field(..., description="Core technology required to build a solution")
    existing_apis: List[str] = Field(..., description="APIs or open source tools that accelerate development")
    complexity_score: int = Field(..., description="1-10 scale (1 = trivial, 10 = impossible)")
    regulatory_blockers: str = Field(..., description="Compliance or legal risks (e.g. HIPAA, SOC2)")
    mvp_capital: str = Field(..., description="Estimated cost/time to build MVP")
    score: float = Field(..., description="0.0 to 1.0 score for technical feasibility (higher is more feasible)")

class DistributionAssessment(BaseModel):
    target_channels: List[str] = Field(..., description="Where these customers hang out online/offline")
    acquisition_method: str = Field(..., description="Most likely path to first 100 customers (e.g. SEO, cold email, virality)")
    difficulty_score: int = Field(..., description="1-10 scale of distribution difficulty (1 = viral/easy, 10 = enterprise sales/hard)")
    score: float = Field(..., description="0.0 to 1.0 score for distribution feasibility (higher is easier)")

class WhyNowAssessment(BaseModel):
    triggers: List[str] = Field(..., description="Changes in tech, law, or society that enable this now")
    explanation: str = Field(..., description="Why this opportunity is attractive NOW vs 5 years ago")
    score: float = Field(..., description="0.0 to 1.0 score for timing (higher means better timing)")

class BullBearDebate(BaseModel):
    bull_case: str = Field(..., description="The absolute strongest argument for building this startup")
    bear_case: str = Field(..., description="The absolute strongest argument for why this will fail")
    verdict: str = Field(..., description="Final synthesis: BUILD, VALIDATE, or KILL")
    confidence: float = Field(..., description="0.0 to 1.0 confidence in the verdict")

class PathBAssessment(BaseModel):
    opportunity_found: bool = Field(..., description="True if a strong opportunity exists between the old problem and recent tech shifts")
    synthesis_title: str = Field(..., description="Title of the new opportunity")
    synthesis_description: str = Field(..., description="How the tech shift solves the hard problem")
    why_now: str = Field(..., description="Why this is possible now but wasn't 3 years ago")
    confidence_score: float = Field(..., description="Score 0.0 to 1.0 of how viable this is")
