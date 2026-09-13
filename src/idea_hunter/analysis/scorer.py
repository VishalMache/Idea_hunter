from typing import Optional, List, Dict, Any
from idea_hunter.db.models import Problem, ProblemResearch, Observation
from datetime import datetime, timezone, timedelta

class EvidenceScorer:
    """Calculates Evidence-Backed scores based on ProblemResearch JSON and raw Observations."""
    
    @staticmethod
    def calculate_ledger(observations: List[Observation], research: Optional[ProblemResearch], existing_solutions_count: int) -> Dict[str, Any]:
        """Calculates the raw evidence ledger counts."""
        user_complaints = len(observations)
        
        # A source is an independent author when available.  Fall back to the
        # observation ID so anonymous observations are never collapsed together.
        independent_sources = len(set(obs.author or f"observation:{obs.id}" for obs in observations))
        platforms_covered = len(set(obs.source_id for obs in observations))
        
        # Competitors from research
        named_competitors = existing_solutions_count
            
        # Pricing signals (naive regex or just checking if WTP is mentioned, but let's do a simple "$" count)
        pricing_signals = sum(1 for obs in observations if "$" in obs.raw_text)
        
        # Recent signals (last 30 days)
        now = datetime.now(timezone.utc)
        recent_signals = sum(
            1 for obs in observations
            if (obs.published_at or obs.collected_at)
            and (now - (obs.published_at or obs.collected_at)) < timedelta(days=30)
        )
        
        return {
            "user_complaints": user_complaints,
            "independent_sources": independent_sources,
            "platforms_covered": platforms_covered,
            "named_competitors": named_competitors,
            "pricing_signals": pricing_signals,
            "recent_signals": recent_signals
        }

    @staticmethod
    def score(problem: Problem, research: Optional[ProblemResearch], observations: List[Observation], existing_solutions_count: int) -> Dict[str, Any]:
        """Returns a comprehensive breakdown of the opportunity score with evidence attached."""
        ledger = EvidenceScorer.calculate_ledger(observations, research, existing_solutions_count)
        
        # Default scores if no research
        pain_score = (problem.severity or 5) / 10.0
        pain_evidence = f"{ledger['user_complaints']} user complaints, {ledger['platforms_covered']} platforms"
        
        why_now_score = 0.5
        why_now_evidence = "No specific triggers identified."
        
        market_score = 0.5
        market_evidence = "Market size unknown."
        
        comp_score = 0.5
        comp_evidence = f"{ledger['named_competitors']} competitors found."
        
        wtp_score = 0.5
        wtp_evidence = f"{ledger['pricing_signals']} pricing signals found in raw complaints."
        
        dist_score = 0.5
        dist_evidence = "Distribution channels unverified."
        
        tech_score = 0.5
        tech_evidence = "Technical complexity unverified."
        
        # Extract from research if available
        if research:
            if research.why_now:
                why_now_score = research.why_now.get("score", 0.5)
                triggers = research.why_now.get("triggers", [])
                if triggers:
                    why_now_evidence = f"Trigger: {triggers[0]}"
            
            if research.market_research:
                market_score = research.market_research.get("score", 0.5)
                market_evidence = f"Est. TAM: {research.market_research.get('estimated_size', 'Unknown')} | {research.market_research.get('growth_trajectory', 'Unknown growth')}"
                
            if research.customer_analysis:
                wtp_score = 0.7 if ledger['pricing_signals'] > 0 else 0.4
                wtp_evidence = f"{ledger['pricing_signals']} explicit pricing signals. Econ: {research.customer_analysis.get('economic_value', 'Unknown')}"
                
            if research.distribution_difficulty:
                dist_score = research.distribution_difficulty.get("score", 0.5)
                dist_evidence = research.distribution_difficulty.get("acquisition_method", dist_evidence)
                
            if research.technical_feasibility:
                tech_score = research.technical_feasibility.get("score", 0.5)
                tech_evidence = f"Complexity: {research.technical_feasibility.get('complexity_score', 5)}/10. {research.technical_feasibility.get('regulatory_blockers', 'No major blockers')}"

        # Opportunity potential and evidence confidence answer different
        # questions.  Keep both: an early signal can be interesting without
        # being sufficiently corroborated to recommend building it yet.
        # Weighting: 20% Pain, 15% Market, 15% WTP, 15% Why Now, 15% Comp, 10% Dist, 10% Tech
        potential_score = (
            pain_score * 0.20 +
            market_score * 0.15 +
            wtp_score * 0.15 +
            why_now_score * 0.15 +
            comp_score * 0.15 +
            dist_score * 0.10 +
            tech_score * 0.10
        )
        
        engagement_signal = min(1.0, sum(max(0, obs.engagement or 0) for obs in observations) / 25)
        evidence_confidence = min(
            1.0,
            0.10
            + (0.10 * min(3, ledger['user_complaints']))
            + (0.15 * min(2, ledger['platforms_covered']))
            + (0.10 * min(3, ledger['independent_sources']))
            + (0.15 * engagement_signal),
        )
        ledger["evidence_confidence"] = evidence_confidence
        ledger["potential_score"] = potential_score

        final_score = potential_score * evidence_confidence
        if evidence_confidence < 0.50:
            recommendation = "VALIDATE: collect corroborating evidence before committing to a build."
        elif potential_score >= 0.65:
            recommendation = "INVESTIGATE: evidence is credible enough for customer interviews or a small test."
        else:
            recommendation = "DEPRIORITIZE: evidence exists, but the current opportunity potential is modest."

        return {
            "final_score": round(min(1.0, final_score), 4),
            "potential_score": round(min(1.0, potential_score), 4),
            "confidence": round(evidence_confidence, 4),
            "recommendation": recommendation,
            "dimensions": {
                "why_now": {"score": why_now_score, "evidence": why_now_evidence},
                "pain": {"score": pain_score, "evidence": pain_evidence},
                "market": {"score": market_score, "evidence": market_evidence},
                "competition": {"score": comp_score, "evidence": comp_evidence},
                "wtp": {"score": wtp_score, "evidence": wtp_evidence},
                "distribution": {"score": dist_score, "evidence": dist_evidence},
                "technical": {"score": tech_score, "evidence": tech_evidence},
                "evidence": {"score": evidence_confidence, "evidence": f"{ledger['independent_sources']} independent sources cross-validated"}
            },
            "ledger": ledger
        }
