from pydantic import BaseModel
from typing import Type, TypeVar
from idea_hunter.llm.client import local_client, hosted_client
from idea_hunter.llm.schemas import (
    ExtractedProblem, ClassificationResult, SignalTriage, CompetitionAnalysis,
    CustomerAnalysis, MarketResearch, TechnicalAssessment, DistributionAssessment,
    WhyNowAssessment, BullBearDebate, PathBAssessment
)
from idea_hunter.llm.prompts import (
    CLUSTER_EXTRACTION_SYSTEM_PROMPT, CLASSIFICATION_SYSTEM_PROMPT, SIGNAL_TRIAGE_SYSTEM_PROMPT, COMPETITION_ANALYSIS_SYSTEM_PROMPT,
    CUSTOMER_RESEARCH_SYSTEM_PROMPT, MARKET_RESEARCH_SYSTEM_PROMPT, TECHNICAL_FEASIBILITY_SYSTEM_PROMPT,
    DISTRIBUTION_DIFFICULTY_SYSTEM_PROMPT, WHY_NOW_SYSTEM_PROMPT, BULL_BEAR_DEBATE_SYSTEM_PROMPT,
    PATH_B_SYSTEM_PROMPT
)
from idea_hunter.config import settings

RESEARCH_EVIDENCE_POLICY = """
Evidence policy: the supplied user observations are the only primary evidence.
Do not present unsupported market sizes, competitors, pricing, regulations, or
customer behavior as established fact. Label general-knowledge conclusions as
"hypothesis" and use "unknown" where the evidence cannot support a claim.
Prefer a concrete next validation action over invented precision.
"""

