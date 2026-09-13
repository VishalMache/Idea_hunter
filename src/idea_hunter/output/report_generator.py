import os
from datetime import datetime
from sqlalchemy import select, desc
from idea_hunter.db.session import session_scope
from idea_hunter.db.models import Opportunity, OpportunityScore, Problem, ProblemResearch

class MarkdownReportGenerator:
    """Generates a markdown report of scored opportunities with Evidence-Backed metrics."""
    
    @staticmethod
    def _score_to_stars(score: float) -> str:
        """Converts a 0.0-1.0 score to a 5-star string."""
        if score is None:
            return "☆☆☆☆☆"
        stars = round(score * 5)
        return ("★" * stars) + ("☆" * (5 - stars))

    async def generate(self, output_path: str = "opportunity_report.md") -> str:
        async with session_scope() as session:
            stmt = (
                select(Opportunity, OpportunityScore, Problem)
                .join(OpportunityScore, Opportunity.id == OpportunityScore.opportunity_id)
                .join(Problem, Opportunity.problem_id == Problem.id)
                .order_by(desc(OpportunityScore.final_score))
            )
            result = await session.execute(stmt)
            rows = result.all()
            
            if not rows:
                return ""
                
            report_lines = [
                "# 🚀 Idea Hunter - Opportunity Intelligence Report",
                f"*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
                "\n---\n"
            ]
            
            for rank, (opp, score, prob) in enumerate(rows, 1):
                # Fetch ProblemResearch
                pr_stmt = select(ProblemResearch).where(ProblemResearch.problem_id == prob.id)
                pr_res = await session.execute(pr_stmt)
                research = pr_res.scalar_one_or_none()
                
                bd = score.breakdown_json or {}
                dims = bd.get("dimensions", {})
                ledger = bd.get("ledger", {})
                
                report_lines.extend([
                    f"## {rank}. {prob.title}",
                    f"**Evidence-adjusted score:** `{int(score.final_score * 100)} / 100`",
                    f"**Opportunity potential:** `{int(bd.get('potential_score', score.final_score) * 100)} / 100`",
                    f"**Confidence:** {int(score.evidence_confidence * 100)}%",
                    f"**Next step:** {bd.get('recommendation', 'Validate the evidence before committing to a build.')}",
                    ""
                ])
                
                # Dimensions
                if dims:
                    report_lines.extend([
                        f"Why Now         {self._score_to_stars(dims.get('why_now', {}).get('score'))}  ({dims.get('why_now', {}).get('evidence', '')})",
                        f"Pain            {self._score_to_stars(dims.get('pain', {}).get('score'))}  ({dims.get('pain', {}).get('evidence', '')})",
                        f"Market          {self._score_to_stars(dims.get('market', {}).get('score'))}  ({dims.get('market', {}).get('evidence', '')})",
                        f"Competition Gap {self._score_to_stars(dims.get('competition', {}).get('score'))}  ({dims.get('competition', {}).get('evidence', '')})",
                        f"Willingness to Pay {self._score_to_stars(dims.get('wtp', {}).get('score'))}  ({dims.get('wtp', {}).get('evidence', '')})",
                        f"Distribution    {self._score_to_stars(dims.get('distribution', {}).get('score'))}  ({dims.get('distribution', {}).get('evidence', '')})",
                        f"Technical       {self._score_to_stars(dims.get('technical', {}).get('score'))}  ({dims.get('technical', {}).get('evidence', '')})",
                        f"Evidence        {self._score_to_stars(dims.get('evidence', {}).get('score'))}  ({dims.get('evidence', {}).get('evidence', '')})",
                        ""
                    ])
                
                # Evidence Ledger
                if ledger:
                    report_lines.extend([
                        "```text",
                        "Evidence Ledger",
                        "───────────────",
                        f"User complaints:         {ledger.get('user_complaints', 0)} observations",
                        f"Independent sources:      {ledger.get('independent_sources', 0)} cross-referenced",
                        f"Platforms covered:        {ledger.get('platforms_covered', 0)}",
                        f"Named competitors found:  {ledger.get('named_competitors', 0)}",
                        f"Pricing evidence signals: {ledger.get('pricing_signals', 0)}",
                        f"Recent signals (30 days): {ledger.get('recent_signals', 0)}",
                        f"Evidence Confidence:      {int(score.evidence_confidence * 100)}%",
                        f"Opportunity Potential:    {int(ledger.get('potential_score', score.final_score) * 100)}%",
                        "```",
                        ""
                    ])
                    
                # Bull vs Bear Debate
                if research:
                    report_lines.extend([
                        f"### VERDICT: **{research.debate_verdict or 'UNKNOWN'}**",
                        "",
                        "**🟢 The Bull Case (Why it's a billion dollar company):**",
                        f"> {research.bull_case or '*No bull case found*'}",
                        "",
                        "**🔴 The Bear Case (Why it will fail):**",
                        f"> {research.bear_case or '*No bear case found*'}",
                        ""
                    ])
                else:
                    report_lines.extend([
                        "### VERDICT: **NEEDS RESEARCH**",
                        "> No Bull/Bear debate found. Run Phase 2 Research agent on this problem.",
                        ""
                    ])
                    
                report_lines.append("---\n")
                
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(report_lines))
                
            return output_path
