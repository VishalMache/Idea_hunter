from typing import Optional, List, Dict, Any
from idea_hunter.db.models import Problem, ProblemResearch, Observation
from idea_hunter.collectors.source_catalog import SOURCE_BY_KEY
from datetime import datetime, timezone, timedelta

class EvidenceScorer:
    """Calculates Evidence-Backed scores based on ProblemResearch JSON and raw Observations."""
    
    @staticmethod
    def calculate_ledger(observations: List[Observation], research: Optional[ProblemResearch], existing_solutions_count: int) -> Dict[str, Any]:
        """Calculates the raw evidence ledger counts."""
        # Discovery listings establish supply/competition context. They are never treated
        # as customer complaints; only direct problem/mixed signals contribute to pain.
        def source_def(obs):
            source_type = getattr(obs, "_source_type", None)
            if not source_type:
                source_type = (getattr(obs, "metadata_json", None) or {}).get("source_type")
            if not source_type:
                source_type = getattr(getattr(obs, "source", None), "source_type", None)
            return SOURCE_BY_KEY.get(source_type) or getattr(obs, "source", None)
        def kind(obs):
            return getattr(source_def(obs), "signal_kind", "mixed")
        def reliability(obs):
            source = source_def(obs)
            return getattr(source, "reliability", getattr(source, "reliability_score", 0.5))
        user_complaints = sum(1 for obs in observations if kind(obs) in {"problem_evidence", "mixed"})
        problem_evidence_count = sum(1 for obs in observations if kind(obs) == "problem_evidence")
        product_market_evidence_count = sum(1 for obs in observations if kind(obs) == "product_market_evidence")
        source_quality_avg = (sum(reliability(obs) for obs in observations) / len(observations)) if observations else 0.0
        category_diversity = len({category for obs in observations for category in getattr(source_def(obs), "categories", ())})
        
        # A source is an independent author when available.  Fall back to the
        # observation ID so anonymous observations are never collapsed together.
        independent_sources = len(set(obs.author or f"observation:{obs.id}" for obs in observations))
        platforms_covered = len({
            getattr(getattr(obs, "source", None), "source_type", None)
            or getattr(obs, "_source_type", None)
            or getattr(obs, "source_id", None)
            or f"observation:{obs.id}"
            for obs in observations
        })
        
        # Competitors from research
        named_competitors = existing_solutions_count
            
        # Pricing signals (naive regex or just checking if WTP is mentioned, but let's do a simple "$" count)
        pricing_signals = sum(1 for obs in observations if "$" in obs.raw_text)
        
        # Recent signals (last 30 days)
        now = datetime.now(timezone.utc)
        dates = []
        for obs in observations:
            observed_at = obs.published_at or obs.collected_at
            if observed_at:
                dates.append(observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=timezone.utc))
        recent_signals = sum(1 for observed_at in dates if (now - observed_at) < timedelta(days=30))
        freshness_days = min((max(0, (now - observed_at).days) for observed_at in dates), default=None)
        
        return {
            "user_complaints": user_complaints,
            "independent_sources": independent_sources,
            "platforms_covered": platforms_covered,
            "named_competitors": named_competitors,
            "pricing_signals": pricing_signals,
            "recent_signals": recent_signals,
            "problem_evidence_count": problem_evidence_count,
            "product_market_evidence_count": product_market_evidence_count,
            "source_quality_avg": round(source_quality_avg, 4),
            "category_diversity": category_diversity
            ,"freshness_days": freshness_days
        }

    @staticmethod
    def score(
        problem: Problem,
        research: Optional[ProblemResearch],
        observations: List[Observation],
        existing_solutions_count: int,
        verified_claim_ratio: float = 0.0,
        contradiction_count: int = 0,
        hypothesis_led: bool = False,
    ) -> Dict[str, Any]:
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
            + (0.15 * engagement_signal)
            + (0.10 * ledger['source_quality_avg'])
            + (0.05 * min(3, ledger['category_diversity']) / 3),
        )
        # Evidence quality includes verifiable citations and visible
        # contradictions. Path-B/hypothesis-led opportunities remain useful,
        # but cannot look validated before real user signals arrive.
        if verified_claim_ratio:
            evidence_confidence = min(1.0, evidence_confidence * 0.8 + (0.2 * verified_claim_ratio))
        evidence_confidence = max(0.0, evidence_confidence - min(0.30, contradiction_count * 0.10))
        freshness_days = ledger["freshness_days"]
        if freshness_days is not None and freshness_days > 14:
            evidence_confidence *= max(0.4, 1 - ((freshness_days - 14) * 0.03))
        if hypothesis_led:
            evidence_confidence = min(evidence_confidence, 0.25)
        ledger["evidence_confidence"] = evidence_confidence
        ledger["potential_score"] = potential_score
        ledger["verified_claim_ratio"] = verified_claim_ratio
        ledger["contradiction_count"] = contradiction_count

        final_score = potential_score * evidence_confidence
        if existing_solutions_count >= 5 and comp_score <= 0.5:
            recommendation = "reject"
        elif evidence_confidence < 0.50:
            recommendation = "collect_more_evidence"
        elif potential_score >= 0.65 and ledger["pricing_signals"] == 0:
            recommendation = "interview_users"
        elif potential_score >= 0.65:
            recommendation = "test_pricing"
        elif potential_score >= 0.55 and evidence_confidence >= 0.65:
            recommendation = "prototype"
        else:
            recommendation = "reject"

        return {
            "final_score": round(min(1.0, final_score), 4),
            "potential_score": round(min(1.0, potential_score), 4),
            "confidence": round(evidence_confidence, 4),
            "recommendation": recommendation,
            "freshness_days": freshness_days,
            "next_step": recommendation,
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
