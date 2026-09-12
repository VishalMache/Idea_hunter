from typing import Optional, Tuple
from idea_hunter.llm.router import model_router
from idea_hunter.llm.schemas import ExtractedProblem, ClassificationResult, CompetitionAnalysis

class ProblemExtractor:
    """Extracts structured problem data from text observations."""
    
    async def process_cluster(self, texts: list[str], run_id: int = None) -> Tuple[Optional[ExtractedProblem], Optional[CompetitionAnalysis]]:
        """
        Extract the core problem from a cluster of related observations.
        """
        try:
            problem = await model_router.extract_problem(texts, run_id=run_id)
            
            # Additional validation
            if problem.confidence < 0.3:
                return None, None
                
            # Chain the competition agent call
            competition = await model_router.analyze_competition(texts, run_id=run_id)
                
            return problem, competition
        except Exception as e:
            print(f"Error during problem/competition extraction: {e}")
            return None, None
