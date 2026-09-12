from typing import List, Dict

class EvidenceConfidence:
    """Calculates confidence score based on the volume and diversity of evidence."""
    
    @staticmethod
    def calculate(
        evidence_count: int,
        source_diversity: int, # Number of unique source types
        source_quality_avg: float,
        recency_score: float # 0.0 to 1.0 based on how recent the evidence is
    ) -> float:
        """
        Calculate a confidence score between 0.0 and 1.0.
        More evidence from diverse, high-quality sources = higher confidence.
        """
        
        # Volume component: log curve, maxes out around 50 pieces of evidence
        import math
        volume_score = min(math.log1p(evidence_count) / math.log1p(50), 1.0)
        
        # Diversity component: 1 source = 0.5, 3+ sources = 1.0
        diversity_score = min(0.5 + (source_diversity - 1) * 0.25, 1.0) if source_diversity > 0 else 0.0
        
        # Combine
        confidence = (volume_score * 0.4) + (diversity_score * 0.3) + (source_quality_avg * 0.2) + (recency_score * 0.1)
        
        return min(max(confidence, 0.0), 1.0)