class ModelRouter:
    """Routes tasks to the appropriate model based on complexity."""
    
    async def classify_complaint(self, text: str) -> ClassificationResult:
        """Use the small local model to quickly classify if text is a complaint."""
        prompt = f"Analyze this text:\n\n{text}"
        return await local_client.generate_structured(
            prompt=prompt,
            system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
            schema=ClassificationResult,
            model=settings.ollama_model_small
        )

    async def triage_signal(self, text: str) -> SignalTriage:
        """Recall-oriented local triage; keyword matching is only one feature."""
        return await local_client.generate_structured(
            prompt=f"Classify this observation:\n\n{text}",
            system_prompt=SIGNAL_TRIAGE_SYSTEM_PROMPT,
            schema=SignalTriage,
            model=settings.ollama_model_small,
        )
        
    async def extract_problem(self, texts: list[str], run_id: int = None) -> ExtractedProblem:
        """Use the hosted model (OpenRouter/Claude/OpenAI) for complex extraction reasoning on a cluster."""
        cluster_text = "\n\n---\n\n".join(texts)
        prompt = f"Extract the core problem from this cluster of related texts:\n\n{cluster_text}"
        
        model_name = None
        if hasattr(hosted_client, 'client') and hasattr(hosted_client.client, 'base_url'):
            model_name = settings.openrouter_model
            
        return await hosted_client.generate_structured(
            prompt=prompt,
            system_prompt=CLUSTER_EXTRACTION_SYSTEM_PROMPT,
            schema=ExtractedProblem,
            model=model_name,
            run_id=run_id
        )

    async def analyze_competition(self, texts: list[str], run_id: int = None) -> CompetitionAnalysis:
        """Use the hosted model to analyze the competitive landscape for a cluster."""
        cluster_text = "\n\n---\n\n".join(texts)
        prompt = f"Analyze the competition based on this cluster of related complaints:\n\n{cluster_text}"
        
        model_name = None
        if hasattr(hosted_client, 'client') and hasattr(hosted_client.client, 'base_url'):
            model_name = settings.openrouter_model
            
        return await hosted_client.generate_structured(
            prompt=prompt,
            system_prompt=COMPETITION_ANALYSIS_SYSTEM_PROMPT,
            schema=CompetitionAnalysis,
            model=model_name,
            run_id=run_id
        )

    async def analyze_customer(self, problem_title: str, problem_desc: str, evidence: list[str], run_id: int = None) -> CustomerAnalysis:
        prompt = RESEARCH_EVIDENCE_POLICY + f"\nProblem: {problem_title}\nDescription: {problem_desc}\n\nEvidence:\n" + "\n\n---\n\n".join(evidence)
        model_name = settings.openrouter_model if hasattr(hosted_client, 'client') else None
        return await hosted_client.generate_structured(
            prompt=prompt, system_prompt=CUSTOMER_RESEARCH_SYSTEM_PROMPT,
            schema=CustomerAnalysis, model=model_name, run_id=run_id
        )

    async def analyze_market(self, problem_title: str, problem_desc: str, evidence: list[str], run_id: int = None) -> MarketResearch:
        prompt = RESEARCH_EVIDENCE_POLICY + f"\nProblem: {problem_title}\nDescription: {problem_desc}\n\nEvidence:\n" + "\n\n---\n\n".join(evidence)
        model_name = settings.openrouter_model if hasattr(hosted_client, 'client') else None
        return await hosted_client.generate_structured(
            prompt=prompt, system_prompt=MARKET_RESEARCH_SYSTEM_PROMPT,
            schema=MarketResearch, model=model_name, run_id=run_id
        )

    async def analyze_technical(self, problem_title: str, problem_desc: str, evidence: list[str], run_id: int = None) -> TechnicalAssessment:
        prompt = RESEARCH_EVIDENCE_POLICY + f"\nProblem: {problem_title}\nDescription: {problem_desc}\n\nEvidence:\n" + "\n\n---\n\n".join(evidence)
        model_name = settings.openrouter_model if hasattr(hosted_client, 'client') else None
        return await hosted_client.generate_structured(
            prompt=prompt, system_prompt=TECHNICAL_FEASIBILITY_SYSTEM_PROMPT,
            schema=TechnicalAssessment, model=model_name, run_id=run_id
        )

    async def analyze_distribution(self, problem_title: str, problem_desc: str, evidence: list[str], run_id: int = None) -> DistributionAssessment:
        prompt = RESEARCH_EVIDENCE_POLICY + f"\nProblem: {problem_title}\nDescription: {problem_desc}\n\nEvidence:\n" + "\n\n---\n\n".join(evidence)
        model_name = settings.openrouter_model if hasattr(hosted_client, 'client') else None
        return await hosted_client.generate_structured(
            prompt=prompt, system_prompt=DISTRIBUTION_DIFFICULTY_SYSTEM_PROMPT,
            schema=DistributionAssessment, model=model_name, run_id=run_id
        )

    async def analyze_why_now(self, problem_title: str, problem_desc: str, evidence: list[str], run_id: int = None) -> WhyNowAssessment:
        prompt = RESEARCH_EVIDENCE_POLICY + f"\nProblem: {problem_title}\nDescription: {problem_desc}\n\nEvidence:\n" + "\n\n---\n\n".join(evidence)
        model_name = settings.openrouter_model if hasattr(hosted_client, 'client') else None
        return await hosted_client.generate_structured(
            prompt=prompt, system_prompt=WHY_NOW_SYSTEM_PROMPT,
            schema=WhyNowAssessment, model=model_name, run_id=run_id
        )

    async def run_bull_bear_debate(self, problem_title: str, problem_desc: str, 
                                   customer: CustomerAnalysis, market: MarketResearch, 
                                   tech: TechnicalAssessment, dist: DistributionAssessment, 
                                   why_now: WhyNowAssessment, run_id: int = None) -> BullBearDebate:
        prompt = (RESEARCH_EVIDENCE_POLICY + f"\nProblem: {problem_title}\nDescription: {problem_desc}\n\n"
                  f"Customer Agent:\n{customer.model_dump_json(indent=2)}\n\n"
                  f"Market Agent:\n{market.model_dump_json(indent=2)}\n\n"
                  f"Technical Agent:\n{tech.model_dump_json(indent=2)}\n\n"
                  f"Distribution Agent:\n{dist.model_dump_json(indent=2)}\n\n"
                  f"Why Now Agent:\n{why_now.model_dump_json(indent=2)}")
        
        model_name = settings.openrouter_model if hasattr(hosted_client, 'client') else None
        return await hosted_client.generate_structured(
            prompt=prompt, system_prompt=BULL_BEAR_DEBATE_SYSTEM_PROMPT,
            schema=BullBearDebate, model=model_name, run_id=run_id
        )

    async def analyze_path_b(self, hard_problem_title: str, hard_problem_desc: str, tech_shifts: list[str], run_id: int = None) -> PathBAssessment:
        shifts_text = "\n".join([f"- {ts}" for ts in tech_shifts])
        prompt = f"Hard Problem: {hard_problem_title}\nDescription: {hard_problem_desc}\n\nRecent Technology/Regulatory Shifts:\n{shifts_text}"
        
        model_name = settings.openrouter_model if hasattr(hosted_client, 'client') else None
        return await hosted_client.generate_structured(
            prompt=prompt, system_prompt=PATH_B_SYSTEM_PROMPT,
            schema=PathBAssessment, model=model_name, run_id=run_id
        )

model_router = ModelRouter()
