import numpy as np
import hdbscan
from typing import List, Dict, Any

class ProblemClusterer:
    """Clusters extracted problems using HDBSCAN."""
    
    def __init__(self, min_cluster_size: int = 5):
        self.min_cluster_size = min_cluster_size

    @staticmethod
    def cosine_distance(left: List[float], right: List[float]) -> float:
        """Return cosine distance for embeddings stored as Python lists."""
        left_array = np.asarray(left, dtype=float)
        right_array = np.asarray(right, dtype=float)
        denominator = np.linalg.norm(left_array) * np.linalg.norm(right_array)
        if denominator == 0:
            return 1.0
        return float(1.0 - np.dot(left_array, right_array) / denominator)
        
    def cluster(self, embeddings: List[List[float]]) -> Dict[str, Any]:
        """Run HDBSCAN on a list of embeddings."""
        if not embeddings or len(embeddings) < self.min_cluster_size:
            return {"labels": [-1] * len(embeddings), "probabilities": [0.0] * len(embeddings)}
            
        data = np.array(embeddings)
        
        # min_samples=2 makes HDBSCAN much less likely to classify points as noise
        clusterer = hdbscan.HDBSCAN(min_cluster_size=self.min_cluster_size, min_samples=2, metric='euclidean')
        clusterer.fit(data)
        
        return {
            "labels": clusterer.labels_.tolist(),
            "probabilities": clusterer.probabilities_.tolist()
        }
