from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from idea_hunter.db.models import Problem, ProblemEvidence, Observation
from dataclasses import dataclass

@dataclass
class VerificationResult:
    verified: bool
    reason: str
    details: dict

class ProblemVerifier:
    """Verifies that an extracted problem meets evidence requirements before scoring."""
    
    @staticmethod
    async def verify(session: AsyncSession, problem_id: int) -> VerificationResult:
        """
        Runs quality checks on a problem's evidence chain.
        Returns True if verified, False if flagged.
        """
        # 1. Get problem severity & frequency
        prob_stmt = select(Problem).where(Problem.id == problem_id)
        prob_res = await session.execute(prob_stmt)
        prob = prob_res.scalar_one_or_none()
        
        if not prob:
            return VerificationResult(False, "missing_problem", {})
            
        # Trivial complaint check
        if (prob.severity or 5) * (prob.frequency or 5) < 25:
            # e.g., 5 * 4 = 20 (failed)
            return VerificationResult(False, "low_severity_frequency", {"severity": prob.severity, "frequency": prob.frequency})
            
        # 2. Check for at least one piece of evidence with engagement > 0 (or multiple diverse sources)
        obs_stmt = (
            select(Observation)
            .join(ProblemEvidence, Observation.id == ProblemEvidence.observation_id)
            .where(ProblemEvidence.problem_id == problem_id)
        )
        obs_res = await session.execute(obs_stmt)
        obs_list = obs_res.scalars().all()
        
        evidence_count = len(obs_list)
        max_engagement = max((obs.engagement or 0 for obs in obs_list), default=0)
        source_count = len(set(obs.source_id for obs in obs_list))
        details = {"evidence_count": evidence_count, "source_count": source_count, "max_engagement": max_engagement,
                   "severity": prob.severity, "frequency": prob.frequency}

        if evidence_count < 2:
            return VerificationResult(False, "needs_more_evidence", details)
        
        if max_engagement == 0 and source_count < 2:
            # If nobody engaged with it, and it only exists on one platform, it's not verified
            return VerificationResult(False, "needs_source_or_engagement", details)
            
        return VerificationResult(True, "verified", details)
