from idea_hunter.llm.client import local_client
from typing import List

class Embedder:
    """Generates embeddings for texts using the LLM client."""
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts."""
        if not texts:
            return []
            
        return await local_client.embed(texts)
        
    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        result = await self.embed_batch([text])
        return result[0] if result else []
